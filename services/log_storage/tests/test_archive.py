import unittest
from datetime import timedelta
from unittest.mock import Mock

from common.log_query import QueryError, QueryUnavailable
from services.log_storage.archive import cleanup, index_window, verified_row
from services.log_storage.contract import Source, normalize
from services.log_storage.tests.test_contract import NOW, raw


class ArchiveTests(unittest.TestCase):
    def test_exact_whitelist_rejects_wildcard_and_legacy_indexes(self):
        for name in ("*", "auditweaver-raw-hot-*", "nginx-log-raw", "matched_logs", "auditweaver-raw-hot-2026.13.01"):
            with self.assertRaises(ValueError):
                index_window(name)

    def test_dry_run_has_no_mutations(self):
        es, ck, metadata = Mock(), Mock(), Mock()
        result = cleanup(es, ck, metadata, "auditweaver-raw-hot-2020.01.01")
        self.assertTrue(result["dry_run"])
        self.assertEqual(es.mock_calls, [])
        self.assertEqual(ck.mock_calls, [])
        self.assertEqual(metadata.mock_calls, [])

    def test_larger_version_without_source_proof_does_not_verify(self):
        payload = {"event_id": "e", "attack_type": "xss", "log_context": {"timestamp": NOW.isoformat()}}
        expected = normalize("events", payload, now=NOW)
        newer = normalize("events", {**payload, "attack_type": "sql_injection"}, Source("events", 0, 42), now=NOW)
        with self.assertRaises(QueryUnavailable):
            verified_row("events", expected, newer)
        verified_row("events", expected, newer, {"events:0": 40})

    def test_matching_content_from_different_partition_does_not_verify(self):
        expected = normalize("raw", raw(), Source("raw", 0, 1), now=NOW)
        other = normalize("raw", raw(), Source("raw", 1, 99), now=NOW)
        with self.assertRaises(QueryUnavailable):
            verified_row("raw", expected, other)

    def test_conflicting_legacy_event_versions_are_rejected(self):
        from services.log_storage.contract import check_identity
        payload = {"event_id": "e", "attack_type": "xss", "log_context": {"timestamp": NOW.isoformat()}}
        expected = normalize("events", payload, now=NOW)
        other = normalize("events", {**payload, "attack_type": "sql_injection"}, now=NOW)
        with self.assertRaises(QueryError):
            check_identity("events", expected, other)
