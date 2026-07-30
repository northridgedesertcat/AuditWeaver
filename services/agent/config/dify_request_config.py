# Dify API 请求格式配置
# 数据配置从 yaml/dify_request.yaml 加载，此文件保留函数逻辑

from typing import Dict, Any
from pathlib import Path
import yaml

_yaml_dir = Path(__file__).parent / 'yaml'

with open(_yaml_dir / 'dify_request.yaml', 'r', encoding='utf-8') as f:
    _cfg = yaml.safe_load(f)

# ========== 数据配置（从 YAML 加载） ==========
INPUTS_FIELDS = _cfg['inputs_fields']
USER_ID_TEMPLATE = _cfg['user_id_template']
RESPONSE_MODE = _cfg['response_mode']
QUERY_TEMPLATE = ""

# ========== 日志字段映射（lambda 函数无法序列化，保留在代码中） ==========
LOG_FIELD_MAPPING = {
    'log_id': lambda data: data.get('event_id', 'unknown'),
    'ip': lambda data: data.get('ip', 'unknown'),
    'path': lambda data: data.get('path', 'unknown'),
    'method': lambda data: data.get('method', 'unknown'),
    'status': lambda data: data.get('status', 'unknown'),
    'user_agent': lambda data: data.get('user_agent', 'unknown'),
    'matched_type': lambda data: data.get('detection_result', {}).get('attack_type', 'unknown'),
}

# ========== 数据处理函数 ==========
def extract_log_fields(log_data: Dict[str, Any]) -> Dict[str, Any]:
    result = {}

    actual_log = log_data
    if 'log_entry' in log_data:
        actual_log = log_data.get('log_entry', {})

    for field_name, extractor in LOG_FIELD_MAPPING.items():
        try:
            result[field_name] = extractor(actual_log)
        except Exception as e:
            result[field_name] = 'unknown'
            print(f"Warning: Failed to extract field '{field_name}': {e}")

    return result

def build_query(log_fields: Dict[str, Any]) -> str:
    return ""

def build_inputs(log_fields: Dict[str, Any]) -> Dict[str, Any]:
    inputs = {}
    for field in INPUTS_FIELDS:
        if field in log_fields:
            inputs[field] = log_fields[field]
    return inputs

def build_user_id(log_fields: Dict[str, Any]) -> str:
    try:
        return USER_ID_TEMPLATE.format(**log_fields)
    except KeyError:
        return 'log_unknown'

def build_dify_payload(log_data: Dict[str, Any]) -> Dict[str, Any]:
    import json

    log_fields = extract_log_fields(log_data)

    inputs_dict = build_inputs(log_fields)
    payload = {
        'inputs': {
            'logDatas': json.dumps(inputs_dict, ensure_ascii=False)
        },
        'user': build_user_id(log_fields)
    }

    return payload
