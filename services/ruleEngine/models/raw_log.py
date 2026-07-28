"""Input model for records consumed from Kafka."""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RawLog:
    """The untrusted log payload as it was received from Kafka."""

    payload: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RawLog":
        if not isinstance(payload, Mapping):
            raise TypeError("RawLog payload must be a mapping")
        return cls(payload=dict(payload))
