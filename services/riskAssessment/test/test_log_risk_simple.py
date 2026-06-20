# 简单测试脚本：验证能否从 Kafka log.risk topic 接收数据
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kafka import KafkaConsumer

KAFKA_BROKERS = 'localhost:29092'
TOPIC = 'log.risk'

print("Testing Kafka log.risk consumer...")
print("Broker:", KAFKA_BROKERS)
print("Topic:", TOPIC)
print("")

try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKERS,
        group_id='test_group',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=5000
    )
    
    print("Connected successfully")
    print("Waiting for messages...")
    
    count = 0
    for msg in consumer:
        data = msg.value
        print("Message received:")
        print("  event_id:", data.get('event_id', 'N/A'))
        print("  ip:", data.get('ip', 'N/A'))
        print("  attack_type:", data.get('rule_match', {}).get('attack_type', 'N/A'))
        count += 1
        if count >= 3:
            break
    
    consumer.close()
    
    if count > 0:
        print("")
        print("SUCCESS: Received", count, "messages from log.risk")
        sys.exit(0)
    else:
        print("")
        print("NO MESSAGES: No messages received in 5 seconds")
        sys.exit(1)
        
except Exception as e:
    print("ERROR:", str(e))
    sys.exit(1)