"""Validation and normalization for incoming HTTP log records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Mapping

from ..models.log_message import LogMessage

logger = logging.getLogger(__name__)


class LogValidationError(ValueError):
    """Raised when a Kafka message cannot be converted to a LogMessage."""


class StructureNormalizer:
    """Maps compatible raw field names to the rule-engine data model."""

    required_fields = ("event_id", "ip", "method", "path", "status")

    def normalize(self, data: Mapping[str, Any], original_data: Mapping[str, Any] | None = None) -> LogMessage:
        missing = [field for field in self.required_fields if self._is_missing(data.get(field))]
        if missing:
            raise LogValidationError("Missing required log fields: " + ", ".join(missing))

        try:
            status = int(data["status"])
            response_bytes = int(data.get("response_bytes", data.get("bytes", 0)) or 0)
        except (TypeError, ValueError) as error:
            raise LogValidationError("status and bytes must be integers") from error

        return LogMessage(
            event_id=str(data["event_id"]),
            ip=str(data["ip"]),
            method=str(data["method"]).upper(),
            path=str(data["path"]),
            original_path=str((original_data or data).get("path", data["path"])),
            http_version=self._http_version(data.get("http_version", "")),
            status=status,
            response_bytes=response_bytes,
            referrer=str(data.get("referrer") or ""),
            user_agent=str(data.get("user_agent") or ""),
            log_timestamp=self._timestamp(data),
        )

    @staticmethod
    def _is_missing(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _http_version(value: Any) -> str:
        version = str(value or "")
        if version and not version.upper().startswith("HTTP/"):
            return f"HTTP/{version}"
        return version

    @staticmethod
    def _timestamp(data: Mapping[str, Any]) -> int:
        value = data.get("log_timestamp", data.get("timestamp", data.get("@timestamp")))
        if value is None or value == "":
            return int(datetime.now(timezone.utc).timestamp() * 1000)
        if isinstance(value, (int, float)):
            return int(value if value > 1_000_000_000_000 else value * 1000)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            try:
                return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
            except ValueError as error:
                raise LogValidationError("log_timestamp must be epoch milliseconds or ISO-8601") from error
