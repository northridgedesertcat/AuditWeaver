# Elasticsearch 映射和数据结构配置
# ELASTICSEARCH_MAPPING 和 DIFY_EXTRACTION_RULES 从 yaml/elastic_mapping.yaml 加载
# 此文件保留数据处理函数逻辑

from typing import Dict, Any
from pathlib import Path
import yaml

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from common.time_utils import epoch_millis_now, to_epoch_millis

_yaml_dir = Path(__file__).parent / 'yaml'

with open(_yaml_dir / 'elastic_mapping.yaml', 'r', encoding='utf-8') as f:
    _cfg = yaml.safe_load(f)

# ========== 数据配置（从 YAML 加载） ==========
ELASTICSEARCH_MAPPING = _cfg['elasticsearch_mapping']

_rules_raw = _cfg['dify_extraction_rules']
DIFY_EXTRACTION_RULES = {
    field: (info['paths'], info['default'])
    for field, info in _rules_raw.items()
}

# ========== 数据处理函数 ==========
def normalize_datetime(date_str: str) -> int:
    return to_epoch_millis(date_str)

def extract_dify_fields(dify_response: Dict[str, Any]) -> Dict[str, Any]:
    result = {}

    structured_output = None

    # 优先级 1: Workflow 模式 - data.outputs.structured_output
    if 'data' in dify_response and isinstance(dify_response['data'], dict):
        if 'outputs' in dify_response['data'] and isinstance(dify_response['data']['outputs'], dict):
            if 'structured_output' in dify_response['data']['outputs'] and isinstance(dify_response['data']['outputs']['structured_output'], dict):
                structured_output = dify_response['data']['outputs']['structured_output']
            else:
                structured_output = dify_response['data']['outputs']

    # 优先级 2: 直接 outputs.structured_output 字段
    if structured_output is None and 'outputs' in dify_response and isinstance(dify_response['outputs'], dict):
        if 'structured_output' in dify_response['outputs'] and isinstance(dify_response['outputs']['structured_output'], dict):
            structured_output = dify_response['outputs']['structured_output']
        else:
            structured_output = dify_response['outputs']

    # 优先级 3: result 字段
    if structured_output is None and 'result' in dify_response:
        structured_output = dify_response['result']

    # 优先级 4: answer 字段
    if structured_output is None and 'answer' in dify_response:
        answer = dify_response['answer']
        if isinstance(answer, dict):
            structured_output = answer
        elif isinstance(answer, str):
            try:
                import json
                structured_output = json.loads(answer)
            except:
                pass

    if structured_output is None:
        structured_output = {}

    for field_name, (paths, default_value) in DIFY_EXTRACTION_RULES.items():
        value = default_value
        for path in paths:
            if path in structured_output:
                value = structured_output[path]
                break
        result[field_name] = value

    return result


def build_elastic_document(log_data: Dict[str, Any], dify_response: Dict[str, Any]) -> Dict[str, Any]:
    # 处理嵌套的 log_entry 结构
    actual_log = log_data
    if 'log_entry' in log_data and isinstance(log_data['log_entry'], dict):
        actual_log = log_data['log_entry']

    dify_fields = extract_dify_fields(dify_response)

    rule_match = actual_log.get('detection_result', actual_log.get('rule_match', {}))

    log_ts = actual_log.get('@timestamp') or actual_log.get('log_timestamp') or actual_log.get('timestamp')

    doc = {
        'event_id': actual_log.get('event_id', ''),
        'ip': actual_log.get('ip', ''),
        'path': actual_log.get('path', ''),
        'method': actual_log.get('method', ''),
        'status': actual_log.get('status', 0),
        'user_agent': actual_log.get('user_agent', ''),
        'attack_type': rule_match.get('attack_type', rule_match.get('matched_type', '')),

        'risk_level': dify_fields.get('risk_level', 'unknown'),
        'risk_score': dify_fields.get('risk_score', 0),
        'attack_type_ai': dify_fields.get('attack_type_ai', ''),
        'summary': dify_fields.get('summary', ''),
        'reasoning': dify_fields.get('reasoning', []),
        'recommendations': dify_fields.get('recommendations', []),

        'log_timestamp': to_epoch_millis(log_ts),
        'analysis_timestamp': epoch_millis_now(),
        'ingestion_time': to_epoch_millis(actual_log.get('ingestion_time')) or epoch_millis_now(),

        'dify_response': dify_response,
        'original_log': log_data
    }

    return doc
