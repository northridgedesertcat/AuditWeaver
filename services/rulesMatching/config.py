# 规则匹配引擎配置文件
# 包含 Kafka、Elasticsearch 和日志相关配置

# ==================== Kafka 配置 ====================
KAFKA_CONFIG = {
    'brokers': 'localhost:29092',           # Kafka broker 地址
    'input_topic': 'log.audit',              # 输入日志的 topic
    'output_topic': 'log.risk',              # 输出风险数据的 topic
    'group_id': 'rules_matching_group_test_v0001',   # 消费者组 ID
    'auto_offset_reset': 'earliest',         # 偏移量重置策略: earliest/latest
    'enable_auto_commit': True,              # 是否自动提交偏移量
    'auto_commit_interval_ms': 5000,         # 自动提交间隔(毫秒)
    'max_poll_records': 10,                  # 每次轮询最多获取的消息数
    'poll_timeout_ms': 1000,                 # 每次轮询等待时间(毫秒)
    'heartbeat_interval_seconds': 30,        # 心跳日志输出间隔(秒)
    'session_timeout_ms': 30000,             # 会话超时时间(毫秒)
    'request_timeout_ms': 45000              # 请求超时时间(毫秒)
}

# ==================== Elasticsearch 配置 ====================
ELASTICSEARCH_CONFIG = {
    'host': 'localhost',                     # Elasticsearch 主机
    'port': 19200,                           # Elasticsearch 端口
    'use_ssl': False,                        # 是否使用 SSL
    'verify_certs': False,                   # 是否验证证书
    'attack_index': 'matched_logs',          # 攻击日志索引名
    'timeout': 30,                           # 连接超时时间(秒)
    'max_retries': 3,                        # 最大重试次数
    'refresh_after_write': True              # 写入后是否立即刷新
}

# ==================== 日志配置 ====================
LOG_CONFIG = {
    'level': 'DEBUG',                        # 日志等级: DEBUG/INFO/WARN/ERROR
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'file_path': 'd:\\tools\\ProgrammeTools\\python\\正规项目\\LogSentinel\\services\\rulesMatching\\rules_matching.log',
    'max_file_size': 10 * 1024 * 1024,       # 最大文件大小(字节)
    'backup_count': 5                        # 备份文件数量
}

# ==================== 数据处理配置 ====================
PROCESSING_CONFIG = {
    'batch_size': 100,                       # 批量处理大小
    'max_concurrent_requests': 10,           # 最大并发请求数
    'normal_log_dir': 'd:\\tools\\ProgrammeTools\\python\\正规项目\\LogSentinel\\services\\rulesMatching\\temporaryDatas\\unmatchDatas',
    'save_normal_logs': True                 # 是否保存正常日志到本地
}

# ==================== 调试配置 ====================
DEBUG_CONFIG = {
    'enable_debug_logging': True,            # 是否启用调试日志
    'log_kafka_messages': True,              # 是否记录 Kafka 消息内容
    'log_elasticsearch_operations': True,    # 是否记录 Elasticsearch 操作
    'log_detection_details': True,           # 是否记录检测详细信息
    'log_performance_metrics': True          # 是否记录性能指标
}