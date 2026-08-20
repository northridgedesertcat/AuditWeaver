"""通用 Kafka 消费者基类。

提供 JSON 反序列化、逐条消费（生成器）和批量消费两种模式。
各模块直接实例化或子类化即可使用。

底层使用 confluent-kafka（librdkafka），规避 Windows 上 kafka-python 的
SelectSelector.unregister 兼容问题（kafka-python-ng issue #180）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

logger = logging.getLogger('kafka_consumer')


def _to_bootstrap_servers(value: str | list[str]) -> str:
    """confluent-kafka 要求 bootstrap.servers 为逗号分隔字符串。"""
    if isinstance(value, (list, tuple)):
        return ','.join(str(v) for v in value)
    return str(value)


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
            from confluent_kafka import Consumer
        except ImportError as error:
            raise RuntimeError('confluent-kafka is required to run the Kafka adapter') from error

        conf: dict[str, Any] = {
            'bootstrap.servers': _to_bootstrap_servers(self.bootstrap_servers),
            'group.id': self.group_id,
            'auto.offset.reset': self.auto_offset_reset,
            'enable.auto.commit': bool(self.enable_auto_commit),
        }
        self._consumer = Consumer(conf)
        self._consumer.subscribe([self.topic])
        logger.info('Kafka consumer connected: %s, topic: %s', self.bootstrap_servers, self.topic)

    def _decode(self, raw: bytes | None) -> dict[str, Any] | None:
        """反序列化单条消息，失败返回 None（由调用方跳过）。

        原 kafka-python 的 value_deserializer 抛异常会中断迭代；新版改为跳过坏消息
        以避免单条坏消息卡死整个消费者（行为更健壮，已记入迁移说明）。
        """
        if raw is None:
            return None
        try:
            return json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            logger.error('Failed to deserialize message: %s', error)
            return None

    def consume(self) -> Iterator[dict[str, Any]]:
        """逐条消费（生成器模式），适用于 while 循环逐条处理。"""
        if self._consumer is None:
            raise RuntimeError('Kafka consumer is not connected')
        while True:
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            err = msg.error()
            if err is not None:
                logger.error('Consumer error: %s', err)
                continue
            value = self._decode(msg.value())
            if value is None:
                continue
            yield value

    def consume_batch(self, max_records: int = 10) -> list[dict[str, Any]]:
        """批量消费，返回最多 max_records 条消息。

        连续多次 poll 超时（约对应原 consumer_timeout_ms 的停顿）时停止收集，
        返回已读到的消息。
        """
        if self._consumer is None:
            logger.error('Kafka consumer not connected')
            return []

        messages: list[dict[str, Any]] = []
        empty_polls = 0
        max_empty_polls = 5
        try:
            while len(messages) < max_records:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    empty_polls += 1
                    if empty_polls >= max_empty_polls:
                        break
                    continue
                empty_polls = 0
                err = msg.error()
                if err is not None:
                    logger.error('Consumer error: %s', err)
                    continue
                value = self._decode(msg.value())
                if value is None:
                    continue
                messages.append(value)
        except Exception:
            logger.error('Error consuming messages', exc_info=True)

        return messages

    def commit(self) -> None:
        """手动提交 offset。"""
        if self._consumer is None:
            raise RuntimeError('Kafka consumer is not connected')
        self._consumer.commit(asynchronous=False)

    def is_connected(self) -> bool:
        """返回是否已连接。"""
        return self._consumer is not None

    def close(self) -> None:
        """关闭消费者连接。"""
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None
            logger.info('Kafka consumer closed')
