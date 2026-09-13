"""Kafka adapter that serializes SecurityEvent objects.

保留 Rule Engine 特有逻辑：SecurityEvent 序列化、多 topic 发送、consumer 联动 offset 提交。
DlqProducer 已提取到 core.kafka.dlq。

底层使用 confluent-kafka（librdkafka）。原 key_serializer/value_serializer 配置
改为 produce 前 bytes 化；acks 显式设为 all 以提升分析管道可靠性。
"""

from __future__ import annotations

import json
from typing import Any

from ..models.security_event import SecurityEvent


def _to_bootstrap_servers(value: list[str] | str) -> str:
    """confluent-kafka 要求 bootstrap.servers 为逗号分隔字符串。"""
    if isinstance(value, (list, tuple)):
        return ','.join(str(v) for v in value)
    return str(value)


class KafkaProducer:
    """SecurityEvent 专用多 topic 生产者，支持 consumer 联动 offset 提交。"""

    def __init__(self, bootstrap_servers: list[str] | str, topics: list[str]) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics
        self._producer: Any = None
        self._consumer: Any = None
        self._delivery_errors: list[str] = []

    def set_consumer(self, consumer: Any) -> None:
        self._consumer = consumer

    def _on_delivery(self, err, msg) -> None:
        if err is not None:
            self._delivery_errors.append(str(err))

    def connect(self) -> None:
        try:
            from confluent_kafka import Producer
        except ImportError as error:
            raise RuntimeError("confluent-kafka is required to run the Kafka adapter") from error
        self._producer = Producer({
            'bootstrap.servers': _to_bootstrap_servers(self.bootstrap_servers),
            'acks': 'all',
            'retries': 3,
        })

    def send(self, event: SecurityEvent) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka producer is not connected")
        payload = event.to_dict()
        value_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        key_bytes = event.event_id.encode("utf-8") if event.event_id else None
        self._delivery_errors.clear()
        for topic in self.topics:
            self._producer.produce(
                topic, value=value_bytes, key=key_bytes,
                on_delivery=self._on_delivery,
            )
            self._producer.poll(0)
        self._producer.flush()
        if self._consumer is not None:
            self._consumer.commit()

    def commit_offset(self) -> None:
        if self._consumer is not None:
            self._consumer.commit()

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush()
            self._producer = None


# Kept as a descriptive alias for callers that want to distinguish this
# infrastructure adapter from confluent-kafka's Producer.
KafkaProducerAdapter = KafkaProducer
