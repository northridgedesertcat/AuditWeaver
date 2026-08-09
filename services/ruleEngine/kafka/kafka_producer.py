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
        self._consumer: Any = None

    def set_consumer(self, consumer: Any) -> None:
        self._consumer = consumer

    def connect(self) -> None:
        try:
            from kafka import KafkaProducer
        except ImportError as error:
            raise RuntimeError("kafka-python is required to run the Kafka adapter") from error
        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            key_serializer=lambda k: k.encode("utf-8"),
            value_serializer=lambda payload: json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def send(self, event: SecurityEvent) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka producer is not connected")
        payload = event.to_dict()
        for topic in self.topics:
            self._producer.send(topic, payload, key=event.event_id)
        self._producer.flush()
        if self._consumer is not None:
            self._consumer.commit()

    def commit_offset(self) -> None:
        if self._consumer is not None:
            self._consumer.commit()

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush()
            self._producer.close()
            self._producer = None


class DlqProducer:
    """独立的 DLQ 生产者，发送原始 dict 到死信队列。"""

    def __init__(self, bootstrap_servers: list[str] | str, topic: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self._producer: Any = None

    def connect(self) -> None:
        try:
            from kafka import KafkaProducer
        except ImportError as error:
            raise RuntimeError("kafka-python is required to run the Kafka adapter") from error
        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            value_serializer=lambda payload: json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def send(self, payload: dict[str, Any], key: str | None = None) -> None:
        if self._producer is None:
            raise RuntimeError("DLQ producer is not connected")
        self._producer.send(self.topic, payload, key=key)
        self._producer.flush()

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush()
            self._producer.close()
            self._producer = None


# Kept as a descriptive alias for callers that want to distinguish this
# infrastructure adapter from kafka-python's KafkaProducer.
KafkaProducerAdapter = KafkaProducer
