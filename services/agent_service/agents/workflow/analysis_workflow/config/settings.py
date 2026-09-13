"""analysis_workflow Agent 专属配置(可覆盖全局默认)。

遵循三层配置结构:全局 common/env.py → shared/config/settings.py → 此处覆盖。

v2.1 升级(对齐 §3.1):
- 从 LLM_CONFIGS['analysis'] 取默认(替代旧 LLM_CONFIG 视图),
  让 workflow 默认对齐 Gateway analysis 角色
- 新增 MAX_ENRICH_COUNT=enrich 循环上限(防死循环,对齐 §3.1 "enrich_count ≤ 2")
- 新增 VALIDATE_TEMPERATURE=validate 节点温度(门控不需高随机性,0.1 保守)
- 新增 RAG_TOP_K=workflow 默认检索条数(可独立于 RAG_CONFIG.top_k 调整)
"""
from common.env import get_env, get_env_float, get_env_int
from shared.config.settings import LLM_CONFIGS, RAG_CONFIG

_ANALYSIS_CFG = LLM_CONFIGS['analysis']

# ============ analyze / report 节点 LLM 配置(强模型)============

# LLM temperature(对齐 Dify qwen2.5:7b 的 0.6,覆盖全局 0.2)
TEMPERATURE = get_env_float('AE_ANALYSIS_TEMPERATURE', 0.6)

# LLM model(默认沿用 analysis 角色,可通过环境变量单独指定)
LLM_MODEL = get_env('AE_ANALYSIS_LLM_MODEL', _ANALYSIS_CFG['model'])

# LLM base_url / api_key(默认沿用 analysis 角色,用于让 workflow 单独走本地 ollama 等其他厂商)
LLM_BASE_URL = get_env('AE_ANALYSIS_LLM_BASE_URL', _ANALYSIS_CFG['base_url'])
LLM_API_KEY = get_env('AE_ANALYSIS_LLM_API_KEY', _ANALYSIS_CFG['api_key'])

# ============ validate 节点 LLM 配置(light 模型,质量门控)============

# 门控不需高随机性,0.1 保守;用 light 角色省钱(对齐 §3.1)
VALIDATE_TEMPERATURE = get_env_float('AE_VALIDATE_TEMPERATURE', 0.1)

# ============ enrich 循环配置 ============

# enrich 循环上限:防死循环,对齐 §3.1 "enrich_count ≤ 2"
# 即使 validate 一直 FAIL,最多补检索 2 次后强制走 report(降级出报告)
MAX_ENRICH_COUNT = get_env_int('AE_WORKFLOW_MAX_ENRICH_COUNT', 2)

# ============ RAG 检索配置(workflow 层覆盖)============

# workflow 默认检索条数,可独立于 RAG_CONFIG.top_k 调整(对齐 §3.1 "K=5")
RAG_TOP_K = get_env_int('AE_WORKFLOW_RAG_TOP_K', RAG_CONFIG.get('top_k', 5))
