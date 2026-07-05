"""
检查 Kafka 消息格式
"""
import sys
import os
import json
import time

from kafka import KafkaConsumer

BROKER = 'localhost:29092'
TOPIC = 'log.audit'

print("=" * 60)
print("检查 Kafka 消息格式")
print("=" * 60)

consumer = None
try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        group_id=f'test_group_format_{int(time.time())}',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=10000
    )
    
    print(f"✓ 消费者创建成功")
    
    print(f"\n等待消息...")
    for i in range(5):
        messages = consumer.poll(timeout_ms=2000)
        if messages:
            for tp, records in messages.items():
                for record in records:
                    msg = record.value
                    print(f"\n消息内容:")
                    print(json.dumps(msg, ensure_ascii=False, indent=2))
                    print(f"\n消息字段: {list(msg.keys())}")
                    
                    required_fields = ['ip', 'path', 'method', 'status']
                    print(f"\n验证必需字段:")
                    for field in required_fields:
                        if field in msg:
                            print(f"  ✓ {field}: {msg[field]}")
                        else:
                            print(f"  ✗ {field}: 缺失")
                    
                    break
                break
            break
        time.sleep(1)
    
    if not messages:
        print(f"\n✗ 没有收到消息")
        
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
finally:
    if consumer:
        consumer.close()
        print("\n消费者已关闭")

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)