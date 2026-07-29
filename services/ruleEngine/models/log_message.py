"""Normalized log model used by the rule engine."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LogMessage:
    event_id: str
    ip: str
    method: str
    path: str
    original_path: str
    http_version: str
    status: int
    response_bytes: int
    referrer: str
    user_agent: str
    log_timestamp: int

    def get_field(self, field_name: str) -> Any:
        """Return a configured target field, without exposing arbitrary attributes."""
        return asdict(self).get(field_name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
