"""analysis_explorer Agent v2.1 六节点测试(对齐 §3.2 + §3.5)。

覆盖目标:
- 图编译成 CompiledStateGraph
- 六节点齐全(plan / agent / tools / deterministic_gate / decision_llm / compact)
- 入口是 plan
- _route_after_agent:有 tool_calls → tools / 无 → END
- _route_after_gate:triggered → decision_llm / 否则 → agent
- _route_after_decision:continue→agent / replan→plan / compact→compact / finish→END / 未知→agent
- _evaluate_gate_conditions 七条触发条件每条单独测 + 正常状态未命中
- plan_node:mock LLM 返回 PlanSchema,验证写 current_plan + budget + tool_rounds=0
- compact_node:mock LLM 验证追加 investigation_summary + compact_count+1 / 达上限降级
- 端到端路由:plan→agent→tools→gate(未命中)→agent→tools→gate(命中)→decision(finish)→END

注:全测试不依赖真实 LLM / ES,通过 mock 节点函数 / LLM 调用,
只测「图结构 + 路由 + state 读写 + 门控规则」逻辑(对齐 §3.2 设计的确定性部分)。

运行(项目根目录):
    $env:AE_MEMORY_BACKEND='memory'
    python -m unittest services.agent_service.tests.test_agent_explorer -v
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# 触发 agents 包注册 analysis_explorer
import agents  # noqa: F401
from agents.react.analysis_explorer.graph import (
    _route_after_agent,
    _route_after_decision,
    _route_after_gate,
    build_graph,
)
from agents.react.analysis_explorer.config.settings import MAX_COMPACT_COUNT
from agents.react.analysis_explorer.nodes import (
    _evaluate_gate_conditions,
    compact_node,
    plan_node,
)
from agents.react.analysis_explorer.schema import (
    CompactSummarySchema,
    DecisionSchema,
    PlanSchema,
)
from agents.react.analysis_explorer.state import AgentState
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph


class TestGraphStructure(unittest.TestCase):
    """图结构测试:编译 + 六节点齐全 + 入口正确。"""

    def test_build_graph_returns_compiled(self):
        """build_graph 编译返回 CompiledStateGraph 实例。"""
        graph = build_graph()
        self.assertIsInstance(graph, CompiledStateGraph)

    def test_graph_has_six_nodes(self):
        """图含 plan / agent / tools / deterministic_gate / decision_llm / compact 六节点。"""
        graph = build_graph()
        node_names = set(graph.get_graph().nodes.keys())
        for expected in (
            "plan", "agent", "tools",
            "deterministic_gate", "decision_llm", "compact",
        ):
            self.assertIn(
                expected, node_names,
                f"图缺少节点 {expected},现有节点:{node_names}",
            )

    def test_entry_point_is_plan(self):
        """入口节点应为 plan(先生成调查计划)。"""
        graph = build_graph()
        graph_data = graph.get_graph()
        start_edges = [
            e for e in graph_data.edges
            if getattr(e, "source", "") == "__start__"
        ]
        self.assertTrue(
            len(start_edges) >= 1,
            f"应至少有一条 __start__ 出边,实际:{graph_data.edges}",
        )
        self.assertEqual(start_edges[0].target, "plan")


class TestRouteAfterAgent(unittest.TestCase):
    """agent 之后的条件路由测试。"""

    def test_with_tool_calls_routes_to_tools(self):
        """agent 输出含 tool_calls → 路由到 tools。"""
        msg = AIMessage(content="", tool_calls=[{"name": "QueryIPLogs",
                                                  "args": {"ip": "1.1.1.1"},
                                                  "id": "call_1"}])
        state = {"messages": [msg]}
        self.assertEqual(_route_after_agent(state), "tools")

    def test_without_tool_calls_routes_to_end(self):
        """agent 输出无 tool_calls(直接给结论)→ 路由到 END。"""
        msg = AIMessage(content="调查完成,该 IP 无异常。")
        state = {"messages": [msg]}
        self.assertEqual(_route_after_agent(state), END)


class TestRouteAfterGate(unittest.TestCase):
    """deterministic_gate 之后的条件路由测试。"""

    def test_triggered_routes_to_decision(self):
        """gate_triggered=True → 路由到 decision_llm。"""
        state = {"gate_triggered": True, "gate_reasons": ["证据不足"]}
        self.assertEqual(_route_after_gate(state), "decision_llm")

    def test_not_triggered_routes_to_agent(self):
        """gate_triggered=False → 路由到 agent(省一次 LLM 调用)。"""
        state = {"gate_triggered": False, "gate_reasons": []}
        self.assertEqual(_route_after_gate(state), "agent")


class TestRouteAfterDecision(unittest.TestCase):
    """decision_llm 之后的条件路由测试(读 decision_result.action)。"""

    def test_continue_routes_to_agent(self):
        state = {"decision_result": {"action": "continue", "reason": "go on"}}
        self.assertEqual(_route_after_decision(state), "agent")

    def test_replan_routes_to_plan(self):
        state = {"decision_result": {"action": "replan", "reason": "wrong dir"}}
        self.assertEqual(_route_after_decision(state), "plan")

    def test_compact_routes_to_compact(self):
        state = {"decision_result": {"action": "compact", "reason": "ctx long"}}
        self.assertEqual(_route_after_decision(state), "compact")

    def test_finish_routes_to_end(self):
        state = {"decision_result": {"action": "finish", "reason": "done"}}
        self.assertEqual(_route_after_decision(state), END)

    def test_unknown_action_defaults_to_agent(self):
        """未知 action 降级为 continue→agent(防 LLM 输出错误动作卡死)。"""
        state = {"decision_result": {"action": "abort", "reason": "x"}}
        self.assertEqual(_route_after_decision(state), "agent")


class TestEvaluateGateConditions(unittest.TestCase):
    """deterministic_gate 七条触发条件测试(纯函数,每条单独测)。"""

    def test_tool_failure_triggers(self):
        """条件 1:最近一轮工具失败。"""
        state = {
            "tool_history": [{"ok": True, "args_summary": "ip=1.1.1.1"},
                             {"ok": False, "args_summary": "ip=2.2.2.2",
                              "source_ids": []}],
            "evidence_pack": {"evidences": []},
            "current_plan": {},
            "budget": 5, "tool_rounds": 1, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("失败" in r for r in reasons))

    def test_consecutive_failure_triggers(self):
        """条件 1:连续失败达 CONSECUTIVE_FAILURE_THRESHOLD。"""
        state = {
            "tool_history": [
                {"ok": False, "args_summary": "a", "source_ids": []},
                {"ok": False, "args_summary": "b", "source_ids": []},
            ],
            "evidence_pack": {"evidences": []},
            "current_plan": {},
            "budget": 5, "tool_rounds": 2, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("连续" in r for r in reasons))

    def test_insufficient_evidence_triggers(self):
        """条件 2:证据不足(evidences 条数 < expected_evidence 下限)。"""
        state = {
            "tool_history": [],
            "evidence_pack": {"evidences": []},
            "current_plan": {"expected_evidence": ["IP 访问记录", "攻击类型"]},
            "budget": 5, "tool_rounds": 0, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("证据不足" in r for r in reasons))

    def test_evidence_conflict_triggers(self):
        """条件 3:证据冲突(多个 risk_level)。"""
        state = {
            "tool_history": [{"ok": True, "args_summary": "a",
                              "source_ids": ["e1"]}],
            "evidence_pack": {"evidences": [
                {"content": "ev1", "source_id": "e1", "raw": {"risk_level": "High"}},
                {"content": "ev2", "source_id": "e2", "raw": {"risk_level": "Low"}},
            ]},
            "current_plan": {"hypotheses": ["h1"]},
            "budget": 5, "tool_rounds": 1, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("冲突" in r for r in reasons))

    def test_budget临界_triggers(self):
        """条件 4:预算临界(剩余轮数 ≤ budget×20%)。"""
        # budget=5, tool_rounds=5, remaining=0 ≤ max(1, int(5*0.2))=1
        state = {
            "tool_history": [{"ok": True, "args_summary": "a",
                              "source_ids": ["e1"]}],
            "evidence_pack": {"evidences": [
                {"content": "ev1", "source_id": "e1", "raw": {}}]},
            "current_plan": {"hypotheses": ["h1", "h2"]},
            "budget": 5, "tool_rounds": 5, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("预算" in r for r in reasons))

    def test_duplicate_rounds_triggers(self):
        """条件 5:重复调用(最近 DUPLICATE_ROUNDS_THRESHOLD 轮 args 相同)。"""
        state = {
            "tool_history": [
                {"ok": True, "args_summary": "ip=1.1.1.1", "source_ids": ["e1"]},
                {"ok": True, "args_summary": "ip=1.1.1.1", "source_ids": ["e2"]},
            ],
            "evidence_pack": {"evidences": [
                {"content": "ev1", "source_id": "e1", "raw": {}}]},
            "current_plan": {"hypotheses": ["h1"]},
            "budget": 5, "tool_rounds": 2, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("重复" in r for r in reasons))

    def test_likely_complete_triggers(self):
        """条件 6:可能完成(evidences 条数 ≥ hypotheses 条数)。"""
        state = {
            "tool_history": [{"ok": True, "args_summary": "a",
                              "source_ids": ["e1", "e2"]}],
            "evidence_pack": {"evidences": [
                {"content": "ev1", "source_id": "e1", "raw": {}},
                {"content": "ev2", "source_id": "e2", "raw": {}}]},
            "current_plan": {"hypotheses": ["h1", "h2"]},
            "budget": 5, "tool_rounds": 2, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertTrue(triggered)
        self.assertTrue(any("完成" in r for r in reasons))

    def test_normal_state_not_triggered(self):
        """正常状态(证据充足、无失败、预算充足)不触发门控。"""
        state = {
            "tool_history": [{"ok": True, "args_summary": "ip=1.1.1.1",
                              "source_ids": ["e1", "e2"]}],
            "evidence_pack": {"evidences": [
                {"content": "ev1", "source_id": "e1", "raw": {"risk_level": "High"}},
                {"content": "ev2", "source_id": "e2", "raw": {"risk_level": "High"}}]},
            "current_plan": {"hypotheses": ["h1", "h2", "h3"],
                             "expected_evidence": ["访问记录"]},
            "budget": 10, "tool_rounds": 1, "total_tokens_used": 0,
        }
        triggered, reasons = _evaluate_gate_conditions(state)
        self.assertFalse(triggered, f"正常状态不应触发,reasons={reasons}")


class TestPlanNode(unittest.TestCase):
    """plan 节点测试:mock LLM 返回 PlanSchema,验证 state 写入。"""

    def test_plan_node_writes_plan_and_resets_rounds(self):
        """plan_node 写 current_plan + budget + tool_rounds=0。"""
        from agents.react.analysis_explorer import nodes as ag_nodes

        mock_plan = PlanSchema(
            hypotheses=["IP 1.1.1.1 在扫描"],
            steps=["查 1.1.1.1 的日志"],
            expected_evidence=["访问记录"],
            budget=5,
        )
        state = {
            "messages": [HumanMessage(content="1.1.1.1 在干什么?")],
            "tool_rounds": 3,  # 之前有调用,replan 后应重置
        }
        with patch.object(ag_nodes, "_ensure_plan_llm", new=AsyncMock()), \
             patch.object(
                 ag_nodes, "invoke_structured_with_retry",
                 new=AsyncMock(return_value=mock_plan),
             ):
            result = asyncio.run(plan_node(state))

        self.assertIn("current_plan", result)
        self.assertEqual(
            result["current_plan"]["hypotheses"], ["IP 1.1.1.1 在扫描"]
        )
        self.assertEqual(result["budget"], 5)
        self.assertEqual(result["tool_rounds"], 0, "replan 后 tool_rounds 应重置")


class TestCompactNode(unittest.TestCase):
    """compact 节点测试。"""

    def _make_messages(self, n: int):
        """构造 n 条消息(供 compact 压缩)。"""
        return [AIMessage(content=f"msg {i}") for i in range(n)]

    def test_compact_appends_summary_and_increments_count(self):
        """compact 追加 investigation_summary + compact_count+1。"""
        from agents.react.analysis_explorer import nodes as ag_nodes

        mock_compact = CompactSummarySchema(
            summary="已查 IP 1.1.1.1 日志,未发现异常",
            preserved_evidence_ids=["e1", "e2"],
            dropped_count=5,
        )
        state = {
            "messages": self._make_messages(10),
            "investigation_summary": "",
            "tool_history": [{"tool_name": "QueryIPLogs",
                              "args_summary": "ip=1.1.1.1",
                              "result_summary": "ok(10)",
                              "source_ids": ["e1", "e2"]}],
            "compact_count": 0,
        }
        with patch.object(ag_nodes, "_ensure_compact_llm", new=AsyncMock()), \
             patch.object(
                 ag_nodes, "invoke_structured_with_retry",
                 new=AsyncMock(return_value=mock_compact),
             ):
            result = asyncio.run(compact_node(state))

        self.assertIn("investigation_summary", result)
        self.assertIn("[compact #1]", result["investigation_summary"])
        self.assertIn("已查 IP 1.1.1.1", result["investigation_summary"])
        self.assertEqual(result["compact_count"], 1)

    def test_compact_at_max_count_degrades_to_noop(self):
        """compact_count ≥ MAX_COMPACT_COUNT 时降级不压缩(返回空 dict)。"""
        from agents.react.analysis_explorer import nodes as ag_nodes

        state = {
            "messages": self._make_messages(10),
            "investigation_summary": "old summary",
            "tool_history": [],
            "compact_count": MAX_COMPACT_COUNT,
        }
        with patch.object(
            ag_nodes, "_ensure_compact_llm",
            new=AsyncMock(),
        ) as mock_ensure:
            result = asyncio.run(compact_node(state))

        # 降级:不调 LLM,返回空 dict(不修改 state)
        self.assertEqual(result, {})
        mock_ensure.assert_not_called()


class TestEndToEndRouting(unittest.TestCase):
    """端到端路由测试:用 mock 节点跑完整 graph,验证路由路径。"""

    def test_plan_agent_tools_gate_decision_finish_path(self):
        """完整路径:plan→agent→tools→gate(未命中)→agent→tools→gate(命中)→decision(finish)→END。

        验证:
        - decision_history 有 1 条记录(decision 被调用 1 次)
        - finish_reason 非空(action=finish 时写 reason)
        - agent 被调用 2 次(tools 后回 agent 2 次)
        - tools 被调用 2 次
        - gate 被调用 2 次(第一次未命中,第二次命中)
        - decision 被调用 1 次(返回 finish)
        """
        from agents.react.analysis_explorer import nodes as ag_nodes

        call_counter = {
            "plan": 0, "agent": 0, "tools": 0,
            "gate": 0, "decision": 0, "compact": 0,
        }

        async def mock_plan(state):
            call_counter["plan"] += 1
            return {
                "current_plan": {"hypotheses": ["h1"], "steps": ["s1"],
                                 "expected_evidence": ["e"], "budget": 5},
                "budget": 5, "tool_rounds": 0,
            }

        async def mock_agent(state):
            call_counter["agent"] += 1
            # 始终返回带 tool_calls 的 AIMessage(让路由进 tools)
            return {"messages": [AIMessage(
                content="", tool_calls=[{"name": "QueryIPLogs",
                                          "args": {"ip": "1.1.1.1"},
                                          "id": f"call_{call_counter['agent']}"}],
            )]}

        async def mock_tools(state):
            call_counter["tools"] += 1
            rounds = call_counter["tools"]
            return {
                "messages": [ToolMessage(
                    content='{"ok": true, "data": {"logs": [{"ip": "1.1.1.1"}]}, '
                            '"source_ids": ["e1"], "duration_ms": 100}',
                    tool_call_id=f"call_{rounds}",
                    name="QueryIPLogs",
                )],
                "evidence_pack": {"evidences": [
                    {"content": "ev1", "source_id": "e1", "raw": {}}]},
                "tool_history": [{"tool_name": "QueryIPLogs",
                                  "args_summary": "ip=1.1.1.1",
                                  "result_summary": "ok(1)",
                                  "source_ids": ["e1"], "ok": True}],
                "tool_rounds": rounds,
            }

        async def mock_gate(state):
            call_counter["gate"] += 1
            # 第一次未命中,第二次命中
            if call_counter["gate"] == 1:
                return {"gate_triggered": False, "gate_reasons": []}
            return {"gate_triggered": True, "gate_reasons": ["可能完成"]}

        async def mock_decision(state):
            call_counter["decision"] += 1
            return {
                "decision_result": {"action": "finish", "reason": "done",
                                    "next_step": "输出结论"},
                "decision_history": [{"action": "finish", "reason": "done"}],
                "finish_reason": "done",
            }

        async def mock_compact(state):
            call_counter["compact"] += 1
            return {}

        # 重新编译 graph(mock 节点替换)
        graph = StateGraph(AgentState)
        graph.add_node("plan", mock_plan)
        graph.add_node("agent", mock_agent)
        graph.add_node("tools", mock_tools)
        graph.add_node("deterministic_gate", mock_gate)
        graph.add_node("decision_llm", mock_decision)
        graph.add_node("compact", mock_compact)
        graph.set_entry_point("plan")
        graph.add_edge("plan", "agent")
        graph.add_conditional_edges(
            "agent", _route_after_agent,
            {"tools": "tools", END: END},
        )
        graph.add_edge("tools", "deterministic_gate")
        graph.add_conditional_edges(
            "deterministic_gate", _route_after_gate,
            {"decision_llm": "decision_llm", "agent": "agent"},
        )
        graph.add_conditional_edges(
            "decision_llm", _route_after_decision,
            {"agent": "agent", "plan": "plan",
             "compact": "compact", END: END},
        )
        graph.add_edge("compact", "agent")
        compiled = graph.compile()

        initial_state = {
            "messages": [HumanMessage(content="1.1.1.1 在干什么?")],
            "current_plan": {}, "investigation_summary": "",
            "evidence_pack": {}, "tool_history": [],
            "decision_history": [], "compact_count": 0,
            "total_tokens_used": 0, "tool_rounds": 0, "budget": 0,
            "gate_triggered": False, "gate_reasons": [],
            "decision_result": {}, "finish_reason": "", "final_report": "",
        }
        result = asyncio.run(compiled.ainvoke(initial_state))

        # 验证调用次数
        self.assertEqual(call_counter["plan"], 1, "plan 应被调用 1 次")
        self.assertEqual(call_counter["agent"], 2, "agent 应被调用 2 次")
        self.assertEqual(call_counter["tools"], 2, "tools 应被调用 2 次")
        self.assertEqual(call_counter["gate"], 2, "gate 应被调用 2 次")
        self.assertEqual(call_counter["decision"], 1, "decision 应被调用 1 次")
        self.assertEqual(call_counter["compact"], 0, "compact 不应被调用")

        # 验证 state 结果
        self.assertEqual(
            len(result.get("decision_history", [])), 1,
            "decision_history 应有 1 条记录",
        )
        self.assertEqual(
            result["decision_result"]["action"], "finish",
            "最终决策应为 finish",
        )
        self.assertTrue(
            result.get("finish_reason"), "finish_reason 应非空",
        )


if __name__ == "__main__":
    unittest.main()
