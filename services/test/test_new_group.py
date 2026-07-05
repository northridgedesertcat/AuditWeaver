"""
使用新的消费者组测试 Kafka
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka import KafkaConsumer

BROKER = KAFKA_BROKERS
TOPIC = 'log.audit'

print("=" * 60)
print("使用新消费者组测试")
print("=" * 60)

print(f"\n[1] 测试新消费者组...")

new_group_id = f'test_new_group_{int(time.time())}'
print(f"    使用新消费者组: {new_group_id}")

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BROKER,
    group_id=new_group_id,
    auto_offset_reset='earliest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    consumer_timeout_ms=10000
)

print(f"    ✓ 消费者创建成功")

print(f"\n[2] 等待分区分配...")
for i in range(15):
    assigned = consumer.assignment()
    print(f"    第{i+1}秒 - 分区: {assigned}")
    if assigned:
        print(f"\n[3] ✓ 分区分配成功！")
        
        print(f"\n[4] 开始接收消息...")
        total = 0
        while True:
            messages = consumer.poll(timeout_ms=2000)
            if messages:
                for tp, records in messages.items():
                    for record in records:
                        total += 1
                        print(f"    收到消息 #{total}: {json.dumps(record.value, ensure_ascii=False)[:100]}...")
            else:
                break
        
        if total > 0:
            print(f"\n[5] ✓ 成功收到 {total} 条消息！")
        else:
            print(f"\n[5] ✗ 没有收到消息（可能偏移量已在最新位置）")
        
        break
    time.sleep(1)

if not consumer.assignment():
    print(f"\n[3] ✗ 分区分配失败")
    print(f"    问题可能出在 Kafka Coordinator")

consumer.close()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)