"""
检查消费者组订阅情况
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import KAFKA_BROKERS
from kafka.admin import KafkaAdminClient

BROKER = KAFKA_BROKERS

print("=" * 60)
print("检查消费者组订阅情况")
print("=" * 60)

try:
    admin_client = KafkaAdminClient(bootstrap_servers=BROKER)
    
    groups = admin_client.list_consumer_groups()
    print(f"\n当前消费者组列表:")
    for group_id, group_type in groups:
        print(f"  - {group_id} ({group_type})")
    
    print(f"\n尝试获取消费者组详情...")
    for group_id, _ in groups:
        try:
            group_describe = admin_client.describe_consumer_groups([group_id])
            if group_describe:
                group = group_describe[0]
                state = group.get('state', 'Unknown')
                members = group.get('members', [])
                print(f"\n  {group_id}:")
                print(f"    状态: {state}")
                print(f"    成员数: {len(members)}")
                for member in members:
                    client_id = member.get('client_id', 'Unknown')
                    client_host = member.get('client_host', 'Unknown')
                    print(f"      - {client_id} ({client_host})")
                
        except Exception as e:
            print(f"\n  {group_id}: 无法获取详情 ({e})")
    
    admin_client.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)