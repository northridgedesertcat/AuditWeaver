# 测试脚本：验证能否从 Kafka log.risk topic 接收数据
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kafka import KafkaConsumer

KAFKA_BROKERS = 'localhost:29092'
TOPIC = 'log.risk'
GROUP_ID = 'risk_assessment_test_group_v1'

def test_kafka_risk_consumer():
    print("=" * 60)
    print("测试 Kafka log.risk topic 消费")
    print("=" * 60)
    
    print("\n[步骤1] 创建 Kafka 消费者...")
    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_BROKERS,
            group_id=GROUP_ID,
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=10000
        )
        print("  [OK] 成功连接到 Kafka: %s" % KAFKA_BROKERS)
        print("  [OK] 订阅 topic: %s" % TOPIC)
        
    except Exception as e:
        print("  [FAIL] 连接失败: %s" % str(e))
        return False
    
    print("\n[步骤2] 开始消费消息 (等待10秒)...")
    message_count = 0
    start_time = time.time()
    
    try:
        for message in consumer:
            message_count += 1
            data = message.value
            
            # 解析嵌套的消息结构
            log_entry = data.get('log_entry', {})
            event_id = log_entry.get('event_id', 'N/A')
            ip = log_entry.get('ip', 'N/A')
            rule_match = log_entry.get('rule_match', {})
            attack_type = rule_match.get('matched_type', 'N/A')
            confidence = rule_match.get('confidence', 0) * 100
            ingestion_time = log_entry.get('ingestion_time', 'N/A')
            
            print("\n  消息 #%d:" % message_count)
            print("    event_id: %s" % event_id)
            print("    ip: %s" % ip)
            print("    attack_type: %s" % attack_type)
            print("    confidence: %.1f%%" % confidence)
            print("    ingestion_time: %s" % ingestion_time)
            
            if message_count >= 5:
                print("\n  已显示5条消息，停止消费")
                break
                
    except Exception as e:
        print("  [FAIL] 消费消息失败: %s" % str(e))
        return False
    finally:
        consumer.close()
        
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    print("  连接状态: [OK] 成功")
    print("  消费时长: %.2f 秒" % elapsed_time)
    print("  收到消息数: %d" % message_count)
    
    if message_count > 0:
        print("\n  SUCCESS: 成功从 log.risk 接收到 %d 条风险日志！" % message_count)
        return True
    else:
        print("\n  WARNING: 未收到任何消息")
        return False

if __name__ == "__main__":
    success = test_kafka_risk_consumer()
    sys.exit(0 if success else 1)