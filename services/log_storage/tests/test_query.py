import unittest
from datetime import timedelta
from unittest.mock import Mock

from common.log_query import LogQueryService, QueryError, QuerySpec, QueryUnavailable
from common.log_query.adapters import ClickHouseReader, ElasticsearchReader
from services.log_storage.tests.test_contract import NOW


class MemoryReader:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fetch(self, spec, start, end, limit, after=None, pit=None, hot=False):
        self.calls.append((start, end, hot))
        rows = [r for r in self.rows if start <= r[0] < end and (not after or [r[0].isoformat(), r[1]] < after)]
        rows.sort(reverse=True)
        return [{"payload": {"event_id": rid}, "after": [when.isoformat(), rid]} for when, rid in rows[:limit]], None

    def close(self, pit):
        pass


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.boundary = NOW - timedelta(days=7)
        self.es = MemoryReader([(self.boundary, "at"), (self.boundary + timedelta(milliseconds=1), "new"), (NOW - timedelta(hours=1), "latest")])
        self.ck = MemoryReader([(self.boundary - timedelta(milliseconds=1), "old"), (self.boundary - timedelta(milliseconds=1), "old2")])
        self.meta = Mock()
        self.meta.coverage.return_value = {"complete": True}
        self.service = LogQueryService(self.es, self.ck, self.meta, mode="hybrid", secret="test", clock=lambda: NOW)
        self.spec = QuerySpec("raw", NOW - timedelta(days=30), NOW)

    def test_boundary_and_cursor_no_loss_at_equal_millisecond(self):
        cursor, ids = None, []
        while True:
            page = self.service.search(self.spec, limit=2, cursor=cursor)
            ids.extend(r["event_id"] for r in page["data"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        self.assertEqual(ids, ["latest", "new", "at", "old2", "old"])
        self.assertEqual(self.es.calls[0][0], self.boundary)
        self.assertEqual(self.ck.calls[0][1], self.boundary)

    def test_pure_hot_does_not_initialize_ck_or_check_coverage(self):
        self.service.search(QuerySpec("raw", NOW - timedelta(days=1), NOW))
        self.meta.coverage.assert_not_called()
        self.assertEqual(self.ck.calls, [])

    def test_pure_cold_does_not_call_es(self):
        self.service.search(QuerySpec("raw", NOW - timedelta(days=30), NOW - timedelta(days=8)))
        self.assertEqual(self.es.calls, [])

    def test_coverage_failure_is_not_empty_success(self):
        self.meta.coverage.side_effect = QueryUnavailable("behind")
        with self.assertRaises(QueryUnavailable):
            self.service.search(self.spec)

    def test_cursor_signature_filter_mode_and_expiry(self):
        cursor = self.service.search(self.spec, limit=1)["next_cursor"]
        for invalid in (cursor + "x", "invalid"):
            with self.assertRaises(QueryError):
                self.service.search(self.spec, cursor=invalid)
        with self.assertRaises(QueryError):
            self.service.search(QuerySpec("raw", self.spec.start, self.spec.end, {"method": "GET"}), cursor=cursor)
        self.service.clock = lambda: NOW + timedelta(minutes=10)
        with self.assertRaises(QueryError):
            self.service.search(self.spec, cursor=cursor)

    def test_transition_uses_legacy_for_cold(self):
        self.service.mode = "transition"
        self.service.search(self.spec)
        self.assertEqual([r[2] for r in self.es.calls], [True, False])
        self.assertEqual(self.ck.calls, [])

    def test_aggregate_uses_ck_once_for_whole_range(self):
        ck = Mock()
        ck.count.return_value = 15
        ck.groups.return_value = [("/a", 9), ("/b", 6)]
        self.service._ck = ck
        result = self.service.aggregate(self.spec, dimensions=("path",))
        self.assertEqual(result["total"], 15)
        ck.count.assert_called_once()
        self.assertEqual(self.es.calls, [])

    def test_sql_values_are_bound_and_final_is_used(self):
        client = Mock()
        client.query.return_value.result_rows = []
        reader = ClickHouseReader(client)
        spec = QuerySpec("raw", self.spec.start, NOW, {"path": "%' OR 1=1 --"})
        reader.fetch(spec, spec.start, spec.end, 10)
        sql = client.query.call_args.args[0]
        self.assertIn(" FINAL ", sql)
        self.assertNotIn("OR 1=1", sql)
        self.assertEqual(client.query.call_args.kwargs["parameters"]["path"], "%' OR 1=1 --")

    def test_ck_timestamp_parameters_keep_millisecond_precision(self):
        client = Mock()
        client.query.return_value.result_rows = []
        reader = ClickHouseReader(client)
        start = NOW - timedelta(milliseconds=1)
        spec = QuerySpec("raw", start, NOW)
        reader.fetch(spec, start, NOW, 10, after=[start.isoformat(), "id"])
        params = client.query.call_args.kwargs["parameters"]
        self.assertTrue(params["start"].endswith(".999000"))
        self.assertTrue(params["last"].endswith(".999000"))

    def test_literal_es_wildcard_is_escaped(self):
        reader = ElasticsearchReader(Mock())
        spec = QuerySpec("raw", self.spec.start, NOW, {"path": "*?%_"})
        query = reader.query(spec, spec.start, spec.end, True)
        self.assertEqual(query["bool"]["filter"][1]["wildcard"]["path"]["value"], "*\\*\\?%_*")
