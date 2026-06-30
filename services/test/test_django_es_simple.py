#!/usr/bin/env python
"""模拟 Django 的 ES 连接方式，检查是否能访问 log_analysis_reports"""

import os
from elasticsearch import Elasticsearch

def test_django_es_connection():
    print("=" * 70)
    print("模拟 Django ES 连接测试")
    print("=" * 70)
    
    ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST', 'localhost')
    ELASTICSEARCH_PORT = int(os.environ.get('ELASTICSEARCH_PORT', 19200))
    ELASTICSEARCH_USER = os.environ.get('ELASTICSEARCH_USER', 'elastic')
    ELASTICSEARCH_PASSWORD = os.environ.get('ELASTICSEARCH_PASSWORD', 'password')
    
    print(f"\n当前环境变量 ES 配置:")
    print(f"  ELASTICSEARCH_HOST: {ELASTICSEARCH_HOST}")
    print(f"  ELASTICSEARCH_PORT: {ELASTICSEARCH_PORT}")
    print(f"  ELASTICSEARCH_USER: {ELASTICSEARCH_USER}")
    print(f"  ELASTICSEARCH_PASSWORD: {ELASTICSEARCH_PASSWORD}")
    
    print("\n--- 测试1: 使用配置的认证信息连接 ---")
    es = Elasticsearch(
        hosts=[f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"],
        basic_auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD),
        verify_certs=False,
        ssl_show_warn=False,
    )
    
    if not es.ping():
        print("❌ 无法连接到 Elasticsearch")
    else:
        print("✅ 连接成功!")
        
        try:
            exists = es.indices.exists(index="log_analysis_reports")
            print(f"  log_analysis_reports 索引存在: {exists}")
            
            if exists:
                total_search = {
                    "size": 0,
                    "track_total_hits": True
                }
                result = es.search(index="log_analysis_reports", body=total_search)
                print(f"  search 查询成功: total = {result['hits']['total']['value']}")
            else:
                print("  ❌ 索引不存在!")
        except Exception as e:
            print(f"  ❌ 发生错误: {type(e).__name__}: {e}")
    
    print("\n--- 测试2: 不使用认证信息连接 (模拟 Agent) ---")
    es_no_auth = Elasticsearch(
        hosts=[f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"],
        verify_certs=False,
        ssl_show_warn=False,
    )
    
    if not es_no_auth.ping():
        print("❌ 无法连接到 Elasticsearch (无认证)")
    else:
        print("✅ 连接成功 (无认证)!")
        
        try:
            exists = es_no_auth.indices.exists(index="log_analysis_reports")
            print(f"  log_analysis_reports 索引存在: {exists}")
        except Exception as e:
            print(f"  ❌ 发生错误: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_django_es_connection()