"""Query Embedding —— 走独立的 OpenAI-compatible embeddings endpoint。

设计要点(对齐 §3.4 / §3.7):
- embedding 专用 endpoint:AE_RAG_EMBEDDING_BASE_URL / AE_RAG_EMBEDDING_API_KEY /
  AE_RAG_EMBEDDING_MODEL(chat 与 embedding 可走不同厂商,如 chat=Ollama +
  embedding=硅基流动 bge-m3)。
- 不再回退到 light LLM 的 endpoint(DeepSeek 等厂商不提供 /embeddings,
  回退会导致 404)。
- 三项全未配置 → 抛 EmbeddingNotConfigured,由 retriever 优雅降级为空 EvidencePack。
- 只配了部分 → 抛 LLMConfigError(配置不完整不静默,对齐项目原则)。
- 不走 ChatOpenAI(那是对话模型),用 openai 库直调 embeddings API。
- 进程内 LRU 缓存:同 query 文本复用 embedding,避免重复调 API。
- 批量接口 embed_batch:建索引时一次批量多文本,省 API 调用次数。

面试能讲什么:
- 为什么 query 和 document 用同一个 embedding 模型:cosine 相似度要求同向量空间
- 为什么走独立 endpoint:chat 厂商(如 DeepSeek 官方)不一定提供 /embeddings
- 为什么缓存:同 query 多次检索(决策门控触发 replan 时)避免重复花 token
"""
from __future__ import annotations

import logging
from typing import Any

from shared.config.settings import RAG_CONFIG
from shared.llm.exceptions import LLMConfigError

logger = logging.getLogger(__name__)


class EmbeddingNotConfigured(LLMConfigError):
    """embedding 未配置(base_url / api_key / model 全空)。

    与 LLMConfigError 的区别:
    - EmbeddingNotConfigured 表示"用户主动不配置 embedding",retriever 应优雅降级
      为空 EvidencePack,不阻断主 Workflow。
    - LLMConfigError 表示"配置了但不完整/不合法",应显式报错让用户改 .env。
    """


# 进程内缓存:key=query 文本(前 200 字),value=embedding 向量
# 不做 LRU 上限:RAG 查询词数量有限,后期可换 functools.lru_cache
_embed_cache: dict[str, list[float]] = {}
_client: Any = None  # openai.OpenAI 实例,懒加载


def _resolve_embed_credentials() -> tuple[str, str, str]:
    """解析 embedding endpoint 凭证,返回 (api_key, base_url, model)。

    规则(对齐 §3.4 / §3.7):
    1. 三项(base_url / api_key / model)全空 → 抛 EmbeddingNotConfigured
       (retriever 捕获后降级为空 EvidencePack)。
    2. 只配了部分 → 抛 LLMConfigError(配置不完整不静默)。
    3. 三项齐全 → 返回凭证。

    不再回退到 light LLM 角色:chat 厂商(如 DeepSeek 官方)不一定提供 /embeddings,
    回退会导致运行时 404,不如显式告知用户配置独立 embedding endpoint。
    """
    emb_api_key = (RAG_CONFIG.get("embedding_api_key") or "").strip()
    emb_base_url = (RAG_CONFIG.get("embedding_base_url") or "").strip()
    emb_model = (RAG_CONFIG.get("embedding_model") or "").strip()

    # 三项全空 → 未配置 embedding,允许 RAG 降级
    if not emb_api_key and not emb_base_url and not emb_model:
        raise EmbeddingNotConfigured(
            "RAG embedding 未配置(AE_RAG_EMBEDDING_BASE_URL / API_KEY / MODEL 均为空)。"
            "RAG 将降级为空 EvidencePack,不影响主 Workflow。"
            "如需启用向量检索,请配置独立的 embedding endpoint(如 Ollama nomic-embed-text)。"
        )

    # 只配了部分 → 配置不完整,显式报错
    missing = []
    if not emb_api_key:
        missing.append("AE_RAG_EMBEDDING_API_KEY")
    if not emb_base_url:
        missing.append("AE_RAG_EMBEDDING_BASE_URL")
    if not emb_model:
        missing.append("AE_RAG_EMBEDDING_MODEL")
    if missing:
        raise LLMConfigError(
            f"RAG embedding 配置不完整,缺少: {missing}。"
            f"embedding 的 base_url / api_key / model 必须同时配置(或同时留空以降级)。"
        )

    return emb_api_key, emb_base_url, emb_model


def _get_embed_client() -> Any:
    """懒加载 openai.OpenAI 客户端。

    凭证解析见 _resolve_embed_credentials(独立 embedding endpoint,不回退 chat)。
    未配置 → EmbeddingNotConfigured(由 retriever 降级);配置不完整 → LLMConfigError。
    """
    global _client
    if _client is not None:
        return _client

    api_key, base_url, _model = _resolve_embed_credentials()

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

    Raises:
        EmbeddingNotConfigured: embedding 未配置时(由 retriever 降级)
        LLMConfigError: 配置不完整时
    """
    if not text:
        return []
    cache_key = text[:200]
    if cache_key in _embed_cache:
        return _embed_cache[cache_key]

    client = _get_embed_client()
    model = model or RAG_CONFIG.get("embedding_model")
    if not model:
        # model 为空理论上不会到这里(_resolve_embed_credentials 已校验),
        # 但兜底显式报错
        raise LLMConfigError(
            "embedding model 未配置,请设置 AE_RAG_EMBEDDING_MODEL。"
        )
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
    model = model or RAG_CONFIG.get("embedding_model")
    if not model:
        raise LLMConfigError(
            "embedding model 未配置,请设置 AE_RAG_EMBEDDING_MODEL。"
        )

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
