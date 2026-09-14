"""RAG 语料索引构建脚本(对齐设计 §3.4)。

功能:
- 从业务索引(matched_logs / nginx-log-raw)抽数据
- 调 chunking.build_corpus_evidences 切片
- 调 embed.embed_batch 生成 embedding
- 用 ES bulk 写入 RAG 语料索引(content + embedding + source_id + source_type + raw)

ES 索引 mapping(auditweaver-rag-corpus):
    统一定义在 docker/config/elasticsearch/mappings/auditweaver-rag-corpus.yaml，
    由 creatMapping.py 在 docker 启动时自动创建；本脚本仅在索引不存在时从同一份 YAML
    加载创建（兜底），不再硬编码 mapping，避免两处漂移。

运行(项目根目录,需真实 ES + LLM embedding endpoint 配置):
    python -m services.agent_service.evals.build_rag_index
    python -m services.agent_service.evals.build_rag_index --max_docs 500 --batch_size 50

注:依赖真实 ES + LLM embedding endpoint(走 light 角色);
索引构建是一次性运维操作,不进单测套件。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

import yaml

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config.settings import RAG_CONFIG  # noqa: E402
from skills.config.settings import ES_INDEX_EVENTS, ES_INDEX_RAW  # noqa: E402
from skills.es import get_es_client, is_es_available  # noqa: E402
from shared.rag.chunking import build_corpus_evidences  # noqa: E402
from shared.rag.embed import embed_batch  # noqa: E402

# RAG 索引 mapping 的单一数据源：与 creatMapping.py 共用同一份 YAML，
# 避免 mapping 在两处漂移。build_rag_index.py 只负责灌数据，不再硬编码 mapping。
# 注：_PROJECT_ROOT 实际指向 services/，docker/ 在项目根目录，需再上溯一级。
_REAL_PROJECT_ROOT = os.path.dirname(_PROJECT_ROOT)
_RAG_MAPPING_YAML = os.path.join(
    _REAL_PROJECT_ROOT, "docker", "config", "elasticsearch", "mappings",
    "auditweaver-rag-corpus.yaml",
)


def _load_rag_mapping() -> dict:
    """从 YAML 加载 RAG 索引 mapping（单一数据源，与 creatMapping.py 共用）。"""
    if not os.path.exists(_RAG_MAPPING_YAML):
        raise FileNotFoundError(
            f"RAG mapping YAML 不存在: {_RAG_MAPPING_YAML}。"
            f"请确认 docker/config/elasticsearch/mappings/auditweaver-rag-corpus.yaml 已创建。"
        )
    with open(_RAG_MAPPING_YAML, "r", encoding="utf-8") as f:
        mapping = yaml.safe_load(f)
    if not mapping or not isinstance(mapping, dict):
        raise ValueError(f"RAG mapping YAML 解析失败或为空: {_RAG_MAPPING_YAML}")
    return mapping


def _get_yaml_embedding_dim(mapping: dict) -> int | None:
    """从 mapping dict 中提取 dense_vector 的 dims，用于一致性校验。"""
    try:
        return (
            mapping.get("mappings", {})
            .get("properties", {})
            .get("embedding", {})
            .get("dims")
        )
    except (AttributeError, TypeError):
        return None


def ensure_rag_index(es, index_name: str) -> None:
    """创建 RAG 语料索引(如不存在)。

    mapping 从 docker/config/elasticsearch/mappings/auditweaver-rag-corpus.yaml 加载，
    与 creatMapping.py 共用同一份 YAML，避免 mapping 漂移。
    若 YAML 中 embedding.dims 与 RAG_CONFIG['embedding_dim'] 不一致，打 warning 提醒。
    """
    if es.indices.exists(index=index_name):
        logger.info("[build_rag_index] 索引已存在: %s", index_name)
        return

    mapping = _load_rag_mapping()

    # 维度一致性校验：YAML dims 必须与 .env 的 AE_RAG_EMBEDDING_DIM 一致，
    # 否则 bulk 写入 embedding 时会因维度不匹配失败。
    yaml_dim = _get_yaml_embedding_dim(mapping)
    env_dim = RAG_CONFIG.get("embedding_dim")
    if yaml_dim is not None and env_dim is not None and yaml_dim != env_dim:
        logger.warning(
            "[build_rag_index] 维度不一致：YAML dims=%d 但 AE_RAG_EMBEDDING_DIM=%d。"
            "请同步修改 docker/config/elasticsearch/mappings/auditweaver-rag-corpus.yaml "
            "和 .env 中的 AE_RAG_EMBEDDING_DIM，否则 bulk 写入会失败。",
            yaml_dim, env_dim,
        )

    es.indices.create(index=index_name, body=mapping)
    logger.info(
        "[build_rag_index] 创建索引 %s (dense_vector dims=%s)",
        index_name, yaml_dim,
    )


def fetch_matched_logs(es, index: str, max_docs: int) -> list[dict]:
    """从 matched_logs 抽数据(按时间倒序)。"""
    body = {
        "size": max_docs,
        "query": {"match_all": {}},
        "sort": [{"log_context.timestamp": {"order": "desc"}}],
    }
    resp = es.search(index=index, body=body)
    hits = (resp.get("hits") or {}).get("hits", [])
    logger.info("[build_rag_index] 从 %s 抽取 %d 条 matched_logs", index, len(hits))
    return hits


def fetch_nginx_by_ip(es, index: str, max_ips: int, per_ip: int) -> dict[str, list[dict]]:
    """从 nginx-log-raw 按 IP 聚合抽数据(供会话切片)。

    Returns: {ip: [hit, hit, ...]}
    """
    # 先聚合出 top-N IP
    agg_body = {
        "size": 0,
        "aggs": {
            "by_ip": {
                "terms": {
                    "field": "log_context.ip",
                    "size": max_ips,
                    "order": {"_count": "desc"},
                }
            }
        },
    }
    resp = es.search(index=index, body=agg_body)
    buckets = (
        ((resp.get("aggregations") or {}).get("by_ip") or {}).get("buckets") or []
    )
    logger.info(
        "[build_rag_index] nginx %s 聚合到 %d 个 IP", index, len(buckets)
    )

    by_ip: dict[str, list[dict]] = {}
    for b in buckets:
        ip = b.get("key")
        if not ip:
            continue
        body = {
            "size": per_ip,
            "query": {"term": {"log_context.ip": ip}},
            "sort": [{"log_context.timestamp": {"order": "asc"}}],
        }
        r = es.search(index=index, body=body)
        hits = (r.get("hits") or {}).get("hits", [])
        if hits:
            by_ip[ip] = hits
    return by_ip


def bulk_write_evidences(es, index: str, evidences_with_emb: list[dict]) -> int:
    """bulk 写入 evidences(每条带 content/embedding/source_id/source_type/raw)。"""
    if not evidences_with_emb:
        return 0
    actions: list[dict] = []
    for doc in evidences_with_emb:
        # 用 source_id 做 ES _id(去重:同 source_id 多次写会覆盖)
        es_id = doc.get("source_id") or None
        action = {"index": {"_index": index}}
        if es_id:
            action["index"]["_id"] = es_id
        actions.append(action)
        actions.append(doc)

    resp = es.bulk(body=actions)
    if resp.get("errors"):
        errs = [item for item in resp.get("items", []) if item.get("index", {}).get("error")]
        logger.warning("[build_rag_index] bulk 部分失败: %d/%d", len(errs), len(evidences_with_emb))
    return len(evidences_with_emb)


def build_index(max_docs: int = 200, max_ips: int = 50, per_ip: int = 30, batch_size: int = 50) -> int:
    """构建 RAG 语料索引。"""
    es = get_es_client()
    if es is None or not is_es_available():
        logger.error("[build_rag_index] ES 不可用,无法构建索引")
        return 0

    index_name = RAG_CONFIG.get("es_index_corpus", "auditweaver-rag-corpus")
    # mapping 从 YAML 加载（与 creatMapping.py 共用），dims 以 YAML 为准；
    # ensure_rag_index 内部会校验 YAML dims 与 AE_RAG_EMBEDDING_DIM 是否一致。
    ensure_rag_index(es, index_name)

    # 1. 抽数据
    matched_hits = fetch_matched_logs(es, ES_INDEX_EVENTS, max_docs)
    nginx_by_ip = fetch_nginx_by_ip(es, ES_INDEX_RAW, max_ips, per_ip)

    # 2. 切片
    matched_docs = [h.get("_source", {}) | {"_id": h.get("_id")} for h in matched_hits]
    evidences = build_corpus_evidences(
        matched_logs_docs=matched_docs,
        nginx_logs_by_ip=nginx_by_ip,
        report_docs=None,  # analysis_report 在 MySQL,P0-3 不灌
    )
    logger.info("[build_rag_index] 切片完成 total=%d", len(evidences))
    if not evidences:
        return 0

    # 3. 批量 embedding + bulk 写入
    total_written = 0
    for i in range(0, len(evidences), batch_size):
        batch = evidences[i : i + batch_size]
        texts = [e.content for e in batch]
        try:
            embs = embed_batch(texts)
        except Exception as e:
            logger.error(
                "[build_rag_index] batch %d-%d embedding 失败: %s,终止",
                i, i + len(batch), e,
            )
            break

        docs: list[dict] = []
        for ev, emb in zip(batch, embs):
            docs.append({
                "content": ev.content,
                "embedding": emb,
                "source_id": ev.source_id,
                "source_type": ev.source_type,
                "raw": ev.raw or {},
            })
        written = bulk_write_evidences(es, index_name, docs)
        total_written += written
        logger.info(
            "[build_rag_index] 已写入 %d / %d", total_written, len(evidences)
        )

    logger.info("[build_rag_index] 完成 total_written=%d", total_written)
    return total_written


def main():
    parser = argparse.ArgumentParser(description="构建 RAG 语料索引")
    parser.add_argument("--max_docs", type=int, default=200, help="matched_logs 抽取上限")
    parser.add_argument("--max_ips", type=int, default=50, help="nginx 聚合 IP 数")
    parser.add_argument("--per_ip", type=int, default=30, help="每个 IP 抽取 nginx 日志数")
    parser.add_argument("--batch_size", type=int, default=50, help="embedding+bulk 批大小")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    n = build_index(
        max_docs=args.max_docs,
        max_ips=args.max_ips,
        per_ip=args.per_ip,
        batch_size=args.batch_size,
    )
    print(f"RAG 语料索引构建完成,写入 {n} 条")


if __name__ == "__main__":
    main()
