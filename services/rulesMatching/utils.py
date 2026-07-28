import re
import json
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.time_utils import epoch_millis_now
from match_config import DETECTION_CONFIG

logging.basicConfig(
    filename=DETECTION_CONFIG['log_file'],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def match_patterns(text, patterns):
    matched = []
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                matched.append(pattern)
        except re.error:
            continue
    return matched


def match_keywords(text, keywords):
    matched = []
    for keyword in keywords:
        if keyword.lower() in text.lower():
            matched.append(keyword)
    return matched


def format_detection_result(log_entry, attack_type, matched_items):
    return {
        'event_id': log_entry.get('event_id', ''),
        'attack_type': attack_type,
        'matched_rules': {
            'keywords': matched_items.get('keywords', []),
            'patterns': matched_items.get('patterns', [])
        },
        'detection_time': epoch_millis_now(),
        'is_attack': True
    }


def validate_log_entry(log_entry):
    if not isinstance(log_entry, dict):
        return False
    required_fields = ['ip', 'path', 'method', 'status']
    for field in required_fields:
        if field not in log_entry:
            return False
    return True


def aggregate_results(results):
    return results


def log_detection(result):
    logger = logging.getLogger('detection')
    logger.warning(f"检测到攻击: {result.get('attack_type')}, IP: {result.get('event_id')}")


def generate_alert_message(result):
    return f"[告警] 检测到{result.get('attack_type')}攻击"
