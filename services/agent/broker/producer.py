# Kafka 生产者模块
# 将 Dify 分析结果发送到 agent.event.save topic，由 Kafka Connect Sink 写入 Elasticsearch

import json
import logging
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger('kafka_producer')

class AnalysisResultProducer:
    """分析结果生产者，将构建好的 ES 文档发送到 Kafka 输出 topic"""

    def __init__(self, bootstrap_servers: str, topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer: Optional[KafkaProducer] = None

    def connect(self) -> bool:
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
            )
            logger.info(f'Kafka producer connected: {self.bootstrap_servers}, topic: {self.topic}')
            return True
        except KafkaError as e:
            logger.error(f'Failed to connect Kafka producer: {str(e)}')
            return False

    def send(self, document: Dict[str, Any], key: str) -> bool:
        if not self.producer:
            logger.error('Kafka producer not connected')
            return False

        try:
            future = self.producer.send(self.topic, value=document, key=key)
            record_metadata = future.get(timeout=10)
            logger.info(
                f'Analysis result sent: topic={record_metadata.topic}, '
                f'partition={record_metadata.partition}, offset={record_metadata.offset}, '
                f'key={key}'
            )
            return True
        except Exception as e:
            logger.error(f'Failed to send analysis result (key={key}): {str(e)}')
            return False

    def is_connected(self) -> bool:
        return self.producer is not None

    def send_dlq(self, payload: Dict[str, Any], key: str = None) -> bool:
        """将处理失败的消息发送到死信队列"""
        if not self.producer:
            logger.error('Kafka producer not connected, cannot send to DLQ')
            return False
        try:
            future = self.producer.send(self.topic, value=payload, key=key)
            record_metadata = future.get(timeout=10)
            logger.info(
                f'DLQ message sent: topic={record_metadata.topic}, '
                f'partition={record_metadata.partition}, offset={record_metadata.offset}, '
                f'key={key}'
            )
            return True
        except Exception as e:
            logger.error(f'Failed to send DLQ message (key={key}): {str(e)}')
            return False

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info('Kafka producer closed')
