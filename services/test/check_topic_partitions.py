"""
检查 Kafka Topic 分区数
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka.admin import KafkaAdminClient

BROKER = KAFKA_BROKERS

print("=" * 60)
print("检查 Kafka Topic 分区")
print("=" * 60)

try:
    admin_client = KafkaAdminClient(bootstrap_servers=BROKER)
    
    topics = admin_client.list_topics()
    print(f"\n可用 Topic: {topics}")
    
    print(f"\nTopic 详情:")
    for topic in topics:
        if topic.startswith('__'):
            continue
            
        topic_metadata = admin_client.describe_topics([topic])
        if topic_metadata:
            partitions = topic_metadata[0].get('partitions', [])
            print(f"\n  {topic}:")
            print(f"    分区数: {len(partitions)}")
            for p in partitions:
                print(f"      分区 {p.get('partition')}: leader={p.get('leader')}, replicas={p.get('replicas')}")
    
    admin_client.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)