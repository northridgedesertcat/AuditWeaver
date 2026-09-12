"""analysis_workflow v2.1 五节点流水线测试(对齐 §3.1)。

覆盖目标:
- 图编译成 CompiledStateGraph
- 五节点齐全(retrieve/analyze/validate/enrich/report)
- validate PASS → 路由到 report(不走 enrich)
- validate FAIL + enrich_count=0 → 路由到 enrich
- validate FAIL + enrich_count >= MAX_ENRICH_COUNT → 强制路由到 report(防死循环)
- enrich 节点合并 evidence_pack 去重 by source_id
- report 输出含 source_id 引用(反幻觉)

注:全测试不依赖真实 LLM / ES,通过 monkey-patch 节点函数 mock 返回值,
只测「图结构 + 路由 + state 读写」逻辑(对齐 §3.1 设计的确定性部分)。

运行(项目根目录):
    $env:AE_MEMORY_BACKEND='memory'
    python -m unittest services.agent_service.tests.test_workflow -v
"""
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


# 触发 agents 包注册 analysis_workflow
import agents  # noqa: F401
from agents.workflow.analysis_workflow.graph import _route_after_validate, build_graph
from agents.workflow.analysis_workflow.config.settings import MAX_ENRICH_COUNT
from langgraph.graph.state import CompiledStateGraph


class TestGraphStructure(unittest.TestCase):
    """图结构测试:编译 + 五节点齐全 + 入口正确。"""

    def test_build_graph_returns_compiled(self):
        """build_graph 编译返回 CompiledStateGraph 实例。"""
        graph = build_graph()
        self.assertIsInstance(graph, CompiledStateGraph)

    def test_graph_has_five_nodes(self):
        """图含 retrieve/analyze/validate/enrich/report 五节点。"""
        graph = build_graph()
        # langgraph CompiledStateGraph.nodes 是 dict,键为节点名
        node_names = set(graph.get_graph().nodes.keys())
        for expected in ("retrieve", "analyze", "validate", "enrich", "report"):
            self.assertIn(
                expected, node_names,
                f"图缺少节点 {expected},现有节点:{node_names}",
            )

    def test_entry_point_is_retrieve(self):
        """入口节点应为 retrieve(纯代码调 RAG,不进 LLM)。

        通过 graph.get_graph().edges 检查 __start__ 边指向 retrieve。
        """
        graph = build_graph()
        graph_data = graph.get_graph()
        # langgraph 的 graph_data.edges 是 list,每项有 source/target
        # __start__ → retrieve 是入口边
        start_edges = [
            e for e in graph_data.edges
            if getattr(e, "source", "") == "__start__"
        ]
        self.assertTrue(
            len(start_edges) >= 1,
            f"应至少有一条 __start__ 出边,实际:{graph_data.edges}",
        )
        # 第一条 __start__ 出边应指向 retrieve
        self.assertEqual(start_edges[0].target, "retrieve")


class TestRouteAfterValidate(unittest.TestCase):
    """条件路由测试:_route_after_validate 的确定性规则。"""

    def test_pass_routes_to_report(self):
        """validate pass=True → 路由到 report。"""
        state = {
            "validate_result": {"pass": True, "missing": [], "reason": "ok"},
            "enrich_count": 0,
        }
        self.assertEqual(_route_after_validate(state), "report")

    def test_fail_zero_count_routes_to_enrich(self):
        """validate pass=False + enrich_count=0 → 路由到 enrich(补检索)。"""
        state = {
            "validate_result": {
                "pass": False,
                "missing": ["攻击类型无载荷证据"],
                "reason": "missing payload evidence",
            },
            "enrich_count": 0,
        }
        self.assertEqual(_route_after_validate(state), "enrich")

    def test_fail_at_max_count_routes_to_report(self):
        """validate pass=False + enrich_count>=MAX → 强制走 report(防死循环)。"""
        state = {
            "validate_result": {
                "pass": False,
                "missing": ["still missing"],
                "reason": "still insufficient",
            },
            "enrich_count": MAX_ENRICH_COUNT,
        }
        self.assertEqual(_route_after_validate(state), "report")

    def test_fail_above_max_count_routes_to_report(self):
        """validate pass=False + enrich_count > MAX → 强制走 report。"""
        state = {
            "validate_result": {"pass": False, "missing": [], "reason": "x"},
            "enrich_count": MAX_ENRICH_COUNT + 1,
        }
        self.assertEqual(_route_after_validate(state), "report")

    def test_fail_one_below_max_routes_to_enrich(self):
        """validate pass=False + enrich_count=MAX-1 → 仍可 enrich(最后一次)。"""
        state = {
            "validate_result": {"pass": False, "missing": [], "reason": "x"},
            "enrich_count": MAX_ENRICH_COUNT - 1,
        }
        self.assertEqual(_route_after_validate(state), "enrich")

    def test_pass_with_high_count_still_routes_to_report(self):
        """validate pass=True 时,即使 enrich_count 高,也走 report(pass 优先)。"""
        state = {
            "validate_result": {"pass": True, "missing": [], "reason": "ok"},
            "enrich_count": 100,
        }
        self.assertEqual(_route_after_validate(state), "report")

    def test_pass_underscore_alias_works(self):
        """ValidateSchema 用 alias='pass',state 里键可能是 'pass_' 兜底。"""
        state = {
            "validate_result": {"pass_": True, "missing": [], "reason": "ok"},
            "enrich_count": 0,
        }
        self.assertEqual(_route_after_validate(state), "report")

    def test_missing_validate_result_defaults_to_report(self):
        """validate_result 缺失(异常情况)默认走 report(降级出报告)。"""
        state = {"enrich_count": 0}
        self.assertEqual(_route_after_validate(state), "report")


class TestEnrichNodeMerge(unittest.TestCase):
    """enrich 节点测试:evidence_pack 合并 + 去重 by source_id。"""

    def test_enrich_merges_and_dedupes_by_source_id(self):
        """enrich 合并新旧 evidence_pack,按 source_id 去重。"""
        import asyncio
        from agents.workflow.analysis_workflow.nodes import enrich_node

        # 构造旧 evidence_pack(2 条,1 条会被新 pack 重复)
        old_pack = {
            "query": "old query",
            "evidences": [
                {"content": "old ev1", "source_id": "evt_001", "score": 0.1,
                 "source_type": "matched_logs", "raw": {}},
                {"content": "old ev2", "source_id": "evt_002", "score": 0.2,
                 "source_type": "matched_logs", "raw": {}},
            ],
            "fused": True,
            "sources": ["bm25", "vector"],
        }
        # 新 pack(mock rag_retrieve 返回):1 条新 + 1 条重复(evt_001)
        from shared.rag.result import Evidence, EvidencePack
        new_pack = EvidencePack(
            query="enrich query",
            evidences=[
                Evidence(content="old ev1 dup", source_id="evt_001", score=0.3,
                         source_type="matched_logs"),
                Evidence(content="new ev3", source_id="evt_003", score=0.4,
                         source_type="matched_logs"),
            ],
            fused=True,
            sources=["bm25", "vector"],
        )

        state = {
            "log_data": {"ip": "1.1.1.1", "path": "/admin", "method": "GET"},
            "evidence_pack": old_pack,
            "validate_result": {"pass": False, "missing": ["缺 SQLi 载荷证据"],
                                "reason": "no payload"},
            "enrich_count": 0,
        }

        with patch(
            "agents.workflow.analysis_workflow.nodes.rag_retrieve",
            new=AsyncMock(return_value=new_pack),
        ) if False else patch(
            "agents.workflow.analysis_workflow.nodes.rag_retrieve",
            return_value=new_pack,
        ):
            # enrich_node 是 async,但 rag_retrieve 是同步函数(retrieve 不是 async)
            # 用 asyncio.run 跑
            result = asyncio.run(enrich_node(state))

        # enrich_count +1
        self.assertEqual(result["enrich_count"], 1)
        # evidence_pack 合并去重:旧 2 条 + 新 2 条 - 1 条重复 = 3 条
        merged = result["evidence_pack"]
        self.assertEqual(len(merged["evidences"]), 3)
        source_ids = [e["source_id"] for e in merged["evidences"]]
        self.assertIn("evt_001", source_ids)
        self.assertIn("evt_002", source_ids)
        self.assertIn("evt_003", source_ids)
        # evt_001 不应出现两次
        self.assertEqual(source_ids.count("evt_001"), 1)

    def test_enrich_rag_failure_keeps_old_pack_and_increments_count(self):
        """RAG 检索失败时,保留原 evidence_pack,enrich_count 仍 +1(防卡死)。"""
        import asyncio
        from agents.workflow.analysis_workflow.nodes import enrich_node

        old_pack = {
            "query": "old",
            "evidences": [
                {"content": "old ev", "source_id": "evt_001", "score": 0.1,
                 "source_type": "matched_logs", "raw": {}},
            ],
            "fused": False,
            "sources": ["bm25"],
        }
        state = {
            "log_data": {"ip": "1.1.1.1"},
            "evidence_pack": old_pack,
            "validate_result": {"pass": False, "missing": [], "reason": "x"},
            "enrich_count": 1,
        }

        with patch(
            "agents.workflow.analysis_workflow.nodes.rag_retrieve",
            side_effect=RuntimeError("ES down"),
        ):
            result = asyncio.run(enrich_node(state))

        # enrich_count +1(即使检索失败)
        self.assertEqual(result["enrich_count"], 2)
        # evidence_pack 不在返回中(保留旧的不动)
        self.assertNotIn("evidence_pack", result)


class TestEndToEndRouting(unittest.TestCase):
    """端到端路由测试:用 mock 节点跑完整 graph,验证路由路径。"""

    def test_pass_path_retrieves_once_no_enrich(self):
        """validate pass 路径:retrieve → analyze → validate → report,
        enrich 不应被调用。
        """
        import asyncio
        from agents.workflow.analysis_workflow import nodes as wf_nodes

        # Mock 所有节点,只返回最小 state 更新
        async def mock_retrieve(state):
            return {"evidence_pack": {"evidences": [], "fused": False,
                                       "sources": [], "query": "test"}}

        async def mock_analyze(state):
            return {"analysis": {"risk_level": "Low", "risk_score": 10,
                                 "attack_type": "", "summary": "ok",
                                 "reasoning": [], "recommendations": []}}

        async def mock_validate_pass(state):
            return {"validate_result": {"pass": True, "missing": [],
                                        "reason": "all good"}}

        async def mock_enrich(state):
            # 这个不应被调用,若被调用会污染 enrich_count
            return {"enrich_count": (state.get("enrich_count", 0) or 0) + 1}

        async def mock_report(state):
            return {"final_report": "final report with [source_id=evt_001]"}

        with patch.object(wf_nodes, "retrieve_node", mock_retrieve), \
             patch.object(wf_nodes, "analyze_node", mock_analyze), \
             patch.object(wf_nodes, "validate_node", mock_validate_pass), \
             patch.object(wf_nodes, "enrich_node", mock_enrich), \
             patch.object(wf_nodes, "report_node", mock_report):
            # 重新编译 graph(因为节点是在编译时绑定的)
            from agents.workflow.analysis_workflow.graph import (
                StateGraph, END, LogAnalysisState,
            )
            graph = StateGraph(LogAnalysisState)
            graph.add_node("retrieve", mock_retrieve)
            graph.add_node("analyze", mock_analyze)
            graph.add_node("validate", mock_validate_pass)
            graph.add_node("enrich", mock_enrich)
            graph.add_node("report", mock_report)
            graph.set_entry_point("retrieve")
            graph.add_edge("retrieve", "analyze")
            graph.add_edge("analyze", "validate")
            graph.add_conditional_edges(
                "validate", _route_after_validate,
                {"report": "report", "enrich": "enrich"},
            )
            graph.add_edge("enrich", "analyze")
            graph.add_edge("report", END)
            compiled = graph.compile()

            initial_state = {
                "log_data": {"ip": "1.1.1.1", "path": "/admin"},
                "retrieved_context": "",
                "analysis": {},
                "evidence_pack": {},
                "validate_result": {},
                "enrich_count": 0,
                "final_report": "",
            }
            # 同步调用(测试用同步,生产用 async + SSE)
            result = asyncio.run(compiled.ainvoke(initial_state))

        self.assertEqual(result.get("enrich_count", 0), 0)  # enrich 未被调用
        self.assertIn("final report", result.get("final_report", ""))
        self.assertTrue(
            result.get("validate_result", {}).get("pass", False),
            "validate 应返回 pass=True",
        )

    def test_fail_then_pass_path_calls_enrich_once(self):
        """validate fail(enrich_count=0) → enrich → analyze → validate(pass) → report。
        enrich 应被调用 1 次,enrich_count=1。
        """
        import asyncio
        from agents.workflow.analysis_workflow.graph import (
            StateGraph, END, LogAnalysisState,
        )

        # 用计数器跟踪调用次数
        call_counter = {"enrich": 0, "analyze": 0, "validate": 0}

        async def mock_retrieve(state):
            return {"evidence_pack": {"evidences": [], "fused": False,
                                       "sources": [], "query": "test"}}

        async def mock_analyze(state):
            call_counter["analyze"] += 1
            return {"analysis": {"risk_level": "Medium", "risk_score": 50,
                                 "attack_type": "SQLi", "summary": "",
                                 "reasoning": [], "recommendations": []}}

        # 第一次 validate 返回 fail,第二次返回 pass
        async def mock_validate(state):
            call_counter["validate"] += 1
            if call_counter["validate"] == 1:
                return {"validate_result": {
                    "pass": False, "missing": ["no payload"], "reason": "fail"}}
            return {"validate_result": {
                "pass": True, "missing": [], "reason": "ok"}}

        async def mock_enrich(state):
            call_counter["enrich"] += 1
            return {
                "enrich_count": (state.get("enrich_count", 0) or 0) + 1,
                "evidence_pack": {"evidences": [
                    {"content": "enriched ev", "source_id": "evt_enriched",
                     "score": 0.5, "source_type": "matched_logs", "raw": {}}
                ], "fused": True, "sources": ["bm25"], "query": "enriched"},
            }

        async def mock_report(state):
            return {"final_report": "final report with [source_id=evt_enriched]"}

        graph = StateGraph(LogAnalysisState)
        graph.add_node("retrieve", mock_retrieve)
        graph.add_node("analyze", mock_analyze)
        graph.add_node("validate", mock_validate)
        graph.add_node("enrich", mock_enrich)
        graph.add_node("report", mock_report)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "analyze")
        graph.add_edge("analyze", "validate")
        graph.add_conditional_edges(
            "validate", _route_after_validate,
            {"report": "report", "enrich": "enrich"},
        )
        graph.add_edge("enrich", "analyze")
        graph.add_edge("report", END)
        compiled = graph.compile()

        initial_state = {
            "log_data": {"ip": "1.1.1.1"},
            "retrieved_context": "",
            "analysis": {},
            "evidence_pack": {},
            "validate_result": {},
            "enrich_count": 0,
            "final_report": "",
        }
        result = asyncio.run(compiled.ainvoke(initial_state))

        self.assertEqual(call_counter["enrich"], 1, "enrich 应被调用 1 次")
        self.assertEqual(call_counter["analyze"], 2, "analyze 应被调用 2 次")
        self.assertEqual(call_counter["validate"], 2, "validate 应被调用 2 次")
        self.assertEqual(result["enrich_count"], 1)
        self.assertTrue(result["validate_result"]["pass"])
        self.assertIn("[source_id=", result["final_report"])

    def test_fail_until_max_count_force_routes_to_report(self):
        """validate 一直 FAIL,enrich_count 达 MAX 后强制走 report(防死循环)。"""
        import asyncio
        from agents.workflow.analysis_workflow.graph import (
            StateGraph, END, LogAnalysisState,
        )

        call_counter = {"enrich": 0, "validate": 0}

        async def mock_retrieve(state):
            return {"evidence_pack": {"evidences": [], "fused": False,
                                       "sources": [], "query": "test"}}

        async def mock_analyze(state):
            return {"analysis": {}}

        # 一直 FAIL
        async def mock_validate(state):
            call_counter["validate"] += 1
            return {"validate_result": {
                "pass": False, "missing": ["still missing"], "reason": "fail"}}

        async def mock_enrich(state):
            call_counter["enrich"] += 1
            return {
                "enrich_count": (state.get("enrich_count", 0) or 0) + 1,
                "evidence_pack": {"evidences": [], "fused": False,
                                   "sources": [], "query": "enrich"},
            }

        async def mock_report(state):
            return {"final_report": "降级报告(证据不足,基于日志推断)"}

        graph = StateGraph(LogAnalysisState)
        graph.add_node("retrieve", mock_retrieve)
        graph.add_node("analyze", mock_analyze)
        graph.add_node("validate", mock_validate)
        graph.add_node("enrich", mock_enrich)
        graph.add_node("report", mock_report)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "analyze")
        graph.add_edge("analyze", "validate")
        graph.add_conditional_edges(
            "validate", _route_after_validate,
            {"report": "report", "enrich": "enrich"},
        )
        graph.add_edge("enrich", "analyze")
        graph.add_edge("report", END)
        compiled = graph.compile()

        initial_state = {
            "log_data": {"ip": "1.1.1.1"},
            "retrieved_context": "",
            "analysis": {},
            "evidence_pack": {},
            "validate_result": {},
            "enrich_count": 0,
            "final_report": "",
        }
        result = asyncio.run(compiled.ainvoke(initial_state))

        # enrich 应被调用 MAX_ENRICH_COUNT 次(2 次),然后强制走 report
        self.assertEqual(
            call_counter["enrich"], MAX_ENRICH_COUNT,
            f"enrich 应被调用 {MAX_ENRICH_COUNT} 次,实际 {call_counter['enrich']}",
        )
        self.assertEqual(
            result["enrich_count"], MAX_ENRICH_COUNT,
            "enrich_count 应等于 MAX_ENRICH_COUNT",
        )
        self.assertFalse(result["validate_result"]["pass"],
                         "validate 仍 FAIL")
        self.assertIn("降级报告", result["final_report"],
                      "应生成降级报告")


class TestReportCitation(unittest.TestCase):
    """report 节点反幻觉测试:报告含 source_id 引用(对齐 §3.1)。"""

    def test_report_prompt_includes_evidence_pack_with_source_ids(self):
        """render_report_prompt 应把 evidence_pack 中的 source_id 注入 prompt。"""
        from agents.workflow.analysis_workflow.prompts import render_report_prompt

        evidence_pack = {
            "query": "test query",
            "evidences": [
                {"content": "SQLi attack from 1.1.1.1",
                 "source_id": "evt_001", "score": 0.5,
                 "source_type": "matched_logs", "raw": {}},
                {"content": "path traversal detected",
                 "source_id": "evt_002", "score": 0.4,
                 "source_type": "matched_logs", "raw": {}},
            ],
            "fused": True,
            "sources": ["bm25", "vector"],
        }
        messages = render_report_prompt(
            log_data={"ip": "1.1.1.1", "path": "/admin?id=1' OR '1'='1"},
            evidence_pack=evidence_pack,
            analysis={"risk_level": "High", "risk_score": 75,
                      "attack_type": "SQLi", "summary": "test"},
            validate_result={"pass": True, "missing": [], "reason": "ok"},
        )
        prompt_text = messages[0].content

        # source_id 应被注入到 prompt 中(供 LLM 引用)
        self.assertIn("evt_001", prompt_text)
        self.assertIn("evt_002", prompt_text)
        # 报告要求中应说明引用规则
        self.assertIn("source_id", prompt_text)
        self.assertIn("推测", prompt_text)

    def test_report_prompt_handles_empty_evidence_pack(self):
        """空 evidence_pack 时,prompt 应明确告知无证据(反幻觉)。"""
        from agents.workflow.analysis_workflow.prompts import render_report_prompt

        messages = render_report_prompt(
            log_data={"ip": "1.1.1.1"},
            evidence_pack={},
            analysis={},
            validate_result=None,
        )
        prompt_text = messages[0].content
        # 应有"无检索证据"占位文本
        self.assertIn("无检索证据", prompt_text)


class TestSchemaSerialization(unittest.TestCase):
    """Schema 序列化测试:ValidateSchema 用 alias='pass' 时正确序列化。"""

    def test_validate_schema_dumps_with_pass_alias(self):
        """ValidateSchema.model_dump(by_alias=True) 应输出键 'pass' 而非 'pass_'。"""
        from agents.workflow.analysis_workflow.schema import ValidateSchema

        v = ValidateSchema(pass_=True, missing=[], reason="ok")
        d = v.model_dump(by_alias=True)
        self.assertIn("pass", d)
        self.assertTrue(d["pass"])
        self.assertNotIn("pass_", d)

    def test_validate_schema_dumps_without_alias_uses_pass_underscore(self):
        """model_dump() 默认(不带 by_alias)用字段名 pass_。"""
        from agents.workflow.analysis_workflow.schema import ValidateSchema

        v = ValidateSchema(pass_=False, missing=["x"], reason="bad")
        d = v.model_dump()
        self.assertIn("pass_", d)
        self.assertFalse(d["pass_"])

    def test_report_schema_has_required_fields(self):
        """ReportSchema 含 report/cited_source_ids/unresolved 三字段。"""
        from agents.workflow.analysis_workflow.schema import ReportSchema

        r = ReportSchema(
            report="test report [source_id=evt_001]",
            cited_source_ids=["evt_001"],
            unresolved=["some speculation"],
        )
        self.assertEqual(r.report, "test report [source_id=evt_001]")
        self.assertEqual(r.cited_source_ids, ["evt_001"])
        self.assertEqual(r.unresolved, ["some speculation"])


if __name__ == "__main__":
    unittest.main()
