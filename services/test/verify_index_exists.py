#!/usr/bin/env python
"""验证 log_analysis_reports 索引是否存在"""

from elasticsearch import Elasticsearch

def check_index():
    print("=" * 70)
    print("验证 log_analysis_reports 索引状态")
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
    
    print("\n--- 1. 列出所有索引 ---")
    try:
        indices = es.indices.get_alias(index="*")
        all_index_names = list(indices.keys())
        print(f"当前共有 {len(all_index_names)} 个索引/别名:")
        for idx in sorted(all_index_names):
            print(f"  - {idx}")
    except Exception as e:
        print(f"❌ 获取索引列表失败: {e}")
        return
    
    print("\n--- 2. 检查 log_analysis_reports 索引 ---")
    target_index = "log_analysis_reports"
    
    try:
        exists = es.indices.exists(index=target_index)
        if exists:
            print(f"✅ log_analysis_reports 索引存在!")
            
            print("\n--- 3. 获取索引信息 ---")
            info = es.indices.get(index=target_index)
            if target_index in info:
                index_info = info[target_index]
                settings = index_info.get('settings', {})
                mappings = index_info.get('mappings', {})
                
                print(f"  索引设置:")
                print(f"    number_of_shards: {settings.get('index', {}).get('number_of_shards')}")
                print(f"    number_of_replicas: {settings.get('index', {}).get('number_of_replicas')}")
                
                print(f"\n  索引映射字段:")
                properties = mappings.get('properties', {})
                for field_name, field_type in properties.items():
                    print(f"    {field_name}: {field_type.get('type', field_type)}")
            
            print("\n--- 4. 统计文档数量 ---")
            count = es.count(index=target_index)
            print(f"  log_analysis_reports 文档总数: {count['count']}")
            
            print("\n--- 5. 测试查询 ---")
            query = {
                "query": {"match_all": {}},
                "size": 1
            }
            result = es.search(index=target_index, body=query)
            hits = result.get('hits', {}).get('hits', [])
            if hits:
                print(f"  查询成功! 返回 {len(hits)} 条记录")
                print(f"  第一条记录: {hits[0].get('_source', {})}")
            else:
                print(f"  查询成功! 但索引为空")
                
        else:
            print(f"❌ log_analysis_reports 索引不存在!")
            
    except Exception as e:
        print(f"❌ 检查索引时发生错误: {type(e).__name__}: {e}")

if __name__ == "__main__":
    check_index()