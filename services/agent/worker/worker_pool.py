# Worker 线程池管理 - 稳定版本
import threading
import logging
import time
from typing import List

logger = logging.getLogger(__name__)


class WorkerPool:
    """Worker 线程池 - 稳定版本"""

    def __init__(self, worker_count: int = 4, kafka_config: dict = None, output_index: str = "agent_analysis_logs"):
        self.worker_count = worker_count
        self.kafka_config = kafka_config or {}
        self.output_index = output_index
        self._workers: List[Worker] = []
        self._running_flag = threading.Event()
        self._started = False

    def start(self):
        """启动线程池 - 只执行一次"""
        if self._started:
            logger.warning("Worker 池已在运行，忽略重复启动请求")
            return

        if self.worker_count <= 0:
            logger.error("Worker 数量必须大于 0")
            return

        self._running_flag.set()
        self._started = True

        logger.info(f"正在启动 {self.worker_count} 个 Worker...")

        from worker.processor import TaskProcessor
        from dify import DifyClient
        from es_client import DataWriter

        dify_client = DifyClient(
            api_key=self.kafka_config.get("dify_api_key", ""),
            api_url=self.kafka_config.get("dify_api_url", ""),
            timeout=30,
            max_retries=3
        )

        data_writer = DataWriter(None, self.output_index)

        processor = TaskProcessor(dify_client, data_writer)

        for i in range(self.worker_count):
            from worker.worker import Worker
            worker = Worker(
                worker_id=i + 1,
                kafka_config=self.kafka_config,
                processor=processor,
                running_flag=self._running_flag,
                output_index=self.output_index
            )
            worker.start()
            self._workers.append(worker)
            time.sleep(0.1)

        logger.info(f"Worker 池启动完成，共 {len(self._workers)} 个 Worker")

    def stop(self, timeout: float = 10.0):
        """优雅停止所有 Worker"""
        if not self._started:
            logger.warning("Worker 池未运行，无需停止")
            return

        logger.info("正在停止 Worker 池...")
        self._running_flag.clear()

        for worker in self._workers:
            worker.join(timeout=timeout)

        self._workers.clear()
        self._started = False
        logger.info("Worker 池已完全停止")

    def is_running(self) -> bool:
        """检查线程池是否正在运行"""
        return self._started and self._running_flag.is_set()

    def get_worker_count(self) -> int:
        """获取 Worker 数量"""
        return len([w for w in self._workers if w.is_alive()])

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
