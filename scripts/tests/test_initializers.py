from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("es_mapping_initializer", ROOT / "docker/config/elasticsearch/creatMapping.py")
mapping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapping)


class MappingTests(unittest.TestCase):
    def test_existing_index_is_successful_without_deletion(self):
        es = Mock()
        es.indices.exists.return_value = True
        with redirect_stdout(io.StringIO()):
            self.assertTrue(mapping.create_index(es, "test-index", {}))
        es.indices.delete.assert_not_called()
        es.indices.create.assert_not_called()

    def test_new_index_failure_is_reported(self):
        es = Mock()
        es.indices.exists.return_value = False
        es.indices.create.side_effect = RuntimeError("index failure")
        with redirect_stdout(io.StringIO()):
            self.assertFalse(mapping.create_index(es, "test-index", {}))

    def test_invalid_mapping_does_not_get_silently_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "broken.yaml").write_text("mapping: [", encoding="utf-8")
            with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                mapping.load_mappings_from_dir(directory)

    def test_main_returns_failure_if_any_index_fails(self):
        es = Mock()
        with patch("sys.argv", ["creatMapping.py"]), patch.object(mapping, "get_es_client", return_value=es), \
                patch.object(mapping, "load_mappings_from_dir", return_value=[("one", {}), ("two", {})]), \
                patch.object(mapping, "create_index", side_effect=[True, False]), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                mapping.main()
        self.assertEqual(result.exception.code, 1)
        es.close.assert_called_once()


class ComposeContractTests(unittest.TestCase):
    def setUp(self):
        self.services = yaml.safe_load((ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8"))["services"]

    def test_dependencies_with_health_checks_are_waited_for(self):
        for name in ("zookeeper", "kafka", "kafka-connect", "elasticsearch", "mysql", "redis"):
            self.assertIn("healthcheck", self.services[name], name)
        for service, dependency in (("kafka", "zookeeper"), ("kafka-connect", "kafka"),
                                    ("logstash", "kafka"), ("logstash", "elasticsearch")):
            self.assertEqual(self.services[service]["depends_on"][dependency]["condition"], "service_healthy")

    def test_kibana_is_optional(self):
        self.assertEqual(self.services["kibana"]["profiles"], ["tools"])


if __name__ == "__main__":
    unittest.main()
