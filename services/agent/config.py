# 配置管理模块
import os
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ElasticsearchConfig:
    """Elasticsearch 配置"""
    hosts: str = "http://localhost:19200"
    input_index: str = "matched_logs"  # 输入索引：待分析的日志
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30


@dataclass
class KafkaConfig:
    """Kafka 配置"""
    bootstrap_servers: str = "localhost:9092"
    topic: str = "log-processing"
    consumer_group: str = "log-sentinel-agent"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True


@dataclass
class DifyConfig:
    """Dify API 配置"""
    api_key: str = "app-gT36NbVTIyfmTZjOOoifHHzf"
    api_url: str = "https://api.dify.ai/v1"
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class WorkerConfig:
    """Worker 配置"""
    worker_count: int = 4
    batch_size: int = 10
    poll_interval: float = 1.0


@dataclass
class OutputConfig:
    """输出配置"""
    index: str = "agent_analysis_logs"  # 输出索引：分析完成的日志
    index_prefix: str = "dify-processed"
    status_field: str = "pipeline.agent_analysis.status"


@dataclass
class AgentConfig:
    """Agent 主配置"""
    es: ElasticsearchConfig = field(default_factory=ElasticsearchConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    dify: DifyConfig = field(default_factory=DifyConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config() -> AgentConfig:
    """从环境变量加载配置"""
    config = AgentConfig()
    
    # Elasticsearch
    if os.getenv("ES_HOST"):
        config.es.hosts = os.getenv("ES_HOST")
    if os.getenv("ES_INPUT_INDEX"):
        config.es.input_index = os.getenv("ES_INPUT_INDEX")
    if os.getenv("ES_USERNAME"):
        config.es.username = os.getenv("ES_USERNAME")
    if os.getenv("ES_PASSWORD"):
        config.es.password = os.getenv("ES_PASSWORD")
    
    # Kafka
    if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
        config.kafka.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    if os.getenv("KAFKA_TOPIC"):
        config.kafka.topic = os.getenv("KAFKA_TOPIC")
    if os.getenv("KAFKA_CONSUMER_GROUP"):
        config.kafka.consumer_group = os.getenv("KAFKA_CONSUMER_GROUP")
    
    # Dify
    if os.getenv("DIFY_API_KEY"):
        config.dify.api_key = os.getenv("DIFY_API_KEY")
    if os.getenv("DIFY_API_URL"):
        config.dify.api_url = os.getenv("DIFY_API_URL")
    
    # Worker
    if os.getenv("WORKER_COUNT"):
        config.worker.worker_count = int(os.getenv("WORKER_COUNT"))
    if os.getenv("BATCH_SIZE"):
        config.worker.batch_size = int(os.getenv("BATCH_SIZE"))
    
    # Output
    if os.getenv("OUTPUT_INDEX"):
        config.output.index = os.getenv("OUTPUT_INDEX")
    
    return config
