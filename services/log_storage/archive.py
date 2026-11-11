"""Streaming backfill and verification. No wildcard deletion is supported."""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import timedelta

from common import env
from common.log_query.types import QueryError, QueryUnavailable, parse_time, utcnow
from .contract import Source, normalize
from .hot import ALIASES
from .metadata import models, topic_for, source_identity


def index_window(index):
    match = re.fullmatch(r"auditweaver-(raw|events)-hot-(\d{4}\.\d{2}\.\d{2})", index)
    if not match:
        raise QueryError("Only an exact daily hot index is eligible for cleanup")
    from datetime import datetime, timezone
    start = datetime.strptime(match[2], "%Y.%m.%d").replace(tzinfo=timezone.utc)
    return match[1], start, start + timedelta(days=1)


@contextmanager
def archive_lock(index):
    from django.db import connection
    models()
    key = "aw:archive:" + hashlib.sha256(index.encode()).hexdigest()[:40]
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", [key])
        if cursor.fetchone()[0] != 1:
            raise QueryUnavailable("Another archive operation owns this index")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [key])


def scan_index(es, index, query=None, batch_size=500):
    pit = es.open_point_in_time(index=index, keep_alive="5m")["id"]
    after = None
    try:
        while True:
            body = {"size": batch_size, "pit": {"id": pit, "keep_alive": "5m"},
                    "query": query or {"match_all": {}}, "sort": [{"_shard_doc": "asc"}]}
            if after is not None:
                body["search_after"] = after
            result = es.search(body=body)
            pit = result.get("pit_id", pit)
            if result.get("timed_out") or result.get("_shards", {}).get("failed", 0):
                raise QueryUnavailable("Incomplete ES archive scan")
            hits = result["hits"]["hits"]
            if not hits:
                return
            yield hits
            after = hits[-1]["sort"]
    finally:
        es.close_point_in_time(id=pit)


def row_from_hit(kind, hit):
    storage = hit["_source"].get("_storage") or {}
    source = Source(storage.get("source_topic", ""), storage.get("source_partition", -1), storage.get("source_offset", -1),
                    kind=storage.get("source_kind", "es_backfill"))
    row = normalize(kind, hit["_source"], source, legacy_id=storage.get("record_id") or f"legacy:{hit['_index']}:{hit['_id']}")
    if storage and any(storage.get(key) != row[key] for key in ("record_id", "version", "payload_hash")):
        raise QueryUnavailable("Stored identity/version/content metadata does not match the document")
    return row


def verified_row(kind, expected, actual, source_bounds=None):
    if actual is None or actual["event_time"] != expected["event_time"]:
        raise QueryUnavailable("Archive record missing or event time differs")
    if actual["payload_hash"] == expected["payload_hash"] and actual["version"] >= expected["version"]:
        if actual["source_kind"] == expected["source_kind"] == "kafka" and (
            actual["source_topic"], actual["source_partition"]
        ) != (expected["source_topic"], expected["source_partition"]):
            raise QueryUnavailable("Matching content has an incompatible Kafka source")
        return
    if kind == "events" and actual["source_kind"] == "kafka":
        if expected["source_kind"] == "kafka":
            if (actual["source_topic"], actual["source_partition"]) == (expected["source_topic"], expected["source_partition"]) and actual["source_offset"] > expected["source_offset"]:
                return
        else:
            boundary = (source_bounds or {}).get(f"{actual['source_topic']}:{actual['source_partition']}")
            if boundary is not None and actual["source_offset"] >= boundary:
                return
    raise QueryUnavailable("Archive content/version differs without proof of a newer event")


def backfill(es, ck, index, kind, start, end, *, copy_hot=False, source_bounds=None):
    if index not in {env.ES_INDEX_NGINX_RAW, env.ES_INDEX_MATCHED_LOGS}:
        raise QueryError("Backfill requires an exact legacy business index")
    expected_index = env.ES_INDEX_NGINX_RAW if kind == "raw" else env.ES_INDEX_MATCHED_LOGS
    if index != expected_index:
        raise QueryError("Index/kind mismatch")
    settings = es.indices.get_settings(index=index)[index]["settings"]["index"]
    if str(settings.get("blocks", {}).get("write", "false")).lower() != "true":
        raise QueryError("Legacy source must be sealed before verified backfill")
    timestamp = "@timestamp" if kind == "raw" else "log_context.timestamp"
    query = {"range": {timestamp: {"gte": start.isoformat(), "lt": end.isoformat()}}}
    from .hot import HotStore
    hot = HotStore(es) if copy_hot else None
    m = models()
    name = f"legacy:{index}:{start.isoformat()}:{end.isoformat()}"
    with archive_lock(name):
        manifest, _ = m.ArchiveManifest.objects.get_or_create(
            index_name=name, defaults={"kind": kind, "start_time": start, "end_time": end},
        )
        manifest.state = "VERIFYING"
        manifest.save()
        count, digest = 0, hashlib.sha256()
        try:
            es.indices.refresh(index=index)
            for hits in scan_index(es, index, query):
                rows = [row_from_hit(kind, h) for h in hits]
                ck.write(kind, rows)
                known = ck.existing(kind, [r["record_id"] for r in rows])
                for row in rows:
                    verified_row(kind, row, known.get(row["record_id"]), source_bounds)
                    digest.update((row["record_id"] + ":" + row["payload_hash"] + "\n").encode())
                if hot:
                    hot.write(kind, rows)
                count += len(rows)
            manifest.state, manifest.record_count, manifest.digest = "VERIFIED", count, digest.hexdigest()
            manifest.source_bounds = source_bounds or {}
            manifest.evidence = {"source_uuid": settings["uuid"], "sealed": True, "verified_at": utcnow().isoformat()}
            manifest.error = ""
            manifest.save()
            return {"records": count, "manifest": name, "state": "VERIFIED"}
        except Exception as exc:
            manifest.state, manifest.error = "BLOCKED", str(exc)[:4000]
            manifest.save()
            raise


def cleanup(es, ck, metadata, index, *, execute=False, backup=None):
    kind, start, end = index_window(index)
    if end > utcnow() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7)):
        raise QueryError("Index still intersects the hot window")
    if not execute:
        # Planning is read-only, including index settings and manifests.
        return {"index": index, "action": "would_seal_verify_and_delete", "dry_run": True}
    if not env.get_env_bool("ES_CLEANUP_ENABLED") or env.get_env_bool("ES_CLEANUP_DRY_RUN", True):
        raise QueryError("Cleanup is disabled or dry-run is enabled")
    if not backup or not backup.get("backup_id") or parse_time(backup.get("covered_until")) < end or parse_time(backup.get("restore_tested_at")) > utcnow():
        raise QueryError("A backup with coverage and a completed restore test is required")
    m = models()
    with archive_lock(index):
        metadata.coverage(kind, start, end)
        manifest, _ = m.ArchiveManifest.objects.get_or_create(index_name=index, defaults={"kind": kind, "start_time": start, "end_time": end})
        try:
            # add_block waits for in-flight writes to finish before acknowledging the block.
            es.indices.add_block(index=index, block="write")
            es.indices.refresh(index=index)
            original = es.indices.get_settings(index=index)[index]["settings"]["index"]
            manifest.state = "VERIFYING"
            manifest.save()
            count, digest, bounds = 0, hashlib.sha256(), {}
            for hits in scan_index(es, index):
                rows = [row_from_hit(kind, h) for h in hits]
                known = ck.existing(kind, [r["record_id"] for r in rows])
                for row in rows:
                    if not start <= row["event_time"] < end:
                        raise QueryUnavailable("Record event time is outside its index day")
                    verified_row(kind, row, known.get(row["record_id"]))
                    if row["source_kind"] == "kafka":
                        key = f"{row['source_topic']}:{row['source_partition']}"
                        bounds[key] = max(bounds.get(key, -1), row["source_offset"])
                    digest.update((row["record_id"] + ":" + row["payload_hash"] + "\n").encode())
                count += len(rows)
            for key, offset in bounds.items():
                topic, partition = key.rsplit(":", 1)
                cp = m.Checkpoint.objects.filter(sink="ck", topic=topic, partition=int(partition)).first()
                if cp is None or cp.next_offset <= offset:
                    raise QueryUnavailable("CK checkpoint has not passed the sealed source boundary")
            manifest.state, manifest.record_count, manifest.digest = "VERIFIED", count, digest.hexdigest()
            manifest.source_bounds, manifest.backup_id = bounds, backup["backup_id"]
            manifest.evidence = {"source_uuid": original["uuid"], "backup": backup}
            manifest.save()
            metadata.coverage(kind, start, end)
            current = es.indices.get_settings(index=index)[index]["settings"]["index"]
            if current["uuid"] != original["uuid"] or str(current.get("blocks", {}).get("write")).lower() != "true":
                raise QueryUnavailable("Index changed since verification")
            manifest.state = "DELETE_PENDING"
            manifest.save()
            es.indices.delete(index=index)
            manifest.state = "DELETED"
            manifest.save()
            return {"index": index, "records": count, "state": "DELETED"}
        except Exception as exc:
            manifest.state, manifest.error = "BLOCKED", str(exc)[:4000]
            manifest.save()
            raise


def certify_coverage(es, ck, metadata, kind, start, handoff):
    """Verify the entire sealed legacy source and its continuous Kafka handoff."""
    m = models()
    topic = topic_for(kind)
    index = env.ES_INDEX_NGINX_RAW if kind == "raw" else env.ES_INDEX_MATCHED_LOGS
    checkpoints = list(m.Checkpoint.objects.filter(sink="ck", topic=topic))
    count = checkpoints[0].partition_count if checkpoints else 0
    expected = {f"{topic}:{p}" for p in range(count)}
    if not count or set(handoff) != expected or {cp.partition for cp in checkpoints} != set(range(count)):
        raise QueryUnavailable("Handoff must cover every source partition exactly")
    deadline = utcnow() - timedelta(seconds=env.get_env_int("STORAGE_MAX_VISIBILITY_LAG_SECONDS", 30))
    for cp in checkpoints:
        if not cp.initial_offset <= handoff[f"{topic}:{cp.partition}"] <= cp.next_offset or cp.next_offset < cp.observed_next_offset or cp.checked_at is None or cp.checked_at < deadline:
            raise QueryUnavailable("Kafka handoff is not covered by fresh durable CK checkpoints")
    if m.Gap.objects.filter(sink="ck", topic=topic, resolved=False).exists():
        raise QueryUnavailable("Repair archive gaps before certification")
    with archive_lock("coverage:" + kind):
        settings = es.indices.get_settings(index=index)[index]["settings"]["index"]
        if str(settings.get("blocks", {}).get("write", "false")).lower() != "true":
            raise QueryError("Legacy source must be sealed")
        es.indices.refresh(index=index)
        records = 0
        for hits in scan_index(es, index):
            rows = [row_from_hit(kind, hit) for hit in hits]
            known = ck.existing(kind, [row["record_id"] for row in rows])
            for row in rows:
                if row["event_time"] < start:
                    raise QueryError("Coverage start excludes legacy records")
                verified_row(kind, row, known.get(row["record_id"]), handoff)
            records += len(rows)
        if records != es.count(index=index)["count"]:
            raise QueryUnavailable("Sealed source count changed")
        current = es.indices.get_settings(index=index)[index]["settings"]["index"]
        if current["uuid"] != settings["uuid"] or str(current.get("blocks", {}).get("write")).lower() != "true":
            raise QueryUnavailable("Legacy source changed during certification")
        end = utcnow()
        evidence = {"live": True, "source_id": source_identity(kind, "ck"), "generation": env.get_env("STORAGE_SOURCE_GENERATION", "v1"), "source_uuid": settings["uuid"],
                    "source_index": index, "records": records, "handoff": {str(cp.partition): handoff[f"{topic}:{cp.partition}"] for cp in checkpoints}}
        window = m.CoverageWindow.objects.create(kind=kind, start_time=start, end_time=end, evidence=evidence, verified=True)
        metadata.coverage(kind, start, end)
        return {"coverage_id": window.pk, "verified": True, "records": records}


def certify_hot(es, kind, handoff):
    m = models()
    topic = topic_for(kind)
    checkpoints = list(m.Checkpoint.objects.filter(sink="es", topic=topic))
    count = checkpoints[0].partition_count if checkpoints else 0
    if not count or set(handoff) != {f"{topic}:{p}" for p in range(count)} or {c.partition for c in checkpoints} != set(range(count)):
        raise QueryUnavailable("Hot handoff must cover every source partition")
    deadline = utcnow() - timedelta(seconds=env.get_env_int("STORAGE_MAX_VISIBILITY_LAG_SECONDS", 30))
    if any(not c.initial_offset <= handoff[f"{topic}:{c.partition}"] <= c.next_offset or c.next_offset < c.observed_next_offset or c.checked_at is None or c.checked_at < deadline for c in checkpoints):
        raise QueryUnavailable("Hot consumers do not cover the source handoff")
    index = env.ES_INDEX_NGINX_RAW if kind == "raw" else env.ES_INDEX_MATCHED_LOGS
    settings = es.indices.get_settings(index=index)[index]["settings"]["index"]
    if str(settings.get("blocks", {}).get("write", "false")).lower() != "true":
        raise QueryError("Seal the legacy source before hot certification")
    start, end = utcnow() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7)), utcnow()
    field = "@timestamp" if kind == "raw" else "log_context.timestamp"
    es.indices.refresh(index=ALIASES[kind])
    records = 0
    for hits in scan_index(es, index, {"range": {field: {"gte": start.isoformat(), "lt": end.isoformat()}}}):
        rows = [row_from_hit(kind, h) for h in hits]
        docs = [{"_index": ALIASES[kind] + row["event_time"].strftime("-%Y.%m.%d"), "_id": row["record_id"]} for row in rows]
        actual = es.mget(docs=docs)["docs"]
        for row, doc in zip(rows, actual):
            if not doc.get("found"):
                raise QueryUnavailable("Hot window is missing a legacy record")
            verified_row(kind, row, row_from_hit(kind, doc), handoff)
        records += len(rows)
    window = m.CoverageWindow.objects.create(kind=kind + "_hot", start_time=start, end_time=end, verified=True,
        evidence={"live": True, "source_id": source_identity(kind, "es"), "generation": env.get_env("STORAGE_SOURCE_GENERATION", "v1"), "records": records,
                  "source_uuid": settings["uuid"], "handoff": {str(c.partition): handoff[f"{topic}:{c.partition}"] for c in checkpoints}})
    return {"coverage_id": window.pk, "records": records, "verified": True}
