from kafka import KafkaProducer
import time
from datetime import datetime, timezone

producer = KafkaProducer(
    bootstrap_servers='localhost:29092'
)

def generate_log():
    now = datetime.now(timezone.utc)

    # Apache log format: 08/Mar/2026:11:30:32 +0000
    timestamp_str = now.strftime('%d/%b/%Y:%H:%M:%S %z')

    log = f'39.144.100.52 - - [{timestamp_str}] "GET /login?redirect=/index HTTP/1.1" 200 1561 "-" "Mozilla/5.0"'
    
    return log

while True:
    log = generate_log()
    producer.send('your-topic', log.encode('utf-8'))
    print("sent:", log)
    time.sleep(2)