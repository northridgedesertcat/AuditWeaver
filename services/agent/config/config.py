import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from common.env import (
    KAFKA_BROKERS,
    DIFY_BASE_URL,
    DIFY_API_KEY,
    DIFY_TIMEOUT,
    ES_HOST,
    ES_PORT,
    LOG_LEVEL,
)

KAFKA_CONFIG = {
    'brokers': KAFKA_BROKERS,
    'input_topic': 'log.analysis',
    'group_id': 'agent_analysis_group_v10022',
    'auto_offset_reset': 'earliest',
    'consumer_timeout_ms': 5000,
    'max_poll_records': 10
}

DIFY_CONFIG = {
    'base_url': DIFY_BASE_URL,
    'api_key': DIFY_API_KEY,
    'endpoint': 'workflows/run',
    'timeout': DIFY_TIMEOUT,
    'response_mode': 'blocking'
}

ELASTICSEARCH_CONFIG = {
    'host': ES_HOST,
    'port': ES_PORT,
    'index': 'log_analysis_reports',
    'refresh': True
}

LOG_CONFIG = {
    'level': LOG_LEVEL,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'agent_analysis.log'
}

PROCESS_CONFIG = {
    'batch_size': 5,
    'poll_interval_ms': 1000,
    'retry_times': 3,
    'retry_delay': 2
}
