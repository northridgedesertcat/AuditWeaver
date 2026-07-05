from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:19200")

indices = ['matched_logs', 'log_analysis_reports', 'nginx-log-raw']

for index in indices:
    print(f"\n{'='*60}")
    print(f"检查索引: {index}")
    print(f"{'='*60}")
    
    if es.indices.exists(index=index):
        mapping = es.indices.get_mapping(index=index)
        props = mapping[index]['mappings'].get('properties', {})
        
        print("\n--- 时间字段类型检查 ---")
        time_fields = ['log_timestamp', 'ingestion_time', 'analysis_timestamp', '@timestamp']
        for field in time_fields:
            if field in props:
                field_type = props[field].get('type', 'N/A')
                field_format = props[field].get('format', 'N/A')
                print(f"  {field}: type={field_type}, format={field_format}")
                if field_type != 'date':
                    print(f"    ⚠️ 类型不正确! 期望: date, 实际: {field_type}")
            else:
                print(f"  {field}: 未定义（ES自动推断）")
        
        print(f"\n--- 文档数量: {es.count(index=index)['count']} ---")
    else:
        print(f"索引 {index} 不存在")
