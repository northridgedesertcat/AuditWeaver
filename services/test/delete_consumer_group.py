"""
删除消费者组
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka.admin import KafkaAdminClient

BROKER = KAFKA_BROKERS
GROUP_ID = 'rules_matching_group_test_v0002'

print("=" * 60)
print("删除消费者组")
print("=" * 60)

try:
    admin_client = KafkaAdminClient(bootstrap_servers=BROKER)
    
    groups = admin_client.list_consumer_groups()
    print(f"\n当前消费者组列表: {[g[0] for g in groups]}")
    
    print(f"\n尝试删除消费者组: {GROUP_ID}")
    admin_client.delete_consumer_groups([GROUP_ID])
    print(f"✓ 消费者组 {GROUP_ID} 删除成功")
    
    admin_client.close()
    
except Exception as e:
    print(f"\nError: {e}")
    print(f"\n可能原因:")
    print(f"1. 消费者组不存在")
    print(f"2. 有消费者正在使用该组")
    print(f"3. 需要等待消费者离开后再尝试")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("操作完成")
print("=" * 60)