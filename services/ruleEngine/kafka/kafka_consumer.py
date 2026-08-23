"""Kafka adapter that only consumes and deserializes raw log records.

底层使用 confluent-kafka（librdkafka），规避 Windows 上 kafka-python 的
SelectSelector 兼容问题。原 value_deserializer 配置改为 poll 后手动反序列化。
"""

from __future__ import annotations

import json
from typing import Any, Iterator


def _to_bootstrap_servers(value: str | list[str]) -> str:
    """confluent-kafka 要求 bootstrap.servers 为逗号分隔字符串。"""
    if isinstance(value, (list, tuple)):
        return ','.join(str(v) for v in value)
    return str(value)


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
            from confluent_kafka import Consumer
        except ImportError as error:
            raise RuntimeError("confluent-kafka is required to run the Kafka adapter") from error
        conf = {
            'bootstrap.servers': _to_bootstrap_servers(self.bootstrap_servers),
            'group.id': self.group_id,
            'auto.offset.reset': self.auto_offset_reset,
            'enable.auto.commit': bool(self.enable_auto_commit),
        }
        self._consumer = Consumer(conf)
        self._consumer.subscribe([self.topic])

    def consume(self) -> Iterator[dict[str, Any]]:
        if self._consumer is None:
            raise RuntimeError("Kafka consumer is not connected")
        while True:
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error() is not None:
                continue
            try:
                value = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            self._last_message = value
            yield value

    def commit(self) -> None:
        if self._consumer is None:
            raise RuntimeError("Kafka consumer is not connected")
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None


# Kept as a descriptive alias for callers that want to distinguish this
# infrastructure adapter from confluent-kafka's Consumer.
KafkaConsumerAdapter = KafkaConsumer
