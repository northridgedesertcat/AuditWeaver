"""Result models exported by the rule engine."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MatchResult:
    field: str
    pattern_id: str
    matched_value: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Detection:
    rule_id: str
    attack_type: str
    matches: tuple[MatchResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "attack_type": self.attack_type,
                "matches": [match.to_dict() for match in self.matches]}


@dataclass(frozen=True)
class SecurityEvent:
    event_id: str
    attack_type: str
    detections: tuple[Detection, ...]
    log_context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "attack_type": self.attack_type,
            "detections": [detection.to_dict() for detection in self.detections],
            "log_context": self.log_context,
        }
