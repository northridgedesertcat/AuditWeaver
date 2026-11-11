from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import dataclass
from datetime import timedelta

from common.log_query.types import QueryError, parse_time, utcnow


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Source:
    topic: str = ""
    partition: int = -1
    offset: int = -1
    timestamp: int | None = None
    kind: str = "kafka"


def normalize(kind, payload, source=None, *, legacy_id=None, now=None):
    source = source or Source(kind="es_backfill")
    now = now or utcnow()
    if kind not in ("raw", "events") or not isinstance(payload, dict):
        raise QueryError("Expected a log object and valid kind")
    payload = {k: v for k, v in payload.items() if k != "_storage"}
    event_id = payload.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        if not legacy_id or source.kind != "es_backfill":
            raise QueryError("Missing event_id")
        event_id = ""
    record_id = event_id or legacy_id
    if len(record_id) > 255:
        raise QueryError("record_id exceeds the supported 255 character limit")
    context = payload if kind == "raw" else payload.get("log_context", {})
    if not isinstance(context, dict):
        raise QueryError("Invalid log_context")
    event_time = parse_time(context.get("@timestamp" if kind == "raw" else "timestamp"))
    if event_time > now + timedelta(minutes=5):
        raise QueryError("Event timestamp is more than five minutes in the future")
    ip = str(context.get("ip") or "")
    if ip:
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError as exc:
            raise QueryError("Invalid IP") from exc
    raw = canonical(payload)
    ingested = payload.get("ingested_at")
    if ingested is None and source.timestamp is not None:
        ingested = source.timestamp
    types = payload.get("attack_type") or ""
    attack_types = [str(v).strip() for v in (types if isinstance(types, list) else str(types).split(",")) if str(v).strip()]
    def number(name, maximum):
        value = context.get(name)
        if value is None:
            return None
        if isinstance(value, bool) or int(value) != float(value) or not 0 <= int(value) <= maximum:
            raise QueryError(f"Invalid {name}")
        return int(value)
    version = source.offset + 2 if source.kind == "kafka" else 1
    if version < 1 or version > 2**63 - 1:
        raise QueryError("Invalid source version")
    return {
        "record_id": record_id, "event_id": event_id, "event_time": event_time,
        "ingested_at": parse_time(ingested) if ingested is not None else None,
        "archived_at": now, "ip": ip, "method": str(context.get("method") or ""),
        "path": str(context.get("path") or ""), "normalized_path": str(context.get("normalized_path") or ""),
        "status": number("status", 65535), "bytes": number("bytes", 2**64 - 1),
        "http_version": str(context.get("http_version") or ""),
        "referrer": str(context.get("referrer") or ""), "user_agent": str(context.get("user_agent") or ""),
        "log_source": str(payload.get("log_source") or ""), "attack_types": sorted(set(attack_types)),
        "rule_ids": sorted({str(d["rule_id"]) for d in payload.get("detections", []) if isinstance(d, dict) and d.get("rule_id")}),
        "raw_payload": raw, "payload_hash": hashlib.sha256(raw.encode()).hexdigest(),
        "schema_version": 1, "source_kind": source.kind, "source_topic": source.topic,
        "source_partition": source.partition, "source_offset": source.offset, "version": version,
    }


def check_identity(kind, previous, row):
    if previous["event_time"] != row["event_time"]:
        raise QueryError("Event time cannot change for the same record_id")
    if kind == "raw" and previous["payload_hash"] != row["payload_hash"]:
        raise QueryError("Raw record_id reused for different content")
    if previous["version"] == row["version"] and previous["payload_hash"] != row["payload_hash"]:
        raise QueryError("Conflicting payload at the same record version")
    if previous["source_kind"] == row["source_kind"] == "kafka":
        if (previous["source_topic"], previous["source_partition"]) != (row["source_topic"], row["source_partition"]):
            raise QueryError("Record moved to another source partition; controlled migration required")
        if previous["version"] == row["version"] and previous["payload_hash"] != row["payload_hash"]:
            raise QueryError("Conflicting payload at the same source offset")
