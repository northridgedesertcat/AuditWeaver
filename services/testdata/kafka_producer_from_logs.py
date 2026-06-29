from kafka import KafkaProducer
import time
import random
import re
from datetime import datetime
from pathlib import Path

producer = KafkaProducer(
    bootstrap_servers='localhost:29092'
)

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
    producer.send(TOPIC, log.encode("utf-8"))
    producer.flush()


def main():
    logs = load_logs(LOG_FILE)
    print(f"已加载 {len(logs)} 条日志")
    
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


if __name__ == "__main__":
    main()