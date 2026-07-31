# Kafka 消费者模块
import json
import logging
from typing import List, Dict, Any, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger('kafka_consumer')

class LogAnalysisConsumer:
    def __init__(self, bootstrap_servers: str, topic: str, group_id: str,
                 auto_offset_reset: str = 'earliest', consumer_timeout_ms: int = 5000):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.consumer_timeout_ms = consumer_timeout_ms
        self.consumer: Optional[KafkaConsumer] = None

    def connect(self) -> bool:
        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                consumer_timeout_ms=self.consumer_timeout_ms,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                enable_auto_commit=True
            )
            logger.info(f'Connected to Kafka: {self.bootstrap_servers}, topic: {self.topic}')
            return True
        except KafkaError as e:
            logger.error(f'Failed to connect to Kafka: {str(e)}')
            return False

    def consume(self, max_records: int = 10) -> List[Dict[str, Any]]:
        if not self.consumer:
            logger.error('Kafka consumer not connected')
            return []

        messages = []
        try:
            for message in self.consumer:
                messages.append(message.value)
                if len(messages) >= max_records:
                    break
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
