"""Agent Evaluation 指标纯函数单测(对齐 §3.8,不依赖 LLM/ES/graph)。

覆盖 evals/metrics.py 的 6 个纯函数 + per_case_metrics + aggregate。
运行(项目根目录):
    python -m unittest services.agent_service.tests.test_eval_metrics
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestCorrectness(unittest.TestCase):
    def test_all_keys_hit(self):
        from evals.metrics import correctness
        self.assertEqual(
            correctness("发现 SQL 注入,来源 1.2.3.4,接口 login", ["SQL", "1.2.3.4", "login"]),
            1.0,
        )

    def test_partial_hit(self):
        from evals.metrics import correctness
        # 只命中 SQL,未命中 1.2.3.4(原文是 1.2.3.5)
        self.assertAlmostEqual(
            correctness("SQL 注入,IP 1.2.3.5", ["SQL", "1.2.3.4"]),
            0.5,
        )

    def test_case_insensitive(self):
        from evals.metrics import correctness
        self.assertEqual(
            correctness("sql injection on LOGIN", ["SQL", "login"]),
            1.0,
        )

    def test_empty_report_or_keys(self):
        from evals.metrics import correctness
        self.assertEqual(correctness("", ["x"]), 0.0)
        self.assertEqual(correctness("report", []), 0.0)


class TestEvidenceCoverage(unittest.TestCase):
    def test_no_constraint_returns_full(self):
        from evals.metrics import evidence_coverage
        self.assertEqual(evidence_coverage(None, []), 1.0)

    def test_full_hit(self):
        from evals.metrics import evidence_coverage
        pack = {"evidences": [
            {"source_id": "evt-1"}, {"source_id": "evt-2"}, {"source_id": "evt-3"},
        ]}
        self.assertEqual(evidence_coverage(pack, ["evt-1", "evt-2"]), 1.0)

    def test_partial_hit(self):
        from evals.metrics import evidence_coverage
        pack = {"evidences": [{"source_id": "evt-1"}, {"source_id": "x"}]}
        self.assertAlmostEqual(evidence_coverage(pack, ["evt-1", "evt-2"]), 0.5)

    def test_no_evidence_with_constraint(self):
        from evals.metrics import evidence_coverage
        self.assertEqual(evidence_coverage({"evidences": []}, ["evt-1"]), 0.0)
        self.assertEqual(evidence_coverage(None, ["evt-1"]), 0.0)


class TestToolRecall(unittest.TestCase):
    def test_no_constraint(self):
        from evals.metrics import tool_recall
        self.assertEqual(tool_recall([], []), 1.0)

    def test_full_recall(self):
        from evals.metrics import tool_recall
        th = [{"tool_name": "query_ip_logs"}, {"tool_name": "query_security_events"}]
        self.assertEqual(
            tool_recall(th, ["query_ip_logs", "query_security_events"]),
            1.0,
        )

    def test_partial_recall(self):
        from evals.metrics import tool_recall
        th = [{"tool_name": "query_ip_logs"}]
        self.assertAlmostEqual(
            tool_recall(th, ["query_ip_logs", "query_security_events"]),
            0.5,
        )

    def test_no_calls_with_constraint(self):
        from evals.metrics import tool_recall
        self.assertEqual(tool_recall([], ["query_ip_logs"]), 0.0)
        self.assertEqual(tool_recall(None, ["x"]), 0.0)


class TestWastedCalls(unittest.TestCase):
    def test_no_calls(self):
        from evals.metrics import wasted_calls
        self.assertEqual(wasted_calls([]), 0)
        self.assertEqual(wasted_calls(None), 0)

    def test_failed_calls_counted(self):
        from evals.metrics import wasted_calls
        th = [
            {"ok": True, "source_ids": ["e1"]},
            {"ok": False, "source_ids": ["e2"]},  # 失败 → 无效
            {"ok": True, "source_ids": []},        # 无 source_ids → 无效
            {"ok": True, "source_ids": ["e3"]},
        ]
        self.assertEqual(wasted_calls(th), 2)

    def test_all_useful(self):
        from evals.metrics import wasted_calls
        th = [{"ok": True, "source_ids": ["e1"]}, {"ok": True, "source_ids": ["e2"]}]
        self.assertEqual(wasted_calls(th), 0)


class TestStepsToFinish(unittest.TestCase):
    def test_counts_tool_rounds_only(self):
        from evals.metrics import steps_to_finish
        th = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]
        # decision_history 不计入
        self.assertEqual(steps_to_finish(th, [{"action": "continue"}] * 5), 3)

    def test_empty(self):
        from evals.metrics import steps_to_finish
        self.assertEqual(steps_to_finish(None, None), 0)


class TestDecisionQuality(unittest.TestCase):
    def test_finished_via_action(self):
        from evals.metrics import decision_quality
        dh = [{"action": "continue"}, {"action": "replan"}, {"action": "finish"}]
        q = decision_quality(dh)
        self.assertTrue(q["finished"])
        self.assertEqual(q["replan_count"], 1)
        self.assertEqual(q["compact_count"], 0)
        self.assertEqual(q["continue_count"], 1)

    def test_finished_via_finish_reason(self):
        from evals.metrics import decision_quality
        # 无 finish action 但 finish_reason 非空 → finished=True
        q = decision_quality([{"action": "continue"}], finish_reason="证据充分")
        self.assertTrue(q["finished"])
        self.assertTrue(q["has_finish_reason"])

    def test_not_finished(self):
        from evals.metrics import decision_quality
        q = decision_quality([{"action": "continue"}, {"action": "compact"}], "")
        self.assertFalse(q["finished"])
        self.assertEqual(q["compact_count"], 1)


class TestPerCaseAndAggregate(unittest.TestCase):
    def test_per_case_metrics_from_final_state(self):
        from evals.metrics import per_case_metrics
        final_state = {
            "final_report": "判定为 SQL 注入,IP 1.2.3.4,接口 login",
            "evidence_pack": {"evidences": [{"source_id": "evt-1"}, {"source_id": "evt-2"}]},
            "tool_history": [
                {"tool_name": "query_ip_logs", "ok": True, "source_ids": ["evt-1"]},
                {"tool_name": "query_security_events", "ok": True, "source_ids": ["evt-2"]},
                {"tool_name": "query_ip_logs", "ok": False, "source_ids": []},
            ],
            "decision_history": [{"action": "continue"}, {"action": "finish"}],
            "finish_reason": "证据充分",
        }
        case = {
            "id": "sqli-001",
            "scenario": "SQLi",
            "difficulty": "easy",
            "expected_keys": ["SQL", "1.2.3.4", "login"],
            "expected_tools": ["query_ip_logs", "query_security_events"],
            "expected_source_ids": ["evt-1"],
        }
        m = per_case_metrics(final_state, case)
        self.assertEqual(m["case_id"], "sqli-001")
        self.assertEqual(m["correctness"], 1.0)
        self.assertEqual(m["evidence_coverage"], 1.0)
        self.assertEqual(m["tool_recall"], 1.0)
        self.assertEqual(m["wasted_calls"], 1)  # 第 3 轮失败且无 source_ids
        self.assertEqual(m["steps_to_finish"], 3)
        self.assertTrue(m["decision_quality"]["finished"])

    def test_per_case_falls_back_to_last_ai_message(self):
        """final_report 为空时兜底取最后一条 AIMessage.content。"""
        from evals.metrics import per_case_metrics
        from langchain_core.messages import AIMessage, HumanMessage
        final_state = {
            "final_report": "",  # 未显式写
            "messages": [
                HumanMessage(content="分析 SQLi"),
                AIMessage(content="这是 SQL 注入,IP 1.2.3.4"),
            ],
        }
        case = {"id": "x", "expected_keys": ["SQL", "1.2.3.4"], "expected_tools": []}
        m = per_case_metrics(final_state, case)
        self.assertEqual(m["correctness"], 1.0)

    def test_aggregate_averages(self):
        from evals.metrics import aggregate
        per_case = [
            {"correctness": 1.0, "evidence_coverage": 1.0, "tool_recall": 1.0,
             "wasted_calls": 0, "steps_to_finish": 2,
             "decision_quality": {"finished": True, "replan_count": 0, "compact_count": 0}},
            {"correctness": 0.5, "evidence_coverage": 0.5, "tool_recall": 0.5,
             "wasted_calls": 2, "steps_to_finish": 4,
             "decision_quality": {"finished": False, "replan_count": 1, "compact_count": 1}},
        ]
        agg = aggregate(per_case)
        self.assertEqual(agg["count"], 2)
        self.assertAlmostEqual(agg["correctness_avg"], 0.75)
        self.assertAlmostEqual(agg["tool_recall_avg"], 0.75)
        self.assertAlmostEqual(agg["wasted_calls_avg"], 1.0)
        self.assertAlmostEqual(agg["steps_to_finish_avg"], 3.0)
        self.assertAlmostEqual(agg["finish_rate"], 0.5)
        self.assertAlmostEqual(agg["replan_avg"], 0.5)
        self.assertAlmostEqual(agg["compact_avg"], 0.5)

    def test_aggregate_empty(self):
        from evals.metrics import aggregate
        agg = aggregate([])
        self.assertEqual(agg["count"], 0)
        self.assertEqual(agg["correctness_avg"], 0.0)


if __name__ == "__main__":
    unittest.main()
