"""Kafka adapter that only consumes and deserializes raw log records."""

from __future__ import annotations

import json
from typing import Any, Iterator


class KafkaConsumer:
    def __init__(self, bootstrap_servers: list[str] | str, topic: str, group_id: str,
                 auto_offset_reset: str = "latest", enable_auto_commit: bool = False) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self._consumer: Any = None
        self._last_message: Any = None

    def connect(self) -> None:
        try:
            from kafka import KafkaConsumer
        except ImportError as error:
            raise RuntimeError("kafka-python is required to run the Kafka adapter") from error
        self._consumer = KafkaConsumer(
            self.topic, bootstrap_servers=self.bootstrap_servers, group_id=self.group_id,
            auto_offset_reset=self.auto_offset_reset, enable_auto_commit=self.enable_auto_commit,
            value_deserializer=lambda payload: json.loads(payload.decode("utf-8")),
        )

    def consume(self) -> Iterator[dict[str, Any]]:
        if self._consumer is None:
            raise RuntimeError("Kafka consumer is not connected")
        for message in self._consumer:
            self._last_message = message
            yield message.value

    def commit(self) -> None:
        if self._consumer is None:
            raise RuntimeError("Kafka consumer is not connected")
        self._consumer.commit()

    def close(self) -> None:
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None


# Kept as a descriptive alias for callers that want to distinguish this
# infrastructure adapter from kafka-python's KafkaConsumer.
KafkaConsumerAdapter = KafkaConsumer
