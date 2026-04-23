from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'test',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest'
)

for msg in consumer:
    print("received:", msg.value.decode())