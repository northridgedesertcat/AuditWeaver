from elasticsearch import Elasticsearch

es = Elasticsearch('http://localhost:19200', basic_auth=('elastic', 'password'))

# 检查索引是否存在
indices = es.cat.indices(format='json')
print("所有索引:")
for idx in indices:
    print(f"  - {idx['index']}")

print("\n检查 log_analysis_reports 索引:")
if es.indices.exists(index='log_analysis_reports'):
    print("索引存在")
    
    # 获取mapping
    mapping = es.indices.get_mapping(index='log_analysis_reports')
    print("\n字段映射:")
    for field in mapping['log_analysis_reports']['mappings']['properties']:
        print(f"  - {field}")
    
    # 获取一条样本数据
    result = es.search(index='log_analysis_reports', body={"query": {"match_all": {}}, "size": 1})
    if result['hits']['hits']:
        print("\n样本数据:")
        import json
        print(json.dumps(result['hits']['hits'][0]['_source'], indent=2, ensure_ascii=False))
else:
    print("索引不存在")