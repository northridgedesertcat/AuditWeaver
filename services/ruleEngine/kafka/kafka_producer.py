"""Kafka adapter that serializes SecurityEvent objects."""

from __future__ import annotations

import json
from typing import Any

from ..models.security_event import SecurityEvent


class KafkaProducer:
    def __init__(self, bootstrap_servers: list[str] | str, topics: list[str]) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics
        self._producer: Any = None

    def connect(self) -> None:
        try:
            from kafka import KafkaProducer
        except ImportError as error:
            raise RuntimeError("kafka-python is required to run the Kafka adapter") from error
        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda payload: json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def send(self, event: SecurityEvent) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka producer is not connected")
        payload = event.to_dict()
        for topic in self.topics:
            self._producer.send(topic, payload)

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush()
            self._producer.close()
            self._producer = None


# Kept as a descriptive alias for callers that want to distinguish this
# infrastructure adapter from kafka-python's KafkaProducer.
KafkaProducerAdapter = KafkaProducer
