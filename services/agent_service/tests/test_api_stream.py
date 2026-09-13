"""P0-8 API/Stream/Tracing 单测(不触发 LLM 与 MCP,纯函数 + 真实 checkpointer)。

覆盖:
- ``_node_event_to_sse``:plan/gate/decision/compact 四类 SSE 事件提取 + 非目标节点
- ``FileTraceCallback``:on_chain_end / on_llm_end / on_tool_* 落盘 JSONL 可读
- ``get_trace_callback``:env 未设 → None(跳过);env 设 → 返回 handler
- ``_serialize_message``(routes.threads):HumanMessage/AIMessage/ToolMessage 序列化
- thread history 路由:未知 thread → 404;真实 checkpoint → 200 + checkpoints + messages

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_api_stream
"""
import asyncio
import json
import os
import sys
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestNodeEventToSSE(unittest.TestCase):
    """stream._node_event_to_sse:Agent 升级后新 SSE 事件的纯函数提取。"""

    def test_plan_node(self):
        from backend.stream import _node_event_to_sse
        out = _node_event_to_sse("plan", {
            "current_plan": {"hypotheses": ["h1"], "steps": ["s1"], "expected_evidence": []},
            "budget": 5,
            "tool_rounds": 0,
        })
        self.assertEqual(out["type"], "plan_generated")
        self.assertEqual(out["hypotheses"], ["h1"])
        self.assertEqual(out["steps"], ["s1"])
        self.assertEqual(out["budget"], 5)

    def test_gate_node_triggered(self):
        from backend.stream import _node_event_to_sse
        out = _node_event_to_sse("deterministic_gate", {
            "gate_triggered": True,
            "gate_reasons": ["证据不足", "预算临界"],
        })
        self.assertEqual(out["type"], "gate_evaluated")
        self.assertTrue(out["triggered"])
        self.assertEqual(out["reasons"], ["证据不足", "预算临界"])

    def test_gate_node_not_triggered(self):
        from backend.stream import _node_event_to_sse
        out = _node_event_to_sse("deterministic_gate", {
            "gate_triggered": False,
            "gate_reasons": [],
        })
        self.assertEqual(out["type"], "gate_evaluated")
        self.assertFalse(out["triggered"])
        self.assertEqual(out["reasons"], [])

    def test_decision_node(self):
        from backend.stream import _node_event_to_sse
        out = _node_event_to_sse("decision_llm", {
            "decision_result": {"action": "replan", "reason": "证据冲突", "next_step": "重规划"},
            "decision_history": [],
            "finish_reason": "",
        })
        self.assertEqual(out["type"], "decision_made")
        self.assertEqual(out["action"], "replan")
        self.assertEqual(out["reason"], "证据冲突")
        self.assertEqual(out["next_step"], "重规划")

    def test_compact_node(self):
        from backend.stream import _node_event_to_sse
        out = _node_event_to_sse("compact", {
            "investigation_summary": "前文摘要\n[compact #1] 后续摘要",
            "compact_count": 1,
        })
        self.assertEqual(out["type"], "compact_done")
        self.assertEqual(out["compact_count"], 1)
        # summary_preview 取末尾 200 字
        self.assertIn("compact #1", out["summary_preview"])

    def test_non_target_node_returns_none(self):
        from backend.stream import _node_event_to_sse
        # agent / tools 节点不在 _NODE_SSE_NODES,忽略
        self.assertIsNone(_node_event_to_sse("agent", {"messages": []}))
        self.assertIsNone(_node_event_to_sse("tools", {"tool_rounds": 1}))
        # 空名 / 未知名
        self.assertIsNone(_node_event_to_sse("", {"current_plan": {}}))
        self.assertIsNone(_node_event_to_sse("LangGraph", {"current_plan": {}}))

    def test_non_dict_output_does_not_crash(self):
        from backend.stream import _node_event_to_sse
        # compact 节点 output 非 dict(异常情况)→ 不崩,compact_count=None
        out = _node_event_to_sse("compact", "not a dict")
        self.assertEqual(out["type"], "compact_done")
        self.assertIsNone(out["compact_count"])


class TestFileTraceCallback(unittest.TestCase):
    """FileTraceCallback:落盘 JSONL 可读 + 字段正确。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="trace_test_")
        self.log_path = os.path.join(self._tmpdir, "agent_trace.jsonl")
        from backend.trace import FileTraceCallback
        self.handler = FileTraceCallback(self.log_path)

    def _read_lines(self):
        with open(self.log_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_on_chain_end_uses_langgraph_node_metadata(self):
        # 节点名应从 metadata.langgraph_node 取(对齐 astream_events v2 契约)
        self.handler.on_chain_end(
            {"current_plan": {"hypotheses": []}},
            metadata={"langgraph_node": "plan"},
            run_id="r1",
        )
        self.handler.on_chain_end(
            {"messages": []},
            metadata={"langgraph_node": "agent"},
            run_id="r2",
        )
        lines = self._read_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["event"], "on_chain_end")
        self.assertEqual(lines[0]["name"], "plan")
        self.assertEqual(lines[0]["run_id"], "r1")
        self.assertEqual(lines[0]["extra"]["output_keys"], ["current_plan"])
        self.assertEqual(lines[1]["name"], "agent")

    def test_on_llm_end_records_tokens(self):
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, LLMResult
        gen = ChatGeneration(message=AIMessage(content="hello world"))
        result = LLMResult(
            generations=[[gen]],
            llm_output={"token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }},
        )
        self.handler.on_llm_end(result, name="analysis-llm", run_id="r3")
        lines = self._read_lines()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line["event"], "on_llm_end")
        self.assertEqual(line["name"], "analysis-llm")
        self.assertEqual(line["extra"]["tokens"]["prompt_tokens"], 10)
        self.assertEqual(line["extra"]["tokens"]["total_tokens"], 15)
        self.assertIn("hello world", line["extra"]["completion_preview"])

    def test_on_tool_start_end(self):
        self.handler.on_tool_start(
            {"name": "query_ip_logs"}, "1.2.3.4", run_id="r4",
        )
        self.handler.on_tool_end("ok(3 records)", name="query_ip_logs", run_id="r5")
        lines = self._read_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["event"], "on_tool_start")
        self.assertEqual(lines[0]["name"], "query_ip_logs")
        self.assertEqual(lines[0]["extra"]["input"], "1.2.3.4")
        self.assertEqual(lines[1]["event"], "on_tool_end")
        self.assertIn("3 records", lines[1]["extra"]["output_preview"])

    def test_error_handlers_write_records(self):
        self.handler.on_llm_error(ValueError("boom"), name="llm", run_id="re1")
        self.handler.on_tool_error(RuntimeError("tool fail"), name="t", run_id="re2")
        lines = self._read_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["event"], "on_llm_error")
        self.assertIn("boom", lines[0]["extra"]["error"])
        self.assertEqual(lines[1]["event"], "on_tool_error")


class TestGetTraceCallback(unittest.TestCase):
    """get_trace_callback:env 驱动的开关(对齐 §3.9 配置缺失跳过不报错)。"""

    def setUp(self):
        from backend import trace as trace_mod
        trace_mod.reset_trace_callback()
        # 备份并清理 env
        self._prev = os.environ.get("AE_TRACE_LOG")
        os.environ.pop("AE_TRACE_LOG", None)

    def tearDown(self):
        from backend import trace as trace_mod
        trace_mod.reset_trace_callback()
        if self._prev is not None:
            os.environ["AE_TRACE_LOG"] = self._prev

    def test_disabled_when_env_unset(self):
        from backend.trace import get_trace_callback
        self.assertIsNone(get_trace_callback())

    def test_enabled_when_env_set(self):
        import tempfile
        from backend.trace import get_trace_callback
        tmp = os.path.join(tempfile.mkdtemp(prefix="trace_env_"), "trace.jsonl")
        os.environ["AE_TRACE_LOG"] = tmp
        from backend import trace as trace_mod
        trace_mod.reset_trace_callback()
        cb = get_trace_callback()
        self.assertIsNotNone(cb)
        self.assertEqual(cb.log_path, tmp)
        # 文件被触摸(可读空)
        self.assertTrue(os.path.exists(tmp))

    def test_singleton(self):
        from backend.trace import get_trace_callback
        os.environ["AE_TRACE_LOG"] = os.path.join(
            tempfile.mkdtemp(prefix="trace_sing_"), "t.jsonl"
        )
        from backend import trace as trace_mod
        trace_mod.reset_trace_callback()
        a = get_trace_callback()
        b = get_trace_callback()
        self.assertIs(a, b)


class TestSerializeMessage(unittest.TestCase):
    """routes.threads._serialize_message:消息序列化(截断 + role 映射)。"""

    def test_human_message(self):
        from backend.routes.threads import _serialize_message
        from langchain_core.messages import HumanMessage
        m = _serialize_message(HumanMessage(content="查 1.2.3.4"))
        self.assertEqual(m.role, "user")
        self.assertEqual(m.content, "查 1.2.3.4")
        self.assertIsNone(m.tool_calls)

    def test_ai_message_with_tool_calls(self):
        from backend.routes.threads import _serialize_message
        from langchain_core.messages import AIMessage
        ai = AIMessage(
            content="",
            tool_calls=[{"name": "query_ip_logs", "args": {"ip": "1.2.3.4"}, "id": "x"}],
        )
        m = _serialize_message(ai)
        self.assertEqual(m.role, "assistant")
        self.assertEqual(len(m.tool_calls), 1)
        self.assertEqual(m.tool_calls[0]["name"], "query_ip_logs")

    def test_tool_message_truncates_long_content(self):
        from backend.routes.threads import _serialize_message
        from langchain_core.messages import ToolMessage
        long_content = "x" * 1000
        m = _serialize_message(
            ToolMessage(content=long_content, tool_call_id="tc1", name="query_ip_logs")
        )
        self.assertEqual(m.role, "tool")
        self.assertEqual(m.name, "query_ip_logs")
        # 截断到 500 字
        self.assertEqual(len(m.content), 500)


class TestThreadHistoryRoute(unittest.TestCase):
    """thread history 路由:404 / 503 / 200(真实 checkpoint)。"""

    @classmethod
    def setUpClass(cls):
        # 强制 memory 后端(测试不依赖 Redis)
        os.environ["AE_MEMORY_BACKEND"] = "memory"
        from fastapi.testclient import TestClient
        from backend.main import app
        cls.client = TestClient(app)

    def test_unknown_thread_returns_404(self):
        r = self.client.get(
            "/agent/analysis_explorer/threads/never-exists-xyz/history"
        )
        self.assertEqual(r.status_code, 404)
        self.assertIn("not found", r.json()["detail"])

    def test_history_after_real_checkpoint(self):
        """用 trivial graph + 共享 checkpointer 写一条 checkpoint,再 GET 验证。"""
        from langgraph.graph import StateGraph, END
        from langgraph.graph.message import MessagesState
        from langchain_core.messages import HumanMessage
        from shared.memory import get_checkpointer

        def _node1(state):
            return {"messages": [HumanMessage(content="hello from trivial")]}

        builder = StateGraph(MessagesState)
        builder.add_node("node1", _node1)
        builder.set_entry_point("node1")
        builder.add_edge("node1", END)
        g = builder.compile(checkpointer=get_checkpointer())

        tid = f"trivial-{int(time.time() * 1000)}-{os.getpid()}"
        # 路由内部命名空间为 "{agent_type}:{thread_id}",这里同步写入共享 MemorySaver
        ns_tid = f"analysis_explorer:{tid}"
        asyncio.run(g.ainvoke(
            {"messages": [HumanMessage(content="hi")]},
            config={"configurable": {"thread_id": ns_tid}},
        ))

        r = self.client.get(f"/agent/analysis_explorer/threads/{tid}/history")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["exists"])
        self.assertEqual(body["agent_type"], "analysis_explorer")
        self.assertEqual(body["thread_id"], tid)
        self.assertGreaterEqual(body["checkpoint_count"], 1)
        # checkpoints 至少有一条(含 node1 写入)
        self.assertTrue(len(body["checkpoints"]) >= 1)
        # messages 含 user 消息
        roles = [m["role"] for m in body["messages"]]
        self.assertIn("user", roles)

    def test_limit_query_validation(self):
        # limit 超出 [1,100] → 422(对齐 Query 约束)
        r = self.client.get(
            "/agent/analysis_explorer/threads/x/history?limit=999"
        )
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
