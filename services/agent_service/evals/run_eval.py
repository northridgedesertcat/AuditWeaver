"""Agent 离线评估编排脚本(对齐设计 §3.8 Evaluation)。

功能:
- 加载 golden_set_agent.jsonl(30 条安全场景)
- 对每条 case 跑 Agent(upgraded 六节点 / baseline 二节点),收 final_state
- 用 evals/metrics.py 算 4 类指标(任务正确性 + 工具轨迹 + 决策质量 + 覆盖)
- 可选:--judge 调 llm_judge.py 对 final_report 打主观分
- 输出 results_{variant}.jsonl(每 case 一行)+ report_agent_eval.md(对比表)

不虚构测试结果:本脚本跑完后才有真实数字,report.md 的表格由跑出的数据填充。
单测不依赖此脚本(metrics.py 有独立单测);此脚本供手动评估 + 面试演示。

运行(项目根目录,需 LLM + ES + RAG 语料):
    python -m services.agent_service.evals.run_eval --variant both
    python -m services.agent_service.evals.run_eval --variant upgraded --limit 5
    python -m services.agent_service.evals.run_eval --variant both --judge
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evals.metrics import per_case_metrics, aggregate  # noqa: E402

GOLDEN_SET_PATH = Path(_HERE) / "golden_set_agent.jsonl"
REPORT_PATH = Path(_HERE) / "report_agent_eval.md"


def load_golden_set(path: Path | None = None) -> list[dict]:
    """加载 golden_set_agent.jsonl(每行一个 case)。"""
    p = path or GOLDEN_SET_PATH
    items: list[dict] = []
    with open(p, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("[run_eval] golden_set 第 %d 行解析失败: %s", line_no, e)
                continue
            if "id" not in item or "input" not in item:
                logger.warning("[run_eval] golden_set 第 %d 行缺 id/input,跳过", line_no)
                continue
            items.append(item)
    logger.info("[run_eval] 加载 golden set %d 条", len(items))
    return items


def build_baseline_graph():
    """构造 v1 baseline graph(二节点 agent⇄tools,无 plan/gate/decision/compact)。

    复用 analysis_explorer 的 agent_node / tools_node(同 LLM 同工具),
    仅去掉 plan/deterministic_gate/decision_llm/compact 四个升级节点,
    作为公平对比基线(对齐 §3.8 baseline vs upgraded)。
    不注册到 registry(避免污染 service),仅本脚本用。
    """
    from langgraph.graph import END, StateGraph

    from agents.react.analysis_explorer.nodes import agent_node, tools_node
    from agents.react.analysis_explorer.graph import _route_after_agent
    from agents.react.analysis_explorer.state import AgentState
    from shared.memory import get_checkpointer

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.set_entry_point("agent")
    g.add_conditional_edges(
        "agent", _route_after_agent, {"tools": "tools", END: END},
    )
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=get_checkpointer())


def get_graph(variant: str):
    """按 variant 取 graph:upgraded 走 registry;baseline 走 inline build。

    upgraded 需先 ``import agents`` 触发注册(agents/__init__.py 调 register_agent),
    否则 registry._REGISTRY 为空,get_agent 抛 ValueError。
    """
    if variant == "baseline":
        return build_baseline_graph()
    # upgraded:先触发 agent 注册(对齐 backend/main.py 的启动流程)
    import agents  # noqa: F401  触发 register_agent
    from registry import get_agent
    return get_agent("analysis_explorer")


async def run_one_case(graph, case: dict, variant: str) -> dict:
    """跑单个 case,返回 {case, final_state, metrics, elapsed_s, error}。

    thread_id 用 "eval:{variant}:{case_id}" 隔离(对齐 stream.py 命名空间)。
    不流式(ainvoke),收 final_state 的 messages/tool_history/decision_history/
    evidence_pack/final_report,灌入 metrics.per_case_metrics。
    """
    from langchain_core.messages import HumanMessage

    case_id = case.get("id", "unknown")
    ns_thread = f"analysis_explorer:eval:{variant}:{case_id}"
    config = {"configurable": {"thread_id": ns_thread}, "recursion_limit": 40}
    inputs = {"messages": [HumanMessage(content=case["input"])]}

    t0 = time.time()
    try:
        final_state = await graph.ainvoke(inputs, config=config)
        elapsed = time.time() - t0
    except Exception as e:
        elapsed = time.time() - t0
        logger.warning("[run_eval] %s case=%s 失败: %s: %s",
                       variant, case_id, type(e).__name__, e)
        return {
            "case_id": case_id, "variant": variant, "error": f"{type(e).__name__}: {e}",
            "elapsed_s": round(elapsed, 2),
        }

    metrics = per_case_metrics(final_state, case)
    # 附 final_report 摘要(便于人工 review,不进 metrics 计算)
    report = final_state.get("final_report") or ""
    return {
        "case_id": case_id,
        "variant": variant,
        "scenario": case.get("scenario", ""),
        "difficulty": case.get("difficulty", ""),
        "elapsed_s": round(elapsed, 2),
        "metrics": metrics,
        "final_report_preview": report[:300],
        "tool_count": len(final_state.get("tool_history") or []),
        "decision_count": len(final_state.get("decision_history") or []),
    }


async def run_variant(graph, cases: list[dict], variant: str, judge: bool) -> list[dict]:
    """跑一个 variant 的全量 case,返回结果 list。"""
    results: list[dict] = []
    for i, case in enumerate(cases, 1):
        logger.info("[run_eval] %s [%d/%d] case=%s ...", variant, i, len(cases), case["id"])
        r = await run_one_case(graph, case, variant)
        # 可选 LLM Judge(仅对有 final_report 的成功 case)
        if judge and r.get("metrics") and r["final_report_preview"]:
            try:
                from evals.llm_judge import judge_report
                r["llm_judge"] = await judge_report(
                    case["input"], r["final_report_preview"], case.get("rubric", ""),
                )
            except Exception as e:
                logger.warning("[run_eval] llm_judge 失败 case=%s: %s", case["id"], e)
                r["llm_judge"] = {"score": None, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
    return results


def write_results_jsonl(results: list[dict], variant: str) -> Path:
    """写 results_{variant}.jsonl(每 case 一行)。"""
    p = Path(_HERE) / f"results_{variant}.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    logger.info("[run_eval] %s 结果写入 %s(%d 条)", variant, p, len(results))
    return p


def format_report(
    upgraded_results: list[dict] | None,
    baseline_results: list[dict] | None,
    judge_used: bool,
) -> str:
    """生成 report_agent_eval.md(baseline vs upgraded 对比表)。

    数字来自跑出的 results(不虚构);未跑的 variant 列填 "未跑"。
    """
    def _agg(results):
        if not results:
            return None
        per_case = [r["metrics"] for r in results if r.get("metrics")]
        return aggregate(per_case) if per_case else None

    up = _agg(upgraded_results)
    base = _agg(baseline_results)

    def _cell(v, fmt=".4f", missing="未跑"):
        if v is None:
            return missing
        return f"{v:{fmt}}"

    lines = [
        "# Agent Evaluation 报告",
        "",
        f"生成时间: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"LLM Judge: {'启用' if judge_used else '未启用'}",
        f"Golden Set: {len(upgraded_results or baseline_results or [])} 条",
        "",
        "## baseline vs upgraded 对比(均值)",
        "",
        "| 指标 | baseline(v1 二节点) | upgraded(v2.1 六节点) |",
        "|---|---|---|",
        f"| case 数 | {_cell(base and base['count'], fmt='d')} | {_cell(up and up['count'], fmt='d')} |",
        f"| 任务正确性(correctness) | {_cell(base and base['correctness_avg'])} | {_cell(up and up['correctness_avg'])} |",
        f"| 证据覆盖(evidence_coverage) | {_cell(base and base['evidence_coverage_avg'])} | {_cell(up and up['evidence_coverage_avg'])} |",
        f"| 工具召回(tool_recall) | {_cell(base and base['tool_recall_avg'])} | {_cell(up and up['tool_recall_avg'])} |",
        f"| 无效调用(wasted_calls) | {_cell(base and base['wasted_calls_avg'], fmt='.2f')} | {_cell(up and up['wasted_calls_avg'], fmt='.2f')} |",
        f"| 完成轮数(steps_to_finish) | {_cell(base and base['steps_to_finish_avg'], fmt='.2f')} | {_cell(up and up['steps_to_finish_avg'], fmt='.2f')} |",
        f"| finish 率 | {_cell(base and base['finish_rate'])} | {_cell(up and up['finish_rate'])} |",
        f"| 平均 replan 次数 | {_cell(base and base['replan_avg'], fmt='.2f')} | {_cell(up and up['replan_avg'], fmt='.2f')} |",
        f"| 平均 compact 次数 | {_cell(base and base['compact_avg'], fmt='.2f')} | {_cell(up and up['compact_avg'], fmt='.2f')} |",
        "",
        "## 指标说明(对齐 §3.8)",
        "- correctness: final_report 命中 expected_keys 的比例(任务结果正确性)",
        "- evidence_coverage: evidence_pack.source_ids 命中 expected_source_ids 的比例",
        "- tool_recall: 实际调用工具覆盖 expected_tools 的比例(轨迹完整性)",
        "- wasted_calls: 失败或无新 source_ids 的工具调用数(越少越好)",
        "- steps_to_finish: 工具调用总轮数(越少越高效)",
        "- finish_rate: decision_llm 给出 finish 的 case 比例",
        "- replan/compact 平均次数: 决策质量(过多=计划不稳/上下文压力)",
        "",
        "## 解读指引",
        "- upgraded 应在 correctness / tool_recall / finish_rate 上不弱于 baseline",
        "- upgraded 的 wasted_calls / steps_to_finish 应更低(plan 指导 + 门控省调用)",
        "- 若 upgraded 的 compact_avg 高,说明上下文压力大(可调 MAX_COMPACT_COUNT)",
        "- 数字为空表示对应 variant 未跑;重新运行 `python -m services.agent_service.evals.run_eval --variant <variant>` 即可填充",
        "",
        "## 详细结果",
        "见同目录 `results_baseline.jsonl` / `results_upgraded.jsonl`(每 case 一行,含 metrics + final_report 预览)",
    ]
    return "\n".join(lines)


async def main_async(args) -> None:
    cases = load_golden_set()
    if args.limit:
        cases = cases[: args.limit]
        logger.info("[run_eval] --limit %d,仅跑前 %d 条", args.limit, len(cases))

    variants = ["baseline", "upgraded"] if args.variant == "both" else [args.variant]
    upgraded_results = None
    baseline_results = None
    for v in variants:
        graph = get_graph(v)
        results = await run_variant(graph, cases, v, judge=args.judge)
        write_results_jsonl(results, v)
        if v == "upgraded":
            upgraded_results = results
        else:
            baseline_results = results

    report = format_report(upgraded_results, baseline_results, judge_used=args.judge)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    logger.info("[run_eval] 报告写入 %s", REPORT_PATH)


def main():
    parser = argparse.ArgumentParser(description="Agent 离线评估(baseline vs upgraded)")
    parser.add_argument(
        "--variant", choices=["baseline", "upgraded", "both"], default="both",
        help="评估变体(both=对比;默认 both)",
    )
    parser.add_argument("--limit", type=int, default=0, help="仅跑前 N 条(0=全部)")
    parser.add_argument("--judge", action="store_true", help="启用 LLM Judge(主观质量打分)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    )
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
