#!/usr/bin/env python
"""检查索引数据来源"""

from elasticsearch import Elasticsearch

def check_data():
    print("=" * 70)
    print("检查索引数据来源")
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
        
        # 获取索引文档数
        try:
            count = es.count(index=index)
            print(f"文档数: {count['count']}")
        except Exception as e:
            print(f"获取文档数失败: {e}")
            continue
        
        # 获取最近5条数据的时间戳和来源信息
        try:
            result = es.search(
                index=index,
                query={"match_all": {}},
                sort=[{"@timestamp": {"order": "desc"}}] if index != 'log_analysis_reports' else [{"analysis_timestamp": {"order": "desc"}}],
                size=5,
                _source=True
            )
            
            hits = result.get('hits', {}).get('hits', [])
            if hits:
                print(f"\n最近5条数据:")
                for i, hit in enumerate(hits, 1):
                    source = hit['_source']
                    
                    # 时间戳信息
                    if '@timestamp' in source:
                        ts = source['@timestamp']
                    elif 'analysis_timestamp' in source:
                        ts = source['analysis_timestamp']
                    else:
                        ts = 'N/A'
                    
                    # 来源/标记信息
                    log_source = source.get('log_source', 'N/A')
                    rule_match = source.get('rule_match', {})
                    has_rule_match = 'is_matched' in rule_match
                    risk_level = source.get('risk_level', 'N/A')
                    
                    print(f"  {i}. ID: {hit['_id'][:10]}..., timestamp: {ts}")
                    print(f"     log_source: {log_source}, has_rule_match: {has_rule_match}, risk_level: {risk_level}")
            else:
                print("  无数据")
                
        except Exception as e:
            print(f"查询数据失败: {e}")
    
    print("\n" + "=" * 70)
    print("creatMapping.py 代码分析:")
    print("=" * 70)
    print("脚本只包含索引创建逻辑，不包含任何数据写入代码")
    print("数据来源可能是:")
    print("  1. Logstash 持续写入 nginx-log-raw")
    print("  2. rulesMatching 模块持续写入 matched_logs")
    print("  3. agent 模块持续写入 log_analysis_reports")
    print("  4. 之前运行的测试脚本(test_all_indices.py, debug_es_write.py)")

if __name__ == "__main__":
    check_data()