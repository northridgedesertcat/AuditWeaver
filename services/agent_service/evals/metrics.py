"""Agent Evaluation 指标计算(纯函数,对齐 §3.8)。

设计要点:
- 所有函数都是纯函数(dict/list in → number/dict out),不依赖 LLM / ES / graph,
  便于单测(tests/test_eval_metrics.py),对齐项目"测试不依赖外部服务"原则。
- 输入是 Agent 跑完的 final_state(dict,对齐 AgentState.model_dump 风格)
  + golden case(dict,对齐 golden_set_agent.jsonl 一行)。
- 4 类指标(对齐 §3.8):
  ① 任务结果正确性:correctness(final_report 命中 expected_keys)
  ② 工具调用轨迹:tool_recall(命中 expected_tools)+ wasted_calls(无效调用)
     + steps_to_finish(总轮数,越少越高效)
  ③ LLM Judge:主观质量(由 llm_judge.py 单独算,不在此处)
  ④ baseline vs upgraded:由 run_eval 跑两遍后用 aggregate 对比(此处提供 aggregate)

不虚构测试结果:本模块只算指标,具体数字由 run_eval 跑完后填入 report.md。
"""
from __future__ import annotations

from typing import Any


def correctness(final_report: str, expected_keys: list[str]) -> float:
    """任务结果正确性:final_report 命中 expected_keys 的比例(大小写不敏感)。

    - final_report 为空或 expected_keys 为空 → 0.0(无约束视为未达成,保守)
    - 命中判定:expected_key 作为子串(小写)出现在 final_report(小写)中
    - 返回 [0, 1],1.0=全部命中
    """
    if not final_report or not expected_keys:
        return 0.0
    report_lower = final_report.lower()
    hit = sum(1 for k in expected_keys if k and k.lower() in report_lower)
    return hit / len(expected_keys)


def evidence_coverage(evidence_pack: dict | None, expected_source_ids: list[str]) -> float:
    """证据覆盖:evidence_pack.source_ids 命中 expected_source_ids 的比例。

    - expected_source_ids 为空 → 1.0(无约束,视为满分覆盖)
    - evidence_pack 为空 → 0.0(有约束但无证据)
    - 命中判定:expected_sid 在 evidence_pack 的 evidences[].source_id 集合中
    """
    if not expected_source_ids:
        return 1.0
    if not isinstance(evidence_pack, dict):
        return 0.0
    evidences = evidence_pack.get("evidences") or []
    collected_ids = {ev.get("source_id") for ev in evidences if isinstance(ev, dict)}
    collected_ids.discard(None)
    collected_ids.discard("")
    if not collected_ids:
        return 0.0
    hit = len(collected_ids & set(expected_source_ids))
    return hit / len(set(expected_source_ids))


def tool_recall(tool_history: list[dict] | None, expected_tools: list[str]) -> float:
    """工具调用轨迹 - 召回:实际调用工具覆盖 expected_tools 的比例。

    - expected_tools 为空 → 1.0(无约束)
    - tool_history 为空但 expected_tools 非空 → 0.0
    - 命中判定:tool_history[].tool_name 与 expected_tools 取交集
    - 返回 [0, 1],1.0=该调的都调了
    """
    if not expected_tools:
        return 1.0
    if not tool_history:
        return 0.0
    called = {h.get("tool_name") for h in tool_history if isinstance(h, dict)}
    called.discard(None)
    called.discard("")
    if not called:
        return 0.0
    hit = len(called & set(expected_tools))
    return hit / len(set(expected_tools))


def wasted_calls(tool_history: list[dict] | None) -> int:
    """工具调用轨迹 - 无效调用数:失败或无新 source_ids 产出的轮次。

    判定(任一即计为无效):
    - ok == False(工具报错)
    - source_ids 为空(调了但没拿到新证据,可能是参数不对或无数据)

    返回整数(越少越好)。无效调用反映 Agent 是否在"空转"。
    """
    if not tool_history:
        return 0
    count = 0
    for h in tool_history:
        if not isinstance(h, dict):
            continue
        if not h.get("ok", True):
            count += 1
            continue
        if not h.get("source_ids"):
            count += 1
    return count


def steps_to_finish(tool_history: list[dict] | None, decision_history: list[dict] | None) -> int:
    """工具调用轨迹 - 完成总轮数:tool_history 长度(决策轮不计入,只计实际工具调用)。

    越少越高效(对齐 §3.8 "trajectory 指标"中 steps_to_finish)。
    decision_history 不计入(决策本身不产生证据,只是反思)。
    """
    return len(tool_history or [])


def decision_quality(decision_history: list[dict] | None, finish_reason: str = "") -> dict:
    """决策质量(启发式,非 LLM Judge):统计 decision_llm 的动作分布。

    返回:
    - finished: 是否最终 finish(有 finish action 或 finish_reason 非空)
    - replan_count: replan 次数(过多=计划不稳)
    - compact_count: compact 次数(过多=上下文压力)
    - continue_count: continue 次数(正常推进)
    - has_finish_reason: finish_reason 是否非空(可追溯)
    """
    dh = decision_history or []
    replan = sum(1 for d in dh if isinstance(d, dict) and str(d.get("action", "")).lower() == "replan")
    compact = sum(1 for d in dh if isinstance(d, dict) and str(d.get("action", "")).lower() == "compact")
    cont = sum(1 for d in dh if isinstance(d, dict) and str(d.get("action", "")).lower() == "continue")
    finished = any(
        isinstance(d, dict) and str(d.get("action", "")).lower() == "finish"
        for d in dh
    ) or bool(finish_reason)
    return {
        "finished": finished,
        "replan_count": replan,
        "compact_count": compact,
        "continue_count": cont,
        "has_finish_reason": bool(finish_reason),
    }


def per_case_metrics(final_state: dict, case: dict) -> dict:
    """单 case 全量指标:把 final_state + case 灌入上面各纯函数,聚合返回。

    final_state 是 graph.ainvoke 的返回(dict,对齐 AgentState 字段)。
    case 是 golden_set_agent.jsonl 一行(dict)。
    返回 {case_id, scenario, difficulty, correctness, evidence_coverage,
          tool_recall, wasted_calls, steps_to_finish, decision_quality}
    """
    report = final_state.get("final_report") or ""
    # final_report 可能空(Agent 未显式写);兜底用 messages 最后一条 AIMessage.content
    if not report:
        messages = final_state.get("messages") or []
        for m in reversed(messages):
            content = getattr(m, "content", None)
            if getattr(m, "type", None) == "ai" and content:
                report = content if isinstance(content, str) else str(content)
                break
    return {
        "case_id": case.get("id", ""),
        "scenario": case.get("scenario", ""),
        "difficulty": case.get("difficulty", ""),
        "correctness": correctness(report, case.get("expected_keys") or []),
        "evidence_coverage": evidence_coverage(
            final_state.get("evidence_pack"), case.get("expected_source_ids") or [],
        ),
        "tool_recall": tool_recall(
            final_state.get("tool_history"), case.get("expected_tools") or [],
        ),
        "wasted_calls": wasted_calls(final_state.get("tool_history")),
        "steps_to_finish": steps_to_finish(
            final_state.get("tool_history"), final_state.get("decision_history"),
        ),
        "decision_quality": decision_quality(
            final_state.get("decision_history"), final_state.get("finish_reason") or "",
        ),
    }


def aggregate(per_case: list[dict]) -> dict:
    """跨 case 聚合(对齐 baseline vs upgraded 对比):各指标取均值。

    输入 per_case_metrics 返回的 list,输出:
    {count, correctness_avg, evidence_coverage_avg, tool_recall_avg,
     wasted_calls_avg, steps_to_finish_avg, finish_rate, replan_avg, compact_avg}

    finish_rate: finished=True 的 case 比例(对齐 §3.8 "任务结果正确性"维度)。
    """
    n = len(per_case) or 1
    finished = sum(1 for c in per_case if c.get("decision_quality", {}).get("finished"))
    replan_total = sum(c.get("decision_quality", {}).get("replan_count", 0) for c in per_case)
    compact_total = sum(c.get("decision_quality", {}).get("compact_count", 0) for c in per_case)
    return {
        "count": len(per_case),
        "correctness_avg": sum(c.get("correctness", 0) for c in per_case) / n,
        "evidence_coverage_avg": sum(c.get("evidence_coverage", 0) for c in per_case) / n,
        "tool_recall_avg": sum(c.get("tool_recall", 0) for c in per_case) / n,
        "wasted_calls_avg": sum(c.get("wasted_calls", 0) for c in per_case) / n,
        "steps_to_finish_avg": sum(c.get("steps_to_finish", 0) for c in per_case) / n,
        "finish_rate": finished / n,
        "replan_avg": replan_total / n,
        "compact_avg": compact_total / n,
    }
