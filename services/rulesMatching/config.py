import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from common.env import (
    KAFKA_BROKERS,
    ES_HOST,
    ES_PORT,
    LOG_LEVEL,
)

KAFKA_CONFIG = {
    'brokers': KAFKA_BROKERS,
    'input_topic': 'log.audit',
    'output_topic': 'log.analysis',
    'group_id': 'rules_matching_group_test_v0002',
    'auto_offset_reset': 'earliest',
    'enable_auto_commit': True,
    'auto_commit_interval_ms': 5000,
    'max_poll_records': 10,
    'poll_timeout_ms': 1000,
    'heartbeat_interval_seconds': 30,
    'session_timeout_ms': 30000,
    'request_timeout_ms': 45000
}

ELASTICSEARCH_CONFIG = {
    'host': ES_HOST,
    'port': ES_PORT,
    'use_ssl': False,
    'verify_certs': False,
    'attack_index': 'matched_logs',
    'timeout': 30,
    'max_retries': 3,
    'refresh_after_write': True
}

LOG_CONFIG = {
    'level': LOG_LEVEL,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'file_path': str(Path(__file__).resolve().parent / 'rules_matching.log'),
    'max_file_size': 10 * 1024 * 1024,
    'backup_count': 5
}

PROCESSING_CONFIG = {
    'batch_size': 100,
    'max_concurrent_requests': 10,
    'normal_log_dir': str(Path(__file__).resolve().parent / 'temporaryDatas' / 'unmatchDatas'),
    'save_normal_logs': True
}

DEBUG_CONFIG = {
    'enable_debug_logging': True,
    'log_kafka_messages': True,
    'log_elasticsearch_operations': True,
    'log_detection_details': True,
    'log_performance_metrics': True
}
