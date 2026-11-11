"""Agent Service 全局配置(LLM Gateway / Memory / Agent 行为)。

所有 Agent 共用;按 ``.env`` 的 ``AE_*`` 切换,不改代码。

v2 升级(对齐设计 §3.7 LLM Gateway):
- LLM_CONFIGS:多角色配置(analysis 强模型 / light 弱模型)
- LLM_FALLBACK_CHAIN:fallback 链,主不可用走备,全失败显式报错
- LLM_RETRY_CONFIG:max_retries / 退避参数(429/5xx 由 langchain SDK 处理)
"""
from common.env import (
    get_env,
    get_env_bool,
    get_env_float,
    get_env_int,
    AE_MEMORY_BACKEND,
    AE_MEMORY_REDIS_URL,
)

# ============ LLM Gateway 多角色配置 ============
# analysis:强模型,用于 workflow analyze / agent plan / ReAct 决策
# light:弱模型,用于 validate / decision gate / compact 摘要(省钱)
# report:强模型,用于 workflow report 节点生成最终报告(可独立于 analysis 配置)
#
# 设计原则(对齐 §3.7 + 本地模型优先):
# - model 不硬编码云端模型名(deepseek-chat / gpt-4o-mini 等),必须由环境变量显式配置;
#   未配置时为空字符串,由 OpenAICompatProvider.validate_config 抛 LLMConfigError fast fail。
# - base_url 默认指向本地 Ollama(http://localhost:11434/v1),开箱即用本地模型。
# - light / report 未单独配置时,默认复用 analysis 的 model/base_url/api_key,
#   避免出现 "base_url 是厂商 A 但 model 是厂商 B" 的错配。
_LLM_ANALYSIS = {
    'provider': get_env('AE_LLM_PROVIDER', 'openai_compat'),
    'base_url': get_env('AE_LLM_BASE_URL', 'http://localhost:11434/v1'),
    'api_key': get_env('AE_LLM_API_KEY', 'ollama'),
    'model': get_env('AE_LLM_MODEL', ''),  # 不硬编码模型名,必须显式配置
    'temperature': get_env_float('AE_LLM_TEMPERATURE', 0.2),
}
_LLM_LIGHT = {
    'provider': get_env('AE_LLM_LIGHT_PROVIDER', _LLM_ANALYSIS['provider']),
    'base_url': get_env('AE_LLM_LIGHT_BASE_URL', _LLM_ANALYSIS['base_url']),
    'api_key': get_env('AE_LLM_LIGHT_API_KEY', _LLM_ANALYSIS['api_key']),
    # 未单独配置 light 模型时复用 analysis,不回退到 OpenAI 模型
    'model': get_env('AE_LLM_LIGHT_MODEL', _LLM_ANALYSIS['model']),
    'temperature': get_env_float('AE_LLM_LIGHT_TEMPERATURE', 0.1),
}
_LLM_REPORT = {
    'provider': get_env('AE_LLM_REPORT_PROVIDER', _LLM_ANALYSIS['provider']),
    'base_url': get_env('AE_LLM_REPORT_BASE_URL', _LLM_ANALYSIS['base_url']),
    'api_key': get_env('AE_LLM_REPORT_API_KEY', _LLM_ANALYSIS['api_key']),
    # 未单独配置 report 模型时复用 analysis
    'model': get_env('AE_LLM_REPORT_MODEL', _LLM_ANALYSIS['model']),
    'temperature': get_env_float('AE_LLM_REPORT_TEMPERATURE', _LLM_ANALYSIS['temperature']),
}

LLM_CONFIGS: dict[str, dict] = {
    'analysis': _LLM_ANALYSIS,
    'light': _LLM_LIGHT,
    'report': _LLM_REPORT,
}

# fallback 链:主 role 实例化失败 → 沿链向后尝试;全失败显式报错(不静默降级)
LLM_FALLBACK_CHAIN: list[str] = ['analysis', 'light', 'report']

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
    # 不硬编码模型名(如 text-embedding-3-small),必须显式配置;
    # 未配置时 embed.py 抛 EmbeddingNotConfigured,retriever 优雅降级为空 EvidencePack。
    'embedding_model': get_env('AE_RAG_EMBEDDING_MODEL', ''),
    # embedding 独立 endpoint(chat 厂商可能不提供 embeddings,如 DeepSeek 官方无 /embeddings):
    # 必须三项(BASE_URL / API_KEY / MODEL)同时配置或同时留空;
    # 全留空 → RAG 优雅降级(空 EvidencePack),不影响主 Workflow。
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
    # ---- v2 双路语料增量(P1-1 / P1-2,对齐 RAG优化需求文档)----
    # knowledge 路 top-K(双路 query 分离后知识证据条数,背景知识 2~3 条够用)
    'kb_top_k': get_env_int('AE_RAG_KB_TOP_K', 3),
    # case 路时间窗口(天):建库与增量同步共用,近 90 天 + 质量筛选
    'case_window_days': get_env_int('AE_RAG_CASE_WINDOW_DAYS', 90),
    # 定时增量同步开关(false = 关闭后台任务,仅手动建库)
    'case_sync_enabled': get_env_bool('AE_RAG_CASE_SYNC_ENABLED', True),
    # 定时增量同步间隔(秒,默认 5 分钟)
    'case_sync_interval': get_env_int('AE_RAG_CASE_SYNC_INTERVAL', 300),
}
