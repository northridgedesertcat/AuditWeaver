"""工具调用规范层(对齐设计 §3.6)。

对外导出:
- ToolResult / ToolErrorType / tool_ok / tool_fail:统一结果格式
- ToolAuditRecord / ToolAuditRecorder / get_tool_audit_recorder:审计
- wrap_tool_with_spec / wrap_mcp_tools:包装现有 BaseTool
"""
from .audit import (
    ToolAuditRecord,
    ToolAuditRecorder,
    ToolAuditSummary,
    get_tool_audit_recorder,
    TOOL_AUDIT_LOG,
)
from .result import ToolErrorType, ToolResult, tool_fail, tool_ok
from .wrapper import (
    DEFAULT_EXPONENTIAL_BASE,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TOOL_TIMEOUT_S,
    wrap_mcp_tools,
    wrap_tool_with_spec,
)

__all__ = [
    "ToolResult",
    "ToolErrorType",
    "tool_ok",
    "tool_fail",
    "ToolAuditRecord",
    "ToolAuditRecorder",
    "ToolAuditSummary",
    "get_tool_audit_recorder",
    "TOOL_AUDIT_LOG",
    "wrap_tool_with_spec",
    "wrap_mcp_tools",
    "DEFAULT_TOOL_TIMEOUT_S",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_EXPONENTIAL_BASE",
]
