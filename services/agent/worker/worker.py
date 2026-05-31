# 单个 Worker - 管理自己的 KafkaConsumer 生命周期
import threading
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class Worker:
    """单个 Worker 线程 - 拥有独立的 KafkaConsumer"""

    def __init__(
        self,
        worker_id: int,
        kafka_config: dict,
        processor,
        running_flag: threading.Event,
        output_index: str = "agent_analysis_logs"
    ):
        self.worker_id = worker_id
        self.kafka_config = kafka_config
        self.processor = processor
        self.running_flag = running_flag
        self.output_index = output_index
        self._thread = None
        self._consumer = None

    def start(self):
        """启动 Worker"""
        self._thread = threading.Thread(
            target=self._run,
            name=f"Worker-{self.worker_id}"
        )
        self._thread.daemon = True
        self._thread.start()
        logger.info(f"Worker {self.worker_id} 已启动")

    def _run(self):
        """Worker 主循环"""
        from message_queue.consumer import KafkaConsumerClient
        from dify import DifyClient
        from es_client import DataWriter

        logger.info(f"[Worker-{self.worker_id}] 初始化中...")

        dify_client = DifyClient(
            api_key=self.kafka_config.get("dify_api_key", ""),
            api_url=self.kafka_config.get("dify_api_url", ""),
            timeout=30,
            max_retries=3
        )

        data_writer = DataWriter(None, self.output_index)

        consumer = KafkaConsumerClient(
            bootstrap_servers=self.kafka_config.get("bootstrap_servers", "localhost:9092"),
            topic=self.kafka_config.get("topic", "log-processing"),
            group_id=self.kafka_config.get("group_id", "log-sentinel-agent"),
            auto_offset_reset="latest"
        )

        if not consumer.connect():
            logger.error(f"[Worker-{self.worker_id}] Kafka 连接失败")
            return

        consumer.start_consuming()
        logger.info(f"[Worker-{self.worker_id}] 开始消费消息")

        message_count = 0
        last_log_time = time.time()

        while self.running_flag.is_set():
            message = consumer.poll(timeout_ms=1000)

            if message is not None:
                message_count += 1
                logger.debug(f"[Worker-{self.worker_id}] 收到消息: {message.get("event_id", "unknown")}")

                success = self.processor.process(message)

                if success:
                    logger.debug(f"[Worker-{self.worker_id}] 消息处理成功")
                else:
                    logger.warning(f"[Worker-{self.worker_id}] 消息处理失败")

                last_log_time = time.time()
            else:
                if time.time() - last_log_time > 60:
                    logger.debug(f"[Worker-{self.worker_id}] 等待消息中...")
                    last_log_time = time.time()

        consumer.stop_consuming()
        consumer.close()
        logger.info(f"[Worker-{self.worker_id}] 已关闭，共处理 {message_count} 条消息")

    def join(self, timeout=None):
        """等待 Worker 结束"""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        """检查 Worker 是否存活"""
        return self._thread and self._thread.is_alive()
