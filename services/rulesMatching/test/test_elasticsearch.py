# Elasticsearch测试文件
from dataTransfer.elasticsearch_client import ElasticsearchClient
from dataAnalysis.rules_engine import RuleEngine

def test_elasticsearch_connection():
    """测试Elasticsearch连接"""
    print("\n=== 测试Elasticsearch连接 ===")
    client = ElasticsearchClient()
    if client.is_connected():
        print("Elasticsearch连接成功")
        logs = client.get_latest_logs(minutes=5, size=10)
        print(f"获取到 {len(logs)} 条最近的日志")
        if logs:
            print("第一条日志:")
            print(logs[0])
    else:
        print("Elasticsearch连接失败")
    client.close()

def test_elasticsearch_data(engine):
    """测试从Elasticsearch获取数据并分析"""
    print("\n=== 测试从Elasticsearch获取数据并分析 ===")
    
    es_client = ElasticsearchClient()
    
    if not es_client.is_connected():
        print("[ERROR] 无法连接到Elasticsearch")
        print("[DEBUG] 请检查：")
        print("[DEBUG] 1. Elasticsearch服务是否正在运行")
        print("[DEBUG] 2. 连接地址是否正确 (默认: http://localhost:9200)")
        print("[DEBUG] 3. 网络连接是否正常")
        return
    
    print("正在从Elasticsearch获取最近5分钟的日志...")
    test_logs = es_client.get_latest_logs(minutes=5, size=50)
    es_client.close()
    
    if not test_logs:
        print("[WARNING] 未从Elasticsearch获取到日志")
        print("[DEBUG] 请检查：")
        print("[DEBUG] 1. 索引名是否正确 (默认: nginx-log)")
        print("[DEBUG] 2. 索引中是否有数据")
        print("[DEBUG] 3. 时间范围是否正确")
        return
    
    print(f"从Elasticsearch获取到 {len(test_logs)} 条日志")
    
    result = engine.detect_batch(test_logs)
    print(f"总日志数: {result['total_logs']}")
    print(f"总检测数: {result['total_detections']}")
    
    for i, res in enumerate(result['results']):
        print(f"\n日志 {i+1}:")
        if 'detections' in res:
            print(f"  检测到 {len(res['detections'])} 个攻击")
            for detection in res['detections']:
                print(f"  - {detection['attack_type']}: {detection['confidence']*100:.1f}%")
        else:
            print("  未检测到攻击")
