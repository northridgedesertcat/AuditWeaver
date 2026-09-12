"""LLM 调用重试辅助。

设计要点(对齐设计 §3.7):
- 429/5xx 指数退避:由 LangChain ChatOpenAI 自带 max_retries 处理(在 openai_compat.py 注入)
- 结构化输出解析失败:本模块提供 with_structured_output_retry 辅助,解析失败时附加错误反馈重试

为什么不自己写 HTTP 层重试:langchain 的 BaseChatModel 已封装 OpenAI SDK 重试,
自己重写一层是 over-engineering,且容易与 SDK 行为冲突。
"""
import asyncio
import logging
from typing import Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# 默认结构化输出重试次数(对齐 LLM_RETRY_CONFIG.max_retries 默认 3,这里单独可调)
DEFAULT_STRUCTURED_RETRIES = 2


async def invoke_structured_with_retry(
    llm_structured,  # RunnableWithStructuredOutput (Runnable)
    messages: list[BaseMessage],
    schema: Type[T],
    *,
    max_retries: int = DEFAULT_STRUCTURED_RETRIES,
    role: str = "analysis",
) -> T:
    """调用结构化输出 LLM,解析失败时附加错误反馈重试。

    策略:
    - 第 0 次:直接调用
    - 失败(ValidationError 或 OutputParserException)时:
      追加 SystemMessage 反馈错误 + 强调 schema,重试
    - 最多 max_retries 次重试,全部失败抛最后一次异常

    Args:
        llm_structured: llm.with_structured_output(schema, method=...) 的产物
        messages: 原始调用消息
        schema: 期望的 Pydantic schema(用于反馈消息构造)
        max_retries: 最大重试次数(不含首次)
        role: 角色名,用于日志

    Returns:
        schema 实例
    """
    last_error: Exception | None = None
    schema_hint = (
        f"请严格按 {schema.__name__} 的 JSON Schema 输出,"
        f"字段:{list(schema.model_fields.keys())}"
    )

    for attempt in range(max_retries + 1):
        attempt_messages = list(messages)
        if attempt > 0 and last_error is not None:
            feedback = (
                f"上次输出解析失败:{type(last_error).__name__}: {str(last_error)[:300]}。"
                f"{schema_hint}。仅输出 JSON,不要任何解释或 markdown 代码块标记。"
            )
            attempt_messages.append(SystemMessage(content=feedback))
            logger.warning(
                "[llm.retry] role=%s structured 输出解析失败(第 %d 次),附加错误反馈重试",
                role, attempt,
            )

        try:
            result = await llm_structured.ainvoke(attempt_messages)
            # 兜底:若返回的是 dict 而非 schema 实例,二次校验
            if isinstance(result, dict):
                return schema.model_validate(result)
            if isinstance(result, schema):
                return result
            # 兼容其他类型:尝试 schema 校验
            return schema.model_validate(result)
        except (ValidationError, ValueError) as e:
            last_error = e
            continue
        except Exception as e:
            # 非解析类异常(网络/超时等)直接抛,不重试
            logger.error(
                "[llm.retry] role=%s 结构化调用遭遇非解析异常,不重试: %s: %s",
                role, type(e).__name__, e,
            )
            raise

    raise last_error  # type: ignore[misc]
