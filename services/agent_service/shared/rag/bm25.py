"""BM25 检索 —— ES match query 对 RAG 语料索引的 content 字段做精确词匹配。

设计要点(对齐 §3.4):
- 复用 skills.es.search 单例(不重复建连,不引入新中间件)
- 默认索引 = RAG_CONFIG['es_index_corpus'](与 vector 检索共用同一索引)
- 返回 list[Evidence],score = ES _score(供 RRF 看 rank,不看绝对值)
- ES 不可用返回空列表(不抛异常),让 retriever 决定降级策略
  (单路失败 vs 双路都失败 的降级语义不同,retriever 统一处理)

面试能讲什么:
- 为什么 BM25 而不是 TF-IDF:BM25 有饱和函数 + 文档长度归一化,更适合短文本
- BM25 适合什么场景:关键词精确匹配(IP / 域名 / 规则名 / attack_type)
- BM25 不擅长什么:语义相似(同义词/攻击描述的不同说法),由 vector 路补
"""
from __future__ import annotations

import logging

from skills.es import search as es_search
from shared.config.settings import RAG_CONFIG

from .result import Evidence, evidence_from_es_hit

logger = logging.getLogger(__name__)


def bm25_search(
    query: str,
    top_k: int = 10,
    index: str | None = None,
    content_field: str = "content",
) -> list[Evidence]:
    """BM25 检索 ES RAG 语料索引。

    Args:
        query: 查询文本(IP / 域名 / 攻击描述等)
        top_k: 返回条数
        index: ES 索引名,默认 RAG_CONFIG['es_index_corpus']
        content_field: BM25 匹配的字段名,默认 'content'

    Returns:
        list[Evidence]: 按 ES _score 降序排列
        ES 不可用 / 查询异常返回空列表(不抛异常)
    """
    if not query:
        return []

    idx = index or RAG_CONFIG.get("es_index_corpus", "auditweaver-rag-corpus")
    body = {
        "size": top_k,
        "query": {"match": {content_field: query}},
    }
    resp = es_search(idx, body)
    if resp is None:
        logger.warning(
            "[rag.bm25] ES 检索失败 index=%s query_len=%d", idx, len(query)
        )
        return []

    hits = (resp.get("hits") or {}).get("hits", [])
    evidences: list[Evidence] = []
    for h in hits:
        ev = evidence_from_es_hit(h, source_type=idx, content_field=content_field)
        evidences.append(ev)
    return evidences
