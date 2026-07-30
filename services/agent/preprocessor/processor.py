# 数据预处理器
# 集中管理所有数据转换逻辑：原始消息 → Dify payload → 响应解析 → ES 文档构建
# 适配规则引擎 v2 输出格式：log_context + detections + attack_type 扁平结构

from typing import Dict, Any
from pathlib import Path
import yaml
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.time_utils import epoch_millis_now, to_epoch_millis

# ========== 加载 YAML 配置 ==========
_yaml_dir = Path(__file__).parent.parent / 'config' / 'yaml'

with open(_yaml_dir / 'dify_request.yaml', 'r', encoding='utf-8') as f:
    _dify_cfg = yaml.safe_load(f)

with open(_yaml_dir / 'extraction_rules.yaml', 'r', encoding='utf-8') as f:
    _extract_cfg = yaml.safe_load(f)

INPUTS_FIELDS = _dify_cfg['inputs_fields']
USER_ID_TEMPLATE = _dify_cfg['user_id_template']
RESPONSE_MODE = _dify_cfg['response_mode']

_rules_raw = _extract_cfg['dify_extraction_rules']
DIFY_EXTRACTION_RULES = {
    field: (info['paths'], info['default'])
    for field, info in _rules_raw.items()
}

# ========== 日志字段映射（适配规则引擎 v2 输出） ==========
LOG_FIELD_MAPPING = {
    'log_id':       lambda data: data.get('event_id', 'unknown'),
    'ip':           lambda data: data.get('log_context', data).get('ip', 'unknown'),
    'path':         lambda data: data.get('log_context', data).get('path', 'unknown'),
    'method':       lambda data: data.get('log_context', data).get('method', 'unknown'),
    'status':       lambda data: data.get('log_context', data).get('status', 'unknown'),
    'user_agent':   lambda data: data.get('log_context', data).get('user_agent', 'unknown'),
    'matched_type': lambda data: data.get('attack_type', 'unknown'),
}

# ========== Dify 请求构建 ==========

def _extract_log_data(raw_message: Dict[str, Any]) -> Dict[str, Any]:
    if 'log_entry' in raw_message and isinstance(raw_message['log_entry'], dict):
        return raw_message['log_entry']
    return raw_message


def extract_log_fields(raw_message: Dict[str, Any]) -> Dict[str, Any]:
    log_data = _extract_log_data(raw_message)
    result = {}
    for field_name, extractor in LOG_FIELD_MAPPING.items():
        try:
            result[field_name] = extractor(log_data)
        except Exception:
            result[field_name] = 'unknown'
    return result


def build_dify_payload(raw_message: Dict[str, Any]) -> Dict[str, Any]:
    log_fields = extract_log_fields(raw_message)

    inputs_dict = {}
    for field in INPUTS_FIELDS:
        if field in log_fields:
            inputs_dict[field] = log_fields[field]

    user_id = 'log_unknown'
    try:
        user_id = USER_ID_TEMPLATE.format(**log_fields)
    except KeyError:
        pass

    return {
        'inputs': {
            'logDatas': json.dumps(inputs_dict, ensure_ascii=False)
        },
        'user': user_id
    }


# ========== Dify 响应解析 ==========

def extract_dify_fields(dify_response: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    structured_output = None

    if 'data' in dify_response and isinstance(dify_response['data'], dict):
        outputs = dify_response['data'].get('outputs', {})
        if isinstance(outputs, dict):
            structured_output = outputs.get('structured_output', outputs)

    if structured_output is None and 'outputs' in dify_response:
        outputs = dify_response['outputs']
        if isinstance(outputs, dict):
            structured_output = outputs.get('structured_output', outputs)

    if structured_output is None and 'result' in dify_response:
        structured_output = dify_response['result']

    if structured_output is None and 'answer' in dify_response:
        answer = dify_response['answer']
        if isinstance(answer, dict):
            structured_output = answer
        elif isinstance(answer, str):
            try:
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


# ========== ES 文档构建（适配规则引擎 v2 输出） ==========

def build_elastic_document(raw_message: Dict[str, Any], dify_response: Dict[str, Any]) -> Dict[str, Any]:
    log_data = _extract_log_data(raw_message)
    ctx = log_data.get('log_context', {}) or {}

    dify_fields = extract_dify_fields(dify_response)

    attack_type = log_data.get('attack_type', '') or \
                  log_data.get('detection_result', {}).get('attack_type', '')

    log_ts = ctx.get('timestamp') or \
             log_data.get('@timestamp') or \
             log_data.get('log_timestamp') or \
             log_data.get('timestamp')

    return {
        'event_id':   log_data.get('event_id', ''),
        'ip':         ctx.get('ip', log_data.get('ip', '')),
        'path':       ctx.get('path', log_data.get('path', '')),
        'method':     ctx.get('method', log_data.get('method', '')),
        'status':     ctx.get('status', log_data.get('status', 0)),
        'user_agent': ctx.get('user_agent', log_data.get('user_agent', '')),
        'detect_type': attack_type,

        'risk_level':     dify_fields.get('risk_level', 'unknown'),
        'risk_score':     dify_fields.get('risk_score', 0),
        'attack_type_ai': dify_fields.get('attack_type_ai', ''),
        'summary':        dify_fields.get('summary', ''),
        'reasoning':      dify_fields.get('reasoning', []),
        'recommendations': dify_fields.get('recommendations', []),

        'log_timestamp':      to_epoch_millis(log_ts),
        'analysis_timestamp': epoch_millis_now(),
        'ingestion_time':     to_epoch_millis(log_data.get('ingestion_time')) or epoch_millis_now(),

        'dify_response': dify_response,
        'original_log':  raw_message
    }
