from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
KINDS = {"raw": "raw_logs", "events": "security_events"}


class QueryError(ValueError):
    pass


class QueryUnavailable(RuntimeError):
    pass


def utcnow():
    return datetime.now(UTC)


def parse_time(value):
    """Strict UTC timestamp parser; numeric inputs are always epoch milliseconds."""
    try:
        if isinstance(value, datetime):
            result = value
        elif isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            result = datetime.fromtimestamp(float(value) / 1000, UTC)
        else:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone required")
        result = result.astimezone(UTC)
        return result.replace(microsecond=(result.microsecond // 1000) * 1000)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise QueryError("Invalid timestamp: use ISO 8601 with timezone or epoch milliseconds") from exc


def millis(value):
    return int(parse_time(value).timestamp() * 1000)


@dataclass(frozen=True)
class QuerySpec:
    kind: str
    start: datetime
    end: datetime
    filters: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise QueryError("Unknown log kind")
        object.__setattr__(self, "start", parse_time(self.start))
        object.__setattr__(self, "end", parse_time(self.end))
        if self.start >= self.end:
            raise QueryError("start_time must be before end_time")
        allowed = {"ip", "method", "status", "path", "attack_type", "event_id", "q"}
        if set(self.filters) - allowed:
            raise QueryError("Unsupported log filter")
        filters = {k: str(v) for k, v in self.filters.items() if v not in (None, "")}
        if filters.get("ip"):
            import ipaddress
            try:
                filters["ip"] = str(ipaddress.ip_address(filters["ip"]))
            except ValueError as exc:
                raise QueryError("Invalid IP filter") from exc
        if any(len(v) > 1024 for v in filters.values()):
            raise QueryError("Filter too long")
        if "status" in filters:
            try:
                if not 0 <= int(filters["status"]) <= 65535:
                    raise ValueError()
            except ValueError as exc:
                raise QueryError("Invalid HTTP status") from exc
        object.__setattr__(self, "filters", filters)

    def digest(self):
        body = [self.kind, self.start.isoformat(), self.end.isoformat(), self.filters]
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_params(cls, params, kind="raw", now=None):
        now = now or utcnow()
        end = parse_time(params["end_time"]) if params.get("end_time") else now
        start = parse_time(params["start_time"]) if params.get("start_time") else end - timedelta(days=1)
        return cls(kind, start, end, {k: params[k] for k in (
            "ip", "method", "status", "path", "attack_type", "event_id", "q"
        ) if params.get(k) not in (None, "")})
