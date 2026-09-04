"""analysis_workflow Agent 专属配置(可覆盖全局默认)。

遵循三层配置结构:全局 common/env.py → shared/config/settings.py → 此处覆盖。
"""
from common.env import get_env, get_env_float
from shared.config.settings import LLM_CONFIG

# LLM temperature(对齐 Dify qwen2.5:7b 的 0.6,覆盖全局 0.2)
TEMPERATURE = get_env_float('AE_ANALYSIS_TEMPERATURE', 0.6)

# LLM model(默认沿用全局,可通过环境变量单独指定)
LLM_MODEL = get_env('AE_ANALYSIS_LLM_MODEL', LLM_CONFIG['model'])

# LLM base_url / api_key(默认沿用全局,用于让 workflow 单独走本地 ollama 等其他厂商)
LLM_BASE_URL = get_env('AE_ANALYSIS_LLM_BASE_URL', LLM_CONFIG['base_url'])
LLM_API_KEY = get_env('AE_ANALYSIS_LLM_API_KEY', LLM_CONFIG['api_key'])
