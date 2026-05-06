# 主入口脚本
from dataAnalysis.rules_engine import RuleEngine
from dataTransfer.elasticsearch_client import ElasticsearchClient
from dataTransfer.data_saver import DataSaver

def analyze_elasticsearch_logs():
    """从Elasticsearch获取数据并分析"""
    print("\n=== 从Elasticsearch获取数据并分析 ===")
    
    es_client = ElasticsearchClient()
    
    if not es_client.is_connected():
        print("[ERROR] 无法连接到Elasticsearch")
        print("[DEBUG] 请检查：")
        print("[DEBUG] 1. Elasticsearch服务是否正在运行")
        print("[DEBUG] 2. 连接地址是否正确 (默认: http://localhost:9200)")
        print("[DEBUG] 3. 网络连接是否正常")
        return
    
    print("正在从Elasticsearch获取最近5分钟的日志...")
    logs = es_client.get_latest_logs(minutes=5, size=50)
    es_client.close()
    
    if not logs:
        print("[WARNING] 未从Elasticsearch获取到日志")
        print("[DEBUG] 请检查：")
        print("[DEBUG] 1. 索引名是否正确 (默认: nginx-log)")
        print("[DEBUG] 2. 索引中是否有数据")
        print("[DEBUG] 3. 时间范围是否正确")
        return
    
    print(f"从Elasticsearch获取到 {len(logs)} 条日志")
    
    # 使用规则引擎分析日志
    engine = RuleEngine()
    result = engine.detect_batch(logs)
    
    print(f"\n分析结果：")
    print(f"总日志数: {result['total_logs']}")
    print(f"总检测数: {result['total_detections']}")
    
    # 显示检测到攻击的日志
    attack_count = 0
    for i, res in enumerate(result['results']):
        if 'detections' in res and res['detections']:
            attack_count += 1
            print(f"\n日志 {i+1} (来源: {res['log_entry'].get('ip', 'Unknown')}):")
            print(f"  请求路径: {res['log_entry'].get('path', 'Unknown')}")
            print(f"  检测到 {len(res['detections'])} 个攻击:")
            for detection in res['detections']:
                print(f"    - {detection['attack_type']}: 置信度 {detection['confidence']*100:.1f}%")
    
    if attack_count == 0:
        print("\n未检测到攻击")
    
    # 保存检测结果到Elasticsearch
    print("\n=== 保存检测结果 ===")
    data_saver = DataSaver()
    
    if not data_saver.is_connected():
        print("[ERROR] 无法连接到Elasticsearch，无法保存检测结果")
        return
    
    print("正在保存检测结果到Elasticsearch...")
    save_result = data_saver.save_batch(logs, result)
    print(f"保存完成: 成功 {save_result['saved']} 条, 失败 {save_result['failed']} 条")
    
    data_saver.close()

def main():
    """主函数"""
    print("=== LogSentinel 规则匹配引擎 ===")
    
    # 验证规则引擎配置
    engine = RuleEngine()
    print("正在验证规则引擎配置...")
    if engine.validate_config():
        print("规则引擎配置验证成功")
    else:
        print("规则引擎配置验证失败")
        return
    
    # 分析Elasticsearch日志
    analyze_elasticsearch_logs()
    
    print("\n=== 分析完成 ===")

if __name__ == "__main__":
    main()
