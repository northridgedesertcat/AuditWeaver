import sys
import os

from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:19200")

indices = ['matched_logs', 'log_analysis_reports', 'nginx-log-raw']

for index in indices:
    print(f"\n{'='*60}")
    print(f"检查索引: {index}")
    print(f"{'='*60}")
    
    mapping = es.indices.get_mapping(index=index)
    print("\n--- 索引映射(Mapping) ---")
    print(mapping)
    
    print("\n--- 数据样例(前3条) ---")
    resp = es.search(index=index, size=3)
    for hit in resp['hits']['hits']:
        print(f"\n文档ID: {hit['_id']}")
        print(f"源数据: {hit['_source']}")
    
    print("\n--- 字段类型检查 ---")
    mapping_body = mapping[index]['mappings']
    if 'properties' in mapping_body:
        for field, props in mapping_body['properties'].items():
            if 'type' in props:
                print(f"  {field}: type={props['type']}, format={props.get('format', 'N/A')}")
