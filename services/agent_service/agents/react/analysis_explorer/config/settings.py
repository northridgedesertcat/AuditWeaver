"""Analysis Explorer Agent 专属配置(可覆盖全局默认)。"""
from common.env import get_env_int
from shared.config.settings import AGENT_CONFIG

# 最大工具调用轮数(防止 LLM 反复调工具不结束)
MAX_TOOL_ROUNDS = get_env_int(
    'AE_AGENT_MAX_TOOL_ROUNDS', AGENT_CONFIG['max_tool_rounds']
)

# 单次工具调用超时(秒)
TOOL_TIMEOUT = get_env_int(
    'AE_AGENT_TOOL_TIMEOUT', AGENT_CONFIG['tool_timeout']
)
