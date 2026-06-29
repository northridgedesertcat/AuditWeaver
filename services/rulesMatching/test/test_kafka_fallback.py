# Kafka连接失败时的降级测试
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.data_saver import DataSaver
import json

def test_kafka_fallback():
    """测试当Kafka连接失败时，Elasticsearch仍能正常保存数据"""
    print("=" * 70)
    print("          Kafka连接失败时的降级测试")
    print("=" * 70)
    
    # 创建测试攻击日志
    test_logs = [
        {
            "ip": "192.168.1.99",
            "timestamp": "16/Apr/2026:11:00:00 +0000",
            "method": "GET",
            "path": "/api/user?id=1%27+OR+1%3D1--",  # SQL注入攻击
            "http_version": "HTTP/1.1",
            "status": 200,
            "bytes": 1000,
            "referrer": "-",
            "user_agent": "Mozilla/5.0",
            "event_id": "test-fallback-001"
        }
    ]
    
    print("\n[步骤1] 创建规则引擎并检测")
    engine = RuleEngine()
    detection_result = engine.detect_batch(test_logs)
    
    print(f"\n检测结果:")
    for i, result in enumerate(detection_result['results']):
        detections = result.get('detections', [])
        if detections:
            print(f"  检测到攻击: {detections[0]['matched_type']} (置信度: {detections[0]['confidence']*100:.1f}%)")
        else:
            print(f"  未检测到攻击")
    
    print("\n[步骤2] 创建DataSaver（使用无效的Kafka地址）")
    # 使用无效的Kafka地址，模拟Kafka连接失败
    data_saver = DataSaver(
        kafka_enabled=True,
        kafka_brokers='localhost:9999',  # 无效端口
        kafka_topic='log.risk'
    )
    
    print(f"\n连接状态:")
    print(f"  is_connected(): {data_saver.is_connected()}")
    print(f"  is_es_connected(): {data_saver.is_es_connected()}")
    print(f"  is_kafka_connected(): {data_saver.is_kafka_connected()}")
    
    if data_saver.is_es_connected():
        print("\n[步骤3] 保存结果（Kafka不可用，但Elasticsearch可用）")
        save_result = data_saver.process_and_save(test_logs, detection_result)
        
        print("\n保存结果:")
        print(f"  攻击日志: 总数={save_result['attack_logs']['total']}")
        print(f"    - Elasticsearch: 已保存={save_result['attack_logs']['saved_es']}, 失败={save_result['attack_logs']['failed_es']}")
        print(f"    - Kafka: 已发送={save_result['attack_logs']['saved_kafka']}, 失败={save_result['attack_logs']['failed_kafka']}")
        
        # 验证Elasticsearch中的数据
        print("\n[步骤4] 验证Elasticsearch中的数据")
        es_client = data_saver.es_client
        if es_client:
            query = {
                "query": {
                    "term": {
                        "event_id.keyword": "test-fallback-001"
                    }
                }
            }
            response = es_client.search(index='matched_logs', body=query)
            hits = response.get('hits', {}).get('hits', [])
            
            if hits:
                print(f"✓ 成功在Elasticsearch中找到测试数据")
                print(f"  ID: {hits[0]['_id']}")
                print(f"  IP: {hits[0]['_source'].get('ip')}")
                print(f"  攻击类型: {hits[0]['_source'].get('rule_match', {}).get('matched_type')}")
            else:
                print("✗ 未在Elasticsearch中找到测试数据")
        
        # 清理测试数据
        print("\n[步骤5] 清理测试数据")
        query = {
            "query": {
                "term": {
                    "event_id.keyword": "test-fallback-001"
                }
            }
        }
        response = es_client.delete_by_query(index='matched_logs', body=query, refresh=True)
        print(f"已删除 {response.get('deleted', 0)} 条测试数据")
    else:
        print("\n[ERROR] Elasticsearch也未连接，无法测试")
    
    data_saver.close()
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    test_kafka_fallback()
