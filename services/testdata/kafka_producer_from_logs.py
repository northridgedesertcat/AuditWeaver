from kafka import KafkaProducer
from kafka.errors import KafkaError
import time
import random
import re
from datetime import datetime
from pathlib import Path

print("[DEBUG] 开始初始化 KafkaProducer...")

producer = KafkaProducer(
    bootstrap_servers='localhost:29092',
    api_version=(2, 8, 0),
    request_timeout_ms=10000,
    retry_backoff_ms=500
)

print(f"[DEBUG] KafkaProducer 初始化完成，连接到: localhost:29092")

TOPIC = "log.raw"

LOG_FILE = Path(__file__).resolve().parent / "demo_access.log"


def load_logs(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        logs = f.readlines()
    return [log.strip() for log in logs if log.strip()]


def replace_log_date(log_line):
    today = datetime.now()
    today_str = today.strftime("%d/%b/%Y")
    return re.sub(r"\[\d{2}/\w{3}/\d{4}:", f"[{today_str}:", log_line)


def send_log_to_kafka(log):
    try:
        print(f"[DEBUG] 准备发送消息到 topic={TOPIC}, 长度={len(log)}")
        future = producer.send(TOPIC, log.encode("utf-8"))
        print(f"[DEBUG] 消息已提交，等待确认...")
        record_metadata = future.get(timeout=10)
        print(f"[DEBUG] 发送成功! partition={record_metadata.partition}, offset={record_metadata.offset}")
        producer.flush()
    except KafkaError as e:
        print(f"[ERROR-Kafka] 发送失败: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] 发送异常: {e}")
        raise


def main():
    print(f"[DEBUG] 开始加载日志文件: {LOG_FILE}")
    logs = load_logs(LOG_FILE)
    print(f"[DEBUG] 已加载 {len(logs)} 条日志")

    if not logs:
        print("[ERROR] 日志文件为空或无可用日志")
        return

    print("[DEBUG] 开始循环发送日志...")
    try:
        while True:
            log = random.choice(logs)
            log = replace_log_date(log)

            send_log_to_kafka(log)
            print(f"[SENT] {log[:80]}...")

            time.sleep(random.uniform(0.5, 2.0))

    except KeyboardInterrupt:
        print("\n停止发送")
        producer.close()
    except Exception as e:
        print(f"\n[ERROR-FATAL] 程序异常退出: {type(e).__name__}: {e}")
        producer.close()
        raise


if __name__ == "__main__":
    main()