import unittest
from datetime import timedelta

from common.log_query.types import QueryError, QuerySpec, parse_time
from services.log_storage.contract import Source, check_identity, normalize

NOW = parse_time("2026-11-11T12:00:00Z")


def raw(event_id="e1", when=NOW, **extra):
    return {"event_id": event_id, "@timestamp": when.isoformat(), "ip": "127.0.0.1", "method": "GET", "path": "/a%_?b=*", "status": 200,
            "event": {"original": "original access line"}, **extra}


class ContractTests(unittest.TestCase):
    def test_timestamp_requires_timezone_and_millis(self):
        for value in (None, "bad", "2026-01-01", "2026-11-11T12:00:00"):
            with self.subTest(value=value), self.assertRaises(QueryError):
                parse_time(value)
        self.assertEqual(parse_time(1794398400000), NOW)

    def test_raw_payload_round_trip_and_replay_stability(self):
        source = Source("log.structured", 0, 12)
        first = normalize("raw", raw(), source, now=NOW)
        second = normalize("raw", raw(), source, now=NOW + timedelta(seconds=2))
        self.assertEqual(first["version"], 14)
        self.assertEqual(first["payload_hash"], second["payload_hash"])
        self.assertEqual(first["raw_payload"], second["raw_payload"])
        self.assertIn("original access line", first["raw_payload"])

    def test_invalid_records_are_rejected(self):
        for value in (raw(event_id=""), raw(when=NOW + timedelta(minutes=6)), raw(status=-1), raw(ip="invalid")):
            with self.subTest(value=value), self.assertRaises((QueryError, ValueError)):
                normalize("raw", value, Source("log.structured", 0, 0), now=NOW)

    def test_legacy_key_and_low_version(self):
        payload = raw()
        del payload["event_id"]
        row = normalize("raw", payload, legacy_id="legacy:index:doc", now=NOW)
        self.assertEqual((row["record_id"], row["version"]), ("legacy:index:doc", 1))

    def test_identity_and_source_partition_invariants(self):
        first = normalize("raw", raw(), Source("topic", 0, 2), now=NOW)
        changed = normalize("raw", raw(path="/different"), Source("topic", 0, 3), now=NOW)
        with self.assertRaises(QueryError):
            check_identity("raw", first, changed)
        changed = normalize("raw", raw(), Source("topic", 1, 3), now=NOW)
        with self.assertRaises(QueryError):
            check_identity("raw", first, changed)

    def test_attack_types_are_exact_tokens(self):
        row = normalize("events", {"event_id": "e", "attack_type": "xss, sql_injection,xss", "log_context": {"timestamp": int(NOW.timestamp() * 1000)}}, Source("events", 0, 1), now=NOW)
        self.assertEqual(row["attack_types"], ["sql_injection", "xss"])

    def test_filter_validation(self):
        for filters in ({"table": "arbitrary"}, {"status": "invalid"}, {"ip": "bad"}):
            with self.assertRaises(QueryError):
                QuerySpec("raw", NOW - timedelta(days=1), NOW, filters)

    def test_clickhouse_driver_utc_and_fixed_string_decoding(self):
        from unittest.mock import Mock
        from services.log_storage.clickhouse import ClickHouseStore
        source = normalize("raw", raw(), now=NOW)
        encoded = {**source, "event_time": source["event_time"].replace(tzinfo=None), "payload_hash": source["payload_hash"].encode("ascii")}
        client = Mock()
        client.query.return_value.named_results.return_value = iter([encoded])
        decoded = ClickHouseStore(client).existing("raw", [source["record_id"]])[source["record_id"]]
        check_identity("raw", decoded, source)
