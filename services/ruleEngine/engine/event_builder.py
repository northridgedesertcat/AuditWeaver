"""Construction of the stable SecurityEvent export contract."""

from __future__ import annotations

from ..models.log_message import LogMessage
from ..models.security_event import Detection, SecurityEvent


class EventBuilder:
    def build(self, log: LogMessage, detections: list[Detection]) -> SecurityEvent:
        attack_types = ",".join(detection.attack_type for detection in detections)
        context = log.to_dict()
        # ``normalized_path`` makes the decoding performed by the preprocessor
        # explicit while preserving the documented context field name.
        context["path"] = context.pop("original_path")
        context["normalized_path"] = log.path
        context["bytes"] = context.pop("response_bytes")
        context["timestamp"] = context.pop("log_timestamp")
        return SecurityEvent(log.event_id, attack_types, tuple(detections), context)
