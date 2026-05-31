# 指标收集器
from typing import Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.metrics = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_completed": 0,
            "dify_calls": 0,
            "dify_errors": 0,
            "kafka_messages_produced": 0,
            "kafka_messages_consumed": 0,
            "es_reads": 0,
            "es_writes": 0,
            "started_at": datetime.now().isoformat()
        }
        self.lock = __import__("threading").Lock()
    
    def increment(self, key: str):
        """增加指标计数"""
        with self.lock:
            if key in self.metrics:
                self.metrics[key] += 1
            else:
                self.metrics[key] = 1
    
    def decrement(self, key: str):
        """减少指标计数"""
        with self.lock:
            if key in self.metrics and self.metrics[key] > 0:
                self.metrics[key] -= 1
    
    def set(self, key: str, value):
        """设置指标值"""
        with self.lock:
            self.metrics[key] = value
    
    def get(self, key: str):
        """获取指标值"""
        return self.metrics.get(key)
    
    def get_all(self) -> Dict:
        """获取所有指标"""
        with self.lock:
            return self.metrics.copy()
    
    def reset(self):
        """重置指标"""
        with self.lock:
            self.metrics = {
                "tasks_processed": 0,
                "tasks_failed": 0,
                "tasks_completed": 0,
                "dify_calls": 0,
                "dify_errors": 0,
                "kafka_messages_produced": 0,
                "kafka_messages_consumed": 0,
                "es_reads": 0,
                "es_writes": 0,
                "started_at": datetime.now().isoformat()
            }
    
    def report(self):
        """输出指标报告"""
        metrics = self.get_all()
        logger.info("=== 指标报告 ===")
        for key, value in metrics.items():
            logger.info(f"{key}: {value}")
        logger.info("===============")
