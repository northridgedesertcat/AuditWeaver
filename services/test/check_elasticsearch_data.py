"""
检查 Elasticsearch 数据
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import ES_HOST, ES_PORT
from elasticsearch import Elasticsearch

print("=" * 60)
print("检查 Elasticsearch 数据")
print("=" * 60)

try:
    es = Elasticsearch(
        [{'host': ES_HOST, 'port': ES_PORT}],
        timeout=30
    )
    
    if not es.ping():
        print("✗ 无法连接到 Elasticsearch")
        sys.exit(1)
    
    print(f"✓ 成功连接到 Elasticsearch: {ES_HOST}:{ES_PORT}")
    
    print(f"\n[1] 获取所有索引...")
    indices = es.cat.indices(format='json')
    print(f"    索引列表:")
    for idx in indices:
        print(f"      - {idx['index']} (文档数: {idx['docs.count']})")
    
    print(f"\n[2] 检查 matched_logs 索引...")
    if es.indices.exists(index='matched_logs'):
        count = es.count(index='matched_logs')['count']
        print(f"    ✓ matched_logs 索引存在，文档数: {count}")
        
        print(f"\n[3] 查询前5条数据...")
        response = es.search(index='matched_logs', size=5)
        for hit in response['hits']['hits']:
            doc_id = hit['_id']
            source = hit['_source']
            print(f"\n    文档 {doc_id}:")
            print(f"      event_id: {source.get('event_id')}")
            print(f"      ip: {source.get('ip')}")
            print(f"      path: {source.get('path')}")
            print(f"      severity: {source.get('severity')}")
            print(f"      confidence: {source.get('confidence')}")
            print(f"      detection_result: {json.dumps(source.get('detection_result', {}), ensure_ascii=False)[:100]}")
        
        print(f"\n[4] 检查字段映射...")
        mapping = es.indices.get_mapping(index='matched_logs')
        fields = list(mapping['matched_logs']['mappings']['properties'].keys())
        print(f"    字段列表: {fields}")
        
    else:
        print(f"    ✗ matched_logs 索引不存在")
    
    print(f"\n[5] 检查其他可能的日志索引...")
    possible_indices = ['attack_logs', 'logs', 'audit_logs', 'events', 'logstash-*']
    for idx_pattern in possible_indices:
        if es.indices.exists(index=idx_pattern):
            count = es.count(index=idx_pattern)['count']
            print(f"    ✓ {idx_pattern}: {count} 条文档")
    
    es.close()
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)