"""Query Embedding —— 走 LLM Gateway light 角色调 OpenAI 兼容 embeddings endpoint。

设计要点(对齐 §3.4 / §3.7):
- 复用 light 角色的 api_key / base_url(省钱,弱模型足够)
- 不走 ChatOpenAI(那是对话模型),用 openai 库直调 embeddings API
- 配置缺失(api_key/base_url)显式抛 LLMConfigError,不静默降级(对齐项目原则)
- 进程内 LRU 缓存:同 query 文本复用 embedding,避免重复调 API
- 批量接口 embed_batch:建索引时一次批量多文本,省 API 调用次数

面试能讲什么:
- 为什么 query 和 document 用同一个 embedding 模型:cosine 相似度要求同向量空间
- 为什么走 light 角色:embedding 不需要推理能力,弱模型/小模型足够且便宜
- 为什么缓存:同 query 多次检索(决策门控触发 replan 时)避免重复花 token
"""
from __future__ import annotations

import logging
from typing import Any

from shared.config.settings import LLM_CONFIGS, RAG_CONFIG
from shared.llm.exceptions import LLMConfigError

logger = logging.getLogger(__name__)

# 进程内缓存:key=query 文本(前 200 字),value=embedding 向量
# 不做 LRU 上限:RAG 查询词数量有限,后期可换 functools.lru_cache
_embed_cache: dict[str, list[float]] = {}
_client: Any = None  # openai.OpenAI 实例,懒加载


def _get_embed_client() -> Any:
    """懒加载 openai.OpenAI 客户端,复用 light 角色配置。

    配置缺失显式报错,不静默降级(对齐项目原则)。
    """
    global _client
    if _client is not None:
        return _client

    # 优先从 light 角色取,fallback 到 analysis(对齐 LLM Gateway 设计)
    config = LLM_CONFIGS.get("light") or LLM_CONFIGS.get("analysis") or {}
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    missing: list[str] = []
    if not api_key:
        missing.append("api_key")
    if not base_url:
        missing.append("base_url")
    if missing:
        raise LLMConfigError(
            f"RAG embedding 配置缺失字段: {missing}。"
            f"请在 .env 中配置 AE_LLM_API_KEY / AE_LLM_BASE_URL"
            f"(或角色专用 AE_LLM_LIGHT_API_KEY / AE_LLM_LIGHT_BASE_URL)。"
        )

    try:
        # openai 库是 langchain_openai 的传递依赖,这里直接用
        import openai
    except ImportError as e:
        raise LLMConfigError(
            f"openai 库未安装,无法调用 embeddings endpoint: {e}。"
            f"请执行 `pip install openai`(或检查 langchain_openai 依赖)。"
        ) from e

    _client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30)
    logger.debug(
        "[rag.embed] 初始化 OpenAI embedding client base_url=%s model=%s",
        base_url, RAG_CONFIG.get("embedding_model"),
    )
    return _client


def embed_query(text: str, model: str | None = None) -> list[float]:
    """单条 query → embedding 向量。

    Args:
        text: 查询文本
        model: embedding 模型名,默认取 RAG_CONFIG['embedding_model']

    Returns:
        list[float]: 维度 = RAG_CONFIG['embedding_dim']

    缓存策略:同 text(前 200 字)直接返回缓存结果,不重复调 API。
    """
    if not text:
        return []
    cache_key = text[:200]
    if cache_key in _embed_cache:
        return _embed_cache[cache_key]

    client = _get_embed_client()
    model = model or RAG_CONFIG.get("embedding_model", "text-embedding-3-small")
    logger.debug("[rag.embed] embed_query model=%s text_len=%d", model, len(text))

    try:
        resp = client.embeddings.create(input=text, model=model)
    except Exception as e:
        # 不吞异常:embedding 失败意味着 RAG vector 路不可用,
        # 让 retriever 决定是否降级(显式报错,不静默)
        logger.error("[rag.embed] embedding API 调用失败: %s: %s", type(e).__name__, e)
        raise

    vec = resp.data[0].embedding
    _embed_cache[cache_key] = vec
    return vec


def embed_batch(texts: list[str], model: str | None = None) -> list[list[float]]:
    """批量 embedding(建索引时用,一次 API 调用处理多文本)。

    Args:
        texts: 待 embedding 的文本列表
        model: embedding 模型名

    Returns:
        list[list[float]]: 与 texts 等长的向量列表

    实现:
        - 先查缓存,过滤出未缓存的
        - 未缓存的批量调 API(OpenAI embeddings 支持一次 input=list)
        - 写回缓存
        - 按 texts 顺序返回(含缓存命中)
    """
    if not texts:
        return []

    client = _get_embed_client()
    model = model or RAG_CONFIG.get("embedding_model", "text-embedding-3-small")

    # 分离缓存命中 / 未命中
    results: list[list[float] | None] = [None] * len(texts)
    miss_idx: list[int] = []
    miss_texts: list[str] = []
    for i, t in enumerate(texts):
        cache_key = t[:200]
        if cache_key in _embed_cache:
            results[i] = _embed_cache[cache_key]
        else:
            miss_idx.append(i)
            miss_texts.append(t)

    if miss_texts:
        logger.debug(
            "[rag.embed] embed_batch total=%d cache_hit=%d api_call=%d model=%s",
            len(texts), len(texts) - len(miss_texts), len(miss_texts), model,
        )
        try:
            resp = client.embeddings.create(input=miss_texts, model=model)
        except Exception as e:
            logger.error("[rag.embed] batch embedding API 失败: %s: %s", type(e).__name__, e)
            raise
        # OpenAI 返回顺序与 input 顺序一致
        for j, item in enumerate(resp.data):
            vec = item.embedding
            original_idx = miss_idx[j]
            results[original_idx] = vec
            _embed_cache[miss_texts[j][:200]] = vec

    # 全部非 None
    return [r if r is not None else [] for r in results]


def clear_embed_cache() -> None:
    """清空进程内 embedding 缓存(测试 / 切换模型时用)。"""
    global _embed_cache
    _embed_cache = {}
