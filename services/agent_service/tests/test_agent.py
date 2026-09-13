"""Analysis Explorer Agent 注册冒烟测试(需安装 langchain / langgraph)。

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_agent
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


class TestRegistry(unittest.TestCase):
    def test_analysis_explorer_registered(self):
        import agents  # noqa: F401  触发注册
        from registry import list_agent_types
        self.assertIn("analysis_explorer", list_agent_types())

    def test_build_graph_returns_compiled(self):
        from langgraph.graph.state import CompiledStateGraph
        from registry import get_agent
        graph = get_agent("analysis_explorer")
        self.assertIsInstance(graph, CompiledStateGraph)

    def test_unknown_agent_raises(self):
        from registry import get_agent
        with self.assertRaises(ValueError):
            get_agent("nope")


if __name__ == "__main__":
    unittest.main()
