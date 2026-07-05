"""
使用 poll() 来触发分区分配
"""
import sys
import os
import json
import time

from kafka import KafkaConsumer

BROKER = 'localhost:29092'
TOPIC = 'log.audit'

print("=" * 60)
print("使用 poll() 触发分区分配")
print("=" * 60)

consumer = None
try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        group_id=f'test_group_poll_{int(time.time())}',
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=30000,
        enable_auto_commit=True,
        auto_commit_interval_ms=5000
    )
    
    print(f"✓ 消费者创建成功")
    print(f"  topic: {consumer.subscription()}")
    
    print(f"\n开始轮询消息（这会触发分区分配）...")
    
    total_received = 0
    for i in range(20):
        messages = consumer.poll(timeout_ms=2000)
        
        assigned = consumer.assignment()
        print(f"  第{i+1}次轮询 - 分区: {assigned}, 消息数: {len(messages)}")
        
        if assigned:
            print(f"\n✓ 分区分配成功！")
            
            if messages:
                for tp, records in messages.items():
                    for record in records:
                        total_received += 1
                        print(f"    消息 #{total_received}: {json.dumps(record.value, ensure_ascii=False)[:80]}")
            
            break
        
        time.sleep(1)
    
    if consumer.assignment():
        print(f"\n等待更多消息...")
        for j in range(5):
            messages = consumer.poll(timeout_ms=2000)
            if messages:
                for tp, records in messages.items():
                    for record in records:
                        total_received += 1
                        print(f"    消息 #{total_received}: {json.dumps(record.value, ensure_ascii=False)[:80]}")
            else:
                break
    
    if total_received > 0:
        print(f"\n✓ 成功收到 {total_received} 条消息！")
    elif consumer.assignment():
        print(f"\n提示: 分区已分配，但没有新消息")
    else:
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