"""kNN 向量检索 —— ES kNN query 对 RAG 语料索引的 embedding 字段做语义检索。

设计要点(对齐 §3.4):
- 复用 skills.es.search 单例
- query embedding 由 embed.embed_query 生成(走 light 角色 OpenAI 兼容 endpoint)
- 默认索引 = RAG_CONFIG['es_index_corpus'](与 BM25 共用同一索引)
- 默认字段 = 'embedding'(dense_vector 类型,建索引时由 chunking + embed_batch 写入)
- ES 不可用 / 字段不存在 / kNN 不支持时返回空列表,让 retriever 决定降级

ES kNN 语法(ES 8.12+ 实测,顶层 knn 参数):
    {"size": N, "knn": {"field": "embedding", "query_vector": [...],
                        "k": N, "num_candidates": M, "filter": {...}}}
    - 走 HNSW 索引,效率高于 script_score 全表算 cosine
    - filter 是 HNSW 图遍历前的预过滤(pre-filter),不丢召回
      (对比后过滤 post-filter:先取 top-K 再过滤,可能不足 K 条)
    - ES 8.12 不支持 query 级 knn 子句(基线阶段实测 400),
      旧实现 "query": {"knn": {field: {...}}} 在当前集群从未生效过,
      vector 路一直降级为纯 BM25 —— 本次修复
    返回的 _score 已被 ES 归一化为 [0,1](cosine 相似度)

面试能讲什么:
- 为什么需要 dense_vector + kNN:BM25 只能匹配词面,无法理解"SQL注入" 和 "数据库注入" 语义相似
- 为什么 query 和 document 用同一 embedding 模型:cosine 相似度要求同向量空间
- 为什么用 ES kNN 而不是 Faiss/Milvus:复用现有 ES 集群,不引入新中间件
- HNSW vs 全表算 cosine:HNSW 是近似最近邻,牺牲一点 Recall 换 O(logN) 查询速度
- kNN filter 预过滤 vs 后过滤:预过滤在图遍历时剪枝,不丢召回(自引用排除的正确姿势)
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
    exclude_ids: list[str] | None = None,
    source_type: str | None = None,
    attack_type: str | None = None,
) -> list[Evidence]:
    """kNN 向量检索 ES RAG 语料索引。

    Args:
        query_embedding: 查询向量(由 embed.embed_query 生成)
        top_k: 返回条数
        index: ES 索引名,默认 RAG_CONFIG['es_index_corpus']
        embedding_field: dense_vector 字段名,默认 'embedding'
        exclude_ids: 排除的 source_id 列表(P0-2 自引用过滤;kNN filter 预过滤,
            HNSW 图遍历前剪枝,不丢召回)
        source_type: 元数据过滤,来源类型(knowledge / case;P1-2 双路 query 分离)
        attack_type: 元数据过滤,攻击类型(P1-2 knowledge 路按 matched_type 过滤)

    Returns:
        list[Evidence]: 按 cosine 相似度降序(ES 已归一化 _score)
        ES 不可用 / 字段不存在 / kNN 不支持返回空列表(不抛异常)
    """
    if not query_embedding:
        return []

    idx = index or RAG_CONFIG.get("es_index_corpus", "auditweaver-rag-corpus")

    # ES 8.12+ 顶层 knn 参数(带 k / num_candidates,否则 400)
    knn_clause: dict = {
        "field": embedding_field,
        "query_vector": query_embedding,
        "k": top_k,
        "num_candidates": max(top_k * 10, 100),
    }
    # 元数据 + 自引用排除:kNN filter(预过滤,图遍历前生效,不丢召回)
    bool_filter: dict = {"filter": []}
    if source_type:
        bool_filter["filter"].append({"term": {"source_type": source_type}})
    if attack_type:
        bool_filter["filter"].append({"term": {"attack_type": attack_type}})
    if exclude_ids:
        bool_filter["must_not"] = [{"terms": {"source_id": exclude_ids}}]
    if bool_filter["filter"] or "must_not" in bool_filter:
        knn_clause["filter"] = {"bool": bool_filter}

    body = {"size": top_k, "knn": knn_clause}
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
