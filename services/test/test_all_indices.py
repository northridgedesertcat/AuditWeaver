#!/usr/bin/env python
"""测试所有三个索引的写入"""

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError
import json

def test_all_indices():
    print("=" * 70)
    print("测试所有索引的写入")
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
    
    # 测试 nginx-log-raw (Logstash 输出)
    print("\n--- 1. 测试 nginx-log-raw ---")
    nginx_data = {
        "@timestamp": "2026-06-30T08:46:11.000Z",
        "@version": "1",
        "bytes": 146,
        "event_id": "41b8d2c9-a9c2-48b8-9cc2-b8ae3f78d65d",
        "http_version": "1.1",
        "ip": "185.199.108.10",
        "method": "GET",
        "path": "/download?file=../../../etc/shadow",
        "referrer": "-",
        "status": 401,
        "user_agent": "python-requests/2.31.0",
        "log_source": "nginx",
        "audit_user": "185.199.108.10",
        "audit_event": "GET /download?file=../../../etc/shadow",
        "pipeline": {"rule_matching": {"status": "pending"}}
    }
    
    try:
        response = es.index(index="nginx-log-raw", document=nginx_data, refresh=True)
        print(f"✅ nginx-log-raw 写入成功! ID: {response['_id']}")
    except Exception as e:
        print(f"❌ nginx-log-raw 写入失败: {type(e).__name__}: {e}")
    
    # 测试 matched_logs (rulesMatching 输出)
    print("\n--- 2. 测试 matched_logs ---")
    matched_data = {
        "@timestamp": "2026-06-30T08:46:11.000Z",
        "@version": "1",
        "event": {"original": '185.199.108.10 - - [30/Jun/2026:08:46:11 +0000] "GET /download?file=../../../etc/shadow HTTP/1.1" 401 146 "-" "python-requests/2.31.0"'},
        "bytes": 146,
        "event_id": "41b8d2c9-a9c2-48b8-9cc2-b8ae3f78d65d",
        "http_version": "1.1",
        "ip": "185.199.108.10",
        "method": "GET",
        "path": "/download?file=../../../etc/shadow",
        "referrer": "-",
        "status": 401,
        "user_agent": "python-requests/2.31.0",
        "log_source": "nginx",
        "audit_user": "185.199.108.10",
        "audit_event": "GET /download?file=../../../etc/shadow",
        "rule_match": {
            "is_matched": True,
            "rule_id": "PATH_TRAVERSAL_001",
            "matched_type": "path_traversal",
            "confidence": 0.21,
            "severity": "low",
            "matched_items": {"keywords": ["../", "/etc/", "shadow"], "patterns": ["\\.\\./", "/etc/shadow"]}
        },
        "ingestion_time": "2026-06-30T08:50:29.000Z",
        "pipeline": {"rule_matching": {"status": "completed"}}
    }
    
    try:
        response = es.index(index="matched_logs", document=matched_data, refresh=True)
        print(f"✅ matched_logs 写入成功! ID: {response['_id']}")
    except Exception as e:
        print(f"❌ matched_logs 写入失败: {type(e).__name__}: {e}")
    
    # 测试 log_analysis_reports (agent 输出 - 使用 epoch_millis)
    print("\n--- 3. 测试 log_analysis_reports ---")
    from datetime import datetime
    now = datetime.utcnow()
    epoch_ms = int(now.timestamp() * 1000)
    
    report_data = {
        "event_id": "41b8d2c9-a9c2-48b8-9cc2-b8ae3f78d65d",
        "ip": "185.199.108.10",
        "path": "/download?file=../../../etc/shadow",
        "method": "GET",
        "status": 401,
        "user_agent": "python-requests/2.31.0",
        
        "attack_type": "path_traversal",
        "confidence": 0.85,
        "severity": "high",
        
        "risk_level": "High",
        "risk_score": 85,
        "attack_type_ai": "path_traversal",
        "summary": "检测到路径遍历攻击，攻击者试图访问敏感文件 /etc/shadow",
        
        "reasoning": "请求路径中包含多个 ../ 序列，试图绕过目录限制访问系统敏感文件",
        "recommendations": "建议检查服务器配置，禁用目录遍历，记录攻击者IP",
        
        "log_timestamp": epoch_ms,
        "analysis_timestamp": epoch_ms,
        "ingestion_time": epoch_ms,
        
        "dify_response": {"status": "success", "message": "Analysis complete"},
        "original_log": {"raw": "185.199.108.10 - - [30/Jun/2026:08:46:11 +0000] \"GET /download?file=../../../etc/shadow HTTP/1.1\" 401 146"}
    }
    
    try:
        response = es.index(index="log_analysis_reports", document=report_data, refresh=True)
        print(f"✅ log_analysis_reports 写入成功! ID: {response['_id']}")
        
        # 验证查询
        query = {
            "query": {"match_all": {}},
            "sort": [{"analysis_timestamp": {"order": "desc"}}],
            "size": 1
        }
        result = es.search(index="log_analysis_reports", query=query)
        hits = result.get('hits', {}).get('hits', [])
        if hits:
            print(f"✅ 查询成功，total: {result['hits']['total']['value']}")
        else:
            print("❌ 查询返回空")
            
    except RequestError as e:
        print(f"❌ RequestError: {e}")
        if hasattr(e, 'info') and 'error' in e.info:
            print(f"   详细错误: {json.dumps(e.info['error'], indent=2)}")
    except Exception as e:
        print(f"❌ log_analysis_reports 写入失败: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 70)
    
    # 显示各索引数据统计
    print("\n--- 索引数据统计 ---")
    for index in ['nginx-log-raw', 'matched_logs', 'log_analysis_reports']:
        try:
            count = es.count(index=index)
            print(f"{index}: {count['count']} 条记录")
        except Exception as e:
            print(f"{index}: 查询失败 - {e}")

if __name__ == "__main__":
    test_all_indices()