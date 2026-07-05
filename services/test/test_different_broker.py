"""
测试不同的 Broker 地址
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kafka import KafkaConsumer

TEST_BROKERS = [
    'localhost:29092',
    'localhost:9092',
]

TOPIC = 'log.audit'

print("=" * 60)
print("测试不同的 Broker 地址")
print("=" * 60)

for broker in TEST_BROKERS:
    print(f"\n{'='*60}")
    print(f"测试 Broker: {broker}")
    print(f"{'='*60}")
    
    consumer = None
    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=broker,
            group_id=f'test_group_{broker.replace(":", "_")}_{int(time.time())}',
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
                
                print(f"\n开始接收消息...")
                total = 0
                for j in range(3):
                    messages = consumer.poll(timeout_ms=2000)
                    if messages:
                        for tp, records in messages.items():
                            for record in records:
                                total += 1
                                print(f"  消息 #{total}: {json.dumps(record.value, ensure_ascii=False)[:80]}")
                    else:
                        break
                
                if total > 0:
                    print(f"\n✓ 成功收到 {total} 条消息！")
                else:
                    print(f"\n提示: 没有新消息")
                
                break
            time.sleep(1)
        
        if not consumer.assignment():
            print(f"\n✗ 分区分配失败")
            
    except Exception as e:
        print(f"\n✗ 错误: {e}")
    finally:
        if consumer:
            consumer.close()
            print("\n消费者已关闭")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)