# Kafka 生产者
from kafka import KafkaProducer as KafkaLibProducer
from kafka.errors import KafkaError
from typing import Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka 消息生产者"""
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "log-processing"
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
    
    def connect(self) -> bool:
        """建立连接"""
        try:
            self.producer = KafkaLibProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                retries=3,
                acks="all"
            )
            logger.info(f"成功连接到 Kafka: {self.bootstrap_servers}")
            return True
        except Exception as e:
            logger.error(f"Kafka 连接失败: {str(e)}")
            return False
    
    def send(self, message: Dict, key: Optional[str] = None) -> bool:
        """发送消息"""
        try:
            future = self.producer.send(
                self.topic,
                value=message,
                key=key.encode("utf-8") if key else None
            )
            record_metadata = future.get(timeout=10)
            logger.debug(f"消息已发送到 {record_metadata.topic}[{record_metadata.partition}]")
            return True
        except KafkaError as e:
            logger.error(f"发送消息失败: {str(e)}")
            return False
    
    def send_batch(self, messages: list) -> Dict[str, int]:
        """批量发送消息"""
        success = 0
        failed = 0
        for msg in messages:
            if self.send(msg):
                success += 1
            else:
                failed += 1
        logger.info(f"批量发送完成: {success}/{len(messages)}")
        return {"success": success, "failed": failed}
    
    def flush(self):
        """刷新消息"""
        if self.producer:
            self.producer.flush()
    
    def close(self):
        """关闭连接"""
        if self.producer:
            self.producer.close()
