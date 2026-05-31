# Kafka 消费者 - 负责单个消费者的生命周期管理
from kafka import KafkaConsumer as KafkaLibConsumer
from kafka.errors import KafkaError
from typing import Dict, Optional
import json
import logging
import threading

logger = logging.getLogger(__name__)


class KafkaConsumerClient:
    """Kafka 消费者客户端 - 每个 Worker 拥有独立的实例"""
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "log-processing",
        group_id: str = "log-sentinel-agent",
        auto_offset_reset: str = "latest"
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self._consumer = None
        self._running = False
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """建立连接"""
        if self._consumer is not None:
            return True
            
        try:
            self._consumer = KafkaLibConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers.split(","),
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                consumer_timeout_ms=1000
            )
            logger.info(f"[{threading.current_thread().name}] 成功连接到 Kafka 主题: {self.topic}, 分组: {self.group_id}")
            return True
        except Exception as e:
            logger.error(f"[{threading.current_thread().name}] Kafka 消费者连接失败: {str(e)}")
            return False
    
    def poll(self, timeout_ms: int = 1000) -> Optional[Dict]:
        """轮询获取单条消息"""
        if self._consumer is None:
            return None
            
        try:
            with self._lock:
                messages = self._consumer.poll(timeout_ms=timeout_ms)
                for _, records in messages.items():
                    for record in records:
                        return record.value
            return None
        except Exception as e:
            logger.error(f"[{threading.current_thread().name}] 轮询消息失败: {str(e)}")
            return None
    
    def start_consuming(self):
        """开始消费（仅设置标志，不真正消费）"""
        self._running = True
        logger.info(f"[{threading.current_thread().name}] 消费者开始工作")
    
    def stop_consuming(self):
        """停止消费"""
        self._running = False
        logger.info(f"[{threading.current_thread().name}] 消费者停止工作")
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    def close(self):
        """关闭连接"""
        with self._lock:
            if self._consumer is not None:
                self._consumer.close()
                self._consumer = None
                logger.info(f"[{threading.current_thread().name}] Kafka 消费者已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
