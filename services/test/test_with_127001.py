"""
使用 127.0.0.1 测试 Kafka
"""
import sys
import os
import json
import time

from kafka import KafkaConsumer

BROKER = '127.0.0.1:29092'
TOPIC = 'log.audit'

print("=" * 60)
print(f"使用 {BROKER} 测试 Kafka")
print("=" * 60)

consumer = None
try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        group_id=f'test_group_127001_{int(time.time())}',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=15000
    )
    
    print(f"✓ 消费者创建成功")
    
    for i in range(15):
        assigned = consumer.assignment()
        print(f"  第{i+1}秒 - 分区: {assigned}")
        if assigned:
            print(f"\n✓ 分区分配成功！")
            
            messages = consumer.poll(timeout_ms=3000)
            if messages:
                total = 0
                for tp, records in messages.items():
                    for record in records:
                        total += 1
                        print(f"  消息 #{total}: {json.dumps(record.value, ensure_ascii=False)[:80]}")
                print(f"\n✓ 成功收到 {total} 条消息！")
            else:
                print(f"\n提示: 没有新消息")
                
            break
        time.sleep(1)
    
    if not consumer.assignment():
        print(f"\n✗ 分区分配失败")
        
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
finally:
    if consumer:
        consumer.close()
        print("\n消费者已关闭")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)