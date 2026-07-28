import unittest

from services.ruleEngine.main import build_pipeline
from services.ruleEngine.preprocessor.preprocessor import Preprocessor
from services.ruleEngine.preprocessor.structure_normalizer import LogValidationError


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = build_pipeline()
        self.base_log = {
            "event_id": "test-event-1",
            "ip": "192.168.1.10",
            "method": "get",
            "http_version": "1.1",
            "status": "200",
            "bytes": "1024",
            "referrer": "",
            "user_agent": "test-agent",
            "log_timestamp": 1720000000000,
        }

    def test_detects_doubly_url_encoded_sql_and_preserves_raw_path(self) -> None:
        event = self.pipeline.process({
            **self.base_log,
            "path": "/search?id=%2527%2520union%2520select",
        })

        self.assertIsNotNone(event)
        assert event is not None
        payload = event.to_dict()
        self.assertEqual(payload["attack_type"], "sql_injection")
        self.assertEqual(payload["detections"][0]["matches"][0]["pattern_id"], "union_select")
        self.assertEqual(payload["log_context"]["path"], "/search?id=%2527%2520union%2520select")
        self.assertEqual(payload["log_context"]["normalized_path"], "/search?id=' union select")

    def test_detects_html_and_unicode_escaped_xss(self) -> None:
        event = self.pipeline.process({
            **self.base_log,
            "path": "/search?q=\\u003cscript\\u003ealert(1)\\u003c/script\\u003e",
        })

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.detections[0].attack_type, "xss")

    def test_returns_no_event_for_a_normal_log(self) -> None:
        self.assertIsNone(self.pipeline.process({**self.base_log, "path": "/index.html"}))

    def test_rejects_missing_required_log_fields(self) -> None:
        with self.assertRaises(LogValidationError):
            Preprocessor().process({"event_id": "only-id"})


if __name__ == "__main__":
    unittest.main()
