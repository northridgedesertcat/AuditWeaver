"""
规则匹配引擎主入口
从Kafka消费日志，进行攻击检测，保存结果到Elasticsearch和Kafka
"""

import sys
import os
import json
import logging
import time

import sys
sys.stdout.flush()

print("[INFO] 规则匹配引擎启动中...", flush=True)

_services_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(f"[INFO] _services_path: {_services_path}", flush=True)
if _services_path not in sys.path:
    sys.path.insert(0, _services_path)

print("[INFO] 导入模块...", flush=True)
from common.time_utils import now_utc, epoch_millis_now
from config import KAFKA_CONFIG, ELASTICSEARCH_CONFIG, LOG_CONFIG, DEBUG_CONFIG, PROCESSING_CONFIG
from match_config import RULES_CONFIG, DETECTION_CONFIG
from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.data_saver import DataSaver
print("[INFO] 模块导入完成", flush=True)

logging.basicConfig(
    level=getattr(logging, LOG_CONFIG['level']),
    format=LOG_CONFIG['format'],
    datefmt=LOG_CONFIG['date_format'],
    handlers=[
        logging.FileHandler(LOG_CONFIG['file_path'], encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

logger = logging.getLogger('rules_matching')
logger.info("日志系统初始化完成")


def create_kafka_consumer():
    from kafka import KafkaConsumer
    from kafka.errors import NoBrokersAvailable
    
    try:
        consumer = KafkaConsumer(
            KAFKA_CONFIG['input_topic'],
            bootstrap_servers=KAFKA_CONFIG['brokers'],
            group_id=KAFKA_CONFIG['group_id'],
            auto_offset_reset=KAFKA_CONFIG['auto_offset_reset'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        logger.info(f"[KAFKA] 消费者已连接到 topic: {KAFKA_CONFIG['input_topic']}")
        
        return consumer
    except NoBrokersAvailable:
        logger.error(f"[KAFKA] Broker不可用: {KAFKA_CONFIG['brokers']}")
        return None
    except Exception as e:
        logger.error(f"[KAFKA] 创建消费者失败: {str(e)}")
        return None


def main():
    logger.info("=" * 60)
    logger.info("规则匹配引擎启动")
    logger.info("=" * 60)
    
    logger.info(f"启动时间: {now_utc().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Kafka Broker: {KAFKA_CONFIG['brokers']}")
    logger.info(f"输入Topic: {KAFKA_CONFIG['input_topic']}")
    logger.info(f"输出Topic: {KAFKA_CONFIG['output_topic']}")
    logger.info(f"消费者组: {KAFKA_CONFIG['group_id']}")
    logger.info(f"Elasticsearch: {ELASTICSEARCH_CONFIG['host']}:{ELASTICSEARCH_CONFIG['port']}")
    logger.info(f"日志等级: {LOG_CONFIG['level']}")
    logger.info("-" * 60)
    
    consumer = None
    data_saver = None
    
    try:
        data_saver = DataSaver(
            es_host=ELASTICSEARCH_CONFIG['host'],
            es_port=ELASTICSEARCH_CONFIG['port'],
            es_index=ELASTICSEARCH_CONFIG['attack_index'],
            kafka_enabled=True,
            kafka_brokers=KAFKA_CONFIG['brokers'],
            kafka_topic=KAFKA_CONFIG['output_topic']
        )
        
        logger.debug(f"[PROCESS] Elasticsearch连接: {data_saver.is_es_connected()}")
        
        consumer = create_kafka_consumer()
        if not consumer:
            logger.error("[FATAL] 无法创建Kafka消费者，退出")
            return
        
        rule_engine = RuleEngine()
        
        logger.info("[PROCESS] 开始消费Kafka消息...")
        
        total_received = 0
        total_processed = 0
        heartbeat_interval = 10
        last_heartbeat_time = time.time()
        
        while True:
            try:
                logger.debug(f"[KAFKA] 轮询消息中... (timeout={KAFKA_CONFIG['poll_timeout_ms']}ms)")
                messages = consumer.poll(timeout_ms=KAFKA_CONFIG['poll_timeout_ms'])
                
                if messages:
                    for tp, records in messages.items():
                        for record in records:
                            total_received += 1
                            total_processed += 1
                            message = record.value
                            
                            try:
                                detection_result = rule_engine.detect(message)
                                
                                if 'detections' in detection_result and detection_result['detections']:
                                    save_result = data_saver.save_attack_log(message, detection_result['detections'])
                                    
                                    if save_result['attack_logs']['saved_es'] > 0:
                                        logger.info(f"[OK] 攻击日志 - Elasticsearch: 已保存={save_result['attack_logs']['saved_es']}")
                                        logger.info(f"     索引: '{ELASTICSEARCH_CONFIG['attack_index']}'")
                                    if save_result['attack_logs']['failed_es'] > 0:
                                        logger.error(f"[FAIL] 攻击日志 - Elasticsearch: 保存失败={save_result['attack_logs']['failed_es']}")
                                    
                                    if save_result.get('kafka', {}).get('sent', 0) > 0:
                                        logger.info(f"[OK] 攻击日志 - Kafka: 已发送到 {KAFKA_CONFIG['output_topic']}")
                                    
                                    if DEBUG_CONFIG['log_detection_details']:
                                        logger.debug(f"[DEBUG] 检测详情: {detection_result['detections']}")
                                else:
                                    if PROCESSING_CONFIG['save_normal_logs']:
                                        data_saver.save_normal_log(message)
                                
                            except Exception as e:
                                logger.error(f"[ERROR] 处理单条消息失败: {str(e)}", exc_info=True)
                
                current_time = time.time()
                if current_time - last_heartbeat_time >= heartbeat_interval:
                    logger.info(f"[HEARTBEAT] 运行中 | 已接收消息: {total_received} | 已处理消息: {total_processed}")
                    last_heartbeat_time = current_time
            
            except KeyboardInterrupt:
                logger.info("[PROCESS] 用户中断，正在关闭...")
                break
            except Exception as e:
                logger.error(f"[ERROR] 主循环异常: {str(e)}", exc_info=True)
                time.sleep(5)
        
        logger.info("[PROCESS] 规则匹配引擎已关闭")
    
    except Exception as e:
        logger.error(f"[FATAL] 启动失败: {str(e)}", exc_info=True)
        logger.error("[PROCESS] 请检查: Elasticsearch和Kafka服务是否正常运行")
        if data_saver and not data_saver.is_es_connected():
            logger.error(f"[PROCESS] Elasticsearch连接失败: {ELASTICSEARCH_CONFIG['host']}:{ELASTICSEARCH_CONFIG['port']}")
    finally:
        if consumer:
            consumer.close()
            logger.info("[KAFKA] 消费者已关闭")
        if data_saver:
            data_saver.close()


if __name__ == '__main__':
    main()
