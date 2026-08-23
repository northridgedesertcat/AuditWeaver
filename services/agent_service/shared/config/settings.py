"""Agent Service 全局配置(LLM / Memory / Agent 行为)。

所有 Agent 共用;按 ``.env`` 的 ``AE_*`` 切换,不改代码。
"""
from common.env import get_env, get_env_float, get_env_int

# LLM(OpenAI 兼容,覆盖 DeepSeek / Qwen / GLM / Kimi / OpenAI 官方)
LLM_CONFIG = {
    'provider': get_env('AE_LLM_PROVIDER', 'openai_compat'),
    'base_url': get_env('AE_LLM_BASE_URL'),
    'api_key': get_env('AE_LLM_API_KEY'),
    'model': get_env('AE_LLM_MODEL', 'deepseek-chat'),
    'temperature': get_env_float('AE_LLM_TEMPERATURE', 0.2),
}

# 会话历史(一版进程内 MemorySaver,预留 Redis)
MEMORY_CONFIG = {
    'backend': get_env('AE_MEMORY_BACKEND', 'memory'),
    'redis_url': get_env('AE_MEMORY_REDIS_URL', 'redis://localhost:6379/0'),
}

# Agent 行为默认值(可在 agents/<name>/config 中覆盖)
AGENT_CONFIG = {
    'max_tool_rounds': get_env_int('AE_AGENT_MAX_TOOL_ROUNDS', 5),
    'tool_timeout': get_env_int('AE_AGENT_TOOL_TIMEOUT', 30),
}
