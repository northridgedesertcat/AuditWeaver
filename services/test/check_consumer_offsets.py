"""
检查 __consumer_offsets topic
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka.admin import KafkaAdminClient

BROKER = KAFKA_BROKERS

print("=" * 60)
print("检查 __consumer_offsets topic")
print("=" * 60)

try:
    admin_client = KafkaAdminClient(bootstrap_servers=BROKER)
    
    topics = admin_client.list_topics()
    print(f"\n可用 Topic: {topics}")
    
    if '__consumer_offsets' in topics:
        print(f"\n✓ __consumer_offsets topic 存在")
        
        topic_metadata = admin_client.describe_topics(['__consumer_offsets'])
        if topic_metadata:
            partitions = topic_metadata[0].get('partitions', [])
            print(f"  分区数: {len(partitions)}")
            if len(partitions) > 0:
                print(f"  ✓ 分区正常")
            else:
                print(f"  ✗ 没有分区")
    else:
        print(f"\n✗ __consumer_offsets topic 不存在")
    
    admin_client.close()
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)