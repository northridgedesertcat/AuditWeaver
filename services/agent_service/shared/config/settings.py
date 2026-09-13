"""Agent Service 全局配置(LLM Gateway / Memory / Agent 行为)。

所有 Agent 共用;按 ``.env`` 的 ``AE_*`` 切换,不改代码。

v2 升级(对齐设计 §3.7 LLM Gateway):
- LLM_CONFIGS:多角色配置(analysis 强模型 / light 弱模型)
- LLM_FALLBACK_CHAIN:fallback 链,主不可用走备,全失败显式报错
- LLM_RETRY_CONFIG:max_retries / 退避参数(429/5xx 由 langchain SDK 处理)
"""
from common.env import (
    get_env,
    get_env_float,
    get_env_int,
    AE_MEMORY_BACKEND,
    AE_MEMORY_REDIS_URL,
)

# ============ LLM Gateway 多角色配置 ============
# analysis:强模型,用于 workflow analyze / agent plan / ReAct 决策
# light:弱模型,用于 validate / decision gate / compact 摘要(省钱)
# light 的字段缺失时,factory 会沿 LLM_FALLBACK_CHAIN 回退到 analysis,
# 不静默使用无效配置。
_LLM_ANALYSIS = {
    'provider': get_env('AE_LLM_PROVIDER', 'openai_compat'),
    'base_url': get_env('AE_LLM_BASE_URL'),
    'api_key': get_env('AE_LLM_API_KEY'),
    'model': get_env('AE_LLM_MODEL', 'deepseek-chat'),
    'temperature': get_env_float('AE_LLM_TEMPERATURE', 0.2),
}
_LLM_LIGHT = {
    'provider': get_env('AE_LLM_LIGHT_PROVIDER', _LLM_ANALYSIS['provider']),
    'base_url': get_env('AE_LLM_LIGHT_BASE_URL', _LLM_ANALYSIS['base_url']),
    'api_key': get_env('AE_LLM_LIGHT_API_KEY', _LLM_ANALYSIS['api_key']),
    'model': get_env('AE_LLM_LIGHT_MODEL', 'gpt-4o-mini'),  # 默认指向更便宜的弱模型
    'temperature': get_env_float('AE_LLM_LIGHT_TEMPERATURE', 0.1),
}

LLM_CONFIGS: dict[str, dict] = {
    'analysis': _LLM_ANALYSIS,
    'light': _LLM_LIGHT,
}

# fallback 链:analysis 不可用 → light → 显式报错(不静默降级)
LLM_FALLBACK_CHAIN: list[str] = ['analysis', 'light']

# retry 配置(注入 ChatOpenAI 的 max_retries,SDK 自带指数退避)
LLM_RETRY_CONFIG: dict = {
    'max_retries': get_env_int('AE_LLM_MAX_RETRIES', 3),
    # 以下参数预留给结构化输出重试辅助(shared/llm/retry.py)
    'initial_delay': get_env_float('AE_LLM_RETRY_INITIAL_DELAY', 1.0),
    'exponential_base': get_env_float('AE_LLM_RETRY_EXPONENTIAL_BASE', 2.0),
}

# ============ 会话历史 ============
# memory=进程内 MemorySaver(默认,不依赖 Redis);redis=RedisSaver 持久化
# 常量来自 common.env;redis 模式下 AE_MEMORY_REDIS_URL 未配置时为 None,由 redis.py fast fail
MEMORY_CONFIG = {
    'backend': AE_MEMORY_BACKEND,
    'redis_url': AE_MEMORY_REDIS_URL,
}

# ============ Agent 行为默认值(可在 agents/<name>/config 中覆盖)============
AGENT_CONFIG = {
    'max_tool_rounds': get_env_int('AE_AGENT_MAX_TOOL_ROUNDS', 5),
    'tool_timeout': get_env_int('AE_AGENT_TOOL_TIMEOUT', 30),
}

# ============ RAG 配置(对齐设计 §3.4)============
# RAG 专用 ES 索引:存 chunking 后的 evidence(content + embedding + source 元数据)
# 与现有 nginx-log-raw / matched_logs 业务索引分离,避免污染业务索引 mapping
# 索引未创建/无 embedding 字段时,运行时显式报错,不静默降级(对齐项目原则)
RAG_CONFIG: dict = {
    # RAG 语料 ES 索引名(由 evals/build_rag_index.py 创建 + 灌数据)
    'es_index_corpus': get_env('AE_RAG_ES_INDEX', 'auditweaver-rag-corpus'),
    # embedding 模型:OpenAI 兼容 embeddings endpoint
    'embedding_model': get_env('AE_RAG_EMBEDDING_MODEL', 'text-embedding-3-small'),
    # embedding 独立 endpoint(chat 厂商可能不提供 embeddings,如 DeepSeek 官方无 /embeddings):
    # 配了就走专用 embedding 服务商(如硅基流动 BAAI/bge-m3);
    # 两项都留空 → 回退 light 角色的 base_url/api_key(向后兼容);
    # 只配一项 → embed.py 显式抛 LLMConfigError(配置不完整不静默)
    'embedding_base_url': get_env('AE_RAG_EMBEDDING_BASE_URL', ''),
    'embedding_api_key': get_env('AE_RAG_EMBEDDING_API_KEY', ''),
    # 向量维度(text-embedding-3-small=1536, bge-m3=1024, nomic=768)
    'embedding_dim': get_env_int('AE_RAG_EMBEDDING_DIM', 1536),
    # RRF 融合参数 k:score = 1/(k + rank),k 越大各路排名差异越平滑
    'rrf_k': get_env_int('AE_RAG_RRF_K', 60),
    # 默认召回 top-K(Evidence Pack 大小)
    'top_k': get_env_int('AE_RAG_TOP_K', 5),
    # 每路 BM25/Vector 候召回数 = top_k * multiplier(融合前抓更大候选集提升 Recall)
    'retrieve_candidate_multiplier': get_env_int('AE_RAG_CANDIDATE_MULTIPLIER', 2),
}
