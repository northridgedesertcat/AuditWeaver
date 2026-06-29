# 简单测试：验证攻击日志保存到Elasticsearch
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.data_saver import DataSaver

def test_es_save():
    """简单测试Elasticsearch保存功能"""
    print("="*70)
    print("简单测试：验证攻击日志保存到Elasticsearch")
    print("="*70)
    
    # 创建测试攻击日志（包含明确的攻击特征）
    test_logs = [
        {
            "ip": "10.0.0.1",
            "timestamp": "16/Apr/2026:12:00:00 +0000",
            "method": "GET",
            "path": "/search?q=<script>alert(document.cookie)</script>",
            "http_version": "HTTP/1.1",
            "status": 200,
            "bytes": 500,
            "referrer": "-",
            "user_agent": "Mozilla/5.0",
            "event_id": "test-es-save-001"
        }
    ]
    
    print("\n1. 创建规则引擎")
    engine = RuleEngine()
    
    print("\n2. 检测攻击")
    result = engine.detect_batch(test_logs)
    
    print("\n3. 检测结果:")
    print("   总日志数:", result['total_logs'])
    print("   总检测数:", result['total_detections'])
    
    # 检查是否检测到攻击
    attack_found = False
    for res in result['results']:
        if res.get('detections'):
            attack_found = True
            print("   检测到攻击:", res['detections'][0]['matched_type'])
            break
    
    if not attack_found:
        print("   未检测到攻击")
        return
    
    print("\n4. 创建DataSaver（仅启用Elasticsearch）")
    data_saver = DataSaver(kafka_enabled=False)
    
    print("   Elasticsearch连接:", data_saver.is_es_connected())
    
    if not data_saver.is_es_connected():
        print("   ERROR: Elasticsearch未连接")
        return
    
    print("\n5. 保存攻击日志到Elasticsearch")
    save_result = data_saver.process_and_save(test_logs, result)
    
    print("\n6. 保存结果:")
    print("   攻击日志总数:", save_result['attack_logs']['total'])
    print("   Elasticsearch已保存:", save_result['attack_logs']['saved_es'])
    print("   Elasticsearch失败:", save_result['attack_logs']['failed_es'])
    
    # 验证
    print("\n7. 验证Elasticsearch中的数据")
    es_client = data_saver.es_client
    query = {
        "query": {
            "term": {
                "event_id.keyword": "test-es-save-001"
            }
        }
    }
    
    try:
        response = es_client.search(index='matched_logs', body=query)
        hits = response.get('hits', {}).get('hits', [])
        
        if hits:
            print("   SUCCESS: 在Elasticsearch中找到数据")
            print("   文档ID:", hits[0]['_id'])
            print("   IP:", hits[0]['_source'].get('ip'))
            print("   攻击类型:", hits[0]['_source'].get('rule_match', {}).get('matched_type'))
            print("   置信度:", hits[0]['_source'].get('rule_match', {}).get('confidence'))
        else:
            print("   FAILED: 未在Elasticsearch中找到数据")
    except Exception as e:
        print("   ERROR:", str(e))
    
    # 清理
    print("\n8. 清理测试数据")
    try:
        query = {
            "query": {
                "term": {
                    "event_id.keyword": "test-es-save-001"
                }
            }
        }
        response = es_client.delete_by_query(index='matched_logs', body=query, refresh=True)
        print("   删除记录数:", response.get('deleted', 0))
    except Exception as e:
        print("   删除失败:", str(e))
    
    data_saver.close()
    
    print("\n" + "="*70)
    print("测试完成")
    print("="*70)

if __name__ == "__main__":
    test_es_save()
