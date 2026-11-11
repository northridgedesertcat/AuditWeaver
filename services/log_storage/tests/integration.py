"""Run against compose.log-storage-test.yml only: python -m services.log_storage.tests.integration."""
import json
import os
import subprocess
import sys
import time
import unittest
import uuid
from datetime import timedelta
from pathlib import Path

if os.environ.get("STORAGE_INTEGRATION_TEST") != "1":
    raise RuntimeError("Set STORAGE_INTEGRATION_TEST=1; this suite requires the disposable test compose")

TOKEN = uuid.uuid4().hex[:10]
os.environ.update({
    "CK_HOST": "localhost", "CK_HTTP_PORT": "28123", "CK_DATABASE": "storage_it_" + TOKEN,
    "CK_ADMIN_USER": "storage_test", "CK_ADMIN_PASSWORD": "isolated-test-only",
    "CK_WRITER_PASSWORD": "isolated-test-writer", "CK_READER_PASSWORD": "isolated-test-reader",
    "ES_HOST": "localhost", "ES_PORT": "29200", "MYSQL_HOST": "localhost", "MYSQL_PORT": "23306",
    "MYSQL_DATABASE": "storage_test", "MYSQL_USER": "root", "MYSQL_PASSWORD": "isolated-test-only",
    "KAFKA_BROKERS": "localhost:39092", "KAFKA_TOPIC_STRUCTURED": "storage-it-raw-" + TOKEN,
    "KAFKA_TOPIC_RULE_EVENTS": "storage-it-events-" + TOKEN,
    "KAFKA_TOPIC_STORAGE_QUARANTINE": "storage-it-quarantine-" + TOKEN,
    "DJANGO_SECRET_KEY": "isolated-storage-tests-only", "LOG_QUERY_CURSOR_SECRET": "isolated-storage-test-cursor",
    "STORAGE_ENABLED": "true", "LOG_QUERY_MODE": "es_legacy",
    "STORAGE_KAFKA_ADDRESS_FAMILY": "v4",
})

import yaml
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from common import env
from common.log_query import LogQueryService, QuerySpec, QueryUnavailable
from common.log_query.clients import ck_client, es_client
from common.log_query.types import utcnow
from services.log_storage.__main__ import initialize
from services.log_storage.archive import backfill, certify_coverage, certify_hot, cleanup
from services.log_storage.clickhouse import ClickHouseStore
from services.log_storage.contract import Source, normalize
from services.log_storage.metadata import DjangoMetadata, models, setup_django, topic_for

ROOT = Path(__file__).resolve().parents[3]


class StorageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_django()
        cls.es = es_client()
        if cls.es.info().get("cluster_name") != "auditweaver-storage-test":
            raise RuntimeError("Refusing to run against an ES instance without the disposable-test cluster marker")
        initialize()
        for index in cls.es.indices.get(index="auditweaver-raw-hot-*,auditweaver-events-hot-*", allow_no_indices=True):
            from services.log_storage.archive import index_window
            index_window(index)
            cls.es.indices.delete(index=index)
        cls.ck = ClickHouseStore()
        cls.meta = DjangoMetadata()
        cls.m = models()
        cls.now = utcnow()
        cls.processes, cls.handles = [], []
        cls.logs = ROOT / "logs/log-storage-integration"
        cls.logs.mkdir(parents=True, exist_ok=True)
        admin = AdminClient({"bootstrap.servers": env.KAFKA_BROKERS, "broker.address.family": "v4"})
        topics = [topic_for("raw"), topic_for("events"), env.get_env("KAFKA_TOPIC_STORAGE_QUARANTINE")]
        for future in admin.create_topics([NewTopic(t, 2, 1) for t in topics]).values():
            future.result(timeout=30)
        # Only the isolated ES instance is touched; use the project's actual mappings.
        for index in (env.ES_INDEX_NGINX_RAW, env.ES_INDEX_MATCHED_LOGS):
            if cls.es.indices.exists(index=index):
                cls.es.indices.delete(index=index)
            mapping = yaml.safe_load((ROOT / "docker/config/elasticsearch/mappings" / (index + ".yaml")).read_text(encoding="utf-8"))
            cls.es.indices.create(index=index, body=mapping)
        cls.producer = Producer({"bootstrap.servers": env.KAFKA_BROKERS, "acks": "all", "broker.address.family": "v4"})
        for sink in ("ck", "es"):
            for kind in ("raw", "events"):
                handle = (cls.logs / f"{TOKEN}-{sink}-{kind}.log").open("wb")
                cls.handles.append(handle)
                cls.processes.append(subprocess.Popen([sys.executable, "-m", "services.log_storage", "worker", "--sink", sink, "--kind", kind], cwd=ROOT,
                    stdout=handle, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))

    @classmethod
    def tearDownClass(cls):
        for process in cls.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
        for handle in cls.handles:
            handle.close()

    def send(self, kind, payload):
        errors = []
        self.producer.produce(topic_for(kind), key=payload["event_id"], value=json.dumps(payload),
                              on_delivery=lambda err, _: errors.append(err) if err else None)
        self.assertEqual(self.producer.flush(15), 0)
        self.assertFalse(errors)

    def wait_for(self, predicate, timeout=35):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for process in self.processes:
                self.assertIsNone(process.poll(), "Storage worker failed; inspect logs/log-storage-integration")
            if predicate():
                return
            time.sleep(0.25)
        self.fail("Storage did not reach the expected progress")

    def caught_up(self):
        cps = list(self.m.Checkpoint.objects.filter(topic__in=[topic_for("raw"), topic_for("events")]))
        return len(cps) == 8 and all(c.next_offset >= c.observed_next_offset for c in cps)

    def payload(self, rid, days=0):
        return {"event_id": TOKEN + rid, "@timestamp": (self.now - timedelta(days=days, hours=1)).isoformat(),
                "ip": "127.0.0.1", "method": "GET", "path": "/literal%_*?", "status": 200,
                "event": {"original": "integration original " + rid}}

    def test_01_real_consumers_archive_hot_and_late_records(self):
        self.__class__.hot, self.__class__.cold = self.payload("hot"), self.payload("cold", days=8)
        self.send("raw", self.hot)
        self.send("raw", self.hot)
        self.send("raw", self.cold)
        self.__class__.event = {"event_id": TOKEN + "event", "attack_type": "xss,sql_injection", "log_context": {
            "timestamp": int((self.now - timedelta(days=8)).timestamp() * 1000), "ip": "127.0.0.1", "path": "/attack", "method": "GET", "status": 200}}
        self.send("events", self.event)
        self.wait_for(lambda: len(self.ck.existing("raw", [self.hot["event_id"], self.cold["event_id"]])) == 2 and bool(self.ck.existing("events", [self.event["event_id"]])))
        self.wait_for(self.caught_up)
        self.es.indices.refresh(index="auditweaver-raw-hot")
        result = self.es.search(index="auditweaver-raw-hot", query={"term": {"event_id": self.hot["event_id"]}})
        self.assertEqual(len(result["hits"]["hits"]), 1)
        late = self.es.search(index="auditweaver-raw-hot", query={"term": {"event_id": self.cold["event_id"]}})
        self.assertEqual(len(late["hits"]["hits"]), 0)
        reader = LogQueryService(mode="hybrid").ck
        spec = QuerySpec("raw", self.now - timedelta(days=30), self.now)
        self.assertEqual(reader.count(spec, spec.start, spec.end), 2)

    def test_02_latest_event_version_filters_after_dedup(self):
        updated = {**self.event, "attack_type": "xss"}
        self.send("events", updated)
        self.wait_for(lambda: self.ck.existing("events", [self.event["event_id"]])[self.event["event_id"]]["attack_types"] == ["xss"])
        old = normalize("events", self.event)
        self.ck.write("events", [old])
        spec = QuerySpec("events", self.now - timedelta(days=30), self.now, {"attack_type": "sql_injection"})
        reader = LogQueryService(mode="hybrid").ck
        self.assertEqual(reader.count(spec, spec.start, spec.end), 0)
        self.assertGreaterEqual(self.m.EventOutbox.objects.filter(topic=topic_for("events")).count(), 2)

    def test_03_sealed_backfill_certification_and_cross_store_paging(self):
        for payload in (self.hot, self.cold):
            self.es.index(index=env.ES_INDEX_NGINX_RAW, id=payload["event_id"], document=payload)
        self.es.indices.add_block(index=env.ES_INDEX_NGINX_RAW, block="write")
        self.es.indices.refresh(index=env.ES_INDEX_NGINX_RAW)
        result = backfill(self.es, self.ck, env.ES_INDEX_NGINX_RAW, "raw", self.now - timedelta(days=90), self.now, copy_hot=True)
        self.assertEqual(result["records"], 2)
        self.wait_for(self.caught_up)
        handoff = {f"{topic_for('raw')}:{c.partition}": c.next_offset for c in self.m.Checkpoint.objects.filter(sink="ck", topic=topic_for("raw"))}
        certify_hot(self.es, "raw", handoff)
        certify_coverage(self.es, self.ck, self.meta, "raw", self.now - timedelta(days=90), handoff)
        service = LogQueryService(mode="hybrid")
        spec = QuerySpec("raw", self.now - timedelta(days=30), self.now, {"path": "%_*?"})
        first = service.search(spec, limit=1)
        self.assertTrue(first["has_more"])
        second = service.search(spec, limit=1, cursor=first["next_cursor"])
        self.assertEqual([first["data"][0]["event_id"], second["data"][0]["event_id"]], [self.hot["event_id"], self.cold["event_id"]])
        self.assertFalse(second["has_more"])
        self.assertEqual(service.aggregate(spec)["total"], 2)
        self.assertEqual(service.get_log(self.cold["event_id"], self.cold["@timestamp"])["data"]["event"]["original"], self.cold["event_id"].replace(TOKEN, "integration original "))

    def test_04_safe_cleanup_only_after_verification(self):
        from services.log_storage.archive import index_window
        from services.log_storage.hot import ALIASES
        row = normalize("raw", self.cold)
        index = ALIASES["raw"] + row["event_time"].strftime("-%Y.%m.%d")
        source = json.loads(row["raw_payload"])
        source["_storage"] = {k: row[k] for k in ("record_id", "payload_hash", "source_kind", "source_topic", "source_partition", "source_offset", "version")}
        self.es.index(index=index, id=row["record_id"], document=source)
        self.assertTrue(cleanup(self.es, self.ck, self.meta, index)["dry_run"])
        self.assertTrue(self.es.indices.exists(index=index))
        with self.assertRaises(ValueError):
            cleanup(self.es, self.ck, self.meta, "nginx-log-raw", execute=True)
        os.environ.update(ES_CLEANUP_ENABLED="true", ES_CLEANUP_DRY_RUN="false")
        with self.assertRaises(ValueError):
            cleanup(self.es, self.ck, self.meta, index, execute=True)
        backup = {"backup_id": "TEST-FIXTURE-NO-PRODUCTION-BACKUP", "covered_until": self.now.isoformat(), "restore_tested_at": self.now.isoformat()}
        result = cleanup(self.es, self.ck, self.meta, index, execute=True, backup=backup)
        self.assertEqual(result["state"], "DELETED")
        self.assertFalse(self.es.indices.exists(index=index))
        self.assertIn(self.cold["event_id"], self.ck.existing("raw", [self.cold["event_id"]]))

    def test_05_rag_notification_includes_late_events(self):
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / "services/agent_service"))
        from shared.rag import case_sync
        index = "storage-it-corpus-" + TOKEN
        self.es.indices.create(index=index, mappings={"properties": {
            "source_type": {"type": "keyword"}, "created_at": {"type": "date", "format": "epoch_millis"},
            "raw": {"type": "object", "enabled": False}, "embedding": {"type": "dense_vector", "dims": 2},
        }})
        self.es.index(index=index, id="__meta__storage_case_sync", document={"bootstrapped": True})
        late = {**self.event, "event_id": TOKEN + "late-event", "attack_type": "xss",
                "log_context": {**self.event["log_context"], "timestamp": int((self.now - timedelta(days=20)).timestamp() * 1000)}}
        self.send("events", late)
        self.wait_for(lambda: bool(self.ck.existing("events", [late["event_id"]])))
        with patch.object(case_sync, "embed_batch", side_effect=lambda texts: [[1.0, 0.0] for _ in texts]):
            result = case_sync.sync_storage_once(self.es, index, window_days=90, batch_size=50)
        self.assertGreaterEqual(result["written"], 2)
        self.es.indices.refresh(index=index)
        doc = self.es.get(index=index, id=late["event_id"])["_source"]
        self.assertEqual(doc["raw"]["event_id"], late["event_id"])
        self.assertFalse(self.m.EventOutbox.objects.filter(topic=topic_for("events"), processed_at__isnull=True).exists())

    def test_06_ck_down_keeps_hot_queries_working_and_blocks_history(self):
        from unittest.mock import Mock
        self.wait_for(self.caught_up)
        unavailable = Mock()
        unavailable.fetch.side_effect = ConnectionError("CK unavailable")
        service = LogQueryService(mode="hybrid", ck=unavailable)
        hot = QuerySpec("raw", self.now - timedelta(days=1), self.now)
        self.assertEqual(service.search(hot)["data"][0]["event_id"], self.hot["event_id"])
        cold = QuerySpec("raw", self.now - timedelta(days=30), self.now - timedelta(days=7))
        with self.assertRaises(QueryUnavailable):
            service.search(cold)

    def test_07_real_millisecond_boundaries_and_equal_time_cursors(self):
        from services.log_storage.hot import HotStore
        from common.log_query.types import parse_time
        now = parse_time(self.now)
        boundary = now - timedelta(days=7)
        path = "/boundary-" + TOKEN
        rows = []
        for suffix, delta in (("cold1", -1), ("cold2", -1), ("at", 0), ("hot", 1)):
            payload = self.payload("boundary-" + suffix)
            payload.update({"@timestamp": (boundary + timedelta(milliseconds=delta)).isoformat(), "path": path})
            rows.append(normalize("raw", payload))
        self.ck.write("raw", rows)
        HotStore(self.es, clock=lambda: now).write("raw", rows)
        self.es.indices.refresh(index="auditweaver-raw-hot")
        service = LogQueryService(mode="hybrid", clock=lambda: now)
        spec = QuerySpec("raw", boundary - timedelta(milliseconds=2), boundary + timedelta(milliseconds=2), {"path": path})
        ids, cursor = [], None
        while True:
            result = service.search(spec, limit=1, cursor=cursor)
            ids.extend(row["event_id"] for row in result["data"])
            cursor = result["next_cursor"]
            if not cursor:
                break
        self.assertEqual(ids, [TOKEN + "boundary-hot", TOKEN + "boundary-at", TOKEN + "boundary-cold2", TOKEN + "boundary-cold1"])
        self.assertEqual(service.aggregate(spec)["total"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
