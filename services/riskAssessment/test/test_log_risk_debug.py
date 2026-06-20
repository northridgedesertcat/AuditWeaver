# 调试脚本：查看 log.risk topic 中消息的实际结构
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kafka import KafkaConsumer

KAFKA_BROKERS = 'localhost:29092'
TOPIC = 'log.risk'

print("Debugging Kafka log.risk messages...")
print("Broker:", KAFKA_BROKERS)
print("Topic:", TOPIC)
print("")

try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKERS,
        group_id='debug_group',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=5000
    )
    
    print("Connected successfully")
    print("")
    
    count = 0
    for msg in consumer:
        data = msg.value
        count += 1
        print("=" * 50)
        print("Message #", count)
        print("=" * 50)
        print("Full message structure:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("")
        
        if count >= 2:
            break
    
    consumer.close()
    
    print("=" * 50)
    print("Total messages received:", count)
    sys.exit(0)
        
except Exception as e:
    print("ERROR:", str(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)