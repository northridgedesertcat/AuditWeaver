# Kafka 生产者模块
# 将 Dify 分析结果发送到 agent.event.save topic，由 Kafka Connect Sink 写入 Elasticsearch
# DlqProducer 已提取到 core.kafka.dlq，send_dlq() 不再在此维护
#
# 底层使用 confluent-kafka（librdkafka）。原 future.get(timeout=10) 的同步语义
# 通过 on_delivery 回调 + flush() 实现；10s 超时由 message.timeout.ms=10000 保证。
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('kafka_producer')


def _to_bootstrap_servers(value):
    """confluent-kafka 要求 bootstrap.servers 为逗号分隔字符串。"""
    if isinstance(value, (list, tuple)):
        return ','.join(str(v) for v in value)
    return str(value)


class AnalysisResultProducer:
    """分析结果生产者，将构建好的 ES 文档发送到 Kafka 输出 topic。"""

    def __init__(self, bootstrap_servers: str, topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer: Optional[Any] = None

    def connect(self) -> bool:
        try:
            from confluent_kafka import Producer
            from confluent_kafka.error import KafkaException
        except ImportError as e:
            logger.error(f'confluent-kafka is required to run the Kafka adapter: {e}')
            return False
        try:
            self.producer = Producer({
                'bootstrap.servers': _to_bootstrap_servers(self.bootstrap_servers),
                'acks': 'all',
                'retries': 3,
                # 对应原 future.get(timeout=10)：librdkafka 内部 10s 投递超时后回调 err
                'message.timeout.ms': 10000,
            })
            logger.info(f'Kafka producer connected: {self.bootstrap_servers}, topic: {self.topic}')
            return True
        except KafkaException as e:
            logger.error(f'Failed to connect Kafka producer: {str(e)}')
            return False

    def send(self, document: Dict[str, Any], key: str) -> bool:
        if not self.producer:
            logger.error('Kafka producer not connected')
            return False

        try:
            value_bytes = json.dumps(document, ensure_ascii=False).encode('utf-8')
            key_bytes = key.encode('utf-8') if key else None
            # 用闭包收集投递结果，flush() 阻塞直到回调触发
            result = {'err': None, 'msg': None}

            def on_delivery(err, msg):
                result['err'] = err
                result['msg'] = msg

            self.producer.produce(
                self.topic, value=value_bytes, key=key_bytes,
                on_delivery=on_delivery,
            )
            self.producer.flush()

            if result['msg'] is None:
                logger.error(f'Failed to send analysis result (key={key}): no delivery confirmation')
                return False
            if result['err'] is not None:
                logger.error(f'Failed to send analysis result (key={key}): {result["err"]}')
                return False
            msg = result['msg']
            logger.info(
                f'Analysis result sent: topic={msg.topic()}, '
                f'partition={msg.partition()}, offset={msg.offset()}, '
                f'key={key}'
            )
            return True
        except Exception as e:
            logger.error(f'Failed to send analysis result (key={key}): {str(e)}')
            return False

    def is_connected(self) -> bool:
        return self.producer is not None

    def close(self):
        if self.producer:
            self.producer.flush()
            self.producer = None
            logger.info('Kafka producer closed')
