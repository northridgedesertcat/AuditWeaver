"""通用 Kafka 生产者基类。

提供 JSON 序列化、单/多 topic 发送。
各模块直接实例化或子类化添加特有逻辑。
"""

from __future__ import annotations

import json
import logging
from typing import Any

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

    def connect(self) -> None:
        """建立 Kafka 连接，失败时抛出 RuntimeError。"""
        try:
            from kafka import KafkaProducer
        except ImportError as error:
            raise RuntimeError('kafka-python is required to run the Kafka adapter') from error

        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            acks=self.acks,
            retries=self.retries,
        )
        logger.info('Kafka producer connected: %s, topics: %s', self.bootstrap_servers, self.topics)

    def send(self, payload: dict[str, Any], key: str | None = None) -> None:
        """发送消息到所有已配置的 topic，发送后 flush 确保写入。"""
        if self._producer is None:
            raise RuntimeError('Kafka producer is not connected')
        for topic in self.topics:
            self._producer.send(topic, value=payload, key=key)
        self._producer.flush()

    def flush(self) -> None:
        """手动 flush 缓冲区。"""
        if self._producer is not None:
            self._producer.flush()

    def is_connected(self) -> bool:
        """返回是否已连接。"""
        return self._producer is not None

    def close(self) -> None:
        """关闭生产者连接。"""
        if self._producer is not None:
            self._producer.flush()
            self._producer.close()
            self._producer = None
            logger.info('Kafka producer closed')
