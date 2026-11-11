import json
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from common.log_query import QueryError, QueryUnavailable
from services.log_storage.hot import HotStore
from services.log_storage.worker import persist_batch
from services.log_storage.tests.test_contract import NOW, raw


def message(offset, payload=None):
    msg = Mock()
    msg.topic.return_value, msg.partition.return_value, msg.offset.return_value = "log.structured", 0, offset
    msg.timestamp.return_value = (1, int(NOW.timestamp() * 1000))
    msg.key.return_value = b"e1"
    msg.value.return_value = json.dumps(payload if payload is not None else raw()).encode()
    return msg


class WorkerTests(unittest.TestCase):
    def setUp(self):
        clock = patch("services.log_storage.contract.utcnow", return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)

    def test_write_before_checkpoint_and_continuous_positions(self):
        calls = []
        store, meta, quarantine = Mock(), Mock(), Mock()
        store.write.side_effect = lambda *_: calls.append("write")
        meta.advance.side_effect = lambda *_: calls.append("checkpoint")
        positions = persist_batch("ck", "raw", [message(0), message(1)], store, meta, quarantine)
        self.assertEqual(calls, ["write", "checkpoint"])
        self.assertEqual(positions, {("log.structured", 0): 2})

    def test_storage_failure_never_advances_checkpoint(self):
        store, meta = Mock(), Mock()
        store.write.side_effect = RuntimeError("offline")
        with self.assertRaises(RuntimeError):
            persist_batch("ck", "raw", [message(0)], store, meta, Mock())
        meta.advance.assert_not_called()

    def test_bad_json_records_gap_and_keeps_offset(self):
        msg, meta, quarantine, store = message(0), Mock(), Mock(), Mock()
        msg.value.return_value = b"{broken"
        with self.assertRaises(QueryError):
            persist_batch("ck", "raw", [msg], store, meta, quarantine)
        meta.gap.assert_called_once()
        quarantine.assert_called_once()
        meta.advance.assert_not_called()
        store.write.assert_not_called()

    def test_identity_conflicts_are_quarantined_without_advancing(self):
        store, meta, quarantine = Mock(), Mock(), Mock()
        store.write.side_effect = QueryError("conflicting identity")
        with self.assertRaises(QueryError):
            persist_batch("ck", "raw", [message(0)], store, meta, quarantine)
        meta.gap.assert_called_once()
        quarantine.assert_called_once()
        meta.advance.assert_not_called()

    def test_partial_bulk_failure_is_not_success(self):
        es = Mock()
        es.mget.return_value = {"docs": [{"found": False}]}
        es.bulk.return_value = {"items": [{"index": {"status": 429, "error": "overload"}}]}
        from services.log_storage.contract import Source, normalize
        row = normalize("raw", raw(), Source("t", 0, 0), now=NOW)
        with self.assertRaises(QueryUnavailable):
            HotStore(es, clock=lambda: NOW).write("raw", [row])

    def test_late_record_does_not_recreate_hot_index(self):
        es = Mock()
        from services.log_storage.contract import Source, normalize
        row = normalize("raw", raw(when=NOW - timedelta(days=8)), Source("t", 0, 0), now=NOW)
        HotStore(es, clock=lambda: NOW).write("raw", [row])
        es.bulk.assert_not_called()
