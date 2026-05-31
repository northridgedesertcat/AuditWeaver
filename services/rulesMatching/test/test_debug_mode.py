# 调试模式测试脚本 - 详细输出整个分析过程
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from config import KAFKA_CONFIG, ELASTICSEARCH_CONFIG, LOG_CONFIG, DEBUG_CONFIG
from match_config import RULES_CONFIG, DETECTION_CONFIG
from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.data_saver import DataSaver

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger('debug_test')

def test_debug_mode():
    """详细调试模式测试"""
    print("="*80)
    print("              规则匹配引擎 - 调试模式测试")
    print("="*80)
    
    # 打印配置信息
    print("\n[配置信息]")
    print(f"  Kafka Broker: {KAFKA_CONFIG['brokers']}")
    print(f"  输入Topic: {KAFKA_CONFIG['input_topic']}")
    print(f"  输出Topic: {KAFKA_CONFIG['output_topic']}")
    print(f"  消费者组: {KAFKA_CONFIG['group_id']}")
    print(f"  Elasticsearch: {ELASTICSEARCH_CONFIG['host']}:{ELASTICSEARCH_CONFIG['port']}")
    print(f"  攻击索引: {ELASTICSEARCH_CONFIG['attack_index']}")
    print(f"  日志等级: {LOG_CONFIG['level']}")
    print(f"  调试模式: {DEBUG_CONFIG['enable_debug_logging']}")
    
    # 创建测试数据（模拟从Kafka接收的数据）
    print("\n[测试数据]")
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
            "event_id": "debug-sql-001"
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
            "event_id": "debug-xss-001"
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
            "event_id": "debug-normal-001"
        }
    ]
    
    for i, log in enumerate(test_logs):
        print(f"\n  日志 #{i+1}:")
        print(f"    IP: {log['ip']}")
        print(f"    方法: {log['method']}")
        print(f"    路径: {log['path']}")
        print(f"    状态码: {log['status']}")
        print(f"    Event ID: {log['event_id']}")
    
    # 步骤1: 规则引擎检测
    print("\n" + "="*80)
    print("[步骤1] 规则引擎检测")
    print("="*80)
    
    logger.info("创建规则引擎...")
    engine = RuleEngine()
    logger.info("规则引擎创建完成")
    
    logger.info("开始攻击检测...")
    result = engine.detect_batch(test_logs)
    
    print("\n[检测结果汇总]")
    print(f"  总日志数: {result['total_logs']}")
    print(f"  检测到攻击: {result['total_detections']}")
    
    # 详细输出每个日志的检测结果
    print("\n[详细检测结果]")
    for i, (log, res) in enumerate(zip(test_logs, result['results'])):
        detections = res.get('detections', [])
        if detections:
            print(f"\n  日志 #{i+1} (IP: {log['ip']}):")
            print(f"    原始路径: {log['path']}")
            print(f"    检测到 {len(detections)} 种攻击:")
            for det in detections:
                print(f"      - 攻击类型: {det['attack_type']}")
                print(f"        置信度: {det['confidence']*100:.2f}%")
                print(f"        严重程度: {det.get('severity', 'low')}")
                if det.get('matched_items'):
                    print(f"        匹配项: {det['matched_items']}")
        else:
            print(f"\n  日志 #{i+1} (IP: {log['ip']}): 正常请求")
    
    # 步骤2: 数据保存
    print("\n" + "="*80)
    print("[步骤2] 数据保存")
    print("="*80)
    
    logger.info("创建DataSaver...")
    data_saver = DataSaver(
        es_host=ELASTICSEARCH_CONFIG['host'],
        es_port=ELASTICSEARCH_CONFIG['port'],
        es_index=ELASTICSEARCH_CONFIG['attack_index'],
        kafka_enabled=True,
        kafka_brokers=KAFKA_CONFIG['brokers'],
        kafka_topic=KAFKA_CONFIG['output_topic']
    )
    
    print("\n[连接状态检查]")
    print(f"  Elasticsearch连接: {'OK' if data_saver.is_es_connected() else 'FAIL'}")
    print(f"  Kafka连接: {'OK' if data_saver.is_kafka_connected() else 'FAIL'}")
    print(f"  整体连接: {'OK' if data_saver.is_connected() else 'FAIL'}")
    
    if not data_saver.is_es_connected():
        print("\n[警告] Elasticsearch未连接，跳过保存测试")
        return
    
    logger.info("开始保存检测结果...")
    save_result = data_saver.process_and_save(test_logs, result)
    
    print("\n[保存结果汇总]")
    print(f"  攻击日志总数: {save_result['attack_logs']['total']}")
    print(f"    - Elasticsearch: 已保存={save_result['attack_logs']['saved_es']}, 失败={save_result['attack_logs']['failed_es']}")
    print(f"    - Kafka: 已发送={save_result['attack_logs']['saved_kafka']}, 失败={save_result['attack_logs']['failed_kafka']}")
    print(f"  正常日志总数: {save_result['normal_logs']['total']}")
    print(f"    - 已保存到JSON: {save_result['normal_logs']['saved']}, 失败={save_result['normal_logs']['failed']}")
    
    # 步骤3: 验证Elasticsearch中的数据
    print("\n" + "="*80)
    print("[步骤3] 验证Elasticsearch数据")
    print("="*80)
    
    es_client = data_saver.es_client
    if es_client:
        # 搜索攻击日志
        query = {
            "query": {
                "terms": {
                    "event_id.keyword": ["debug-sql-001", "debug-xss-001", "debug-normal-001"]
                }
            },
            "size": 10
        }
        
        try:
            response = es_client.search(index=ELASTICSEARCH_CONFIG['attack_index'], body=query)
            hits = response.get('hits', {}).get('hits', [])
            
            print(f"\n在 '{ELASTICSEARCH_CONFIG['attack_index']}' 索引中找到 {len(hits)} 条记录:")
            for hit in hits:
                source = hit['_source']
                print(f"\n  文档ID: {hit['_id']}")
                print(f"    IP: {source.get('ip')}")
                print(f"    路径: {source.get('path')}")
                print(f"    Event ID: {source.get('event_id')}")
                
                rule_match = source.get('rule_match', {})
                if rule_match.get('is_matched'):
                    print(f"    攻击检测: DETECTED")
                    print(f"      攻击类型: {rule_match.get('attack_type')}")
                    print(f"      置信度: {rule_match.get('confidence')*100:.2f}%")
                    print(f"      规则ID: {rule_match.get('rule_id')}")
                else:
                    print(f"    攻击检测: NONE (正常请求)")
                
                # 检查pipeline状态
                pipeline = source.get('pipeline', {})
                if pipeline:
                    rm_status = pipeline.get('rule_matching', {}).get('status')
                    aa_status = pipeline.get('agent_analysis', {}).get('status')
                    print(f"    Pipeline状态:")
                    print(f"      rule_matching: {rm_status}")
                    print(f"      agent_analysis: {aa_status}")
        except Exception as e:
            print(f"[ERROR] 搜索Elasticsearch失败: {str(e)}")
    
    # 步骤4: 清理测试数据
    print("\n" + "="*80)
    print("[步骤4] 清理测试数据")
    print("="*80)
    
    try:
        query = {
            "query": {
                "terms": {
                    "event_id.keyword": ["debug-sql-001", "debug-xss-001", "debug-normal-001"]
                }
            }
        }
        response = es_client.delete_by_query(
            index=ELASTICSEARCH_CONFIG['attack_index'], 
            body=query, 
            refresh=True
        )
        print(f"\n已删除 {response.get('deleted', 0)} 条测试数据")
    except Exception as e:
        print(f"[ERROR] 清理测试数据失败: {str(e)}")
    
    data_saver.close()
    
    print("\n" + "="*80)
    print("调试测试完成")
    print("="*80)

if __name__ == "__main__":
    test_debug_mode()