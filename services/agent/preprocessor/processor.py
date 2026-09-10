# 数据预处理器
# 集中管理所有数据转换逻辑：原始消息 → Dify payload → 响应解析 → MySQL 报告记录构建
# 适配规则引擎 v2 输出格式：log_context + detections + attack_type 扁平结构

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Any, Optional
from pathlib import Path
import yaml
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.time_utils import now_utc, utc_from_epoch_millis

if TYPE_CHECKING:
    # 仅类型标注用；运行时导入会与 dify/analysis 形成循环导入
    from analysis.base import AnalysisResult

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


# ========== MySQL 报告记录构建（适配规则引擎 v2 输出） ==========

def _to_utc_datetime(value: Any) -> Optional[datetime]:
    """epoch 毫秒/秒、ISO 字符串或 datetime → tz-aware UTC datetime；无效值返回 None。"""
    if value is None or value == '' or value == 0:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        ms = value if value > 1e12 else value * 1000
        return utc_from_epoch_millis(int(ms))

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            v = int(s)
            ms = v if v > 1e12 else v * 1000
            return utc_from_epoch_millis(ms)
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return None


def _normalize_status(value: Any) -> Optional[int]:
    """HTTP 状态码：非数字/0/负数 → None（落库 NULL）。"""
    try:
        status = int(value)
    except (TypeError, ValueError):
        return None
    return status if status > 0 else None


def _safe_int(value: Any, default: int = 0) -> int:
    """风险评分等整数：非数字 → default（LLM 偶发返回字符串/空值的防御）。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_report_record(raw_message: Dict[str, Any], result: AnalysisResult) -> Dict[str, Any]:
    """组装 MySQL analysis_report 行记录（替代原 ES 文档构建）。

    归一规则：
    - risk_level 写入前 .lower()（critical/high/medium/low/normal/unknown）；
    - status 缺失/0 → None（NULL）；ip 空/unknown → None；
    - 三个时间字段由 epoch 毫秒转为 UTC datetime（DATETIME(6) 按 UTC 约定存取）；
    - reasoning/recommendations 保持字符串数组；raw_response/original_log 原样 JSON。
    """
    log_data = _extract_log_data(raw_message)
    ctx = log_data.get('log_context', {}) or {}

    attack_type = log_data.get('attack_type', '') or \
                  log_data.get('detection_result', {}).get('attack_type', '')

    log_ts = ctx.get('timestamp') or \
             log_data.get('@timestamp') or \
             log_data.get('log_timestamp') or \
             log_data.get('timestamp')

    ip = ctx.get('ip', log_data.get('ip', '')) or ''

    return {
        'event_id':   log_data.get('event_id', ''),
        'ip':         ip if ip and ip != 'unknown' else None,
        'path':       ctx.get('path', log_data.get('path', '')) or '',
        'method':     ctx.get('method', log_data.get('method', '')) or '',
        'status':     _normalize_status(ctx.get('status', log_data.get('status'))),
        'user_agent': ctx.get('user_agent', log_data.get('user_agent', '')) or '',
        'detect_type': attack_type or '',

        'risk_level':      (result.risk_level or 'unknown').lower() or 'unknown',
        'risk_score':      _safe_int(result.risk_score),
        'attack_type_ai':  result.attack_type_ai or '',
        'summary':         result.summary or '',
        'reasoning':       result.reasoning if isinstance(result.reasoning, list) else [],
        'recommendations': result.recommendations if isinstance(result.recommendations, list) else [],

        'log_timestamp':      _to_utc_datetime(log_ts),
        'analysis_timestamp': now_utc(),
        'ingestion_time':     _to_utc_datetime(log_data.get('ingestion_time')) or now_utc(),

        'raw_response': result.raw_response,
        'original_log': raw_message,
    }
