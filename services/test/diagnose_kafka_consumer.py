"""
诊断 Kafka 消费者问题
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

BROKER = KAFKA_BROKERS
TOPIC = 'log.audit'
GROUP_ID = 'rules_matching_group_test_v0002'

print("=" * 70)
print("Kafka 消费者诊断")
print("=" * 70)

print(f"\n[1] 连接信息")
print(f"    Broker: {BROKER}")
print(f"    Topic: {TOPIC}")
print(f"    Group ID: {GROUP_ID}")

print(f"\n[2] 创建消费者并监控状态...")

consumer = None
try:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        group_id=GROUP_ID,
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=30000
    )
    
    print(f"    ✓ 消费者创建成功")
    print(f"    ✓ 订阅的topic: {consumer.subscription()}")
    
    print(f"\n[3] 等待分区分配（最多30秒）...")
    for i in range(30):
        assigned = consumer.assignment()
        print(f"    第{i+1}秒 - 已分配分区: {assigned}")
        
        if assigned:
            print(f"\n[4] 分区分配成功！")
            for tp in assigned:
                committed = consumer.committed(tp)
                end_offset = consumer.end_offsets([tp]).get(tp)
                beginning_offset = consumer.beginning_offsets([tp]).get(tp)
                
                print(f"    分区 {tp.partition}:")
                print(f"      - 起始偏移量: {beginning_offset}")
                print(f"      - 当前偏移量: {committed}")
                print(f"      - 结束偏移量: {end_offset}")
                
                if beginning_offset is not None and end_offset is not None:
                    message_count = end_offset - beginning_offset
                    print(f"      - 总消息数: {message_count}")
                
                if committed == end_offset:
                    print(f"      - ⚠️ 消费者组偏移量已在最新位置")
            
            print(f"\n[5] 开始轮询消息...")
            total_received = 0
            for j in range(10):
                messages = consumer.poll(timeout_ms=2000)
                if messages:
                    for tp, records in messages.items():
                        for record in records:
                            total_received += 1
                            print(f"    收到消息 #{total_received}: event_id={record.value.get('event_id', 'N/A')}")
                else:
                    print(f"    第{j+1}次轮询 - 无消息")
                    time.sleep(1)
            
            if total_received > 0:
                print(f"\n[6] ✓ 成功收到 {total_received} 条消息！")
            else:
                print(f"\n[6] ✗ 未收到任何消息")
                print(f"    可能原因:")
                print(f"    - log.audit topic 中没有消息")
                print(f"    - 消费者组偏移量已在最新位置")
                
            break
        
        time.sleep(1)
    
    if not consumer.assignment():
        print(f"\n[4] ✗ 等待30秒后仍未分配到任何分区")
        print(f"    可能原因:")
        print(f"    - Topic {TOPIC} 不存在或没有分区")
        print(f"    - Kafka Coordinator 异常")
        print(f"    - 消费者组协议不一致")
        
        print(f"\n[5] 检查 Topic 状态...")
        try:
            admin_client = KafkaAdminClient(bootstrap_servers=BROKER)
            topics = admin_client.list_topics()
            print(f"    可用topic列表: {topics}")
            
            if TOPIC in topics:
                print(f"    ✓ {TOPIC} topic 存在")
            else:
                print(f"    ✗ {TOPIC} topic 不存在")
                
            admin_client.close()
        except Exception as e:
            print(f"    ✗ 无法获取topic列表: {e}")
    
except Exception as e:
    print(f"\n[ERROR] 创建消费者失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    if consumer:
        consumer.close()
        print(f"\n[7] 消费者已关闭")

print("\n" + "=" * 70)
print("诊断完成")
print("=" * 70)