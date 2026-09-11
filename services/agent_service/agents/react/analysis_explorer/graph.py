"""Analysis Explorer Agent 的 LangGraph 组装(对齐 §3.2 + §3.5)。

v2.1 升级:从 v1 的二节点(agent ⇄ tools)扩展为六节点:

    START → plan → agent ──→(有 tool_calls)→ tools → deterministic_gate ──→
                        │                                              │
                        │                                              ├─(未命中)→ agent
                        │                                              └─(命中)→ decision_llm
                        └─(无 tool_calls)→ END                                         │
                                                                   ┌────────────────┤
                                                                   │ continue → agent
                                                                   │ replan   → plan
                                                                   │ compact  → compact → agent
                                                                   │ finish   → END
                                                                   └─(未知)→ agent

设计要点:
- plan 是入口:先生成调查计划(Plan-and-Solve),给后续 ReAct 明确任务指导
- agent ⇄ tools:保留 v1 的 ReAct 内核(LLM 自主决定调工具还是直接回答)
- deterministic_gate:纯代码规则(零 LLM),命中触发条件才进 decision_llm
- decision_llm:light 模型四选一(continue/replan/compact/finish)
- compact:结构化上下文压缩,不重写 message history(对齐 §3.5)
- checkpointer:启用(对齐 v1,thread_id 持久化,供 P0-8 SSE 流式续接)

条件路由:
- _route_after_agent:有 tool_calls → tools / 无 → END(LLM 直接给结论)
- _route_after_gate:gate_triggered → decision_llm / 否则 → agent(省 LLM 调用)
- _route_after_decision:读 decision_result.action 路由到对应节点
"""
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from shared.memory import get_checkpointer
from .nodes import (
    agent_node,
    compact_node,
    decision_llm_node,
    deterministic_gate_node,
    plan_node,
    tools_node,
)
from .state import AgentState


def _route_after_agent(state: dict) -> str:
    """agent 之后的条件路由:有 tool_calls → tools / 无 → END。

    无 tool_calls 表示 LLM 已给出最终回答(无需再调工具),直接结束。
    有 tool_calls 表示 LLM 要调工具,进 tools 节点执行。
    """
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    has_tool_calls = bool(getattr(last, "tool_calls", None))
    return "tools" if has_tool_calls else END


def _route_after_gate(state: dict) -> str:
    """deterministic_gate 之后的条件路由(纯代码,确定性)。

    - gate_triggered=True → decision_llm(命中触发条件,需 LLM 语义判断)
    - gate_triggered=False → agent(未命中,继续 ReAct 循环,省一次 LLM 调用)
    """
    triggered = state.get("gate_triggered", False)
    return "decision_llm" if triggered else "agent"


def _route_after_decision(state: dict) -> str:
    """decision_llm 之后的条件路由(读 decision_result.action)。

    - continue → agent(继续当前调查路径)
    - replan → plan(重新规划,清空当前计划)
    - compact → compact(压缩上下文后回 agent)
    - finish → END(结束调查)
    - 未知 → agent(降级,防 LLM 输出错误动作卡死)
    """
    decision = state.get("decision_result") or {}
    action = str(decision.get("action", "continue")).lower().strip()
    if action == "continue":
        return "agent"
    if action == "replan":
        return "plan"
    if action == "compact":
        return "compact"
    if action == "finish":
        return END
    # 未知动作降级为 continue(防卡死)
    return "agent"


def build_graph() -> CompiledStateGraph:
    """构建六节点 Agent graph(对齐 §3.2)。

    节点顺序:plan → agent ⇄ tools → deterministic_gate →
              (未命中)→ agent / (命中)→ decision_llm →
              continue→agent / replan→plan / compact→compact→agent / finish→END

    compact 后回 agent(用新的 investigation_summary 继续 ReAct)。
    checkpointer 启用(thread_id 持久化,供 P0-8 SSE 流式续接)。
    """
    graph = StateGraph(AgentState)

    # 注册六节点
    graph.add_node("plan", plan_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("deterministic_gate", deterministic_gate_node)
    graph.add_node("decision_llm", decision_llm_node)
    graph.add_node("compact", compact_node)

    # 入口:plan(先生成调查计划)
    graph.set_entry_point("plan")

    # 线性边:plan → agent
    graph.add_edge("plan", "agent")

    # 条件边:agent →(有 tool_calls)→ tools / (无)→ END
    graph.add_conditional_edges(
        "agent", _route_after_agent,
        {"tools": "tools", END: END},
    )

    # 线性边:tools → deterministic_gate(每轮工具调用后必走门控)
    graph.add_edge("tools", "deterministic_gate")

    # 条件边:deterministic_gate →(命中)→ decision_llm / (未命中)→ agent
    graph.add_conditional_edges(
        "deterministic_gate", _route_after_gate,
        {"decision_llm": "decision_llm", "agent": "agent"},
    )

    # 条件边:decision_llm → continue→agent / replan→plan / compact→compact / finish→END
    graph.add_conditional_edges(
        "decision_llm", _route_after_decision,
        {
            "agent": "agent",
            "plan": "plan",
            "compact": "compact",
            END: END,
        },
    )

    # 线性边:compact → agent(压缩后回 agent,用新 summary 继续)
    graph.add_edge("compact", "agent")

    # 启用 checkpointer(thread_id 持久化,对齐 v1,供 P0-8 SSE 续接)
    return graph.compile(checkpointer=get_checkpointer())
