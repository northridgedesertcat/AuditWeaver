#!/usr/bin/env python
"""模拟 Django 的 ES 连接方式，检查是否能访问 log_analysis_reports"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'website'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.v1.backend.settings')

import django
django.setup()

from django.conf import settings
from elasticsearch import Elasticsearch

def test_django_es_connection():
    print("=" * 70)
    print("模拟 Django ES 连接测试")
    print("=" * 70)
    
    print(f"\nDjango ES 配置:")
    print(f"  ELASTICSEARCH_HOST: {settings.ELASTICSEARCH_HOST}")
    print(f"  ELASTICSEARCH_PORT: {settings.ELASTICSEARCH_PORT}")
    print(f"  ELASTICSEARCH_USER: {settings.ELASTICSEARCH_USER}")
    print(f"  ELASTICSEARCH_PASSWORD: {settings.ELASTICSEARCH_PASSWORD}")
    
    es = Elasticsearch(
        hosts=[f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"],
        basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
        verify_certs=False,
        ssl_show_warn=False,
    )
    
    print(f"\nES 客户端对象: {es}")
    
    if not es.ping():
        print("❌ 无法连接到 Elasticsearch")
        return
    
    print("✅ 连接成功!")
    
    print("\n--- 检查 log_analysis_reports 索引 ---")
    try:
        exists = es.indices.exists(index="log_analysis_reports")
        print(f"  索引存在: {exists}")
        
        if exists:
            count = es.count(index="log_analysis_reports")
            print(f"  文档数量: {count['count']}")
            
            total_search = {
                "size": 0,
                "track_total_hits": True
            }
            result = es.search(index="log_analysis_reports", body=total_search)
            print(f"  search 查询结果: total = {result['hits']['total']['value']}")
        else:
            print("  ❌ 索引不存在!")
            
    except Exception as e:
        print(f"  ❌ 发生错误: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_django_es_connection()