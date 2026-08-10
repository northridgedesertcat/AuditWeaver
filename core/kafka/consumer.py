"""通用 Kafka 消费者基类。

提供 JSON 反序列化、逐条消费（生成器）和批量消费两种模式。
各模块直接实例化或子类化即可使用。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

logger = logging.getLogger('kafka_consumer')


class KafkaBaseConsumer:
    """Kafka 消费者基类，支持逐条和批量消费。"""

    def __init__(
        self,
        bootstrap_servers: str | list[str],
        topic: str,
        group_id: str,
        auto_offset_reset: str = 'latest',
        enable_auto_commit: bool = False,
        consumer_timeout_ms: int | None = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.consumer_timeout_ms = consumer_timeout_ms
        self._consumer: Any = None

    def connect(self) -> None:
        """建立 Kafka 连接，失败时抛出 RuntimeError。"""
        try:
            from kafka import KafkaConsumer
        except ImportError as error:
            raise RuntimeError('kafka-python is required to run the Kafka adapter') from error

        kwargs: dict[str, Any] = {
            'bootstrap_servers': self.bootstrap_servers,
            'group_id': self.group_id,
            'auto_offset_reset': self.auto_offset_reset,
            'enable_auto_commit': self.enable_auto_commit,
            'value_deserializer': lambda m: json.loads(m.decode('utf-8')),
        }
        if self.consumer_timeout_ms is not None:
            kwargs['consumer_timeout_ms'] = self.consumer_timeout_ms

        self._consumer = KafkaConsumer(self.topic, **kwargs)
        logger.info('Kafka consumer connected: %s, topic: %s', self.bootstrap_servers, self.topic)

    def consume(self) -> Iterator[dict[str, Any]]:
        """逐条消费（生成器模式），适用于 while 循环逐条处理。"""
        if self._consumer is None:
            raise RuntimeError('Kafka consumer is not connected')
        for message in self._consumer:
            yield message.value

    def consume_batch(self, max_records: int = 10) -> list[dict[str, Any]]:
        """批量消费，返回最多 max_records 条消息。"""
        if self._consumer is None:
            logger.error('Kafka consumer not connected')
            return []

        messages: list[dict[str, Any]] = []
        try:
            for message in self._consumer:
                messages.append(message.value)
                if len(messages) >= max_records:
                    break
        except Exception:
            logger.error('Error consuming messages', exc_info=True)

        return messages

    def commit(self) -> None:
        """手动提交 offset。"""
        if self._consumer is None:
            raise RuntimeError('Kafka consumer is not connected')
        self._consumer.commit()

    def is_connected(self) -> bool:
        """返回是否已连接。"""
        return self._consumer is not None

    def close(self) -> None:
        """关闭消费者连接。"""
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None
            logger.info('Kafka consumer closed')
