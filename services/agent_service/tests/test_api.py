"""FastAPI 接口冒烟测试(需安装 fastapi / httpx;不触发 LLM 与 MCP)。

覆盖:/agent/health、/agent/types、未知 agent_type 404、请求校验 422。
不覆盖 /chat(会调 LLM,需真实配置,留待联调)。

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_api
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


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from backend.main import app
        cls.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/agent/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_types(self):
        r = self.client.get("/agent/types")
        self.assertEqual(r.status_code, 200)
        self.assertIn("analysis_explorer", r.json()["types"])

    def test_unknown_agent_404(self):
        r = self.client.post(
            "/agent/nope/chat/sync",
            json={"message": "hi", "thread_id": "t1", "history": []},
        )
        self.assertEqual(r.status_code, 404)

    def test_chat_sync_request_validation(self):
        # 缺 message 字段 → 422,不触达 agent / LLM
        r = self.client.post(
            "/agent/analysis_explorer/chat/sync",
            json={"thread_id": "t1"},
        )
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
