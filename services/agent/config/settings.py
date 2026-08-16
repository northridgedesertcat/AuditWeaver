import sys
from pathlib import Path
import yaml

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from common.env import (
    KAFKA_BROKERS,
    KAFKA_TOPIC_ANALYSIS,
    DIFY_BASE_URL,
    DIFY_API_KEY,
    DIFY_TIMEOUT,
    LOG_LEVEL,
)

_yaml_dir = Path(__file__).parent / 'yaml'

with open(_yaml_dir / 'agent.yaml', 'r', encoding='utf-8') as f:
    _cfg = yaml.safe_load(f)

KAFKA_CONFIG = {
    'brokers': KAFKA_BROKERS,
    'input_topic': KAFKA_TOPIC_ANALYSIS,
    'group_id': _cfg['kafka']['group_id'],
    'auto_offset_reset': _cfg['kafka']['auto_offset_reset'],
    'consumer_timeout_ms': _cfg['kafka']['consumer_timeout_ms'],
    'max_poll_records': _cfg['kafka']['max_poll_records'],
    'output_topic': _cfg['kafka']['output_topic'],
    'dlq_topic': _cfg['kafka']['dlq_topic'],
}

DIFY_CONFIG = {
    'base_url': DIFY_BASE_URL,
    'api_key': DIFY_API_KEY,
    'endpoint': _cfg['dify']['endpoint'],
    'timeout': DIFY_TIMEOUT,
    'response_mode': _cfg['dify']['response_mode'],
}

LOG_CONFIG = {
    'level': LOG_LEVEL,
    'format': _cfg['logging']['format'],
    'file': _cfg['logging']['file'],
}

PROCESS_CONFIG = {
    'batch_size': _cfg['process']['batch_size'],
    'poll_interval_ms': _cfg['process']['poll_interval_ms'],
    'retry_times': _cfg['process']['retry_times'],
    'retry_delay': _cfg['process']['retry_delay'],
    'retry_max_delay': _cfg['process'].get('retry_max_delay', 10),
}

CIRCUIT_CONFIG = {
    'fail_max': _cfg['circuit_breaker']['fail_max'],
    'reset_timeout': _cfg['circuit_breaker']['reset_timeout'],
    'success_threshold': _cfg['circuit_breaker']['success_threshold'],
}
