#!/usr/bin/env python
"""调试 Elasticsearch 写入失败问题"""

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError
import json

def test_write():
    print("=" * 70)
    print("调试 Elasticsearch 写入失败")
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
    
    # 模拟日志数据（从用户日志中提取）
    test_data = {
        "audit_user": "185.199.108.10",
        "pipeline": {"rule_matching": {"status": "pending"}},
        "referrer": "-",
        "event": {"original": '185.199.108.10 - - [30/Jun/2026:08:46:11 +0000] "GET /download?file=../../../etc/shadow HTTP/1.1" 401 146 "-" "python-requests/2.31.0"'},
        "ip": "185.199.108.10",
        "@version": "1",
        "method": "GET",
        "status": 401,
        "user_agent": "python-requests/2.31.0",
        "event_id": "41b8d2c9-a9c2-48b8-9cc2-b8ae3f78d65d",
        "path": "/download?file=../../../etc/shadow",
        "@timestamp": "2026-06-30T08:46:11.000Z",
        "http_version": "1.1",
        "bytes": 146,
        "audit_event": "GET /download?file=../../../etc/shadow",
        "log_source": "nginx",
        "rule_match": {
            "is_matched": True,
            "rule_id": "PATH_TRAVERSAL_001",
            "matched_type": "path_traversal",
            "confidence": 0.21,
            "severity": "low",
            "matched_items": {"keywords": ["../", "/etc/", "shadow"], "patterns": ["\\.\\./", "/etc/shadow"]}
        },
        "ingestion_time": "2026-06-30T08:50:29.000Z"
    }
    
    print("\n1. 当前 matched_logs 索引 mapping:")
    try:
        mapping = es.indices.get_mapping(index="matched_logs")
        props = mapping['matched_logs']['mappings']['properties']
        print(f"已定义字段: {list(props.keys())}")
    except Exception as e:
        print(f"❌ 获取 mapping 失败: {e}")
    
    print("\n2. 测试数据中的字段:")
    print(f"数据字段: {list(test_data.keys())}")
    
    print("\n3. 检查未在 mapping 中定义的字段:")
    missing_fields = []
    for field in test_data.keys():
        if field not in props:
            missing_fields.append(field)
    print(f"未定义字段: {missing_fields}")
    
    print("\n4. 尝试写入测试数据到 matched_logs:")
    try:
        response = es.index(index="matched_logs", document=test_data, refresh=True)
        print(f"✅ 写入成功! ID: {response['_id']}")
        
        # 验证写入
        get_response = es.get(index="matched_logs", id=response['_id'])
        print(f"✅ 验证成功")
        
    except RequestError as e:
        print(f"❌ RequestError: {e}")
        if hasattr(e, 'info') and 'error' in e.info:
            print(f"   详细错误: {json.dumps(e.info['error'], indent=2)}")
    except Exception as e:
        print(f"❌ 写入失败: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_write()