import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka import KafkaConsumer
from dataTransfer.data_saver import DataSaver
from dataAnalysis.rules_engine import RuleEngine
import json

# 测试配置
KAFKA_BROKERS = 'localhost:29092'
INPUT_TOPIC = 'log.audit'

print("测试完整流程: Kafka -> 规则引擎 -> Elasticsearch")
print("=" * 60)

# 1. 从Kafka消费消息
print("\n[步骤1] 从Kafka消费消息...")
try:
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BROKERS,
        group_id='test_full_flow',
        auto_offset_reset='earliest',
        consumer_timeout_ms=5000,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    logs = []
    for message in consumer:
        log_entry = message.value
        print(f"  收到消息: event_id={log_entry.get('event_id', 'N/A')}")
        logs.append(log_entry)
        if len(logs) >= 5:
            break
    
    consumer.close()
    print(f"  共收到 {len(logs)} 条消息")
    
    if not logs:
        print("  警告: 没有收到任何消息！")
        
except Exception as e:
    print(f"  消费消息失败: {str(e)}")
    sys.exit(1)

# 2. 规则引擎检测
print("\n[步骤2] 规则引擎检测...")
engine = RuleEngine()
result = engine.detect_batch(logs)
print(f"  检测结果: 总日志={result['total_logs']}, 检测到攻击={result['total_detections']}")

# 3. 保存到Elasticsearch
print("\n[步骤3] 保存到Elasticsearch...")
data_saver = DataSaver(
    es_host='localhost',
    es_port=19200,
    es_index='matched_logs',
    kafka_enabled=False
)

print(f"  Elasticsearch连接: {'OK' if data_saver.is_es_connected() else 'FAIL'}")

if data_saver.is_es_connected():
    save_result = data_saver.process_and_save(logs, result)
    print(f"  攻击日志 - Elasticsearch: 已保存={save_result['attack_logs']['saved_es']}, 失败={save_result['attack_logs']['failed_es']}")
    
    # 验证数据是否写入成功 - 使用 ingestion_time 查询最新写入的数据
    print("\n[步骤4] 验证Elasticsearch数据...")
    es_client = data_saver.es_client
    query = {
        "query": {
            "exists": {
                "field": "ingestion_time"
            }
        },
        "sort": {
            "ingestion_time": "desc"
        },
        "size": 5
    }
    try:
        response = es_client.search(index='matched_logs', body=query)
        hits = response.get('hits', {}).get('hits', [])
        print(f"  在 matched_logs 索引中找到 {len(hits)} 条带 ingestion_time 的记录")
        for hit in hits:
            source = hit['_source']
            ingestion_time = source.get('ingestion_time', 'N/A')
            if ingestion_time != 'N/A':
                ingestion_time = ingestion_time[:19]  # 只显示时间部分
            print(f"    - IP: {source.get('ip')}, attack_type: {source.get('rule_match', {}).get('attack_type', 'N/A')}, ingestion_time: {ingestion_time}")
    except Exception as e:
        print(f"  查询失败: {str(e)}")
else:
    print("  无法保存: Elasticsearch未连接")

data_saver.close()
print("\n测试完成！")