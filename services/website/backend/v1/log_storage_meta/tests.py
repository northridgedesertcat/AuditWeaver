from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from common.log_query import QueryUnavailable
from common.log_query.types import utcnow
from services.log_storage.metadata import DjangoMetadata, topic_for, source_identity
from .models import Checkpoint, CoverageWindow, EventOutbox, Gap


class MetadataTests(TestCase):
    def setUp(self):
        self.meta = DjangoMetadata()
        self.now = utcnow()
        self.topic = topic_for("raw")
        Checkpoint.objects.create(sink="ck", topic=self.topic, partition=0, partition_count=1,
            initial_offset=5, next_offset=10, observed_next_offset=10, checked_at=self.now)
        CoverageWindow.objects.create(kind="raw", start_time=self.now - timedelta(days=90), end_time=self.now,
            verified=True, evidence={"live": True, "source_id": source_identity("raw", "ck"), "generation": "v1", "handoff": {"0": 7}})

    def test_fresh_caught_up_progress_has_coverage(self):
        result = self.meta.coverage("raw", self.now - timedelta(days=30), self.now)
        self.assertTrue(result["complete"])

    def test_stale_or_lagging_checkpoint_blocks_coverage(self):
        for changes in ({"observed_next_offset": 11}, {"checked_at": self.now - timedelta(minutes=2)}):
            with self.subTest(changes=changes):
                Checkpoint.objects.filter(topic=self.topic).update(**changes)
                with self.assertRaises(QueryUnavailable):
                    self.meta.coverage("raw", self.now - timedelta(days=30), self.now)

    def test_gap_and_missing_history_are_not_complete(self):
        Gap.objects.create(sink="ck", topic=self.topic, partition=0, offset=8, error="bad")
        with self.assertRaises(QueryUnavailable):
            self.meta.coverage("raw", self.now - timedelta(days=30), self.now)
        Gap.objects.all().delete()
        CoverageWindow.objects.all().delete()
        with self.assertRaises(QueryUnavailable):
            self.meta.coverage("raw", self.now - timedelta(days=30), self.now)

    def test_evidence_from_another_storage_does_not_grant_coverage(self):
        CoverageWindow.objects.update(evidence={"live": True, "source_id": "another-database", "generation": "v1", "handoff": {"0": 7}})
        with self.assertRaises(QueryUnavailable):
            self.meta.coverage("raw", self.now - timedelta(days=30), self.now)

    def test_kafka_retention_and_partition_changes_are_blocked(self):
        with self.assertRaises(QueryUnavailable):
            self.meta.observe("ck", self.topic, 0, 11, 12, 1)
        with self.assertRaises(QueryUnavailable):
            self.meta.observe("ck", self.topic, 0, 0, 12, 2)

    def test_checkpoint_and_event_outbox_share_transaction(self):
        rows = [{"source_topic": "events", "source_partition": 0, "source_offset": 5,
                 "record_id": "e1", "event_time": self.now}]
        with patch.object(EventOutbox.objects, "get_or_create", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                self.meta.advance("ck", "events", rows, {("events", 0): 6})
        self.assertFalse(Checkpoint.objects.filter(topic="events").exists())
        self.meta.advance("ck", "events", rows, {("events", 0): 6})
        self.meta.advance("ck", "events", rows, {("events", 0): 6})
        self.assertEqual(EventOutbox.objects.count(), 1)


class ApiTests(TestCase):
    def request(self, path):
        from api.log_views import LogsView
        request = APIRequestFactory().get(path)
        force_authenticate(request, user=Mock(is_authenticated=True))
        return LogsView.as_view()(request)

    def test_unauthenticated_requests_are_rejected(self):
        from api.log_views import LogsView
        response = LogsView.as_view()(APIRequestFactory().get("/logs/"))
        self.assertEqual(response.status_code, 401)

    def test_unavailable_storage_returns_503_and_incomplete_coverage(self):
        with patch("api.log_views.get_log_query_service") as factory:
            factory.return_value.search.side_effect = QueryUnavailable("archive behind")
            response = self.request("/logs/")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.data["coverage"]["complete"])

    def test_invalid_pagination_returns_400(self):
        for query in ("size=bad", "page=0", "page=11"):
            with patch("api.log_views.get_log_query_service"):
                response = self.request("/logs/?" + query)
            self.assertEqual(response.status_code, 400)
