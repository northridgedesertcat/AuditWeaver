# Kafka生产者模块
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
import json
import logging

logger = logging.getLogger('kafka_producer')

class KafkaProducerClient:
    """Kafka生产者客户端类，负责将数据发送到Kafka消息队列"""
    
    def __init__(self, bootstrap_servers='localhost:29092', topic='log.risk'):
        """初始化Kafka生产者"""
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self.connect()
    
    def connect(self):
        """连接到Kafka集群"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                retries=3,
                acks='all',
                linger_ms=10,
                batch_size=16384
            )
            logger.info(f"成功连接到Kafka: {self.bootstrap_servers}")
        except NoBrokersAvailable as e:
            logger.error(f"Kafka broker不可用: {self.bootstrap_servers}, 错误: {str(e)}")
            self.producer = None
        except Exception as e:
            logger.error(f"Kafka初始化错误: {str(e)}")
            self.producer = None
    
    def is_connected(self):
        """检查是否连接成功"""
        return self.producer is not None
    
    def send_message(self, message, key=None):
        """发送消息到Kafka topic"""
        if not self.producer:
            logger.error("Kafka生产者未连接")
            return False
        
        try:
            future = self.producer.send(
                self.topic,
                value=message,
                key=key
            )
            
            # 异步发送，不阻塞
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)
            
            return True
        except Exception as e:
            logger.error(f"发送消息到Kafka失败: {str(e)}")
            return False
    
    def send_message_sync(self, message, key=None, timeout=10):
        """同步发送消息到Kafka topic"""
        if not self.producer:
            logger.error("Kafka生产者未连接")
            return False
        
        try:
            future = self.producer.send(
                self.topic,
                value=message,
                key=key
            )
            
            # 同步等待发送结果
            record_metadata = future.get(timeout=timeout)
            logger.info(f"消息已发送到Kafka: topic={record_metadata.topic}, partition={record_metadata.partition}, offset={record_metadata.offset}")
            return True
        except KafkaError as e:
            logger.error(f"Kafka发送错误: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"发送消息到Kafka失败: {str(e)}")
            return False
    
    def _on_send_success(self, record_metadata):
        """消息发送成功回调"""
        logger.debug(f"消息发送成功: topic={record_metadata.topic}, partition={record_metadata.partition}, offset={record_metadata.offset}")
    
    def _on_send_error(self, exc):
        """消息发送失败回调"""
        logger.error(f"消息发送失败: {str(exc)}")
    
    def flush(self, timeout=None):
        """刷新缓冲区，确保所有消息都已发送"""
        if self.producer:
            try:
                self.producer.flush(timeout=timeout)
                logger.info("Kafka缓冲区已刷新")
            except Exception as e:
                logger.error(f"刷新Kafka缓冲区失败: {str(e)}")
    
    def close(self):
        """关闭Kafka生产者"""
        if self.producer:
            try:
                self.producer.close()
                logger.info("Kafka生产者已关闭")
            except Exception as e:
                logger.error(f"关闭Kafka生产者失败: {str(e)}")
            finally:
                self.producer = None
