"""LLM Gateway 对外入口(对齐设计 §3.7)。

对外导出:
- get_llm:多角色路由 + fallback 链工厂
- invoke_structured_with_retry:结构化输出解析失败重试辅助
- get_token_recorder / TokenUsageRecorder / TokenUsageCallbackHandler:token 统计
- LLMConfigError / LLMUnavailableError:显式错误类型
- BaseLLMProvider:provider 抽象
"""
from .base import BaseLLMProvider
from .exceptions import LLMConfigError, LLMError, LLMUnavailableError
from .factory import get_llm
from .retry import DEFAULT_STRUCTURED_RETRIES, invoke_structured_with_retry
from .token_usage import (
    TokenUsageCallbackHandler,
    TokenUsageRecord,
    TokenUsageRecorder,
    get_token_recorder,
)

__all__ = [
    "BaseLLMProvider",
    "get_llm",
    "invoke_structured_with_retry",
    "DEFAULT_STRUCTURED_RETRIES",
    "TokenUsageRecord",
    "TokenUsageRecorder",
    "TokenUsageCallbackHandler",
    "get_token_recorder",
    "LLMError",
    "LLMConfigError",
    "LLMUnavailableError",
]
