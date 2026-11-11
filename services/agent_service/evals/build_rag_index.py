"""RAG 语料索引构建脚本 v2(对齐 RAG优化需求文档 §4/§P0-1)。

双路语料(knowledge + case)→ 版本化物理索引 → alias 蓝绿切换:

    python -m services.agent_service.evals.build_rag_index                    # 全量(knowledge+case)
    python -m services.agent_service.evals.build_rag_index --source knowledge # 只重建知识库
    python -m services.agent_service.evals.build_rag_index --source case      # 只重建历史案例
    python -m services.agent_service.evals.build_rag_index --switch-alias     # alias 蓝绿切换

设计要点(对齐需求文档 §4.1/§4.2):
- 物理索引带版本号(auditweaver-rag-corpus-v2/v3/...),版本号由本脚本管理,不进 yaml;
  读写统一走 alias `auditweaver-rag-corpus`(RAG_CONFIG['es_index_corpus'])
- knowledge 路:resources/rag/knowledge/*.md → frontmatter + H2 切片(knowledge.py)
- case 路:matched_logs 近 N 天(默认 90)+ 质量筛选 → 事件切片(chunking.py 复用)
- 写入统一 bulk upsert(_id = source_id,幂等,重跑不重复)
- --switch-alias:数据灌好并验证 count>0 后,原子 update_aliases 切换;
  首次迁移时旧物理索引占用 alias 名,验证新索引有数据后删除(新索引内容为其超集)

mapping 单一数据源:docker/config/elasticsearch/mappings/auditweaver-rag-corpus.yaml
(与 creatMapping.py 共用,本脚本仅兜底创建)。

注:依赖真实 ES + embedding endpoint(走 RAG 专用 AE_RAG_EMBEDDING_* 配置);
索引构建是运维操作,不进单测套件。
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time

import yaml

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config.settings import RAG_CONFIG  # noqa: E402
from skills.es import get_es_client, is_es_available  # noqa: E402
from shared.rag.embed import embed_batch  # noqa: E402
from shared.rag.knowledge import load_knowledge_chunks  # noqa: E402
from shared.rag.case_sync import (  # noqa: E402
    hits_to_corpus_docs,
    quality_filter_case,
)

# RAG 索引 mapping 的单一数据源:与 creatMapping.py 共用同一份 YAML
_REAL_PROJECT_ROOT = os.path.dirname(_PROJECT_ROOT)
_RAG_MAPPING_YAML = os.path.join(
    _REAL_PROJECT_ROOT, "docker", "config", "elasticsearch", "mappings",
    "auditweaver-rag-corpus.yaml",
)

# case 路默认时间窗口(近 90 天,对齐需求文档 P0-1;历史数据后续按需扩展)
DEFAULT_CASE_WINDOW_DAYS = 90


def _load_rag_mapping() -> dict:
    """从 YAML 加载 RAG 索引 mapping(单一数据源,与 creatMapping.py 共用)。"""
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
    """从 mapping dict 中提取 dense_vector 的 dims,用于一致性校验。"""
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
    """创建 RAG 语料索引(如不存在)。mapping 从 YAML 加载,与 creatMapping.py 共用。"""
    if es.indices.exists(index=index_name):
        logger.info("[build_rag_index] 索引已存在: %s", index_name)
        return

    mapping = _load_rag_mapping()

    # 维度一致性校验:YAML dims 必须与 .env 的 AE_RAG_EMBEDDING_DIM 一致,
    # 否则 bulk 写入 embedding 时会因维度不匹配失败。
    yaml_dim = _get_yaml_embedding_dim(mapping)
    env_dim = RAG_CONFIG.get("embedding_dim")
    if yaml_dim is not None and env_dim is not None and yaml_dim != env_dim:
        logger.warning(
            "[build_rag_index] 维度不一致:YAML dims=%d 但 AE_RAG_EMBEDDING_DIM=%d。"
            "请同步修改 mapping yaml 和 .env,否则 bulk 写入会失败。",
            yaml_dim, env_dim,
        )

    es.indices.create(index=index_name, body=mapping)
    logger.info(
        "[build_rag_index] 创建索引 %s (dense_vector dims=%s)",
        index_name, yaml_dim,
    )


def _alias_name() -> str:
    """读写统一走的 alias 名(= RAG_CONFIG['es_index_corpus'],运行时不感知版本)。"""
    return RAG_CONFIG.get("es_index_corpus", "auditweaver-rag-corpus")


def resolve_version_index(es, explicit: str | None = None) -> str:
    """解析本次建库的物理索引名(版本号由建库脚本管理,不进 yaml)。

    规则:
    - explicit 优先(--index auditweaver-rag-corpus-v3)
    - 自动:扫描已存在的 {alias}-vN 物理索引(N 为数字),取最大版本 +1(蓝绿:每次重建开新版本)
    - 无历史版本时从 v2 开始(v1 视为旧的无版本物理索引时代)
    """
    alias = _alias_name()
    if explicit:
        return explicit
    pattern = re.compile(rf"^{re.escape(alias)}-v(\d+)$")
    try:
        existing = list(es.indices.get(index=f"{alias}-v*").keys())
    except Exception:
        existing = []
    versions = [int(m.group(1)) for name in existing if (m := pattern.match(name))]
    next_v = max(versions) + 1 if versions else 2
    return f"{alias}-v{next_v}"


# ============ case 路:matched_logs 近 N 天 + 质量筛选 ============

def fetch_matched_logs_recent(es, index: str, days: int, max_docs: int) -> list[dict]:
    """从 matched_logs 拉取近 N 天事件(按时间升序,供增量/全量建库)。"""
    cutoff = int((time.time() - days * 86400) * 1000)
    body = {
        "size": max_docs,
        "query": {"range": {"log_context.timestamp": {"gte": cutoff}}},
        "sort": [
            {"log_context.timestamp": {"order": "asc"}},
            {"event_id": {"order": "asc"}},
        ],
    }
    resp = es.search(index=index, body=body)
    hits = (resp.get("hits") or {}).get("hits", [])
    total = (resp.get("hits") or {}).get("total", {}).get("value", len(hits))
    logger.info(
        "[build_rag_index] %s 近 %d 天命中 %s 条,拉取 %d 条(上限 %d)",
        index, days, total, len(hits), max_docs,
    )
    return hits


def build_case_corpus_docs(es, days: int, max_docs: int) -> list[dict]:
    """case 路:matched_logs → 质量筛选 → 事件切片 → corpus 文档列表。

    质量筛选与事件→corpus 转换复用 shared/rag/case_sync.py(与定时增量单一逻辑源)。
    """
    from skills.config.settings import ES_INDEX_EVENTS

    hits = fetch_matched_logs_recent(es, ES_INDEX_EVENTS, days=days, max_docs=max_docs)
    valid, stats = quality_filter_case(hits)
    logger.info(
        "[build_rag_index] case 质量筛选: 拉取 %d,保留 %d,筛掉 %d "
        "(no_attack_type=%d no_ip=%d no_timestamp=%d no_content=%d)",
        stats["total"], stats["kept"], stats["dropped"],
        stats["no_attack_type"], stats["no_ip"], stats["no_timestamp"], stats["no_content"],
    )
    docs = hits_to_corpus_docs(valid)
    logger.info("[build_rag_index] case 路 corpus 文档 %d 条", len(docs))
    return docs


# ============ knowledge 路:知识语料 markdown ============

def build_knowledge_corpus_docs() -> list[dict]:
    """knowledge 路:resources/rag/knowledge/*.md → H2 切片 → corpus 文档列表。"""
    chunks = load_knowledge_chunks()
    docs = [c.to_corpus_doc() for c in chunks]
    logger.info("[build_rag_index] knowledge 路 corpus 文档 %d 条", len(docs))
    return docs


# ============ 统一 embed + bulk upsert ============

def embed_and_write(es, index: str, corpus_docs: list[dict], batch_size: int = 50) -> int:
    """批量 embedding + bulk upsert 写入(_id = source_id,幂等,重跑不重复)。

    embedding 失败整批终止并抛出(显式报错,对齐项目原则)。
    """
    total_written = 0
    for i in range(0, len(corpus_docs), batch_size):
        batch = corpus_docs[i: i + batch_size]
        texts = [d["content"] for d in batch]
        try:
            embs = embed_batch(texts)
        except Exception as e:
            logger.error(
                "[build_rag_index] batch %d-%d embedding 失败: %s,终止(已写入 %d 条)",
                i, i + len(batch), e, total_written,
            )
            raise

        actions: list[dict] = []
        for d, emb in zip(batch, embs):
            doc = dict(d)
            doc["embedding"] = emb
            # upsert 幂等:_id = source_id,同 source_id 重跑覆盖不重复
            actions.append({"index": {"_index": index, "_id": doc["source_id"]}})
            actions.append(doc)

        resp = es.bulk(body=actions)
        if resp.get("errors"):
            errs = [it for it in resp.get("items", []) if it.get("index", {}).get("error")]
            raise RuntimeError(
                f"bulk 写入部分失败: {len(errs)}/{len(batch)}(首个错误: "
                f"{errs[0].get('index', {}).get('error') if errs else 'n/a'})"
            )
        total_written += len(batch)
        logger.info("[build_rag_index] 已写入 %d / %d", total_written, len(corpus_docs))
    return total_written


# ============ alias 蓝绿切换 ============

def switch_alias(es, new_index: str) -> None:
    """alias 原子切换到 new_index(蓝绿)。

    前置校验:new_index 存在且 count > 0(空索引不允许切换,防误切丢流量)。
    首次迁移特例:旧物理索引占用了 alias 名(无版本号时代),验证后删除腾出名字
    (新索引为其内容超集:case 全量重灌 + knowledge 新增)。
    后续版本切换(v2→v3):原子 update_aliases,旧版本保留观察期,人工确认后删。
    """
    alias = _alias_name()

    # 1. 校验新索引有数据
    if not es.indices.exists(index=new_index):
        raise RuntimeError(f"目标索引不存在: {new_index},请先建库")
    count = es.count(index=new_index)["count"]
    if count <= 0:
        raise RuntimeError(f"目标索引 {new_index} 为空(count=0),拒绝切换 alias")

    # 2. 当前 alias 指向(可能无 / 可能指向旧版本 / 名字被物理索引占用)
    actions: list[dict] = []
    try:
        current = es.indices.get_alias(name=alias)
        for cur_index in current:
            actions.append({"remove": {"index": cur_index, "alias": alias}})
        logger.info("[build_rag_index] alias %s 当前指向: %s", alias, list(current))
    except Exception:
        current = {}
        # alias 不存在:检查是否被旧物理索引占用(首次迁移场景)
        if es.indices.exists(index=alias):
            old_count = es.count(index=alias)["count"]
            logger.warning(
                "[build_rag_index] 首次迁移:旧物理索引 %s(count=%d)占用 alias 名,"
                "新索引 %s(count=%d)为其内容超集,删除旧索引腾出 alias 名",
                alias, old_count, new_index, count,
            )
            es.indices.delete(index=alias)

    # 3. 原子切换(es-py 客户端 actions 参数 = 列表,客户端自行包装 body)
    actions.append({"add": {"index": new_index, "alias": alias}})
    try:
        es.indices.update_aliases(actions=actions)
    except Exception as e:
        # 首次迁移路径中旧物理索引已删除,此处失败 = alias 名空闲但未指回,显式报错人工介入
        logger.exception(
            "[build_rag_index] update_aliases 失败(actions=%s),请手动执行:"
            "PUT /%s/_alias/%s", actions, new_index, alias,
        )
        raise
    logger.info(
        "[build_rag_index] alias %s → %s 切换完成(count=%d);旧索引可保留观察期后删除",
        alias, new_index, count,
    )


def main():
    parser = argparse.ArgumentParser(description="构建 RAG 语料索引 v2(双路语料 + 版本化索引)")
    parser.add_argument(
        "--source", choices=["knowledge", "case", "all"], default="all",
        help="建库语料源:knowledge(知识库)/ case(历史攻击日志)/ all(默认)",
    )
    parser.add_argument(
        "--index", type=str, default=None,
        help="物理索引名(默认自动递增版本:auditweaver-rag-corpus-v2/v3/...)",
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_CASE_WINDOW_DAYS,
        help=f"case 路时间窗口天数(默认 {DEFAULT_CASE_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--max_docs", type=int, default=10000,
        help="case 路拉取上限(默认 10000,近 90 天全量)",
    )
    parser.add_argument("--batch_size", type=int, default=50, help="embedding+bulk 批大小")
    parser.add_argument(
        "--switch-alias", action="store_true",
        help="只执行 alias 蓝绿切换(建库完成后单独调用)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    es = get_es_client()
    if es is None or not is_es_available():
        logger.error("[build_rag_index] ES 不可用,无法构建索引")
        sys.exit(1)

    if args.switch_alias:
        # 切换模式:--index 指定目标(默认取当前最大版本号的索引)
        target = args.index or resolve_version_index(es)
        # 自动解析时 resolve_version_index 返回"下一个"版本,切换模式要"当前最大"版本:
        # 重新扫描取最大者(已建好的最新索引)
        if not args.index:
            alias = _alias_name()
            pattern = re.compile(rf"^{re.escape(alias)}-v(\d+)$")
            try:
                existing = list(es.indices.get(index=f"{alias}-v*").keys())
            except Exception:
                existing = []
            versions = [int(m.group(1)) for name in existing if (m := pattern.match(name))]
            if not versions:
                logger.error("[build_rag_index] 不存在版本化索引,无可切换目标;请先建库")
                sys.exit(1)
            target = f"{alias}-v{max(versions)}"
        switch_alias(es, target)
        print(f"alias {_alias_name()} 已切换到 {target}")
        return

    # 建库模式
    index_name = resolve_version_index(es, explicit=args.index)
    ensure_rag_index(es, index_name)
    logger.info("[build_rag_index] 目标物理索引: %s (alias=%s)", index_name, _alias_name())

    corpus_docs: list[dict] = []
    if args.source in ("knowledge", "all"):
        corpus_docs.extend(build_knowledge_corpus_docs())
    if args.source in ("case", "all"):
        corpus_docs.extend(build_case_corpus_docs(es, days=args.days, max_docs=args.max_docs))

    if not corpus_docs:
        logger.error("[build_rag_index] 无可入库语料(source=%s),终止", args.source)
        sys.exit(1)

    total = embed_and_write(es, index_name, corpus_docs, batch_size=args.batch_size)
    logger.info(
        "[build_rag_index] 完成: source=%s index=%s 写入 %d 条;"
        "验证无误后执行 --switch-alias 切换",
        args.source, index_name, total,
    )
    print(f"RAG 语料入库完成: index={index_name}, source={args.source}, 写入 {total} 条")


if __name__ == "__main__":
    main()
