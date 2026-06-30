#!/usr/bin/env python
"""验证索引 mapping 是否正确创建"""

from elasticsearch import Elasticsearch

def verify_mappings():
    print("=" * 70)
    print("验证 Elasticsearch 索引 Mapping")
    print("=" * 70)
    
    es = Elasticsearch(
        hosts=["http://localhost:19200"],
        basic_auth=('elastic', 'password'),
        verify_certs=False,
        ssl_show_warn=False,
    )
    
    if not es.ping():
        print("❌ 无法连接到 Elasticsearch")
        return
    
    indices = ['nginx-log-raw', 'matched_logs', 'log_analysis_reports']
    
    for index in indices:
        print(f"\n--- {index} ---")
        try:
            mapping = es.indices.get_mapping(index=index)
            properties = mapping[index]['mappings']['properties']
            
            print(f"字段列表: {list(properties.keys())}")
            
            if index == 'log_analysis_reports':
                print(f"\n关键字段类型验证:")
                print(f"  risk_level: {properties.get('risk_level', {}).get('type', 'N/A')}")
                print(f"  analysis_timestamp: {properties.get('analysis_timestamp', {}).get('type', 'N/A')}")
                print(f"  attack_type_ai: {properties.get('attack_type_ai', {}).get('type', 'N/A')}")
                print(f"  log_timestamp: {properties.get('log_timestamp', {}).get('type', 'N/A')}")
                print(f"  confidence: {properties.get('confidence', {}).get('type', 'N/A')}")
                
                print(f"\n时间戳字段格式:")
                print(f"  analysis_timestamp format: {properties.get('analysis_timestamp', {}).get('format', 'N/A')}")
                print(f"  log_timestamp format: {properties.get('log_timestamp', {}).get('format', 'N/A')}")
            
            elif index == 'nginx-log-raw':
                print(f"\n关键字段类型验证:")
                print(f"  @timestamp: {properties.get('@timestamp', {}).get('type', 'N/A')}")
                print(f"  event_id: {properties.get('event_id', {}).get('type', 'N/A')}")
                print(f"  ip: {properties.get('ip', {}).get('type', 'N/A')}")
                print(f"  status: {properties.get('status', {}).get('type', 'N/A')}")
            
            elif index == 'matched_logs':
                print(f"\n关键字段类型验证:")
                print(f"  @timestamp: {properties.get('@timestamp', {}).get('type', 'N/A')}")
                print(f"  event_id: {properties.get('event_id', {}).get('type', 'N/A')}")
                print(f"  rule_match.is_matched: {properties.get('rule_match', {}).get('properties', {}).get('is_matched', {}).get('type', 'N/A')}")
                print(f"  rule_match.confidence: {properties.get('rule_match', {}).get('properties', {}).get('confidence', {}).get('type', 'N/A')}")
                
        except Exception as e:
            print(f"❌ 获取 mapping 失败: {e}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    verify_mappings()