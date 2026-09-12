"""LLM Gateway 异常类型。

设计原则(对齐项目约定):配置缺失显式报错,不静默降级。
- LLMConfigError: 配置缺失/不合法时抛出
- LLMUnavailableError: 所有 fallback 都失败时抛出
"""


class LLMError(Exception):
    """LLM Gateway 基础异常。"""


class LLMConfigError(LLMError):
    """配置缺失或不合法。

    典型场景:
    - role 未在 LLM_CONFIGS 中定义
    - 必填字段(api_key / base_url / model)缺失
    - fallback 链全部不可用且未配置任何可用 provider
    """


class LLMUnavailableError(LLMError):
    """所有 provider 都不可用。

    在 fallback 链全部尝试失败时抛出,不静默返回默认 LLM。
    """
