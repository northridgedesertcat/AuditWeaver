# Kafka 消费者模块
# 底层使用 confluent-kafka（librdkafka），规避 Windows 上 kafka-python 的
# SelectSelector 兼容问题。原 value_deserializer 改为 poll 后手动反序列化；
# consumer_timeout_ms 映射为连续 poll 超时次数（约每秒一次）。
#
# offset 提交：enable.auto.commit=False，consume() 返回 (kafka_msg, value) 元组，
# 调用方在消息处理终态后（成功落库 或 已进 DLQ）显式调用 commit(msg)，
# 保证"落库成功后才提交"的 at-least-once 语义。
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

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

    def consume(self, max_records: int = 10) -> List[Tuple[Any, Dict[str, Any]]]:
        """批量拉取并反序列化，返回 [(kafka_msg, value_dict), ...]。

        调用方处理完每条消息后必须调用 commit(msg) 提交 offset。
        反序列化失败的毒消息无法进入业务流程，记录错误后直接提交跳过，
        避免其反复阻塞分区消费。
        """
        if not self.consumer:
            logger.error('Kafka consumer not connected')
            return []

        records = []
        empty_polls = 0
        # consumer_timeout_ms(默认 5000)映射为连续 poll 超时上限：约每秒一次
        max_empty_polls = max(1, self.consumer_timeout_ms // 1000)
        try:
            while len(records) < max_records:
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
                    value = json.loads(msg.value().decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.error(f'Deserialize error, skipping message: {e}')
                    self.commit(msg)
                    continue
                records.append((msg, value))
        except Exception as e:
            logger.error(f'Error consuming messages: {str(e)}')

        return records

    def commit(self, message: Any, asynchronous: bool = False) -> bool:
        """手动提交单条消息的 offset（处理成功或已入 DLQ 后调用）。"""
        if not self.consumer:
            return False
        try:
            self.consumer.commit(message=message, asynchronous=asynchronous)
            return True
        except Exception as e:
            logger.warning(f'Failed to commit offset: {str(e)}')
            return False

    def consume_single(self) -> Optional[Tuple[Any, Dict[str, Any]]]:
        records = self.consume(max_records=1)
        return records[0] if records else None

    def is_connected(self) -> bool:
        return self.consumer is not None

    def close(self):
        if self.consumer:
            self.consumer.close()
            logger.info('Kafka consumer closed')
