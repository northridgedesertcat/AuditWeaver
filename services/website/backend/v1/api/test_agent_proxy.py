import json
import os
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .views import AgentProxyView


@override_settings(AGENT_FASTAPI_BASE="http://127.0.0.1:8001")
class AgentProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AgentProxyView()
        self.post_request = self.factory.post(
            "/api/v1/agent/analysis_explorer/chat/",
            {"message": "hello"},
            format="json",
            HTTP_ACCEPT="text/event-stream",
        )

    @patch.dict(os.environ, {"ALL_PROXY": "socks5://127.0.0.1:1080", "NO_PROXY": ""})
    def test_stream_does_not_use_environment_proxy(self):
        def handler(request):
            self.assertEqual(str(request.url), "http://127.0.0.1:8001/agent/analysis_explorer/chat/")
            self.assertEqual(json.loads(request.content), {"message": "hello"})
            return httpx.Response(200, text='data: {"type":"done"}\n\n', headers={
                "content-type": "text/event-stream",
            })

        # Install a direct mock transport without changing client/proxy selection.
        with patch.object(httpx.Client, "_init_transport", return_value=httpx.MockTransport(handler)):
            response = self.view.post(self.post_request)
            try:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Content-Type"], "text/event-stream")
                self.assertEqual(b"".join(response.streaming_content), b'data: {"type":"done"}\n\n')
            finally:
                response.close()

    def test_connection_error_returns_502(self):
        with patch("api.views.httpx.Client.send", side_effect=httpx.ConnectError("unavailable")):
            response = self.view.post(self.post_request)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(json.loads(response.content)["error"], "agent service unavailable")

    def test_health_uses_direct_connection(self):
        request = self.factory.get("/api/v1/agent/health/")
        with patch("api.views.httpx.get", return_value=httpx.Response(200, json={"status": "ok"})) as get:
            response = self.view.get(request)
        get.assert_called_once_with("http://127.0.0.1:8001/agent/health/", timeout=10, trust_env=False)
        self.assertEqual(response.status_code, 200)

    def test_non_json_health_response_returns_502(self):
        request = self.factory.get("/api/v1/agent/health/")
        with patch("api.views.httpx.get", return_value=httpx.Response(500, text="upstream error")):
            response = self.view.get(request)
        self.assertEqual(response.status_code, 502)
