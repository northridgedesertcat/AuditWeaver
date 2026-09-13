"""Tool 规范 P0-5 单元测试(对齐设计 §3.6)。

覆盖:
- ToolResult / tool_ok / tool_fail 字段语义
- source_ids 提取:从嵌套 dict / list 扫描 event_id / _id / id
- wrap_tool_with_spec:成功归一化为 ToolResult(ok=True)
- 超时:超过 timeout_s 返回 ok=False, error_type=timeout,不抛异常
- 重试:瞬时错误重试 N 次后成功 / 重试耗尽返回 retry_exhausted
- 非瞬时错误:不重试直接返回 execution_error
- 审计:每次调用写一条 JSONL,聚合统计正确
- 包装后保留 name / description / args_schema(供 bind_tools)

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_tool_spec
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_SERVICE_DIR = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_AGENT_SERVICE_DIR)
for _p in (_AGENT_SERVICE_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# 构造一个最小 BaseTool 用于测试(避免依赖 MCP 实际启动子进程)
def _make_inner_tool(
    name: str = "test_tool",
    description: str = "a test tool",
    side_effect=None,
    delay: float = 0.0,
    raises: Exception | None = None,
):
    """构造一个简单的 BaseTool,实现 ainvoke。

    用 StructuredTool 构造(避开 BaseTool 子类的 Pydantic 字段默认值坑)。
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class _Args(BaseModel):
        x: int = Field(description="x param")

    # 用 closure 计数(避开 BaseTool Pydantic 字段约束)
    state = {'count': 0}

    async def _arun(**kwargs):
        state['count'] += 1
        if delay:
            await asyncio.sleep(delay)
        if raises is not None:
            raise raises
        if callable(side_effect):
            return side_effect(kwargs)
        return {"echo": kwargs}

    def _run(**kwargs):
        return asyncio.run(_arun(**kwargs))

    tool = StructuredTool(
        name=name,
        description=description,
        args_schema=_Args,
        func=_run,
        coroutine=_arun,
    )
    # 暴露内部状态供测试断言
    tool._test_state = state  # type: ignore[attr-defined]
    return tool


class TestToolResult(unittest.TestCase):
    """ToolResult 数据结构。"""

    def test_tool_ok_basic(self):
        from shared.tools.result import tool_ok, ToolResult
        r = tool_ok({"a": 1}, source_ids=["e1", "e2"])
        self.assertTrue(r.ok)
        self.assertEqual(r.data, {"a": 1})
        self.assertEqual(r.source_ids, ["e1", "e2"])
        self.assertIsNone(r.error)

    def test_tool_fail_basic(self):
        from shared.tools.result import ToolErrorType, tool_fail
        r = tool_fail("boom", error_type=ToolErrorType.TIMEOUT)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "boom")
        self.assertEqual(r.error_type, ToolErrorType.TIMEOUT)

    def test_to_json_serializable(self):
        from shared.tools.result import tool_ok
        import json
        r = tool_ok({"x": 1}, source_ids=["a"])
        s = r.to_json()
        d = json.loads(s)
        self.assertTrue(d["ok"])
        self.assertEqual(d["data"], {"x": 1})
        self.assertEqual(d["source_ids"], ["a"])


class TestExtractSourceIds(unittest.TestCase):
    """source_ids 提取逻辑。"""

    def test_nested_dict_with_event_id(self):
        from shared.tools.wrapper import _extract_source_ids
        data = {
            "ip": "1.2.3.4",
            "logs": [
                {"event_id": "ev1", "method": "GET"},
                {"event_id": "ev2", "method": "POST"},
            ],
        }
        ids = _extract_source_ids(data)
        self.assertIn("ev1", ids)
        self.assertIn("ev2", ids)

    def test_list_of_dicts_with_id(self):
        from shared.tools.wrapper import _extract_source_ids
        data = [{"id": "a"}, {"id": "b"}, {"other": 1}]
        ids = _extract_source_ids(data)
        self.assertIn("a", ids)
        self.assertIn("b", ids)

    def test_no_id_fields(self):
        from shared.tools.wrapper import _extract_source_ids
        ids = _extract_source_ids({"foo": "bar", "list": [1, 2, 3]})
        self.assertEqual(ids, [])

    def test_truncates_at_50(self):
        from shared.tools.wrapper import _extract_source_ids
        data = [{"event_id": f"e{i}"} for i in range(100)]
        ids = _extract_source_ids(data)
        self.assertEqual(len(ids), 50)


class TestWrapToolWithSpec(unittest.TestCase):
    """包装器:成功 / 超时 / 重试 / 非瞬时错误。"""

    def test_success_returns_tool_result_ok(self):
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolResult
        import json

        inner = _make_inner_tool(side_effect=lambda kw: {"echoed": kw["x"]})
        wrapped = wrap_tool_with_spec(inner, timeout_s=2.0, max_retries=0)
        result_str = asyncio.run(wrapped.ainvoke({"x": 42}))
        result = ToolResult(**json.loads(result_str))
        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"echoed": 42})
        self.assertGreater(result.duration_ms, 0)

    def test_timeout_returns_ok_false_with_timeout_error_type(self):
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolErrorType, ToolResult
        import json

        inner = _make_inner_tool(delay=0.5)
        wrapped = wrap_tool_with_spec(inner, timeout_s=0.1, max_retries=0)
        result_str = asyncio.run(wrapped.ainvoke({"x": 1}))
        result = ToolResult(**json.loads(result_str))
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, ToolErrorType.TIMEOUT)
        self.assertIn("timeout", result.error)

    def test_retry_succeeds_after_transient_error(self):
        """瞬时错误重试后第 N 次成功。"""
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolResult
        import json

        # 构造一个前 2 次抛 ConnectionError,第 3 次成功的工具
        call_count = {'n': 0}

        def side_effect(kw):
            call_count['n'] += 1
            if call_count['n'] < 3:
                raise ConnectionError("connection refused")
            return {"ok": True}

        inner = _make_inner_tool(side_effect=side_effect)
        wrapped = wrap_tool_with_spec(
            inner, timeout_s=2.0, max_retries=3,
            initial_delay=0.01, exponential_base=2.0,
        )
        result_str = asyncio.run(wrapped.ainvoke({"x": 1}))
        result = ToolResult(**json.loads(result_str))
        self.assertTrue(result.ok)
        self.assertEqual(call_count['n'], 3)

    def test_retry_exhausted_returns_retry_exhausted(self):
        """瞬时错误重试耗尽后返回 retry_exhausted。"""
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolErrorType, ToolResult
        import json

        inner = _make_inner_tool(raises=ConnectionError("network down"))
        wrapped = wrap_tool_with_spec(
            inner, timeout_s=2.0, max_retries=1,
            initial_delay=0.01, exponential_base=2.0,
        )
        result_str = asyncio.run(wrapped.ainvoke({"x": 1}))
        result = ToolResult(**json.loads(result_str))
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, ToolErrorType.RETRY_EXHAUSTED)

    def test_non_transient_error_not_retried(self):
        """非瞬时错误(ValueError)直接返回 execution_error,不重试。"""
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolErrorType, ToolResult
        import json

        call_count = {'n': 0}

        def side_effect(kw):
            call_count['n'] += 1
            raise ValueError("invalid input")  # 非瞬时

        inner = _make_inner_tool(side_effect=side_effect)
        wrapped = wrap_tool_with_spec(
            inner, timeout_s=2.0, max_retries=3,
            initial_delay=0.01, exponential_base=2.0,
        )
        result_str = asyncio.run(wrapped.ainvoke({"x": 1}))
        result = ToolResult(**json.loads(result_str))
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, ToolErrorType.EXECUTION_ERROR)
        self.assertEqual(call_count['n'], 1)  # 不重试

    def test_wrapped_tool_preserves_name_description_schema(self):
        """包装后 name/description/args_schema 与原工具一致(供 bind_tools)。"""
        from shared.tools.wrapper import wrap_tool_with_spec

        inner = _make_inner_tool(name="query_ip", description="queries ip")
        wrapped = wrap_tool_with_spec(inner, max_retries=0)
        self.assertEqual(wrapped.name, "query_ip")
        self.assertEqual(wrapped.description, "queries ip")
        # args_schema 应保留(原 inner.args_schema)
        self.assertIsNotNone(wrapped.args_schema)


class TestToolAudit(unittest.TestCase):
    """审计记录。"""

    def test_recorder_is_singleton(self):
        from shared.tools.audit import get_tool_audit_recorder
        a = get_tool_audit_recorder()
        b = get_tool_audit_recorder()
        self.assertIs(a, b)

    def test_success_writes_audit_record(self):
        from shared.tools.audit import get_tool_audit_recorder
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolResult
        import json

        inner = _make_inner_tool(side_effect=lambda kw: {"ok": True})
        wrapped = wrap_tool_with_spec(inner, max_retries=0, caller="test_node")
        rec = get_tool_audit_recorder()
        before = rec.get_summary()
        asyncio.run(wrapped.ainvoke({"x": 1}))
        after = rec.get_summary()
        self.assertEqual(after['total_calls'] - before['total_calls'], 1)
        self.assertEqual(after['ok_calls'] - before['ok_calls'], 1)

    def test_failure_writes_audit_with_error(self):
        from shared.tools.audit import get_tool_audit_recorder
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolResult
        import json

        inner = _make_inner_tool(raises=RuntimeError("boom"))
        wrapped = wrap_tool_with_spec(inner, max_retries=0)
        rec = get_tool_audit_recorder()
        before = rec.get_summary()
        asyncio.run(wrapped.ainvoke({"x": 1}))
        after = rec.get_summary()
        self.assertEqual(after['failed_calls'] - before['failed_calls'], 1)

    def test_audit_summary_by_tool(self):
        """by_tool 聚合正确。"""
        from shared.tools.audit import get_tool_audit_recorder
        from shared.tools.wrapper import wrap_tool_with_spec

        inner = _make_inner_tool(name="audit_test_tool", side_effect=lambda kw: {"r": 1})
        wrapped = wrap_tool_with_spec(inner, max_retries=0)
        asyncio.run(wrapped.ainvoke({"x": 1}))
        asyncio.run(wrapped.ainvoke({"x": 2}))
        rec = get_tool_audit_recorder()
        summary = rec.get_summary()
        self.assertIn("audit_test_tool", summary['by_tool'])
        self.assertGreaterEqual(summary['by_tool']['audit_test_tool']['calls'], 2)


class TestSourceIdsExtractionIntegration(unittest.TestCase):
    """端到端:工具返回的数据里 source_ids 被提取。"""

    def test_event_id_extracted_into_tool_result(self):
        from shared.tools.wrapper import wrap_tool_with_spec
        from shared.tools.result import ToolResult
        import json

        def side_effect(kw):
            return {
                "ip": "1.1.1.1",
                "logs": [
                    {"event_id": "ev_001", "path": "/"},
                    {"event_id": "ev_002", "path": "/login"},
                ],
            }

        inner = _make_inner_tool(name="query_ip_logs", side_effect=side_effect)
        wrapped = wrap_tool_with_spec(inner, max_retries=0)
        result_str = asyncio.run(wrapped.ainvoke({"x": 1}))
        result = ToolResult(**json.loads(result_str))
        self.assertTrue(result.ok)
        self.assertIn("ev_001", result.source_ids)
        self.assertIn("ev_002", result.source_ids)


if __name__ == "__main__":
    unittest.main()
