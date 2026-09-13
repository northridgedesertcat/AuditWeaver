"""统一 ToolResult 规范(对齐设计 §3.6)。

核心思想:工具调用永远不抛异常给 LLM,而是返回结构化结果,
让 LLM 能读懂错误并自我修正(而非把异常冒泡到 Agent 主流程)。

字段约定:
- ok: bool,调用是否成功
- data: 任意类型(原工具返回值,成功时填)
- error: str | None,失败原因(面向 LLM 的可读文本)
- error_type: ToolErrorType | None,失败分类(便于审计/调试)
- source_ids: list[str],证据来源 ID 列表(用于 Evidence Pack 追溯,见 §3.5)
- duration_ms: float,本次调用耗时(审计用)
"""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolErrorType(str, Enum):
    """工具失败分类。"""
    TIMEOUT = "timeout"  # 超时
    RETRY_EXHAUSTED = "retry_exhausted"  # 重试耗尽
    VALIDATION_ERROR = "validation_error"  # 入参校验失败
    EXECUTION_ERROR = "execution_error"  # 工具内部异常
    NOT_FOUND = "not_found"  # 资源未找到
    EMPTY_RESULT = "empty_result"  # 工具主动返回空(非错误,但 LLM 应感知)


class ToolResult(BaseModel):
    """统一工具调用结果。

    LLM 看到的 ToolMessage 内容 = self.model_dump_json(),
    字段语义清晰可被 LLM 解析用于决策下一步。
    """
    ok: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[ToolErrorType] = None
    source_ids: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0

    def to_json(self) -> str:
        """序列化为 JSON 字符串(供 ToolMessage.content 用)。"""
        return self.model_dump_json()


def tool_ok(
    data: Any,
    *,
    source_ids: list[str] | None = None,
    duration_ms: float = 0.0,
) -> ToolResult:
    """构造成功结果。"""
    return ToolResult(
        ok=True,
        data=data,
        source_ids=source_ids or [],
        duration_ms=duration_ms,
    )


def tool_fail(
    error: str,
    *,
    error_type: ToolErrorType = ToolErrorType.EXECUTION_ERROR,
    data: Any = None,
    duration_ms: float = 0.0,
) -> ToolResult:
    """构造失败结果(不抛异常,LLM 可读懂自我修正)。"""
    return ToolResult(
        ok=False,
        data=data,
        error=error,
        error_type=error_type,
        duration_ms=duration_ms,
    )
