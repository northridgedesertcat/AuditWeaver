# Kafka 消费者模块
# 底层使用 confluent-kafka（librdkafka），规避 Windows 上 kafka-python 的
# SelectSelector 兼容问题。原 value_deserializer 改为 poll 后手动反序列化；
# consumer_timeout_ms 映射为连续 poll 超时次数（约每秒一次）。
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger('kafka_consumer')


def _to_bootstrap_servers(value):
    """confluent-kafka 要求 bootstrap.servers 为逗号分隔字符串。"""
    if isinstance(value, (list, tuple)):
        return ','.join(str(v) for v in value)
    return str(value)


class LogAnalysisConsumer:
    def __init__(self, bootstrap_servers: str, topic: str, group_id: str,
                 auto_offset_reset: str = 'earliest', consumer_timeout_ms: int = 5000):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        # confluent 无 consumer_timeout_ms 配置，靠 poll 超时次数实现
        self.consumer_timeout_ms = consumer_timeout_ms
        self.consumer: Optional[Any] = None

    def connect(self) -> bool:
        try:
            from confluent_kafka import Consumer
            from confluent_kafka.error import KafkaException
        except ImportError as e:
            logger.error(f'confluent-kafka is required to run the Kafka adapter: {e}')
            return False
        try:
            self.consumer = Consumer({
                'bootstrap.servers': _to_bootstrap_servers(self.bootstrap_servers),
                'group.id': self.group_id,
                'auto.offset.reset': self.auto_offset_reset,
                'enable.auto.commit': True,
            })
            self.consumer.subscribe([self.topic])
            logger.info(f'Connected to Kafka: {self.bootstrap_servers}, topic: {self.topic}')
            return True
        except KafkaException as e:
            logger.error(f'Failed to connect to Kafka: {str(e)}')
            return False

    def consume(self, max_records: int = 10) -> List[Dict[str, Any]]:
        if not self.consumer:
            logger.error('Kafka consumer not connected')
            return []

        messages = []
        empty_polls = 0
        # consumer_timeout_ms(默认 5000)映射为连续 poll 超时上限：约每秒一次
        max_empty_polls = max(1, self.consumer_timeout_ms // 1000)
        try:
            while len(messages) < max_records:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    empty_polls += 1
                    if empty_polls >= max_empty_polls:
                        break
                    continue
                empty_polls = 0
                if msg.error() is not None:
                    logger.error(f'Consumer error: {msg.error()}')
                    continue
                try:
                    messages.append(json.loads(msg.value().decode('utf-8')))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.error(f'Deserialize error: {e}')
                    continue
        except Exception as e:
            logger.error(f'Error consuming messages: {str(e)}')

        return messages

    def consume_single(self) -> Optional[Dict[str, Any]]:
        messages = self.consume(max_records=1)
        return messages[0] if messages else None

    def is_connected(self) -> bool:
        return self.consumer is not None

    def close(self):
        if self.consumer:
            self.consumer.close()
            logger.info('Kafka consumer closed')
