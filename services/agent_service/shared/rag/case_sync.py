"""case 语料定时增量同步(P1-1,对齐 RAG优化需求文档 §P1-1)。

机制:复合游标 + Meta 文档水位
- 水位状态持久化在语料索引内的 Meta 文档(_id=__meta__case_sync,零新增索引):
    {"last_created_at": <epoch ms>, "last_event_id": "...", "updated_at": <epoch ms>}
- 拉取条件(防同时间戳多事件在边界丢失/重复):
    log_context.timestamp > last_created_at
    OR (== last_created_at AND event_id > last_event_id)
- 批内按 (created_at, event_id) 升序,游标随批推进;
  游标推进与数据写入同批完成(写完该批才更新 Meta 文档);
  失败不推进游标 → 下轮自动补齐;bulk upsert(_id=source_id)幂等,重放无重复
- embedding 调用失败:整批终止并报错,下轮重试(显式报错不静默)

首次运行(无 Meta 文档):游标 (0, "") + 近 N 天窗口 → 等价全量建库的 case 路
(与 build_rag_index.py 共用 quality_filter_case / hits_to_corpus_docs,单一逻辑源)。

入口:
- sync_once(): 单轮增量(定时任务每轮调;CLI 手动触发)
- run_case_sync_forever(): 常驻循环(agent_service FastAPI lifespan 起后台线程任务)
- python -m services.agent_service.shared.rag.case_sync  # 手动跑一轮

JD 对齐:第 7 条"安全数据 ETL" —— ES 内跨索引带复合游标幂等增量,就是一个小型 ETL。
"""
from __future__ import annotations

import asyncio
import logging
import time

from skills.config.settings import ES_INDEX_EVENTS
from skills.es import get_es_client, is_es_available

from .chunking import chunk_event_to_evidence
from .embed import embed_batch

logger = logging.getLogger(__name__)

# Meta 文档 _id(存于语料索引内,与语料文档同索引不同 _id 前缀)
META_DOC_ID = "__meta__case_sync"

# 单轮拉取批大小(游标按批推进)
DEFAULT_BATCH_SIZE = 50


# ============ 质量筛选 + 事件→corpus 文档(与 build_rag_index.py 共用)============

def quality_filter_case(docs: list[dict]) -> tuple[list[dict], dict]:
    """case 路质量筛选(对齐需求文档 P0-1:只入有效事件,筛掉统计数打日志,不静默丢)。

    筛选条件:
    - attack_type 非空(规则命中有效)
    - log_context.ip / log_context.timestamp 非空(上下文完整)
    - _describe_event 产出非空 content(可向量化;由 chunk_event_to_evidence 判定)

    Returns:
        (valid_docs, stats) stats 含各条件筛掉的数量,供对账
    """
    stats = {"total": len(docs), "no_attack_type": 0, "no_ip": 0, "no_timestamp": 0, "no_content": 0}
    valid: list[dict] = []
    for h in docs:
        src = h.get("_source", {}) or {}
        ctx = src.get("log_context") or {}
        if not src.get("attack_type"):
            stats["no_attack_type"] += 1
            continue
        if not ctx.get("ip"):
            stats["no_ip"] += 1
            continue
        if ctx.get("timestamp") is None:
            stats["no_timestamp"] += 1
            continue
        if chunk_event_to_evidence(h, "matched_logs") is None:
            stats["no_content"] += 1
            continue
        valid.append(h)
    stats["kept"] = len(valid)
    stats["dropped"] = stats["total"] - len(valid)
    return valid, stats


def hits_to_corpus_docs(hits: list[dict]) -> list[dict]:
    """matched_logs hits → corpus 文档列表(事件切片,复用 chunking.py)。

    corpus 文档字段(对齐 v2 mapping):content / source_id(= event_id)/
    source_type='case' / attack_type(主类型)/ created_at(事件时间 epoch ms)/ raw
    """
    docs: list[dict] = []
    for h in hits:
        ev = chunk_event_to_evidence(h, "matched_logs")
        if ev is None:
            continue
        raw = ev.raw or {}
        attack_type = str(raw.get("attack_type", "")).split(",")[0].strip()
        created_at = (raw.get("log_context") or {}).get("timestamp")
        docs.append({
            "content": ev.content,
            "source_id": ev.source_id,
            "source_type": "case",
            "attack_type": attack_type,
            "created_at": created_at,
            "raw": raw,
        })
    return docs


# ============ 复合游标 ============

def load_cursor(es, corpus_index: str) -> tuple[int, str]:
    """读取 Meta 文档水位;无 Meta 文档(首次)返回 (0, '')。"""
    try:
        resp = es.get(index=corpus_index, id=META_DOC_ID)
        src = resp.get("_source") or {}
        return int(src.get("last_created_at", 0)), str(src.get("last_event_id", ""))
    except Exception:
        # 404 not found(首次)或其他读取异常都从零水位开始;
        # 异常场景会全量重拉,upsert 幂等无重复,安全
        return 0, ""


def save_cursor(es, corpus_index: str, last_created_at: int, last_event_id: str) -> None:
    """持久化水位 Meta 文档(游标推进与数据写入同批完成后调用)。"""
    es.index(
        index=corpus_index,
        id=META_DOC_ID,
        body={
            "last_created_at": int(last_created_at),
            "last_event_id": str(last_event_id),
            "updated_at": int(time.time() * 1000),
        },
    )


def fetch_incremental(
    es,
    last_created_at: int,
    last_event_id: str,
    window_days: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[dict]:
    """按复合游标拉取 matched_logs 增量(近 N 天窗口内,(timestamp, event_id) 升序)。

    query 语义:
        filter: timestamp >= now - window_days(滚动时间窗)
        should: timestamp > last_created_at
                OR (timestamp == last_created_at AND event_id > last_event_id)
    """
    cutoff_ms = int((time.time() - window_days * 86400) * 1000)
    body = {
        "size": batch_size,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"log_context.timestamp": {"gte": cutoff_ms}}},
                    {
                        "bool": {
                            "should": [
                                {"range": {"log_context.timestamp": {"gt": last_created_at}}},
                                {
                                    "bool": {
                                        "filter": [
                                            {"term": {"log_context.timestamp": last_created_at}},
                                            {"range": {"event_id": {"gt": last_event_id}}},
                                        ]
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                ]
            }
        },
        "sort": [
            {"log_context.timestamp": {"order": "asc"}},
            {"event_id": {"order": "asc"}},
        ],
    }
    resp = es.search(index=ES_INDEX_EVENTS, body=body)
    return (resp.get("hits") or {}).get("hits", [])


# ============ 单轮同步 ============

def _embed_and_upsert(es, corpus_index: str, corpus_docs: list[dict]) -> None:
    """单批 embedding + bulk upsert(_id=source_id 幂等);任一失败抛出,不推进游标。"""
    if not corpus_docs:
        return
    embs = embed_batch([d["content"] for d in corpus_docs])  # 失败直接抛(显式报错)
    actions: list[dict] = []
    for d, emb in zip(corpus_docs, embs):
        doc = dict(d)
        doc["embedding"] = emb
        actions.append({"index": {"_index": corpus_index, "_id": doc["source_id"]}})
        actions.append(doc)
    resp = es.bulk(body=actions)
    if resp.get("errors"):
        errs = [it for it in resp.get("items", []) if it.get("index", {}).get("error")]
        raise RuntimeError(
            f"bulk upsert 部分失败: {len(errs)}/{len(corpus_docs)}"
            f"(首个错误: {errs[0].get('index', {}).get('error') if errs else 'n/a'})"
        )


def sync_once(
    es=None,
    corpus_index: str | None = None,
    window_days: int = 90,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """执行一轮增量同步(定时任务每轮调;返回统计)。

    流程:读水位 → 分批拉取 → 质量筛选 → 切片 → embed → bulk upsert → 推进水位。
    任一批失败:抛异常终止本轮,水位停留在上一批成功位置,下轮自动补齐。
    """
    from shared.config.settings import RAG_CONFIG  # 延迟导入避免循环依赖

    if es is None:
        es = get_es_client()
        if es is None or not is_es_available():
            raise RuntimeError("ES 不可用,case 语料增量同步失败")
    corpus_index = corpus_index or RAG_CONFIG.get("es_index_corpus", "auditweaver-rag-corpus")
    window_days = window_days or RAG_CONFIG.get("case_window_days", 90)

    stats = {"fetched": 0, "kept": 0, "dropped": 0, "written": 0, "batches": 0}
    last_created_at, last_event_id = load_cursor(es, corpus_index)
    logger.info(
        "[case_sync] 开始增量同步 cursor=(%d, %s) window=%dd",
        last_created_at, last_event_id or "-", window_days,
    )

    while True:
        hits = fetch_incremental(
            es, last_created_at, last_event_id,
            window_days=window_days, batch_size=batch_size,
        )
        if not hits:
            break

        stats["fetched"] += len(hits)
        valid, fstats = quality_filter_case(hits)
        stats["kept"] += fstats["kept"]
        stats["dropped"] += fstats["dropped"]
        corpus_docs = hits_to_corpus_docs(valid)

        # 写入失败(含 embedding 失败)→ 抛出,水位不推进,下轮重拉本批
        _embed_and_upsert(es, corpus_index, corpus_docs)
        stats["written"] += len(corpus_docs)
        stats["batches"] += 1

        # 游标推进到最后一条 hit(含被筛掉的:无效事件永久跳过,不再重筛)
        last_hit_src = hits[-1].get("_source", {}) or {}
        last_created_at = int((last_hit_src.get("log_context") or {}).get("timestamp", 0))
        last_event_id = str(last_hit_src.get("event_id", ""))
        save_cursor(es, corpus_index, last_created_at, last_event_id)

        if len(hits) < batch_size:
            break  # 无更多增量

    logger.info(
        "[case_sync] 本轮完成: fetched=%d kept=%d dropped=%d written=%d batches=%d "
        "cursor=(%d, %s)",
        stats["fetched"], stats["kept"], stats["dropped"], stats["written"],
        stats["batches"], last_created_at, last_event_id or "-",
    )
    return stats


# ============ 常驻循环(agent_service 后台任务)============

async def run_case_sync_forever(interval: int = 300) -> None:
    """常驻增量同步循环(FastAPI lifespan 起的 asyncio 任务)。

    每轮 sync_once;失败记 error 日志(不静默),下轮自动重试(水位未推进)。
    阻塞的 ES/embedding 调用走 asyncio.to_thread,不卡事件循环。
    """
    logger.info("[case_sync] 定时增量同步已启动 interval=%ds", interval)
    # 启动先跑一轮(服务起来即对齐水位)
    while True:
        try:
            await asyncio.to_thread(sync_once)
        except Exception as e:
            logger.error(
                "[case_sync] 本轮同步失败(水位未推进,下轮自动补齐): %s: %s",
                type(e).__name__, e,
            )
        await asyncio.sleep(interval)


def main():
    """CLI 手动触发单轮增量(python -m services.agent_service.shared.rag.case_sync)。"""
    import argparse
    from shared.config.settings import RAG_CONFIG

    parser = argparse.ArgumentParser(description="case 语料单轮增量同步")
    parser.add_argument("--days", type=int, default=None, help="时间窗(默认取 RAG_CONFIG)")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    stats = sync_once(
        window_days=args.days or RAG_CONFIG.get("case_window_days", 90),
        batch_size=args.batch_size,
    )
    print(f"case 语料增量同步完成: {stats}")


if __name__ == "__main__":
    main()
