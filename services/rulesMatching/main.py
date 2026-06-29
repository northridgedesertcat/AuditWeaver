"""
规则匹配引擎主入口
从Kafka消费日志，进行攻击检测，保存结果到Elasticsearch和Kafka
"""

import sys
import os
import json
import logging
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入配置和模块
from config import KAFKA_CONFIG, ELASTICSEARCH_CONFIG, LOG_CONFIG, DEBUG_CONFIG
from match_config import RULES_CONFIG, DETECTION_CONFIG
from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.data_saver import DataSaver

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_CONFIG['level']),
    format=LOG_CONFIG['format'],
    datefmt=LOG_CONFIG['date_format'],
    handlers=[
        logging.FileHandler(LOG_CONFIG['file_path'], encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('rules_matching')

def setup_logging():
    """设置详细的日志记录"""
    logger.setLevel(logging.DEBUG if DEBUG_CONFIG['enable_debug_logging'] else logging.INFO)
    
    # 创建格式器
    formatter = logging.Formatter(LOG_CONFIG['format'], datefmt=LOG_CONFIG['date_format'])
    
    # 文件处理器
    file_handler = logging.FileHandler(LOG_CONFIG['file_path'], encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG_CONFIG['enable_debug_logging'] else logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.debug("=== 日志系统初始化完成 ===")

def validate_kafka_message(message):
    """验证Kafka消息格式是否正确"""
    required_fields = ['ip', 'method', 'path', 'status']
    
    if not isinstance(message, dict):
        logger.debug(f"[VALIDATION] 消息不是字典类型: {type(message)}")
        return False
    
    # 检查必需字段
    missing_fields = [field for field in required_fields if field not in message]
    if missing_fields:
        logger.debug(f"[VALIDATION] 缺少必需字段: {missing_fields}")
        return False
    
    # 检查时间戳字段
    if 'timestamp' not in message and '@timestamp' not in message:
        logger.debug(f"[VALIDATION] 缺少时间戳字段")
        return False
    
    logger.debug(f"[VALIDATION] 消息格式验证通过: ip={message.get('ip')}, path={message.get('path')[:50] if message.get('path') else 'N/A'}")
    return True

def process_logs(logs):
    """处理日志并保存结果"""
    if not logs:
        logger.debug("[PROCESS] 没有待处理的日志")
        return
    
    logger.debug(f"[PROCESS] 开始处理 {len(logs)} 条日志")
    
    # 创建规则引擎
    logger.debug("[PROCESS] 创建规则引擎...")
    engine = RuleEngine()
    logger.debug("[PROCESS] 规则引擎创建完成")
    
    # 检测攻击
    logger.debug(f"[PROCESS] 开始检测攻击...")
    start_time = time.time()
    result = engine.detect_batch(logs)
    detection_time = time.time() - start_time
    logger.debug(f"[PROCESS] 攻击检测完成，耗时 {detection_time:.2f} 秒")
    
    logger.debug(f"[DETECTION] 检测结果: 总日志={result['total_logs']}, 检测到攻击={result['total_detections']}")
    
    if DEBUG_CONFIG['log_detection_details']:
        for i, log in enumerate(logs):
            if i < len(result['results']):
                detections = result['results'][i].get('detections', [])
                if detections:
                    logger.debug(f"[DETECTION] 日志 {i+1}: IP={log['ip']}, 检测到 {len(detections)} 种攻击")
                    for det in detections:
                        logger.debug(f"            - 攻击类型: {det['matched_type']}, 置信度: {det['confidence']*100:.1f}%")
                else:
                    logger.debug(f"[DETECTION] 日志 {i+1}: IP={log['ip']}, 未检测到攻击")
    
    # 创建DataSaver
    logger.debug("[PROCESS] 创建DataSaver...")
    data_saver = DataSaver(
        kafka_enabled=True,
        kafka_brokers=KAFKA_CONFIG['brokers'],
        kafka_topic=KAFKA_CONFIG['output_topic'],
        es_host=ELASTICSEARCH_CONFIG['host'],
        es_port=ELASTICSEARCH_CONFIG['port'],
        es_index=ELASTICSEARCH_CONFIG['attack_index']
    )
    logger.debug("[PROCESS] DataSaver创建完成")
    
    # 检查连接状态
    logger.debug(f"[PROCESS] Elasticsearch连接: {data_saver.is_es_connected()}")
    logger.debug(f"[PROCESS] Kafka连接: {data_saver.is_kafka_connected()}")
    
    # 保存检测结果
    logger.debug("[PROCESS] 准备保存结果...")
    if data_saver.is_connected():
        start_time = time.time()
        save_result = data_saver.process_and_save(logs, result)
        save_time = time.time() - start_time
        
        logger.debug(f"[PROCESS] 保存完成，耗时 {save_time:.2f} 秒")
        logger.info(f"====== 处理结果 ======")
        logger.info(f"总日志数: {result['total_logs']}")
        logger.info(f"检测到攻击: {result['total_detections']}")
        
        # 只有在实际保存成功后才显示成功消息
        if save_result['attack_logs']['saved_es'] > 0:
            logger.info(f"[OK] 攻击日志 - Elasticsearch: 已保存={save_result['attack_logs']['saved_es']} (已验证)")
            logger.info(f"     索引: '{ELASTICSEARCH_CONFIG['attack_index']}'")
        if save_result['attack_logs']['failed_es'] > 0:
            logger.error(f"[FAIL] 攻击日志 - Elasticsearch: 保存失败={save_result['attack_logs']['failed_es']}")
        
        if save_result['attack_logs']['saved_kafka'] > 0:
            logger.info(f"[OK] 攻击日志 - Kafka: 已发送={save_result['attack_logs']['saved_kafka']} (已刷新)")
            logger.info(f"     Topic: '{KAFKA_CONFIG['output_topic']}'")
        if save_result['attack_logs']['failed_kafka'] > 0:
            logger.error(f"[FAIL] 攻击日志 - Kafka: 发送失败={save_result['attack_logs']['failed_kafka']}")
        
        logger.info(f"正常日志: 已保存={save_result['normal_logs']['saved']}, 失败={save_result['normal_logs']['failed']}")
        
        # 检查是否有失败
        if save_result['attack_logs']['failed_es'] > 0:
            logger.error(f"警告: {save_result['attack_logs']['failed_es']} 条攻击日志保存到Elasticsearch失败")
        if save_result['attack_logs']['failed_kafka'] > 0:
            logger.error(f"警告: {save_result['attack_logs']['failed_kafka']} 条攻击日志发送到Kafka失败")
    else:
        logger.error("[PROCESS] 无法保存结果: DataSaver未连接")
        logger.error("[PROCESS] 请检查: Elasticsearch和Kafka服务是否正常运行")
        
        if not data_saver.is_es_connected():
            logger.error(f"[PROCESS] Elasticsearch连接失败: {ELASTICSEARCH_CONFIG['host']}:{ELASTICSEARCH_CONFIG['port']}")
        if not data_saver.is_kafka_connected():
            logger.error(f"[PROCESS] Kafka连接失败: {KAFKA_CONFIG['brokers']}")
    
    data_saver.close()
    logger.debug("[PROCESS] 处理完成")

def main():
    """主函数"""
    setup_logging()
    logger.info("="*70)
    logger.info("    规则匹配引擎启动")
    logger.info("="*70)
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Kafka Broker: {KAFKA_CONFIG['brokers']}")
    logger.info(f"输入Topic: {KAFKA_CONFIG['input_topic']}")
    logger.info(f"输出Topic: {KAFKA_CONFIG['output_topic']}")
    logger.info(f"消费者组: {KAFKA_CONFIG['group_id']}")
    logger.info(f"Elasticsearch: {ELASTICSEARCH_CONFIG['host']}:{ELASTICSEARCH_CONFIG['port']}")
    logger.info(f"日志等级: {LOG_CONFIG['level']}")
    logger.info("-"*70)
    
    try:
        # 创建Kafka消费者
        from kafka import KafkaConsumer
        
        logger.debug("[KAFKA] 创建Kafka消费者...")
        consumer = KafkaConsumer(
            KAFKA_CONFIG['input_topic'],
            bootstrap_servers=KAFKA_CONFIG['brokers'],
            group_id=KAFKA_CONFIG['group_id'],
            auto_offset_reset=KAFKA_CONFIG['auto_offset_reset'],
            enable_auto_commit=KAFKA_CONFIG['enable_auto_commit'],
            auto_commit_interval_ms=KAFKA_CONFIG['auto_commit_interval_ms'],
            max_poll_records=KAFKA_CONFIG['max_poll_records'],
            session_timeout_ms=KAFKA_CONFIG['session_timeout_ms'],
            request_timeout_ms=KAFKA_CONFIG['request_timeout_ms'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        logger.info(f"[KAFKA] 消费者已连接到 topic: {KAFKA_CONFIG['input_topic']}")
        logger.debug(f"[KAFKA] 消费者配置: group_id={KAFKA_CONFIG['group_id']}, auto_offset_reset={KAFKA_CONFIG['auto_offset_reset']}")
        
        last_heartbeat = time.time()
        total_messages_received = 0
        total_messages_processed = 0
        
        while True:
            try:
                # 轮询消息
                logger.debug(f"[KAFKA] 轮询消息中... (timeout={KAFKA_CONFIG['poll_timeout_ms']}ms)")
                messages = consumer.poll(timeout_ms=KAFKA_CONFIG['poll_timeout_ms'])
                
                if messages:
                    logs = []
                    for topic_partition, records in messages.items():
                        for record in records:
                            total_messages_received += 1
                            message = record.value
                            
                            if DEBUG_CONFIG['log_kafka_messages']:
                                logger.debug(f"[KAFKA] 收到消息: partition={topic_partition.partition}, offset={record.offset}")
                                logger.debug(f"[KAFKA] 消息内容: {json.dumps(message, ensure_ascii=False)[:200]}...")
                            
                            # 验证消息格式
                            if validate_kafka_message(message):
                                logs.append(message)
                            else:
                                logger.debug(f"[KAFKA] 消息格式无效，跳过")
                    
                    if logs:
                        logger.debug(f"[KAFKA] 有效消息数: {len(logs)}/{len([r for _, records in messages.items() for r in records])}")
                        process_logs(logs)
                        total_messages_processed += len(logs)
                
                # 心跳日志
                current_time = time.time()
                if current_time - last_heartbeat >= KAFKA_CONFIG['heartbeat_interval_seconds']:
                    logger.info(f"[HEARTBEAT] 运行中 | 已接收消息: {total_messages_received} | 已处理消息: {total_messages_processed}")
                    last_heartbeat = current_time
                
            except Exception as e:
                logger.error(f"[KAFKA] 消费消息时发生错误: {str(e)}", exc_info=True)
                time.sleep(5)  # 等待5秒后重试
    
    except KeyboardInterrupt:
        logger.info("收到终止信号，正在退出...")
    except Exception as e:
        logger.error(f"[ERROR] 启动失败: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()