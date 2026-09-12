"""kNN 向量检索 —— ES kNN query 对 RAG 语料索引的 embedding 字段做语义检索。

设计要点(对齐 §3.4):
- 复用 skills.es.search 单例
- query embedding 由 embed.embed_query 生成(走 light 角色 OpenAI 兼容 endpoint)
- 默认索引 = RAG_CONFIG['es_index_corpus'](与 BM25 共用同一索引)
- 默认字段 = 'embedding'(dense_vector 类型,建索引时由 chunking + embed_batch 写入)
- ES 不可用 / 字段不存在 / kNN 不支持时返回空列表,让 retriever 决定降级

ES kNN query 用法:
    ES 8.x 用 "query": {"knn": {field: {"query_vector": [...]}}},
    走 HNSW 索引,效率高于 script_score 全表算 cosine
    返回的 _score 已被 ES 归一化为 [0,1](cosine 相似度)

面试能讲什么:
- 为什么需要 dense_vector + kNN:BM25 只能匹配词面,无法理解"SQL注入" 和 "数据库注入" 语义相似
- 为什么 query 和 document 用同一 embedding 模型:cosine 相似度要求同向量空间
- 为什么用 ES kNN 而不是 Faiss/Milvus:复用现有 ES 集群,不引入新中间件
- HNSW vs 全表算 cosine:HNSW 是近似最近邻,牺牲一点 Recall 换 O(logN) 查询速度
"""
from __future__ import annotations

import logging

from skills.es import search as es_search
from shared.config.settings import RAG_CONFIG

from .result import Evidence, evidence_from_es_hit

logger = logging.getLogger(__name__)


def knn_search(
    query_embedding: list[float],
    top_k: int = 10,
    index: str | None = None,
    embedding_field: str = "embedding",
) -> list[Evidence]:
    """kNN 向量检索 ES RAG 语料索引。

    Args:
        query_embedding: 查询向量(由 embed.embed_query 生成)
        top_k: 返回条数
        index: ES 索引名,默认 RAG_CONFIG['es_index_corpus']
        embedding_field: dense_vector 字段名,默认 'embedding'

    Returns:
        list[Evidence]: 按 cosine 相似度降序(ES 已归一化 _score)
        ES 不可用 / 字段不存在 / kNN 不支持返回空列表(不抛异常)
    """
    if not query_embedding:
        return []

    idx = index or RAG_CONFIG.get("es_index_corpus", "auditweaver-rag-corpus")
    # ES 8.x knn query(走 HNSW 索引,高效)
    body = {
        "size": top_k,
        "query": {
            "knn": {
                embedding_field: {
                    "query_vector": query_embedding,
                }
            }
        },
    }
    resp = es_search(idx, body)
    if resp is None:
        logger.warning(
            "[rag.vector] kNN 检索失败 index=%s field=%s", idx, embedding_field
        )
        return []

    hits = (resp.get("hits") or {}).get("hits", [])
    evidences: list[Evidence] = []
    for h in hits:
        ev = evidence_from_es_hit(h, source_type=idx)
        evidences.append(ev)
    return evidences
