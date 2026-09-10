"""SSE 流式封装 + 同步执行 helper。

把 LangGraph 的 astream_events / ainvoke 转成前端可逐 token 渲染的 SSE。
FastAPI 只做转发,不做业务判断。
"""
import json
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def sse_line(data: dict) -> str:
    """SSE 单行:data: {...}\\n\\n"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_tool_content(content):
    """ToolMessage.content 可能是 str(JSON) / dict / list,统一成可读结构。"""
    if isinstance(content, (dict, list)):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception:
            return content
    return content


def _summarize_tool_output(output) -> str:
    """把工具返回压缩成一句话摘要给前端展示。"""
    data = _parse_tool_content(output)
    if isinstance(data, dict):
        if "total" in data:
            return f"{data.get('total')} 条记录"
        if "returned" in data:
            return f"{data.get('returned')} 条记录"
        for key in ("reports", "events", "logs"):
            if key in data:
                return f"{len(data.get(key) or [])} 条{ {'reports':'报告','events':'事件','logs':'日志'}.get(key,'记录') }"
        if "error" in data:
            return f"错误: {data.get('error')}"
    text = str(data)
    return text if len(text) <= 120 else text[:120] + "..."


def _build_inputs(message: str, history: list[dict] | None, thread_id: str | None) -> dict:
    """构造 graph 输入。

    - 有 thread_id:依赖 checkpointer 维护多轮历史,只追加本轮用户消息。
    - 无 thread_id:单次无状态,把 history 前置拼进去。
    """
    if thread_id:
        return {"messages": [HumanMessage(content=message)]}
    msgs = []
    for h in history or []:
        role = h.get("role")
        content = h.get("content", "")
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=message))
    return {"messages": msgs}


def _namespaced_thread(agent_type: str, thread_id: str | None) -> str | None:
    """每个 agent_type 独立命名空间,避免不同 Agent 的对话串。"""
    if not thread_id:
        return None
    return f"{agent_type}:{thread_id}"


async def stream_agent_chat(
    graph,
    agent_type: str,
    message: str,
    thread_id: str | None,
    history: list[dict] | None,
) -> AsyncIterator[str]:
    """流式跑 graph,逐 token / 工具事件产出 SSE 行。"""
    ns_thread = _namespaced_thread(agent_type, thread_id)
    config = {"configurable": {"thread_id": ns_thread}} if ns_thread else {}
    inputs = _build_inputs(message, history, thread_id)

    try:
        async for event in graph.astream_events(inputs, config=config, version="v2"):
            kind = event.get("event")
            data = event.get("data", {}) or {}

            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    yield sse_line({"type": "token", "content": content})

            elif kind == "on_tool_start":
                yield sse_line({
                    "type": "tool_call",
                    "tool": event.get("name"),
                    "args": data.get("input") or {},
                })

            elif kind == "on_tool_end":
                yield sse_line({
                    "type": "tool_result",
                    "tool": event.get("name"),
                    "summary": _summarize_tool_output(data.get("output")),
                })
    except Exception as e:
        yield sse_line({"type": "error", "content": f"agent stream error: {type(e).__name__}: {e}"})

    yield sse_line({"type": "done"})


async def run_agent_sync(
    graph,
    agent_type: str,
    message: str,
    thread_id: str | None,
    history: list[dict] | None,
) -> dict:
    """非流式:一次跑完,返回完整 answer + 工具调用清单。"""
    ns_thread = _namespaced_thread(agent_type, thread_id)
    config = {"configurable": {"thread_id": ns_thread}} if ns_thread else {}
    inputs = _build_inputs(message, history, thread_id)

    try:
        final_state = await graph.ainvoke(inputs, config=config)
    except Exception as e:
        return {
            "agent_type": agent_type,
            "answer": f"agent error: {e}",
            "tool_calls": [],
            "thread_id": thread_id,
        }

    messages = final_state.get("messages", [])

    answer = ""
    last_ai = None
    for m in messages:
        if isinstance(m, AIMessage):
            last_ai = m
    if last_ai is not None:
        answer = last_ai.content or ""

    tool_calls: list[dict] = []
    for m in messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                tool_calls.append({
                    "tool": tc.get("name"),
                    "args": tc.get("args") or {},
                    "summary": "",
                })
        elif isinstance(m, ToolMessage):
            for entry in reversed(tool_calls):
                if not entry["summary"]:
                    entry["summary"] = _summarize_tool_output(m.content)
                    break

    return {
        "agent_type": agent_type,
        "answer": answer,
        "tool_calls": tool_calls,
        "thread_id": thread_id,
    }
