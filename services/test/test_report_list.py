#!/usr/bin/env python
"""测试ReportList无法读取ES数据的问题"""

import sys
import os
from elasticsearch import Elasticsearch

def test_elasticsearch_direct():
    print("=" * 70)
    print("ReportList 数据读取问题诊断")
    print("=" * 70)
    
    host = 'localhost'
    port = 19200
    index = 'log_analysis_reports'
    
    print(f"\n1. 连接信息: host={host}, port={port}, index={index}")
    
    try:
        es = Elasticsearch(
            hosts=[f"http://{host}:{port}"],
            basic_auth=('elastic', 'password'),
            verify_certs=False,
            ssl_show_warn=False,
        )
        
        if es.ping():
            print("✅ Elasticsearch 连接成功")
        else:
            print("❌ Elasticsearch 连接失败")
            return
            
    except Exception as e:
        print(f"❌ ES连接异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n2. 检查索引状态:")
    try:
        indices = es.cat.indices(index=index, format="json")
        if indices:
            idx_info = indices[0]
            print(f"   ✅ 索引存在")
            print(f"      - docs.count: {idx_info.get('docs.count', 'N/A')}")
            print(f"      - docs.deleted: {idx_info.get('docs.deleted', 'N/A')}")
            print(f"      - store.size: {idx_info.get('store.size', 'N/A')}")
            total_docs = int(idx_info.get('docs.count', 0))
        else:
            print(f"   ❌ 索引 {index} 不存在")
            return
    except Exception as e:
        print(f"   ❌ 检查索引失败: {e}")
        return
    
    print("\n3. 获取索引mapping:")
    try:
        mapping = es.indices.get_mapping(index=index)
        properties = mapping[index]['mappings']['properties']
        print(f"   字段列表: {list(properties.keys())}")
        print(f"   risk_level 类型: {properties.get('risk_level', {}).get('type', 'N/A')}")
        print(f"   analysis_timestamp 类型: {properties.get('analysis_timestamp', {}).get('type', 'N/A')}")
        print(f"   attack_type_ai 类型: {properties.get('attack_type_ai', {}).get('type', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 获取mapping失败: {e}")
    
    print("\n4. 执行与后端相同的查询:")
    print("   (模拟 ReportListView 的查询逻辑)")
    
    query = {
        "query": {
            "bool": {
                "must": [{"match_all": {}}]
            }
        },
        "sort": [{"analysis_timestamp": {"order": "desc"}}],
        "from": 0,
        "size": 10,
        "track_total_hits": True
    }
    
    try:
        result = es.search(index=index, body=query)
        hits = result.get('hits', {}).get('hits', [])
        total = result['hits']['total']['value']
        
        print(f"   ✅ 查询成功")
        print(f"   - total: {total}")
        print(f"   - hits: {len(hits)}")
        
        if hits:
            print("\n5. 查看第一条数据:")
            source = hits[0]['_source']
            print(f"   _id: {hits[0]['_id']}")
            print(f"   关键字段:")
            for key in ['risk_level', 'attack_type_ai', 'attack_type', 'confidence', 
                       'ip', 'path', 'analysis_timestamp', 'log_timestamp', 'ingestion_time']:
                print(f"     - {key}: {source.get(key, 'N/A')}")
            
            print("\n6. 检查字段类型:")
            print(f"   analysis_timestamp 类型: {type(source.get('analysis_timestamp'))}")
            print(f"   confidence 类型: {type(source.get('confidence'))}")
            print(f"   risk_level 值: '{source.get('risk_level')}'")
            
        else:
            print("\n5. ❌ 没有找到任何数据")
            
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n7. 测试 risk_level 过滤查询:")
    risk_levels = ['Critical', 'High', 'Medium', 'Low', 'critical', 'high', 'medium', 'low']
    
    for level in risk_levels:
        test_query = {
            "size": 0,
            "track_total_hits": True,
            "query": {
                "match": {
                    "risk_level": level
                }
            }
        }
        try:
            result = es.search(index=index, body=test_query)
            count = result['hits']['total']['value']
            print(f"   risk_level='{level}': {count} 条")
        except Exception as e:
            print(f"   risk_level='{level}': 查询失败 - {e}")
    
    print("\n8. 测试 risk_level.keyword 聚合:")
    agg_query = {
        "size": 0,
        "aggs": {
            "risk_levels": {
                "terms": {
                    "field": "risk_level.keyword",
                    "size": 10
                }
            }
        }
    }
    try:
        result = es.search(index=index, body=agg_query)
        buckets = result.get('aggregations', {}).get('risk_levels', {}).get('buckets', [])
        print(f"   聚合结果:")
        for bucket in buckets:
            print(f"     - {bucket['key']}: {bucket['doc_count']}")
    except Exception as e:
        print(f"   ❌ 聚合失败: {e}")
    
    print("\n9. 检查 attack_type_ai 字段:")
    agg_query = {
        "size": 0,
        "aggs": {
            "attack_types": {
                "terms": {
                    "field": "attack_type_ai.keyword",
                    "size": 10
                }
            }
        }
    }
    try:
        result = es.search(index=index, body=agg_query)
        buckets = result.get('aggregations', {}).get('attack_types', {}).get('buckets', [])
        print(f"   attack_type_ai 值分布:")
        for bucket in buckets:
            print(f"     - {bucket['key']}: {bucket['doc_count']}")
    except Exception as e:
        print(f"   ❌ 聚合失败: {e}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_elasticsearch_direct()