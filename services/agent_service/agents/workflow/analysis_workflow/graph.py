"""analysis_workflow 的 LangGraph 组装:带质量门控的流水线(对齐 §3.1)。

v2.1 升级:从 v1 的 START → analyze → END 单节点,扩展为五节点流水线:

    START → retrieve ──→ analyze ──→ validate ──┬─(pass)─→ report ──→ END
                                  ▲              └─(fail)─→ enrich ──┘
                                  └── enrich_count ≤ MAX_ENRICH_COUNT,补检索词/扩时间窗

条件路由(deterministic_gate_after_validate):
- validate_result.pass == True → report
- validate_result.pass == False 且 enrich_count < MAX_ENRICH_COUNT → enrich(循环回 analyze)
- validate_result.pass == False 但 enrich_count >= MAX_ENRICH_COUNT → report(防死循环,降级出报告)

enrich 后回到 analyze(用合并后的 evidence_pack 重新分析)。

checkpointer:v1 不启用,无状态单次执行(向后兼容)。
v2.1 仍不强制启用 checkpointer,留作 §3.3 P0-8 API/Stream 升级时再加。
"""
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config.settings import MAX_ENRICH_COUNT
from .nodes import (
    analyze_node,
    enrich_node,
    report_node,
    retrieve_node,
    validate_node,
)
from .state import LogAnalysisState


def _route_after_validate(state: dict) -> str:
    """validate 之后的条件路由(纯代码,确定性)。

    Returns:
        "report" 或 "enrich"

    规则:
    1. validate_result 缺失/为空 → report(validate 异常,降级出报告,不进 enrich 死循环)
    2. pass=True → report(质量达标,出报告)
    3. pass=False 且 enrich_count < MAX_ENRICH_COUNT → enrich(补检索循环)
    4. pass=False 且 enrich_count >= MAX_ENRICH_COUNT → report(防死循环,降级)
    """
    validate_result = state.get("validate_result") or {}
    # validate_result 缺失表示 validate 节点异常,直接降级走 report
    if not validate_result:
        return "report"
    # 兼容 pass / pass_ 两种键(ValidateSchema 用 alias="pass")
    passed = validate_result.get("pass", validate_result.get("pass_", False))
    enrich_count = state.get("enrich_count", 0) or 0

    if passed:
        return "report"
    if enrich_count < MAX_ENRICH_COUNT:
        return "enrich"
    # 防死循环:enrich 次数已达上限,即使 validate FAIL 也强制走 report
    return "report"


def build_graph() -> CompiledStateGraph:
    """构建带质量门控的流水线 graph。

    节点顺序:retrieve → analyze → validate →(条件边)→ enrich ↺ / report → END
    enrich 后回到 analyze(用合并后的 evidence_pack 重新分析)。
    """
    graph = StateGraph(LogAnalysisState)

    # 注册五节点
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("validate", validate_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("report", report_node)

    # 入口:retrieve(纯代码调 RAG,不进 LLM)
    graph.set_entry_point("retrieve")

    # 线性边:retrieve → analyze → validate
    graph.add_edge("retrieve", "analyze")
    graph.add_edge("analyze", "validate")

    # 条件边:validate →(pass)→ report / (fail)→ enrich
    # enrich_count 达上限时强制走 report(防死循环)
    graph.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "report": "report",
            "enrich": "enrich",
        },
    )

    # enrich 后回到 analyze(用合并后的 evidence_pack 重新分析)
    graph.add_edge("enrich", "analyze")

    # report → END
    graph.add_edge("report", END)

    # v2.1 仍不启用 checkpointer(留作 P0-8 API/Stream 升级时再加)
    return graph.compile()
