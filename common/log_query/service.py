from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from common import env
from .types import QueryError, QuerySpec, QueryUnavailable, parse_time, utcnow


class LogQueryService:
    def __init__(self, es=None, ck=None, metadata=None, mode=None, secret=None, clock=utcnow):
        self._es, self._ck, self._metadata = es, ck, metadata
        self.mode = mode or env.get_env("LOG_QUERY_MODE", "es_legacy")
        if self.mode not in {"es_legacy", "transition", "hybrid"}:
            raise QueryError("Invalid LOG_QUERY_MODE")
        self.secret = secret or env.get_env("LOG_QUERY_CURSOR_SECRET") or env.DJANGO_SECRET_KEY
        self.clock = clock

    @property
    def es(self):
        if self._es is None:
            from .adapters import ElasticsearchReader
            self._es = ElasticsearchReader()
        return self._es

    @property
    def ck(self):
        if self._ck is None:
            from .adapters import ClickHouseReader
            self._ck = ClickHouseReader()
        return self._ck

    @property
    def metadata(self):
        if self._metadata is None:
            from services.log_storage.metadata import DjangoMetadata
            self._metadata = DjangoMetadata()
        return self._metadata

    def _encode(self, state):
        if not self.secret:
            raise QueryError("Configure LOG_QUERY_CURSOR_SECRET or DJANGO_SECRET_KEY")
        raw = base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()
        sig = hmac.new(self.secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        return raw + "." + sig

    def _decode(self, cursor):
        try:
            if not self.secret or len(cursor) > 16384:
                raise ValueError()
            raw, sig = cursor.rsplit(".", 1)
            if not hmac.compare_digest(hmac.new(self.secret.encode(), raw.encode(), hashlib.sha256).hexdigest(), sig):
                raise ValueError()
            state = json.loads(base64.urlsafe_b64decode(raw))
            if state["expires"] < self.clock().timestamp() or state["mode"] != self.mode:
                raise ValueError()
            return state
        except (ValueError, TypeError, KeyError) as exc:
            raise QueryError("Invalid or expired log cursor; restart the query") from exc

    def spec_from_params(self, params, kind="raw"):
        params = dict(params.items())
        if params.get("cursor"):
            state = self._decode(params["cursor"])
            params.setdefault("start_time", state["start"])
            params.setdefault("end_time", state["end"])
        return QuerySpec.from_params(params, kind=kind, now=self.clock())

    def _segments(self, spec, boundary):
        if self.mode == "es_legacy":
            return [("es", spec.start, spec.end, False)]
        segments = []
        if spec.end > boundary:
            segments.append(("es", max(boundary, spec.start), spec.end, True))
        if spec.start < boundary:
            segments.append(("ck" if self.mode == "hybrid" else "es", spec.start, min(boundary, spec.end), False))
        return segments

    def _coverage(self, spec, segments):
        coverage = {"complete": True, "start_time": spec.start.isoformat(), "end_time": spec.end.isoformat(),
                    "sources": list(dict.fromkeys(s[0] for s in segments))}
        for source, start, end, _ in segments:
            if source == "ck":
                coverage.update(self.metadata.coverage(spec.kind, start, end))
        if self.mode != "es_legacy" and any(source == "es" and hot for source, _, _, hot in segments):
            self.metadata.hot_coverage(spec.kind)
        return coverage

    def search(self, spec, *, limit=20, cursor=None):
        if not 1 <= limit <= 1000:
            raise QueryError("size must be between 1 and 1000")
        if (spec.end - spec.start).total_seconds() > env.get_env_int("LOG_QUERY_MAX_DAYS", 90) * 86400:
            raise QueryError("Time range exceeds LOG_QUERY_MAX_DAYS; use a narrower range")
        now = self.clock()
        state = self._decode(cursor) if cursor else {
            "mode": self.mode, "digest": spec.digest(), "start": spec.start.isoformat(), "end": spec.end.isoformat(),
            "boundary": (now - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7))).isoformat(),
            "expires": (now + timedelta(seconds=env.get_env_int("LOG_QUERY_CURSOR_TTL_SECONDS", 300))).timestamp(),
            "segment": 0, "after": None, "pit": None,
        }
        if state["digest"] != spec.digest():
            raise QueryError("Cursor does not match query filters")
        segments = self._segments(spec, parse_time(state["boundary"]))
        try:
            coverage = self._coverage(spec, segments)
            logs = []
            while state["segment"] < len(segments):
                source, start, end, hot = segments[state["segment"]]
                reader = self.es if source == "es" else self.ck
                remaining = limit - len(logs)
                rows, pit = reader.fetch(spec, start, end, remaining + 1, state["after"], state["pit"], hot)
                state["pit"] = pit
                logs.extend({k: v for k, v in r["payload"].items() if k != "_storage"} for r in rows[:remaining])
                if len(rows) > remaining:
                    if remaining:
                        state["after"] = rows[remaining - 1]["after"]
                    return {"data": logs, "total": None, "total_relation": "unknown", "has_more": True,
                            "next_cursor": self._encode(state), "coverage": coverage}
                reader.close(pit)
                state.update(segment=state["segment"] + 1, after=None, pit=None)
            return {"data": logs, "total": None, "total_relation": "unknown", "has_more": False,
                    "next_cursor": None, "coverage": coverage}
        except (QueryError, QueryUnavailable):
            if state.get("pit"):
                self.es.close(state["pit"])
            raise
        except Exception as exc:
            if state.get("pit"):
                self.es.close(state["pit"])
            raise QueryUnavailable("Log storage is unavailable or query coverage cannot be verified") from exc

    def aggregate(self, spec, dimensions=(), hourly=False):
        if set(dimensions) - {"ip", "path", "status", "method"}:
            raise QueryError("Unsupported aggregate dimension")
        boundary = self.clock() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7))
        # The full CK range provides exact cross-boundary aggregates without summing duplicates.
        segments = [("ck", spec.start, spec.end, False)] if self.mode == "hybrid" else self._segments(spec, boundary)
        try:
            coverage = self._coverage(spec, segments)
            total, groups, hours = 0, {d: Counter() for d in dimensions}, Counter()
            for source, start, end, hot in segments:
                reader = self.ck if source == "ck" else self.es
                total += reader.count(spec, start, end, hot)
                for dimension in dimensions:
                    groups[dimension].update(dict(reader.groups(spec, start, end, dimension, hot)))
                if hourly:
                    hours.update(dict(reader.hourly(spec, start, end, hot)))
            return {"total": total, "groups": {k: sorted(v.items(), key=lambda item: (-item[1], str(item[0]))) for k, v in groups.items()},
                    "hours": sorted(hours.items()), "coverage": coverage, "total_relation": "eq"}
        except (QueryError, QueryUnavailable):
            raise
        except Exception as exc:
            raise QueryUnavailable("Log aggregation is unavailable") from exc

    def get_log(self, event_id, event_time_hint=None, kind="raw"):
        now = self.clock()
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        spec = QuerySpec(kind, epoch, now + timedelta(minutes=5), {"event_id": event_id})
        # Exact ID lookup intentionally bypasses the interactive time-window limit.
        if self.mode == "es_legacy":
            candidates = [("es", epoch, spec.end, False)]
        else:
            cutoff = now - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7))
            candidates = [("es", cutoff, spec.end, True),
                          ("ck" if self.mode == "hybrid" else "es", epoch, spec.end, False)]
            if event_time_hint and parse_time(event_time_hint) < cutoff:
                candidates.reverse()
        try:
            for source, start, end, hot in candidates:
                reader = self.ck if source == "ck" else self.es
                rows, pit = reader.fetch(spec, start, end, 1, hot=hot)
                reader.close(pit)
                if rows:
                    return {"status": "found", "source": source, "data": {k: v for k, v in rows[0]["payload"].items() if k != "_storage"}}
            if self.mode == "hybrid":
                hint = parse_time(event_time_hint) if event_time_hint else epoch
                self.metadata.coverage(kind, hint, hint + timedelta(milliseconds=1) if event_time_hint else now)
            return {"status": "not_found", "data": None}
        except Exception as exc:
            raise QueryUnavailable("Original log cannot currently be retrieved") from exc

    def scan_security_events(self, spec, batch_size=500):
        if spec.kind != "events":
            raise QueryError("Expected security event query")
        if not 1 <= batch_size <= 1000:
            raise QueryError("Scan batch size must be between 1 and 1000")
        boundary = self.clock() - timedelta(days=env.get_env_int("LOG_HOT_RETENTION_DAYS", 7))
        segments = self._segments(spec, boundary)
        self._coverage(spec, segments)
        for source, start, end, hot in segments:
            reader = self.ck if source == "ck" else self.es
            after, pit = None, None
            try:
                while True:
                    rows, pit = reader.fetch(spec, start, end, batch_size, after, pit, hot)
                    if not rows:
                        break
                    yield [{"_id": r["payload"].get("event_id"), "_source": {k: v for k, v in r["payload"].items() if k != "_storage"}} for r in rows]
                    after = rows[-1]["after"]
            finally:
                reader.close(pit)


def get_log_query_service():
    return LogQueryService()
