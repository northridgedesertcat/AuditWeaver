from kafka import KafkaProducer
import time

producer = KafkaProducer(
    bootstrap_servers='localhost:29092'
)

log = '39.144.100.52 - - [08/Mar/2026:11:30:32 +0000] "GET /login?redirect=/index HTTP/1.1" 200 1561 "-" "Mozilla/5.0"'

while True:
    producer.send('your-topic', log.encode('utf-8'))
    print("sent:", log)
    time.sleep(2)


    