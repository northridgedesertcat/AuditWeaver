"""工具调用规范包装器(对齐设计 §3.6)。

在现有 MCP 工具外包一层,提供:
- 统一 ToolResult 输出(ok/data/error/source_ids/duration_ms)
- 超时(默认 10s,超时返回 ok=False 不抛异常)
- 重试(瞬时失败如网络/超时,指数退避,默认 2 次)
- 审计(每次调用写 JSONL)
- source_ids 提取(从返回值里扫描常见 ID 字段,用于 Evidence Pack 追溯)

不改 MCP 协议:包装后的工具仍是 LangChain BaseTool,
bind_tools / ToolNode 无感知。
"""
import asyncio
import logging
import time
from typing import Any, Optional

from langchain_core.tools import BaseTool, StructuredTool

from shared.config.settings import AGENT_CONFIG
from .audit import (
    ToolAuditRecord,
    _truncate_for_log,
    get_tool_audit_recorder,
)
from .result import ToolErrorType, ToolResult, tool_fail, tool_ok

logger = logging.getLogger(__name__)

# 默认参数(可由 AGENT_CONFIG / 环境变量覆盖)
DEFAULT_TOOL_TIMEOUT_S = float(AGENT_CONFIG.get("tool_timeout", 30))
DEFAULT_MAX_RETRIES = 2
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_EXPONENTIAL_BASE = 2.0

# 瞬时错误:重试;其他错误(如 ValidationError)直接放弃
# 用异常类名做模糊匹配,避免引入各种 SDK 的具体异常类型
_TRANSIENT_ERROR_KEYWORDS = ("timeout", "timed out", "connection", "network",
                              "429", "rate limit", "temporary", "unavailable")


def _is_transient(error: Exception) -> bool:
    """判断是否瞬时错误(可重试)。"""
    msg = str(error).lower()
    name = type(error).__name__.lower()
    return any(kw in msg or kw in name for kw in _TRANSIENT_ERROR_KEYWORDS)


# source_ids 候选字段名(按优先级)
_SOURCE_ID_FIELDS = ("event_id", "source_id", "_id", "_source.id", "id")


def _extract_source_ids(data: Any) -> list[str]:
    """从工具返回值里扫描常见 ID 字段,生成 source_id 列表。

    递归扫描 dict / list,匹配 _SOURCE_ID_FIELDS 字段名(命中即收集)。
    截断到前 50 条避免日志膨胀。
    """
    ids: list[str] = []

    def _scan(node: Any, depth: int = 0) -> None:
        if depth > 8 or len(ids) >= 50:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _SOURCE_ID_FIELDS and isinstance(v, (str, int)):
                    ids.append(str(v))
                    if len(ids) >= 50:
                        return
                else:
                    _scan(v, depth + 1)
        elif isinstance(node, list):
            for item in node:
                _scan(item, depth + 1)
                if len(ids) >= 50:
                    return

    _scan(data)
    return ids


async def _run_with_spec(
    inner: BaseTool,
    args: dict,
    *,
    timeout_s: float,
    max_retries: int,
    initial_delay: float,
    exponential_base: float,
    caller: Optional[str],
) -> str:
    """执行单次工具调用,套用 timeout/retry/audit/ToolResult 归一化。

    返回 ToolResult.model_dump_json(),供 ToolMessage.content 用。
    """
    audit = ToolAuditRecord(
        ts=time.time(),
        tool_name=inner.name,
        args=args,
        ok=False,
        duration_ms=0.0,
        caller=caller,
    )
    start = time.perf_counter()
    last_error: Optional[Exception] = None
    retry_count = 0

    for attempt in range(max_retries + 1):
        try:
            async with asyncio.timeout(timeout_s):
                raw = await inner.ainvoke(args)
            # 成功:归一化为 ToolResult
            if isinstance(raw, ToolResult):
                result = raw
            elif isinstance(raw, dict) and "ok" in raw and isinstance(raw.get("ok"), bool):
                # 兼容已经是 ToolResult dict 的情况
                result = ToolResult(**raw)
            else:
                result = tool_ok(
                    raw,
                    source_ids=_extract_source_ids(raw),
                )
            audit.ok = True
            audit.source_ids = result.source_ids
            audit.data_summary = _truncate_for_log(raw)
            audit.retry_count = retry_count
            break  # 成功跳出循环
        except asyncio.TimeoutError:
            retry_count = attempt
            last_error = TimeoutError(f"tool '{inner.name}' timeout after {timeout_s}s")
            logger.warning(
                "[tool.spec] %s timeout,attempt %d/%d",
                inner.name, attempt + 1, max_retries + 1,
            )
            if attempt < max_retries:
                await asyncio.sleep(initial_delay * (exponential_base ** attempt))
                continue
        except Exception as e:
            retry_count = attempt
            last_error = e
            transient = _is_transient(e)
            logger.warning(
                "[tool.spec] %s 调用异常:%s: %s (transient=%s, attempt %d/%d)",
                inner.name, type(e).__name__, e, transient, attempt + 1, max_retries + 1,
            )
            if transient and attempt < max_retries:
                await asyncio.sleep(initial_delay * (exponential_base ** attempt))
                continue
            # 非瞬时错误直接放弃
            break

    # 构造最终结果(成功已 break;失败在循环外构造)
    if audit.ok:
        result_final: ToolResult = result  # type: ignore[possibly-undefined]
    else:
        if isinstance(last_error, TimeoutError):
            error_type = ToolErrorType.TIMEOUT
            error_msg = f"timeout after {timeout_s}s"
        elif _is_transient(last_error):  # type: ignore[arg-type]
            error_type = ToolErrorType.RETRY_EXHAUSTED
            error_msg = f"retry exhausted: {type(last_error).__name__}: {last_error}"  # type: ignore[arg-type]
        else:
            error_type = ToolErrorType.EXECUTION_ERROR
            error_msg = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown error"  # type: ignore[arg-type]
        result_final = tool_fail(
            error=error_msg, error_type=error_type,
        )
        audit.error = error_msg
        audit.error_type = error_type.value

    audit.duration_ms = (time.perf_counter() - start) * 1000
    # 让 ToolResult 也带 duration_ms(供 LLM/观察者看)
    result_final.duration_ms = audit.duration_ms
    get_tool_audit_recorder().record(audit)
    return result_final.to_json()


def wrap_tool_with_spec(
    inner: BaseTool,
    *,
    timeout_s: float = DEFAULT_TOOL_TIMEOUT_S,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    caller: Optional[str] = None,
) -> BaseTool:
    """把一个 BaseTool 包装成带 spec(timeout/retry/audit/ToolResult)的 BaseTool。

    保留原工具的 name / description / args_schema,
    bind_tools / ToolNode 无感知。
    """
    tool_name = inner.name
    tool_description = inner.description or ""
    args_schema = getattr(inner, "args_schema", None)

    async def _wrapped_coroutine(**kwargs):
        return await _run_with_spec(
            inner, kwargs,
            timeout_s=timeout_s,
            max_retries=max_retries,
            initial_delay=initial_delay,
            exponential_base=exponential_base,
            caller=caller,
        )

    # 同步回退(ToolNode 在非 async 上下文会调 _run)
    def _wrapped_sync(**kwargs):
        import asyncio as _asyncio
        try:
            loop = _asyncio.get_event_loop()
            if loop.is_running():
                # 已在 loop 中:用 ensure_future 排队(罕见路径)
                # ToolNode 通常走 ainvoke 路径,这里兜底
                raise RuntimeError("sync call inside running loop")
        except RuntimeError:
            # 无运行 loop,新建
            return _asyncio.run(_wrapped_coroutine(**kwargs))
        return _asyncio.run(_wrapped_coroutine(**kwargs))

    return StructuredTool(
        name=tool_name,
        description=tool_description,
        args_schema=args_schema,
        func=_wrapped_sync,
        coroutine=_wrapped_coroutine,
    )


def wrap_mcp_tools(
    tools: list[BaseTool],
    *,
    timeout_s: float = DEFAULT_TOOL_TIMEOUT_S,
    max_retries: int = DEFAULT_MAX_RETRIES,
    caller: Optional[str] = None,
) -> list[BaseTool]:
    """批量包装 MCP 工具列表。"""
    return [
        wrap_tool_with_spec(
            t,
            timeout_s=timeout_s,
            max_retries=max_retries,
            caller=caller,
        )
        for t in tools
    ]
