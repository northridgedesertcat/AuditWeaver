#!/usr/bin/env python
"""测试Elasticsearch连接和数据"""

import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'website', 'backend', 'v1'))

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from api.es_client import get_es_client, is_es_available
from datetime import datetime

def test_elasticsearch():
    print("=" * 60)
    print("Elasticsearch 连接测试")
    print("=" * 60)
    
    # 1. 检查ES是否可用
    print(f"\n1. ES是否可用: {is_es_available()}")
    
    if not is_es_available():
        print("❌ ES连接失败！请检查ES服务是否启动")
        return
    
    # 2. 获取ES客户端
    es = get_es_client()
    print(f"\n2. ES客户端: {es}")
    
    if not es:
        print("❌ 无法创建ES客户端！")
        return
    
    # 3. 列出所有索引
    print("\n3. 所有索引列表:")
    try:
        indices = es.cat.indices(format="json")
        for idx in indices:
            print(f"   - {idx['index']} (docs: {idx.get('docs.count', 'N/A')})")
    except Exception as e:
        print(f"   ❌ 获取索引列表失败: {e}")
    
    # 4. 检查log_analysis_reports索引
    print("\n4. 检查 log_analysis_reports 索引:")
    try:
        indices = es.cat.indices(index="log_analysis_reports", format="json")
        if indices:
            print(f"   ✅ 索引存在")
            print(f"   索引信息: {indices}")
        else:
            print("   ❌ 索引不存在")
    except Exception as e:
        print(f"   ❌ 检查索引失败: {e}")
    
    # 5. 获取总数
    print("\n5. 获取报告总数:")
    try:
        search_body = {
            "size": 0,
            "track_total_hits": True
        }
        result = es.search(index="log_analysis_reports", body=search_body)
        total = result['hits']['total']['value']
        print(f"   ✅ 总报告数: {total}")
        
        # 显示一些示例数据
        if total > 0:
            print("\n6. 示例数据 (前3条):")
            sample_search = {
                "size": 3,
                "track_total_hits": True
            }
            sample_result = es.search(index="log_analysis_reports", body=sample_search)
            for hit in sample_result['hits']['hits']:
                source = hit['_source']
                print(f"   - ID: {hit['_id']}")
                print(f"     risk_level: {source.get('risk_level', 'N/A')}")
                print(f"     analysis_timestamp: {source.get('analysis_timestamp', 'N/A')}")
                print()
    except Exception as e:
        print(f"   ❌ 获取总数失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. 检查risk_level字段的值
    print("\n7. risk_level 字段聚合:")
    try:
        agg_body = {
            "size": 0,
            "aggs": {
                "risk_levels": {
                    "terms": {
                        "field": "risk_level",
                        "size": 10
                    }
                }
            }
        }
        result = es.search(index="log_analysis_reports", body=agg_body)
        buckets = result['aggregations']['risk_levels']['buckets']
        for bucket in buckets:
            print(f"   - {bucket['key']}: {bucket['doc_count']}")
    except Exception as e:
        print(f"   ❌ 聚合失败: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_elasticsearch()
