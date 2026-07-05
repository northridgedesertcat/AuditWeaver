"""
删除所有消费者组
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka.admin import KafkaAdminClient

BROKER = KAFKA_BROKERS

print("=" * 60)
print("删除所有消费者组")
print("=" * 60)

try:
    admin_client = KafkaAdminClient(bootstrap_servers=BROKER)
    
    groups = admin_client.list_consumer_groups()
    print(f"\n当前消费者组列表: {[g[0] for g in groups]}")
    
    group_ids = [g[0] for g in groups]
    
    for group_id in group_ids:
        try:
            admin_client.delete_consumer_groups([group_id])
            print(f"✓ 删除成功: {group_id}")
        except Exception as e:
            print(f"✗ 删除失败: {group_id} ({e})")
    
    admin_client.close()
    
    print(f"\n删除完成")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("操作完成")
print("=" * 60)