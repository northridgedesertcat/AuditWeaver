# Agent 模块配置文件

# ========== Kafka 配置 ==========
KAFKA_CONFIG = {
    'brokers': 'localhost:29092',
    'input_topic': 'log.analysis',
    'group_id': 'agent_analysis_group_v10022',
    'auto_offset_reset': 'earliest',
    'consumer_timeout_ms': 5000,
    'max_poll_records': 10
}

# ========== Dify API 配置 ==========
DIFY_CONFIG = {
    'base_url': 'http://localhost/v1',      # Dify API 基础地址（不含 trailing slash）
    'api_key': 'app-QVX3LTdC3hC2ZDbdCD2vUBqR',  # Dify API Key
    'endpoint': 'workflows/run',            # API 端点路径（不含 /v1/）- Workflow 模式
    'timeout': 60,                          # 请求超时时间（秒）
    'response_mode': 'blocking'             # 响应模式：blocking 或 streaming
}

# ========== Elasticsearch 配置 ==========
ELASTICSEARCH_CONFIG = {
    'host': 'localhost',
    'port': 19200,
    'index': 'log_analysis_reports',
    'refresh': True
}

# ========== 日志配置 ==========
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'agent_analysis.log'
}

# ========== 处理配置 ==========
PROCESS_CONFIG = {
    'batch_size': 5,
    'poll_interval_ms': 1000,
    'retry_times': 3,
    'retry_delay': 2
}
