# test_elasticsearch_save.py
from elasticsearch import Elasticsearch
import json

def test_es_connection():
    """测试Elasticsearch连接"""
    try:
        es = Elasticsearch(['http://localhost:19200'], timeout=30)
        if es.ping():
            print("✓ 成功连接到Elasticsearch")
            
            # 检查索引
            if es.indices.exists(index='matched_logs'):
                print("✓ matched_logs 索引存在")
            else:
                print("✗ matched_logs 索引不存在，尝试创建...")
                # 创建索引
                index_mapping = {
                    "mappings": {
                        "properties": {
                            "ip": {"type": "text"},
                            "path": {"type": "text"},
                            "@timestamp": {"type": "date"},
                            "rule_match": {"type": "object"}
                        }
                    }
                }
                es.indices.create(index='matched_logs', body=index_mapping)
                print("✓ 成功创建 matched_logs 索引")
            
            # 尝试保存测试数据
            test_data = {
                "event_id": "test-123",
                "ip": "192.168.1.100",
                "path": "/test",
                "@timestamp": "2024-01-01T00:00:00Z",
                "rule_match": {"is_matched": True, "attack_type": "TEST"}
            }
            
            response = es.index(index='matched_logs', body=test_data)
            print(f"✓ 成功保存测试数据: {response['_id']}")
            
            # 验证数据是否保存成功
            result = es.get(index='matched_logs', id=response['_id'])
            print(f"✓ 验证成功: {result['_source']['ip']}")
            
            es.close()
            return True
        else:
            print("✗ 无法连接到Elasticsearch")
            return False
    except Exception as e:
        print(f"✗ 连接失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_es_connection()