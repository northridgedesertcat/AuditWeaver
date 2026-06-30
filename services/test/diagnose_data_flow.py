#!/usr/bin/env python
"""诊断完整数据流问题"""

from elasticsearch import Elasticsearch
import subprocess

def check_es_indices():
    print("=" * 70)
    print("诊断完整数据流")
    print("=" * 70)
    
    es = Elasticsearch(
        hosts=["http://localhost:19200"],
        basic_auth=('elastic', 'password'),
        verify_certs=False,
        ssl_show_warn=False,
    )
    
    if not es.ping():
        print("❌ Elasticsearch 连接失败")
        return
    
    print("\n--- 1. Elasticsearch 索引状态 ---")
    indices = ['nginx-log-raw', 'matched_logs', 'log_analysis_reports']
    for index in indices:
        try:
            count = es.count(index=index)
            print(f"   {index}: {count['count']} 条")
        except Exception as e:
            print(f"   {index}: 查询失败 - {e}")
    
    print("\n--- 2. Kafka 主题检查 ---")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            topics = result.stdout.strip().split('\n')
            print(f"   Kafka 主题列表:")
            for topic in topics:
                if topic.strip():
                    print(f"     - {topic.strip()}")
        else:
            print(f"   ❌ 获取 Kafka 主题失败: {result.stderr}")
    except Exception as e:
        print(f"   ❌ 检查 Kafka 失败: {e}")
    
    print("\n--- 3. 检查各服务运行状态 ---")
    services = ['logstash', 'kafka', 'elasticsearch', 'redis']
    for service in services:
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"docker inspect {service} --format '{{{{.State.Running}}}}'"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                status = result.stdout.strip()
                if status == 'true':
                    print(f"   ✅ {service}: 运行中")
                else:
                    print(f"   ❌ {service}: 未运行")
            else:
                print(f"   ❓ {service}: 检查失败")
        except Exception as e:
            print(f"   ❓ {service}: 检查异常 - {e}")
    
    print("\n--- 4. 检查 agent 模块 ---")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker inspect agent --format '{{{{.State.Running}}}}'"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            status = result.stdout.strip()
            if status == 'true':
                print("   ✅ agent: 运行中")
                # 获取日志
                try:
                    log_result = subprocess.run(
                        ["powershell", "-Command", "docker logs agent --tail 30"],
                        capture_output=True, text=True, timeout=30
                    )
                    if log_result.returncode == 0:
                        print("   agent 最近30行日志:")
                        print("   " + "=" * 60)
                        for line in log_result.stdout.strip().split('\n')[-30:]:
                            print(f"   {line}")
                except Exception as e:
                    print(f"   ❌ 获取 agent 日志失败: {e}")
            else:
                print("   ❌ agent: 未运行")
        else:
            print("   ❓ agent: 检查失败")
    except Exception as e:
        print(f"   ❓ agent: 检查异常 - {e}")
    
    print("\n--- 5. 检查 rulesMatching 模块 ---")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker inspect rulesmatching --format '{{{{.State.Running}}}}'"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            status = result.stdout.strip()
            if status == 'true':
                print("   ✅ rulesMatching: 运行中")
            else:
                print("   ❌ rulesMatching: 未运行")
        else:
            print("   ❓ rulesMatching: 检查失败")
    except Exception as e:
        print(f"   ❓ rulesMatching: 检查异常 - {e}")
    
    print("\n--- 6. 检查 agent 模块的 Kafka 消费者 ---")
    print("   检查 log.analysis 主题是否有消息")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker exec kafka kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic log.analysis --time -1"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"   log.analysis 主题偏移量: {result.stdout.strip()}")
        else:
            print(f"   ❌ 获取偏移量失败: {result.stderr[:200]}")
    except Exception as e:
        print(f"   ❌ 检查偏移量失败: {e}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_es_indices()