"""SSE 流式封装 + 同步执行 helper。

把 LangGraph 的 astream_events / ainvoke 转成前端可逐 token 渲染的 SSE。
FastAPI 只做转发,不做业务判断。

v2.1 升级(对齐 §3.3 + §3.9):
- SSE 新事件:plan_generated / gate_evaluated / decision_made / compact_done,
  从 on_chain_end 的 metadata.langgraph_node + 节点 output 提取(对齐
  langgraph 0.2.x astream_events v2 契约)。契约只增不改(兼容现有前端)。
- Tracing:get_trace_callback() 启用时,挂到 graph config 的 callbacks,
  节点/LLM/工具调用落盘 logs/agent_trace.jsonl(对齐 §3.9 轻量 Tracing)。
"""
import json
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .trace import get_trace_callback


def sse_line(data: dict) -> str:
    """SSE 单行:data: {...}\\n\\n"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# Agent 升级后需要发 SSE 事件的节点(对齐 §3.3 "plan/decision/compact" + gate)
_NODE_SSE_NODES = {"plan", "deterministic_gate", "decision_llm", "compact"}


def _node_event_to_sse(node_name: str, output) -> dict | None:
    """从节点 on_chain_end 的 output 提取 Agent 升级后的新 SSE 事件。

    设计要点:
    - 用 metadata.langgraph_node 判定节点名(astream_events v2 契约,对齐
      langgraph 0.2.x);node_name 不在 _NODE_SSE_NODES 则返回 None(忽略)。
    - 节点 output 是节点返回的 state delta dict;按节点名提取关键字段
      组装 SSE 事件,字段精简(前端只展示思考过程,不传整 state)。
    - 返回 None 表示该 on_chain_end 不是目标节点事件(由调用方跳过)。

    纯函数,无副作用,便于单测(见 tests/test_api_stream.py)。
    """
    if node_name not in _NODE_SSE_NODES:
        return None
    if not isinstance(output, dict):
        output = {}
    if node_name == "plan":
        plan = output.get("current_plan") or {}
        return {
            "type": "plan_generated",
            "hypotheses": plan.get("hypotheses") or [],
            "steps": plan.get("steps") or [],
            "budget": output.get("budget"),
        }
    if node_name == "deterministic_gate":
        return {
            "type": "gate_evaluated",
            "triggered": bool(output.get("gate_triggered")),
            "reasons": output.get("gate_reasons") or [],
        }
    if node_name == "decision_llm":
        d = output.get("decision_result") or {}
        return {
            "type": "decision_made",
            "action": d.get("action"),
            "reason": d.get("reason"),
            "next_step": d.get("next_step"),
        }
    # compact
    return {
        "type": "compact_done",
        "compact_count": output.get("compact_count"),
        "summary_preview": (output.get("investigation_summary") or "")[-200:],
    }


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


def _build_config(ns_thread: str | None) -> dict:
    """构造 graph config:thread_id(会话隔离)+ trace callback(若启用)。

    - ns_thread 为 None 时单次无状态(不挂 thread_id)
    - trace callback 未启用(AE_TRACE_LOG 未设)时跳过,不传 callbacks
    """
    config: dict = {}
    if ns_thread:
        config["configurable"] = {"thread_id": ns_thread}
    cb = get_trace_callback()
    if cb is not None:
        config["callbacks"] = [cb]
    return config


async def stream_agent_chat(
    graph,
    agent_type: str,
    message: str,
    thread_id: str | None,
    history: list[dict] | None,
) -> AsyncIterator[str]:
    """流式跑 graph,逐 token / 工具 / 节点事件产出 SSE 行。

    v2.1 升级(对齐 §3.3):新增 plan_generated / gate_evaluated /
    decision_made / compact_done 事件,从 on_chain_end 的
    metadata.langgraph_node 提取(对齐 langgraph 0.2.x v2 契约)。
    """
    ns_thread = _namespaced_thread(agent_type, thread_id)
    config = _build_config(ns_thread)
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

            elif kind == "on_chain_end":
                # 节点名从 metadata.langgraph_node 取(astream_events v2 契约)
                metadata = event.get("metadata") or {}
                node_name = metadata.get("langgraph_node") or ""
                sse = _node_event_to_sse(node_name, data.get("output"))
                if sse:
                    yield sse_line(sse)
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
    config = _build_config(ns_thread)
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
