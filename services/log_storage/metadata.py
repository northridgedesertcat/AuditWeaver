from __future__ import annotations

import os
import sys
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from common import env
from common.log_query.types import QueryUnavailable, utcnow


def setup_django():
    import django
    from django.apps import apps
    if not apps.ready:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "website/backend/v1"))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        django.setup()


def models():
    setup_django()
    from log_storage_meta import models as storage_models
    return storage_models


def topic_for(kind):
    return env.KAFKA_TOPIC_STRUCTURED if kind == "raw" else env.get_env("KAFKA_TOPIC_RULE_EVENTS", "rule.event.save")


def source_identity(kind, sink):
    if sink == "ck":
        location = [env.get_env("CK_HOST", "localhost"), env.get_env_int("CK_HTTP_PORT", 18123), env.get_env("CK_DATABASE", "auditweaver_logs")]
    else:
        location = [env.ES_HOST, env.ES_PORT, "auditweaver-" + ("raw" if kind == "raw" else "events") + "-hot"]
    return hashlib.sha256(json.dumps([kind, sink, topic_for(kind), location, env.get_env("STORAGE_SOURCE_GENERATION", "v1")]).encode()).hexdigest()


class DjangoMetadata:
    def hot_coverage(self, kind):
        m = models()
        topic = topic_for(kind)
        checkpoints = list(m.Checkpoint.objects.filter(sink="es", topic=topic))
        count = checkpoints[0].partition_count if checkpoints else 0
        deadline = utcnow() - timedelta(seconds=env.get_env_int("STORAGE_MAX_VISIBILITY_LAG_SECONDS", 30))
        if not count or {c.partition for c in checkpoints} != set(range(count)) or any(
            c.generation != env.get_env("STORAGE_SOURCE_GENERATION", "v1") or c.checked_at is None or c.checked_at < deadline or c.next_offset < c.observed_next_offset for c in checkpoints
        ):
            raise QueryUnavailable("Hot index consumers are behind or unavailable")
        generation = env.get_env("STORAGE_SOURCE_GENERATION", "v1")
        windows = m.CoverageWindow.objects.filter(kind=kind + "_hot", verified=True)
        if m.Gap.objects.filter(sink="es", topic=topic, resolved=False).exists():
            raise QueryUnavailable("Unresolved hot storage gaps")
        if not any(w.evidence.get("source_id") == source_identity(kind, "es") and w.evidence.get("generation") == generation and w.evidence.get("live") and all(
            c.initial_offset <= w.evidence.get("handoff", {}).get(str(c.partition), -1) <= c.next_offset for c in checkpoints
        ) for w in windows):
            raise QueryUnavailable("Hot window has not passed full verification")

    def advance(self, sink, kind, rows, positions):
        from django.db import transaction
        m = models()
        generation = env.get_env("STORAGE_SOURCE_GENERATION", "v1")
        with transaction.atomic():
            for (topic, partition), next_offset in positions.items():
                obj, _ = m.Checkpoint.objects.select_for_update().get_or_create(
                    sink=sink, topic=topic, partition=partition, defaults={"generation": generation},
                )
                if obj.generation != generation:
                    raise QueryUnavailable("Source generation changed; migration required")
                obj.next_offset = max(obj.next_offset, next_offset)
                obj.save()
                m.Gap.objects.filter(sink=sink, topic=topic, partition=partition,
                                     offset__in=[r["source_offset"] for r in rows if r["source_topic"] == topic and r["source_partition"] == partition]).update(resolved=True)
            if sink == "ck" and kind == "events":
                for r in rows:
                    m.EventOutbox.objects.get_or_create(
                        topic=r["source_topic"], partition=r["source_partition"], offset=r["source_offset"],
                        defaults={"event_id": r["record_id"], "event_time": r["event_time"]},
                    )

    def gap(self, sink, source, error):
        models().Gap.objects.update_or_create(
            sink=sink, topic=source.topic, partition=source.partition, offset=source.offset,
            defaults={"error": str(error)[:4000], "resolved": False},
        )

    def observe(self, sink, topic, partition, low, high, count, initial_offset=None):
        from django.db import transaction
        m = models()
        generation = env.get_env("STORAGE_SOURCE_GENERATION", "v1")
        with transaction.atomic():
            cp, created = m.Checkpoint.objects.select_for_update().get_or_create(
                sink=sink, topic=topic, partition=partition,
                defaults={"generation": generation, "next_offset": low if initial_offset is None else initial_offset,
                          "initial_offset": low if initial_offset is None else initial_offset},
            )
            if cp.generation != generation or cp.partition_count not in (0, count):
                raise QueryUnavailable("Topic generation or partition count changed")
            if cp.next_offset < low:
                raise QueryUnavailable("Kafka retention passed the durable checkpoint; recovery required")
            if cp.next_offset > high:
                raise QueryUnavailable("Kafka offsets moved backwards; recovery required")
            cp.partition_count = count
            cp.observed_next_offset = high
            cp.checked_at = utcnow()
            cp.save()
            return cp.next_offset

    def coverage(self, kind, start, end):
        m = models()
        topic = topic_for(kind)
        checkpoints = list(m.Checkpoint.objects.filter(sink="ck", topic=topic))
        count = checkpoints[0].partition_count if checkpoints else 0
        deadline = utcnow() - timedelta(seconds=env.get_env_int("STORAGE_MAX_VISIBILITY_LAG_SECONDS", 30))
        if not count or {c.partition for c in checkpoints} != set(range(count)):
            raise QueryUnavailable("Archive checkpoint coverage is missing")
        if any(c.generation != env.get_env("STORAGE_SOURCE_GENERATION", "v1") or c.checked_at is None or c.checked_at < deadline or c.next_offset < c.observed_next_offset for c in checkpoints):
            raise QueryUnavailable("Archive consumer is behind or its progress is stale")
        if m.Gap.objects.filter(sink="ck", topic=topic, resolved=False).exists():
            raise QueryUnavailable("Unresolved archive gaps")
        windows = m.CoverageWindow.objects.filter(kind=kind, verified=True, end_time__gt=start).order_by("start_time")
        covered = start
        for window in windows:
            if window.evidence.get("source_id") != source_identity(kind, "ck"):
                continue
            if window.start_time > covered:
                break
            covered = max(covered, window.end_time)
            if window.evidence.get("live") and window.evidence.get("generation") == env.get_env("STORAGE_SOURCE_GENERATION", "v1"):
                handoff = window.evidence.get("handoff", {})
                if all(c.initial_offset <= handoff.get(str(c.partition), -1) <= c.next_offset for c in checkpoints):
                    covered = max(covered, utcnow())
            if covered >= end:
                break
        if covered < end:
            raise QueryUnavailable("Requested history has not been verified; use transition mode until backfill completes")
        return {"complete": True, "visibility_checked_at": min(c.checked_at for c in checkpoints).isoformat(),
                "positions": {str(c.partition): c.next_offset for c in checkpoints}}
