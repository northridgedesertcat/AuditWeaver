"""RAG 检索编排 —— BM25 + Vector → RRF → Evidence Pack(对齐 §3.4)。

入口函数:
    retrieve(query, top_k=5) -> EvidencePack

流程:
    1. embed_query(query) → query embedding(走 LLM Gateway light 角色)
    2. bm25_search(query, candidate_k) + knn_search(embedding, candidate_k)
       candidate_k = top_k * retrieve_candidate_multiplier(融合前抓更大候选集)
    3. rrf_fusion([bm25_list, vector_list], k, top_k=top_k)
    4. 返回 EvidencePack(query, evidences, fused, sources)

降级策略(显式,不静默):
    - 两路都成功 → RRF 融合(fused=True, sources=['bm25','vector'])
    - 只 BM25 成功 → 单路 BM25(fused=False, sources=['bm25'])
    - 只 Vector 成功 → 单路 Vector(fused=False, sources=['vector'])
    - 两路都失败 → 空 EvidencePack(fused=False, sources=[])
    - embed_query 失败 → 不降级,直接抛错(配置问题应改 .env,不是运行时降级)

面试能讲什么:
- 为什么用 EvidencePack 而不是 list:携带 fusion 元信息,LLM/前端可看是否融合 + 来源
- 降级语义:vector 路失败不等于配置错(可能索引没数据),降级合理;
  embed 配置错是环境问题,降级反而掩盖 bug,必须显式报错
- candidate_k > top_k:融合前抓更大候选集提升 Recall,融合后再裁剪
"""
from __future__ import annotations

import logging

from shared.config.settings import RAG_CONFIG
from shared.llm.exceptions import LLMError

from .bm25 import bm25_search
from .embed import embed_query
from .result import EvidencePack
from .rrf import rrf_fusion
from .vector import knn_search

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    top_k: int | None = None,
    rrf_k: int | None = None,
) -> EvidencePack:
    """混合检索 BM25 + Vector,RRF 融合返回 EvidencePack。

    Args:
        query: 查询文本
        top_k: 返回条数,默认 RAG_CONFIG['top_k']
        rrf_k: RRF 参数 k,默认 RAG_CONFIG['rrf_k']

    Returns:
        EvidencePack(query, evidences, fused, sources)
    """
    if not query:
        return EvidencePack(query=query or "", evidences=[], fused=False, sources=[])

    top_k = top_k or RAG_CONFIG.get("top_k", 5)
    rrf_k = rrf_k or RAG_CONFIG.get("rrf_k", 60)
    multiplier = RAG_CONFIG.get("retrieve_candidate_multiplier", 2)
    candidate_k = max(top_k * multiplier, top_k)

    # 1. embed query(失败显式抛错,不降级 —— 配置问题不应静默)
    try:
        query_embedding = embed_query(query)
    except LLMError:
        # LLM 配置错:抛给上层处理(对齐项目原则)
        raise
    except Exception as e:
        # 非 LLM 配置错(网络等):也显式抛,不掩盖
        logger.error(
            "[rag.retrieve] embed_query 失败(非配置错): %s: %s",
            type(e).__name__, e,
        )
        raise

    # 2. 两路检索(顺序执行;ES 同连,顺序开销小,后期需并发可加 asyncio.to_thread)
    bm25_results = bm25_search(query, top_k=candidate_k)
    vector_results = knn_search(query_embedding, top_k=candidate_k)

    # 3. 决策融合 / 降级(显式语义,不静默)
    if bm25_results and vector_results:
        # 两路都成功:RRF 融合
        fused = rrf_fusion(
            [bm25_results, vector_results],
            k=rrf_k,
            top_k=top_k,
        )
        logger.info(
            "[rag.retrieve] RRF 融合 bm25=%d vector=%d → fused=%d (top_k=%d)",
            len(bm25_results), len(vector_results), len(fused), top_k,
        )
        return EvidencePack(
            query=query,
            evidences=fused,
            fused=True,
            sources=["bm25", "vector"],
        )

    if bm25_results:
        # vector 路无结果(可能索引未建/无 embedding 字段/数据量小),降级纯 BM25
        logger.info(
            "[rag.retrieve] vector 路无结果,降级为纯 BM25(query=%s)",
            query[:60],
        )
        return EvidencePack(
            query=query,
            evidences=bm25_results[:top_k],
            fused=False,
            sources=["bm25"],
        )

    if vector_results:
        # BM25 路无结果(可能 content 字段未配 analyzer/无匹配词),降级纯 Vector
        logger.info(
            "[rag.retrieve] BM25 路无结果,降级为纯 Vector(query=%s)",
            query[:60],
        )
        return EvidencePack(
            query=query,
            evidences=vector_results[:top_k],
            fused=False,
            sources=["vector"],
        )

    # 两路都失败(ES 不可用 / 索引未建 / 无匹配)
    logger.warning(
        "[rag.retrieve] BM25 + Vector 均无结果(query=%s) "
        "请检查 RAG 语料索引 %s 是否已建 + 是否有数据",
        query[:60],
        RAG_CONFIG.get("es_index_corpus"),
    )
    return EvidencePack(
        query=query,
        evidences=[],
        fused=False,
        sources=[],
    )
