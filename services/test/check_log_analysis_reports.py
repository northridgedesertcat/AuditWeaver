"""
检查 log_analysis_reports 索引数据
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.env import ES_HOST, ES_PORT
from elasticsearch import Elasticsearch

print("=" * 60)
print("检查 log_analysis_reports 索引")
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
    
    print(f"\n[1] 检查 log_analysis_reports 索引...")
    if es.indices.exists(index='log_analysis_reports'):
        count = es.count(index='log_analysis_reports')['count']
        print(f"    ✓ log_analysis_reports 索引存在，文档数: {count}")
        
        print(f"\n[2] 查询前5条数据...")
        response = es.search(index='log_analysis_reports', size=5)
        for hit in response['hits']['hits']:
            doc_id = hit['_id']
            source = hit['_source']
            print(f"\n    文档 {doc_id}:")
            print(f"      risk_level: {source.get('risk_level')}")
            print(f"      attack_type_ai: {source.get('attack_type_ai')}")
            print(f"      analysis_timestamp: {source.get('analysis_timestamp')}")
            print(f"      confidence: {source.get('confidence')}")
            print(f"      ip: {source.get('ip')}")
            print(f"      path: {source.get('path')}")
            print(f"      event_id: {source.get('event_id')}")
            print(f"      summary: {source.get('summary', '')[:50]}...")
        
        print(f"\n[3] 检查字段映射...")
        mapping = es.indices.get_mapping(index='log_analysis_reports')
        fields = list(mapping['log_analysis_reports']['mappings']['properties'].keys())
        print(f"    字段列表: {fields}")
        
    else:
        print(f"    ✗ log_analysis_reports 索引不存在")
    
    print(f"\n[4] 检查 nginx-log-raw 索引...")
    if es.indices.exists(index='nginx-log-raw'):
        count = es.count(index='nginx-log-raw')['count']
        print(f"    ✓ nginx-log-raw 索引存在，文档数: {count}")
        
        response = es.search(index='nginx-log-raw', size=2)
        for hit in response['hits']['hits']:
            source = hit['_source']
            print(f"\n    字段: {list(source.keys())[:10]}...")
            print(f"      @timestamp: {source.get('@timestamp')}")
            print(f"      ip: {source.get('ip')}")
            print(f"      path: {source.get('path')}")
    else:
        print(f"    ✗ nginx-log-raw 索引不存在")
    
    es.close()
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("检查完成")
print("=" * 60)