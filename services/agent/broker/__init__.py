# 消息代理模块（Kafka 消费者；分析结果改为直接写 MySQL，不再需要结果生产者）
from .consumer import LogAnalysisConsumer

__all__ = ['LogAnalysisConsumer']
