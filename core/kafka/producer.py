"""通用 Kafka 生产者基类。

提供 JSON 序列化、单/多 topic 发送。
各模块直接实例化或子类化添加特有逻辑。

底层使用 confluent-kafka（librdkafka）。confluent 的 produce 为异步投递，
通过 on_delivery 回调 + poll(0) + flush() 实现原 send+flush 的语义。
Producer 无显式 close()，flush 后置 None 交由 GC 回收。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .consumer import _to_bootstrap_servers

logger = logging.getLogger('kafka_producer')


class KafkaBaseProducer:
    """Kafka 生产者基类，支持单 topic 和多 topic 发送。"""

    def __init__(
        self,
        bootstrap_servers: str | list[str],
        topics: str | list[str],
        acks: str = 'all',
        retries: int = 3,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topics: list[str] = topics if isinstance(topics, list) else [topics]
        self.acks = acks
        self.retries = retries
        self._producer: Any = None
        self._delivery_errors: list[str] = []

    def _on_delivery(self, err, msg) -> None:
        """投递回调，由 poll()/flush() 触发。"""
        if err is not None:
            self._delivery_errors.append(str(err))
            logger.error('Delivery failed: topic=%s, error=%s', msg.topic(), err)

    def connect(self) -> None:
        """建立 Kafka 连接，失败时抛出 RuntimeError。"""
        try:
            from confluent_kafka import Producer
        except ImportError as error:
            raise RuntimeError('confluent-kafka is required to run the Kafka adapter') from error

        conf: dict[str, Any] = {
            'bootstrap.servers': _to_bootstrap_servers(self.bootstrap_servers),
            'acks': self.acks,
            'retries': self.retries,
        }
        self._producer = Producer(conf)
        logger.info('Kafka producer connected: %s, topics: %s', self.bootstrap_servers, self.topics)

    def _serialize(self, payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False).encode('utf-8')

    def send(self, payload: dict[str, Any], key: str | None = None) -> None:
        """发送消息到所有已配置的 topic，发送后 flush 确保写入。

        与原 kafka-python 行为一致：不主动抛投递异常，仅记录日志；
        投递错误收集到 _delivery_errors，可由 has_delivery_errors() 查询。
        """
        if self._producer is None:
            raise RuntimeError('Kafka producer is not connected')
        value_bytes = self._serialize(payload)
        key_bytes = key.encode('utf-8') if key else None
        self._delivery_errors.clear()
        for topic in self.topics:
            self._producer.produce(
                topic, value=value_bytes, key=key_bytes,
                on_delivery=self._on_delivery,
            )
            self._producer.poll(0)
        self._producer.flush()

    def flush(self) -> None:
        """手动 flush 缓冲区。"""
        if self._producer is not None:
            self._producer.flush()

    def has_delivery_errors(self) -> bool:
        """返回上一次 send 是否有投递错误。"""
        return bool(self._delivery_errors)

    def is_connected(self) -> bool:
        """返回是否已连接。"""
        return self._producer is not None

    def close(self) -> None:
        """关闭生产者连接。"""
        if self._producer is not None:
            self._producer.flush()
            self._producer = None
            logger.info('Kafka producer closed')
