# d:\tools\ProgrammeTools\python\正规项目\LogSentinel\services\rulesMatching\test\test_kafka_consumer.py

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
import json
import time

def test_kafka_connection(broker, topic):
    """测试Kafka连接和数据接收"""
    print(f"=" * 60)
    print(f"测试Kafka连接: {broker}")
    print(f"测试Topic: {topic}")
    print("=" * 60)
    
    try:
        # 创建消费者
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=broker,
            group_id='test_consumer_group',
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=5000
        )
        
        print("✓ 成功创建Kafka消费者")
        
        # 获取topic列表
        topics = consumer.topics()
        print(f"\n可用Topics: {list(topics)}")
        
        if topic in topics:
            print(f"✓ {topic} topic存在")
            
            # 获取分区信息
            partitions = consumer.partitions_for_topic(topic)
            print(f"{topic} 分区数: {len(partitions) if partitions else 0}")
            
            # 尝试获取消息
            print("\n尝试获取消息...")
            messages = consumer.poll(timeout_ms=3000)
            
            if messages:
                total_messages = sum(len(records) for _, records in messages.items())
                print(f"✓ 成功获取到 {total_messages} 条消息")
                
                # 显示前3条消息
                count = 0
                for tp, records in messages.items():
                    for record in records:
                        count += 1
                        if count <= 3:
                            print(f"\n消息 #{count}:")
                            print(f"  Offset: {record.offset}")
                            print(f"  内容: {json.dumps(record.value, ensure_ascii=False)[:200]}...")
            else:
                print("✗ 未获取到消息")
                print("\n可能的原因:")
                print("  1. Topic中没有数据")
                print("  2. 消费者组偏移量已在最新位置")
                print("  3. 网络连接问题")
                
            consumer.close()
            return True
        else:
            print(f"✗ {topic} topic不存在")
            consumer.close()
            return False
            
    except NoBrokersAvailable:
        print(f"✗ Kafka Broker不可用: {broker}")
        return False
    except Exception as e:
        print(f"✗ 连接失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_producer(broker, topic):
    """测试Kafka生产者"""
    print(f"\n" + "=" * 60)
    print("测试Kafka生产者")
    print("=" * 60)
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=broker,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8')
        )
        
        print("✓ 成功创建Kafka生产者")
        
        # 发送测试消息
        test_message = {
            "event_id": f"test-{int(time.time())}",
            "ip": "192.168.1.100",
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "@timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "method": "GET",
            "path": "/test/path?id=123",
            "status": 200,
            "user_agent": "Test-Client/1.0",
            "bytes": 1000
        }
        
        print(f"\n发送测试消息到 {topic}...")
        future = producer.send(topic, test_message)
        producer.flush()
        record_metadata = future.get(timeout=10)
        print(f"✓ 消息发送成功:")
        print(f"  Topic: {record_metadata.topic}")
        print(f"  Partition: {record_metadata.partition}")
        print(f"  Offset: {record_metadata.offset}")
        
        producer.close()
        return True
        
    except Exception as e:
        print(f"✗ 生产者测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("          Kafka连接测试脚本")
    print("=" * 60)
    
    # 配置
    BROKER = 'localhost:29092'
    TOPIC = 'log.audit'
    
    # 测试消费者
    consumer_success = test_kafka_connection(BROKER, TOPIC)
    
    # 如果消费者测试成功，测试生产者
    if consumer_success:
        test_producer(BROKER, TOPIC)
        
        # 再次测试消费者，验证消息是否能被接收
        print("\n" + "=" * 60)
        print("再次测试消费者（验证刚发送的消息）")
        print("=" * 60)
        test_kafka_connection(BROKER, TOPIC)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)