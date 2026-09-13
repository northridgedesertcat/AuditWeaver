"""Skills 单元测试(mock ES,不依赖真实集群)。

运行(项目根目录):
    python -m unittest services.agent_service.tests.test_skills
"""
import unittest
from unittest.mock import patch


class TestTimeRange(unittest.TestCase):
    def test_parse_time_range_hour(self):
        from common.time_utils import parse_time_range
        gte, lte = parse_time_range("1h")
        self.assertLess(gte, lte)
        self.assertAlmostEqual(lte - gte, 3_600_000, delta=2000)

    def test_parse_time_range_all(self):
        from common.time_utils import parse_time_range
        gte, lte = parse_time_range("all")
        self.assertEqual(gte, 0)
        self.assertGreater(lte, 0)


class TestQueryIPLogs(unittest.TestCase):
    def test_returns_structure_and_strips_es_fields(self):
        from services.agent_service.skills import query_ip_logs as mod
        fake = {
            "hits": {
                "total": {"value": 1},
                "hits": [{
                    "_source": {
                        "@timestamp": 1726370000000,
                        "method": "POST",
                        "path": "/login",
                        "status": 401,
                        "user_agent": "curl",
                        "event_id": "e1",
                    },
                    "_score": 1.0,
                    "_index": "nginx-log-raw",
                }],
            }
        }
        with patch.object(mod, "search", return_value=fake):
            r = mod.query_ip_logs("192.168.1.100", "24h", 10)
        self.assertEqual(r["ip"], "192.168.1.100")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["returned"], 1)
        self.assertEqual(len(r["logs"]), 1)
        log = r["logs"][0]
        self.assertEqual(log["event_id"], "e1")
        self.assertEqual(log["status"], 401)
        self.assertNotIn("_score", log)
        self.assertNotIn("_index", log)

    def test_es_unavailable(self):
        from services.agent_service.skills import query_ip_logs as mod
        with patch.object(mod, "search", return_value=None):
            r = mod.query_ip_logs("10.0.0.1", "24h", 5)
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["logs"], [])
        self.assertIn("error", r)


class TestQueryAnalysisResults(unittest.TestCase):
    def test_structure(self):
        from services.agent_service.skills import query_analysis_results as mod
        fake = {
            "hits": {
                "total": {"value": 1},
                "hits": [{
                    "_source": {
                        "event_id": "e2", "ip": "1.2.3.4",
                        "attack_type_ai": "Brute Force", "risk_level": "High",
                        "risk_score": 80, "summary": "疑似暴力破解",
                        "analysis_timestamp": 1726370000000,
                    }
                }],
            }
        }
        with patch.object(mod, "search", return_value=fake):
            r = mod.query_analysis_results(ip="1.2.3.4", risk_level="High")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["reports"][0]["risk_level"], "High")
        self.assertNotIn("_score", r["reports"][0])


class TestQuerySecurityEvents(unittest.TestCase):
    def test_structure_and_nested_extract(self):
        from services.agent_service.skills import query_security_events as mod
        fake = {
            "hits": {
                "total": {"value": 1},
                "hits": [{
                    "_source": {
                        "event_id": "e3", "attack_type": "sql_injection",
                        "log_context": {
                            "ip": "5.6.7.8", "path": "/?id=1", "method": "GET",
                            "status": 200, "timestamp": 1726370000000,
                        },
                        "detections": [{
                            "rule_id": "r1",
                            "matches": [{"matched_value": "1' OR '1'='1"}],
                        }],
                    }
                }],
            }
        }
        with patch.object(mod, "search", return_value=fake):
            r = mod.query_security_events(attack_type="sql_injection")
        ev = r["events"][0]
        self.assertEqual(ev["attack_type"], "sql_injection")
        self.assertEqual(ev["rule_id"], "r1")
        self.assertEqual(ev["matched_value"], "1' OR '1'='1")
        self.assertNotIn("_score", ev)


if __name__ == "__main__":
    unittest.main()
