"""Analysis Explorer Agent 专属配置(可覆盖全局默认)。

遵循三层配置结构:全局 common/env.py → shared/config/settings.py → 此处覆盖。

v2.1 升级(对齐 §3.2):
- 保留 v1 的 MAX_TOOL_ROUNDS / TOOL_TIMEOUT(向后兼容,不再用于硬上限,
  改用预算制 budget,但保留字段避免破坏旧调用)
- 新增 MAX_COMPACT_COUNT:compact 上限(防过度压缩,对齐 §3.5.3)
- 新增 DECISION_TEMPERATURE:decision_llm 温度(门控保守 0.1,对齐 §3.2.3)
- 新增 PLAN_TEMPERATURE:plan 节点温度(规划需一定创造性 0.3)
- 新增 COMPACT_TEMPERATURE:compact 节点温度(摘要要忠实 0.0)
- 新增 DEFAULT_BUDGET_SIMPLE / DEFAULT_BUDGET_COMPLEX:预算制(简单 3/复杂 10,对齐 §3.2.2)
- 新增 TOKEN_BUDGET_THRESHOLD:token 预算阈值(触发 compact,对齐 §3.2.3)
- 新增 RECENT_MESSAGES_N:compact 时保留的最近消息数(对齐 §3.5.3)
- 新增 EXPECTED_EVIDENCE_MIN:预期证据下限(deterministic_gate 判断证据不足用)
- 新增 CONSECUTIVE_FAILURE_THRESHOLD:连续失败阈值(触发 gate)
- 新增 DUPLICATE_ROUNDS_THRESHOLD:重复调用阈值(触发 gate)
"""
from common.env import get_env, get_env_float, get_env_int
from shared.config.settings import AGENT_CONFIG, LLM_CONFIGS

_ANALYSIS_CFG = LLM_CONFIGS['analysis']

# ============ v1 保留配置(向后兼容,不再作为硬上限)============

# 最大工具调用轮数(v1 用于硬上限,v2.1 改用 budget 预算制,此字段保留避免破坏旧引用)
MAX_TOOL_ROUNDS = get_env_int(
    'AE_AGENT_MAX_TOOL_ROUNDS', AGENT_CONFIG['max_tool_rounds']
)

# 单次工具调用超时(秒)
TOOL_TIMEOUT = get_env_int(
    'AE_AGENT_TOOL_TIMEOUT', AGENT_CONFIG['tool_timeout']
)

# ============ v2.1 新增:Agent 升级配置(对齐 §3.2)============

# compact 上限:防过度压缩(对齐 §3.5.3 "compact_count +1,防过度压缩")
# 达上限时降级为不压缩,避免无限压缩
MAX_COMPACT_COUNT = get_env_int('AE_AGENT_MAX_COMPACT_COUNT', 2)

# decision_llm 温度:门控保守,0.1(对齐 §3.2.3)
DECISION_TEMPERATURE = get_env_float('AE_AGENT_DECISION_TEMPERATURE', 0.1)

# plan 节点温度:规划需一定创造性,但不要太散,0.3
PLAN_TEMPERATURE = get_env_float('AE_AGENT_PLAN_TEMPERATURE', 0.3)

# compact 节点温度:摘要要忠实,0.0
COMPACT_TEMPERATURE = get_env_float('AE_AGENT_COMPACT_TEMPERATURE', 0.0)

# 预算制:plan 阶段决定简单问题 3 轮、复杂调查 10 轮(对齐 §3.2.2)
DEFAULT_BUDGET_SIMPLE = get_env_int('AE_AGENT_BUDGET_SIMPLE', 3)
DEFAULT_BUDGET_COMPLEX = get_env_int('AE_AGENT_BUDGET_COMPLEX', 10)

# token 预算阈值:累计 token 超此值触发 compact(对齐 §3.2.3 "token 接近阈值")
TOKEN_BUDGET_THRESHOLD = get_env_int('AE_AGENT_TOKEN_BUDGET_THRESHOLD', 8000)

# compact 时保留的最近消息数(对齐 §3.5.3 "保留最近 N 轮")
RECENT_MESSAGES_N = get_env_int('AE_AGENT_RECENT_MESSAGES_N', 4)

# 预期证据下限:evidence_pack 条数少于此值时,gate 命中"证据不足"
EXPECTED_EVIDENCE_MIN = get_env_int('AE_AGENT_EXPECTED_EVIDENCE_MIN', 2)

# 连续失败阈值:连续工具失败达此值时,gate 命中"工具失败/连续失败"
CONSECUTIVE_FAILURE_THRESHOLD = get_env_int('AE_AGENT_CONSECUTIVE_FAILURE_THRESHOLD', 2)

# 重复调用阈值:最近 N 轮工具调用相同入参时,gate 命中"重复/停滞"
DUPLICATE_ROUNDS_THRESHOLD = get_env_int('AE_AGENT_DUPLICATE_ROUNDS_THRESHOLD', 2)

# ============ LLM 配置(沿用 analysis 角色,可独立覆盖)============

TEMPERATURE = get_env_float('AE_AGENT_TEMPERATURE', _ANALYSIS_CFG['temperature'])
LLM_MODEL = get_env('AE_AGENT_LLM_MODEL', _ANALYSIS_CFG['model'])
LLM_BASE_URL = get_env('AE_AGENT_LLM_BASE_URL', _ANALYSIS_CFG['base_url'])
LLM_API_KEY = get_env('AE_AGENT_LLM_API_KEY', _ANALYSIS_CFG['api_key'])
