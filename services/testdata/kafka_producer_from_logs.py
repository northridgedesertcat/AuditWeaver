from kafka import KafkaProducer
from kafka.errors import KafkaError
import time
import random
import re
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.env import KAFKA_BROKERS

print("[DEBUG] 开始初始化 KafkaProducer...")

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,
    api_version=(2, 8, 0),
    request_timeout_ms=10000,
    retry_backoff_ms=500
)

print(f"[DEBUG] KafkaProducer 初始化完成，连接到: {KAFKA_BROKERS}")

TOPIC = "log.raw"

LOG_FILE = Path(__file__).resolve().parent / "demo_access.log"


def load_logs(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        logs = f.readlines()
    return [log.strip() for log in logs if log.strip()]


MONTH_ABBREV = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}

def replace_log_date(log_line):
    local_now = datetime.now()
    utc_now = local_now.astimezone(timezone.utc)
    month_abbr = MONTH_ABBREV[utc_now.month]
    utc_timestamp = f"{utc_now.day:02d}/{month_abbr}/{utc_now.year}:{utc_now.hour:02d}:{utc_now.minute:02d}:{utc_now.second:02d}"
    return re.sub(r"\[\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}", f"[{utc_timestamp}", log_line)


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