"""analysis_workflow 的 LangGraph 组装:线性工作流。

v1: START → analyze → END
v2: START → retrieve → analyze → END(仅需取消注释 + 改边)
"""
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .nodes import analyze_node
from .state import LogAnalysisState


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(LogAnalysisState)

    # v1:仅 analyze 节点
    graph.add_node("analyze", analyze_node)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", END)

    # ---- v2 扩展点(本阶段不启用)----
    # from .nodes import retrieve_node
    # graph.add_node("retrieve", retrieve_node)
    # graph.set_entry_point("retrieve")
    # graph.add_edge("retrieve", "analyze")

    # v1 无 checkpointer:无状态单次执行
    return graph.compile()
