# 主入口脚本
import logging
import signal
import sys
import os

# 根据运行方式选择导入方式
if __name__ == "__main__" and __package__ is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from config import load_config
    from es_client import ElasticsearchClient, DataFetcher, DataWriter
    from message_queue import KafkaProducer
    from worker import WorkerPool
    from dify import DifyClient
    from monitor import MetricsCollector, HealthChecker
    from models import Task
else:
    from .config import load_config
    from .es_client import ElasticsearchClient, DataFetcher, DataWriter
    from .message_queue import KafkaProducer
    from .worker import WorkerPool
    from .dify import DifyClient
    from .monitor import MetricsCollector, HealthChecker
    from .models import Task


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("agent.log")
        ]
    )


def handle_signal(running_flag, worker_pool):
    """处理信号"""
    logger = logging.getLogger(__name__)
    logger.info(f"收到退出信号，正在优雅关闭...")
    if worker_pool:
        worker_pool.stop()
    sys.exit(0)


def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=== LogSentinel Agent 启动 ===")

    # 加载配置
    config = load_config()
    logger.info("配置加载完成")

    # 初始化组件
    try:
        # Elasticsearch 客户端
        es_client = ElasticsearchClient(
            hosts=config.es.hosts,
            username=config.es.username,
            password=config.es.password
        )
        if not es_client.connect():
            logger.error("无法连接到 Elasticsearch")
            return

        # 数据采集器
        data_fetcher = DataFetcher(es_client)

        # 数据写入器（Worker 会创建自己的实例）
        # data_writer = DataWriter(es_client, config.output.index)

        # Kafka 生产者
        kafka_producer = KafkaProducer(
            bootstrap_servers=config.kafka.bootstrap_servers,
            topic=config.kafka.topic
        )
        if not kafka_producer.connect():
            logger.error("无法连接到 Kafka")
            return

        # Dify 客户端（Worker 会创建自己的实例）
        # dify_client = DifyClient(...)

        # 指标收集器
        metrics = MetricsCollector()

        # 健康检查器
        health_checker = HealthChecker()
        health_checker.register_check("elasticsearch", es_client.connect)
        health_checker.register_check("kafka", kafka_producer.connect)

        logger.info("所有组件初始化完成")

        # 启动数据采集（后台线程）
        import threading
        running_flag = threading.Event()
        running_flag.set()

        def data_collection_loop():
            while running_flag.is_set():
                try:
                    logs = data_fetcher.fetch_pending_logs(
                        config.es.input_index,
                        minutes=10,
                        size=config.worker.batch_size
                    )
                    if logs:
                        tasks = [Task.create_from_log(log).to_dict() for log in logs]
                        kafka_producer.send_batch(tasks)
                        metrics.increment("kafka_messages_produced")
                        logger.info(f"已发送 {len(tasks)} 条消息到 Kafka")
                except Exception as e:
                    logger.error(f"数据采集异常: {str(e)}")
                import time
                time.sleep(5)

        collector_thread = threading.Thread(target=data_collection_loop, daemon=True)
        collector_thread.start()
        logger.info("数据采集线程已启动")

        # 准备 Worker 配置
        kafka_config = {
            "bootstrap_servers": config.kafka.bootstrap_servers,
            "topic": config.kafka.topic,
            "group_id": config.kafka.consumer_group,
            "dify_api_key": config.dify.api_key,
            "dify_api_url": config.dify.api_url,
        }

        # 启动 Worker 池（每个 Worker 有自己的 KafkaConsumer）
        worker_pool = WorkerPool(
            worker_count=config.worker.worker_count,
            kafka_config=kafka_config,
            output_index=config.output.index
        )

        # 注册信号处理
        signal.signal(signal.SIGINT, lambda s, f: handle_signal(running_flag, worker_pool))
        signal.signal(signal.SIGTERM, lambda s, f: handle_signal(running_flag, worker_pool))

        worker_pool.start()
        logger.info(f"Worker 池已启动 ({config.worker.worker_count} 个 Worker)")

        # 保持运行
        import time
        while running_flag.is_set():
            time.sleep(1)
            if not worker_pool.is_running():
                logger.warning("所有 Worker 已停止，退出程序")
                break

    except Exception as e:
        logger.error(f"启动失败: {str(e)}", exc_info=True)
    finally:
        logger.info("Agent 已关闭")


if __name__ == "__main__":
    main()
