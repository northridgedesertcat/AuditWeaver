"""RAG 模块:BM25 + Vector → RRF → Evidence Pack + citation(对齐设计 §3.4)。

核心组件:
    - Evidence / EvidencePack:检索结果数据结构,带 source_id 用于 citation 溯源
    - rrf_fusion:多路检索结果融合的纯函数(score = 1/(k+rank))
    - embed_query / embed_batch:走 LLM Gateway light 角色调 OpenAI 兼容 embeddings
    - bm25_search:ES match query 对 RAG 语料索引的 content 字段做精确词匹配
    - knn_search:ES kNN query 对 embedding 字段做语义检索
    - chunk_event_to_evidence / chunk_nginx_session:安全日志按"事件/会话"切片
    - retrieve:混合检索编排,返回 EvidencePack

入口:
    from shared.rag import retrieve, EvidencePack
    pack = retrieve("SQL 注入攻击", top_k=5)
    for ev in pack.evidences:
        print(ev.source_id, ev.content, ev.score)
"""
from __future__ import annotations

from .bm25 import bm25_search
from .chunking import (
    NGINX_SESSION_WINDOW_MS,
    build_corpus_evidences,
    chunk_event_to_evidence,
    chunk_nginx_session,
)
from .embed import clear_embed_cache, embed_batch, embed_query
from .result import Evidence, EvidencePack, evidence_from_es_hit
from .retriever import retrieve
from .rrf import rrf_fusion
from .vector import knn_search

__all__ = [
    # result
    "Evidence",
    "EvidencePack",
    "evidence_from_es_hit",
    # rrf
    "rrf_fusion",
    # embed
    "embed_query",
    "embed_batch",
    "clear_embed_cache",
    # bm25 / vector
    "bm25_search",
    "knn_search",
    # chunking
    "chunk_event_to_evidence",
    "chunk_nginx_session",
    "build_corpus_evidences",
    "NGINX_SESSION_WINDOW_MS",
    # retriever
    "retrieve",
]
