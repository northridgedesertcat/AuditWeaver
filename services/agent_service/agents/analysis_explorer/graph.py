"""Analysis Explorer Agent 的 LangGraph 组装。

采用 tool-calling ReAct 单层结构:agent_node → (有 tool_calls?) → tools_node → agent_node … → END。
max_tool_rounds 防止 LLM 反复调工具不结束。
"""
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from shared.memory import get_checkpointer
from .config.settings import MAX_TOOL_ROUNDS
from .nodes import agent_node, tools_node
from .state import AgentState


def _route_after_agent(state: dict) -> str:
    """有 tool_calls 且未超轮数 → tools;否则 END。"""
    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    has_tool_calls = bool(getattr(last, "tool_calls", None))
    # 已完成的工具调用轮数 = 历史 ToolMessage 数
    tool_rounds = sum(1 for m in messages if getattr(m, "type", None) == "tool")
    if has_tool_calls and tool_rounds < MAX_TOOL_ROUNDS:
        return "tools"
    return END


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _route_after_agent)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=get_checkpointer())
