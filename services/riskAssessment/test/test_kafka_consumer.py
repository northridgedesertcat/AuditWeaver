# Kafka消费者测试脚本
# 用于验证Kafka是否正确接收和转发了规则匹配模块发送的数据
from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable
import json
import logging
import time
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('kafka_consumer_test')

class KafkaConsumerTest:
    """Kafka消费者测试类"""
    
    def __init__(self, bootstrap_servers='localhost:9092', topic='log.risk', group_id='risk_assessment_group'):
        """初始化Kafka消费者"""
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.consumer = None
        self.message_count = 0
        self.error_count = 0
    
    def connect(self):
        """连接到Kafka"""
        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset='latest',  # 从最新消息开始消费
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=30000  # 30秒超时
            )
            logger.info(f"成功连接到Kafka: {self.bootstrap_servers}")
            logger.info(f"订阅的topic: {self.topic}")
            return True
        except NoBrokersAvailable as e:
            logger.error(f"Kafka broker不可用: {self.bootstrap_servers}")
            logger.error(f"错误信息: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Kafka消费者初始化失败: {str(e)}")
            return False
    
    def consume_messages(self, max_messages=10, timeout=30):
        """消费消息"""
        if not self.consumer:
            logger.error("Kafka消费者未连接")
            return
        
        logger.info(f"开始消费消息，最多消费 {max_messages} 条，超时 {timeout} 秒")
        
        start_time = time.time()
        received_messages = []
        
        try:
            for message in self.consumer:
                elapsed_time = time.time() - start_time
                
                if elapsed_time > timeout:
                    logger.info(f"消费超时，已运行 {elapsed_time:.2f} 秒")
                    break
                
                if self.message_count >= max_messages:
                    logger.info(f"已达到最大消息数 {max_messages}")
                    break
                
                try:
                    # 解析消息
                    msg_value = message.value
                    self.message_count += 1
                    received_messages.append(msg_value)
                    
                    # 打印消息摘要
                    self._print_message_summary(msg_value, self.message_count)
                    
                except json.JSONDecodeError as e:
                    self.error_count += 1
                    logger.error(f"消息解析失败: {str(e)}")
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"处理消息失败: {str(e)}")
                    
        except KafkaError as e:
            logger.error(f"Kafka消费错误: {str(e)}")
        except KeyboardInterrupt:
            logger.info("用户中断消费")
        except Exception as e:
            logger.error(f"消费过程异常: {str(e)}")
        
        return received_messages
    
    def _print_message_summary(self, message, index):
        """打印消息摘要"""
        try:
            timestamp = message.get('timestamp', '未知')
            log_entry = message.get('log_entry', {})
            detection_result = message.get('detection_result', {})
            
            ip = log_entry.get('ip', '未知IP')
            method = log_entry.get('method', '未知方法')
            path = log_entry.get('path', '未知路径')
            
            rule_match = log_entry.get('rule_match', {})
            is_matched = rule_match.get('is_matched', False)
            attack_type = rule_match.get('attack_type', '未知')
            confidence = rule_match.get('confidence', 0.0)
            
            total_detections = detection_result.get('total_detections', 0)
            
            logger.info(f"\n--- 消息 #{index} ---")
            logger.info(f"时间戳: {timestamp}")
            logger.info(f"来源IP: {ip}")
            logger.info(f"请求方法: {method}")
            logger.info(f"请求路径: {path}")
            logger.info(f"是否匹配: {is_matched}")
            logger.info(f"攻击类型: {attack_type}")
            logger.info(f"置信度: {confidence:.2f}")
            logger.info(f"检测数量: {total_detections}")
            
        except Exception as e:
            logger.error(f"打印消息摘要失败: {str(e)}")
            logger.info(f"原始消息: {message}")
    
    def print_stats(self):
        """打印统计信息"""
        logger.info(f"\n=== 消费统计 ===")
        logger.info(f"成功接收消息: {self.message_count} 条")
        logger.info(f"处理错误消息: {self.error_count} 条")
        
        if self.message_count > 0:
            logger.info("✓ Kafka数据接收测试成功！")
        else:
            logger.warning("✗ 未接收到任何消息，请检查：")
            logger.warning("  - Kafka服务是否正常运行")
            logger.warning("  - Topic 'log.risk' 是否已创建")
            logger.warning("  - 规则匹配模块是否正在发送数据")
    
    def close(self):
        """关闭消费者"""
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka消费者已关闭")
            except Exception as e:
                logger.error(f"关闭消费者失败: {str(e)}")

def main():
    """主函数"""
    logger.info("=== Kafka消费者测试脚本 ===")
    
    # 创建消费者
    consumer = KafkaConsumerTest(
        bootstrap_servers='localhost:9092',
        topic='log.risk',
        group_id='risk_assessment_test_group'
    )
    
    # 连接Kafka
    if not consumer.connect():
        logger.error("无法连接到Kafka，测试终止")
        return
    
    try:
        # 开始消费
        consumer.consume_messages(max_messages=10, timeout=30)
        
        # 打印统计
        consumer.print_stats()
        
    finally:
        # 关闭连接
        consumer.close()

if __name__ == '__main__':
    main()
