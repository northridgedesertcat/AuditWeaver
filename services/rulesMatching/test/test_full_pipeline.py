# 完整流程测试脚本 - 验证规则引擎检测和保存到Elasticsearch
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.data_saver import DataSaver
import json

def test_full_pipeline():
    """测试完整的规则引擎处理和保存流程"""
    print("=" * 70)
    print("          规则引擎完整流程测试")
    print("=" * 70)
    
    # 创建测试日志数据（包含攻击特征）
    test_logs = [
        {
            "ip": "192.168.1.100",
            "timestamp": "16/Apr/2026:10:00:00 +0000",
            "method": "GET",
            "path": "/api/user?id=1%27+OR+1%3D1--",  # SQL注入攻击
            "http_version": "HTTP/1.1",
            "status": 200,
            "bytes": 1000,
            "referrer": "-",
            "user_agent": "Mozilla/5.0",
            "event_id": "test-sql-injection-001"
        },
        {
            "ip": "192.168.1.101",
            "timestamp": "16/Apr/2026:10:01:00 +0000",
            "method": "GET",
            "path": "/search?q=<script>alert('xss')</script>",  # XSS攻击
            "http_version": "HTTP/1.1",
            "status": 200,
            "bytes": 500,
            "referrer": "-",
            "user_agent": "Mozilla/5.0",
            "event_id": "test-xss-001"
        },
        {
            "ip": "192.168.1.102",
            "timestamp": "16/Apr/2026:10:02:00 +0000",
            "method": "GET",
            "path": "/index.html",  # 正常请求
            "http_version": "HTTP/1.1",
            "status": 200,
            "bytes": 2000,
            "referrer": "-",
            "user_agent": "Mozilla/5.0",
            "event_id": "test-normal-001"
        }
    ]
    
    print("\n[步骤1] 创建规则引擎并检测")
    engine = RuleEngine()
    
    # 批量检测
    print("正在检测测试日志...")
    detection_result = engine.detect_batch(test_logs)
    
    print(f"\n检测结果汇总:")
    print(f"  总日志数: {detection_result['total_logs']}")
    print(f"  总检测数: {detection_result['total_detections']}")
    
    for i, result in enumerate(detection_result['results']):
        log_entry = test_logs[i]
        detections = result.get('detections', [])
        if detections:
            print(f"\n  日志 #{i+1} (IP: {log_entry['ip']}):")
            print(f"    路径: {log_entry['path']}")
            print(f"    检测到攻击:")
            for det in detections:
                print(f"      - {det['matched_type']}: 置信度 {det['confidence']*100:.1f}%")
        else:
            print(f"\n  日志 #{i+1} (IP: {log_entry['ip']}): 正常")
    
    print("\n[步骤2] 创建DataSaver并保存结果")
    data_saver = DataSaver(kafka_enabled=False)  # 禁用Kafka，只测试Elasticsearch
    
    if not data_saver.is_connected():
        print("[ERROR] DataSaver连接失败")
        return
    
    print("[OK] DataSaver连接成功")
    
    # 保存结果
    print("\n正在保存检测结果...")
    save_result = data_saver.process_and_save(test_logs, detection_result)
    
    print("\n保存结果:")
    print(f"  攻击日志: 总数={save_result['attack_logs']['total']}")
    print(f"    - Elasticsearch: 已保存={save_result['attack_logs']['saved_es']}, 失败={save_result['attack_logs']['failed_es']}")
    print(f"    - Kafka: 已发送={save_result['attack_logs']['saved_kafka']}, 失败={save_result['attack_logs']['failed_kafka']}")
    print(f"  正常日志: 总数={save_result['normal_logs']['total']}, 已保存={save_result['normal_logs']['saved']}, 失败={save_result['normal_logs']['failed']}")
    
    # 验证保存结果
    print("\n[步骤3] 验证Elasticsearch中的数据")
    es_client = data_saver.es_client
    if es_client:
        # 搜索保存的攻击日志
        query = {
            "query": {
                "match": {
                    "rule_match.is_matched": True
                }
            },
            "size": 10
        }
        
        try:
            response = es_client.search(index='matched_logs', body=query)
            hits = response.get('hits', {}).get('hits', [])
            
            print(f"\n在matched_logs索引中找到 {len(hits)} 条攻击日志:")
            for hit in hits:
                source = hit['_source']
                print(f"\n  ID: {hit['_id']}")
                print(f"    IP: {source.get('ip', 'Unknown')}")
                print(f"    路径: {source.get('path', 'Unknown')}")
                print(f"    攻击类型: {source.get('rule_match', {}).get('matched_type', 'Unknown')}")
                print(f"    置信度: {source.get('rule_match', {}).get('confidence', 0)*100:.1f}%")
        except Exception as e:
            print(f"搜索Elasticsearch失败: {str(e)}")
    
    # 清理测试数据
    print("\n[步骤4] 清理测试数据")
    try:
        # 删除测试数据
        query = {
            "query": {
                "terms": {
                    "event_id.keyword": ["test-sql-injection-001", "test-xss-001", "test-normal-001"]
                }
            }
        }
        response = es_client.delete_by_query(index='matched_logs', body=query, refresh=True)
        print(f"已删除 {response.get('deleted', 0)} 条测试数据")
    except Exception as e:
        print(f"清理测试数据失败: {str(e)}")
    
    data_saver.close()
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    test_full_pipeline()
