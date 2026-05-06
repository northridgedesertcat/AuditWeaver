# 规则引擎测试文件
import json
from dataAnalysis.rules_engine import RuleEngine
from .test_data import load_test_logs

def test_single_log(engine):
    """测试单条日志检测"""
    print("\n=== 测试单条日志检测 ===")
    test_log = {
        'ip': '10.0.0.1',
        'timestamp': '16/Apr/2026:10:00:00 +0000',
        'method': 'GET',
        'path': "/login.php?username=admin' OR 1=1 --&password=test",
        'http_version': 'HTTP/1.1',
        'status': 200,
        'bytes': 512,
        'referrer': '-',
        'user_agent': 'Mozilla/5.0'
    }
    result = engine.detect(test_log)
    print(json.dumps(result, indent=2, ensure_ascii=False))

def test_batch_logs(engine):
    """测试批量日志检测"""
    print("\n=== 测试批量日志检测 ===")
    test_logs = load_test_logs()
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

def test_config_validation(engine):
    """测试配置验证"""
    print("\n=== 测试配置验证 ===")
    is_valid = engine.validate_config()
    if is_valid:
        print("配置验证成功")
    else:
        print("配置验证失败")
