# 常量定义模块

# 任务状态
TASK_STATUS = {
    "PENDING": "pending",
    "PROCESSING": "processing",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "RETRY": "retry"
}

# 规则匹配状态
RULE_MATCHING_STATUS = {
    "PENDING": "pending",
    "PROCESSED": "processed",
    "FAILED": "failed"
}

# Kafka 消息键
MESSAGE_KEYS = {
    "TASK_ID": "task_id",
    "EVENT_ID": "event_id",
    "DATA": "data",
    "TIMESTAMP": "timestamp",
    "STATUS": "status"
}

# 错误码
ERROR_CODES = {
    "ES_CONNECTION_ERROR": "ES_CONNECTION_ERROR",
    "KAFKA_PRODUCE_ERROR": "KAFKA_PRODUCE_ERROR",
    "DIFY_API_ERROR": "DIFY_API_ERROR",
    "VALIDATION_ERROR": "VALIDATION_ERROR"
}

# 默认索引名格式
INDEX_FORMAT = "{prefix}-{date}"
