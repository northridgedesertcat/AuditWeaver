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
    
    # 4. 检查 nginx-log-raw 索引（报告详情"原始日志行"仍依赖该索引）
    print("\n4. 检查 nginx-log-raw 索引:")
    try:
        indices = es.cat.indices(index="nginx-log-raw", format="json")
        if indices:
            print(f"   ✅ 索引存在")
            print(f"   索引信息: {indices}")
        else:
            print("   ❌ 索引不存在")
    except Exception as e:
        print(f"   ❌ 检查索引失败: {e}")

    # 注：AI 分析报告（原 log_analysis_reports 索引）已迁移至 MySQL
    # analysis_report 表，请用 Django ORM / MySQL 客户端核对，不再走 ES。

    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_elasticsearch()
