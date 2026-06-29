# Elasticsearch 映射和数据结构配置文件
# 用于定义如何存储 Dify 返回的结构化结果到 Elasticsearch

from typing import Dict, Any, List, Optional
from datetime import datetime
import re

# ========== Elasticsearch 索引映射配置 ==========
# 定义 Elasticsearch 索引的字段映射
ELASTICSEARCH_MAPPING = {
    'mappings': {
        'properties': {
            # ========== 原始日志字段 ==========
            'event_id': {'type': 'keyword'},           # 日志事件ID
            'ip': {'type': 'ip'},                      # 客户端IP地址
            'path': {'type': 'keyword'},               # 请求路径
            'method': {'type': 'keyword'},             # HTTP方法
            'status': {'type': 'integer'},             # 响应状态码
            'user_agent': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},  # 用户代理
            
            # 规则匹配结果
            'attack_type': {'type': 'keyword'},        # 攻击类型
            'confidence': {'type': 'float'},           # 置信度
            'severity': {'type': 'keyword'},           # 严重程度
            
            # ========== Dify 结构化分析结果 ==========
            'risk_level': {'type': 'keyword'},         # 风险等级: high/medium/low/unknown
            'risk_score': {'type': 'integer'},         # 风险分数 0-100
            'attack_type_ai': {'type': 'keyword'},     # AI识别的攻击类型
            'summary': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},  # 事件摘要
            
            'reasoning': {                             # 推理理由列表
                'type': 'text',
                'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}
            },
            
            'recommendations': {                       # 建议措施列表
                'type': 'text',
                'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}
            },
            
            # ========== 时间戳字段（使用 epoch_millis 格式避免 text 映射问题） ==========
            'log_timestamp': {'type': 'date', 'format': 'epoch_millis'},
            'analysis_timestamp': {'type': 'date', 'format': 'epoch_millis'},
            'ingestion_time': {'type': 'date', 'format': 'epoch_millis'},
            
            # ========== 原始数据（用于调试，不参与搜索） ==========
            'dify_response': {'type': 'object', 'enabled': False},  # 完整Dify响应
            'original_log': {'type': 'object', 'enabled': False}    # 原始日志数据
        }
    },
    'settings': {
        'number_of_shards': 1,
        'number_of_replicas': 0,
        'analysis': {
            'analyzer': {
                'default': {
                    'type': 'standard'
                }
            }
        }
    }
}

# ========== Dify 响应字段提取规则 ==========
# 定义如何从 Dify 返回的结构化数据中提取字段
DIFY_EXTRACTION_RULES = {
    # 字段名: (提取路径列表, 默认值)
    'risk_level': (['risk_level', 'threat_level'], 'unknown'),
    'risk_score': (['risk_score', 'score'], 0),
    'attack_type_ai': (['attack_type', 'attack_category'], ''),
    'summary': (['summary', 'event_summary', 'analysis_summary'], ''),
    'reasoning': (['reasoning', 'analysis_reasoning'], []),
    'recommendations': (['recommendations', 'suggestions', 'mitigation_steps'], []),
}

def normalize_datetime(date_str: str) -> int:
    """
    将日期字符串转换为 epoch_millis 格式
    
    Args:
        date_str: 日期字符串，可以是 ISO8601 格式或其他格式
        
    Returns:
        epoch_millis 时间戳（整数）
    """
    if not date_str:
        return int(datetime.now().timestamp() * 1000)
    
    # 尝试匹配 ISO8601 格式: 2026-06-11T13:25:19.353700 或 2026-06-11T13:25:19Z
    # 特别处理带 Z 后缀的 UTC 时间
    iso8601_pattern = r'(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(\.\d+)?(Z)?'
    match = re.match(iso8601_pattern, date_str)
    
    if match:
        date_part = match.group(1)
        time_part = match.group(2)
        is_utc = match.group(4) == 'Z'
        
        try:
            if is_utc:
                # 如果是 UTC 时间
                from datetime import timezone
                utc_dt = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M:%S')
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                return int(utc_dt.timestamp() * 1000)
            else:
                dt = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M:%S')
                return int(dt.timestamp() * 1000)
        except:
            return int(datetime.now().timestamp() * 1000)
    
    # 尝试匹配 yyyy-MM-dd HH:mm:ss 格式
    standard_pattern = r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})'
    match = re.match(standard_pattern, date_str)
    
    if match:
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            return int(dt.timestamp() * 1000)
        except:
            return int(datetime.now().timestamp() * 1000)
    
    # 如果都不匹配，返回当前时间
    return int(datetime.now().timestamp() * 1000)

def extract_dify_fields(dify_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 Dify 响应中提取结构化字段
    
    Args:
        dify_response: Dify API 的完整响应
        
    Returns:
        提取后的字段字典
    """
    result = {}
    
    # 尝试从多个可能的位置获取结构化输出
    structured_output = None
    
    # 优先级 1: Workflow 模式 - data.outputs.structured_output
    if 'data' in dify_response and isinstance(dify_response['data'], dict):
        if 'outputs' in dify_response['data'] and isinstance(dify_response['data']['outputs'], dict):
            # 先检查是否有 structured_output 子字段
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
    
    # 优先级 4: answer 字段（可能是 JSON 字符串或字典）
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
    
    # 如果还是没有找到结构化输出
    if structured_output is None:
        structured_output = {}
    
    # 根据提取规则提取字段
    for field_name, (paths, default_value) in DIFY_EXTRACTION_RULES.items():
        value = default_value
        for path in paths:
            if path in structured_output:
                value = structured_output[path]
                break
        result[field_name] = value
    
    return result

def to_epoch_millis(ts):
    """将时间戳转换为 epoch_millis 格式"""
    if ts is None:
        return int(datetime.now().timestamp() * 1000)
    if isinstance(ts, (int, float)):
        # 如果已经是数字（秒或毫秒），转换为毫秒
        if ts > 1e12:  # 已经是毫秒
            return int(ts)
        else:  # 是秒
            return int(ts * 1000)
    if isinstance(ts, str):
        try:
            # 尝试解析 ISO 格式
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except:
            try:
                # 尝试解析标准格式
                dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                return int(dt.timestamp() * 1000)
            except:
                return int(datetime.now().timestamp() * 1000)
    return int(datetime.now().timestamp() * 1000)

def build_elastic_document(log_data: Dict[str, Any], dify_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    构建完整的 Elasticsearch 文档
    
    Args:
        log_data: 原始日志数据（可能嵌套在 log_entry 中）
        dify_response: Dify API 响应
        
    Returns:
        完整的 Elasticsearch 文档（扁平结构，便于 Kibana 查询）
    """
    # 处理嵌套的 log_entry 结构
    actual_log = log_data
    if 'log_entry' in log_data and isinstance(log_data['log_entry'], dict):
        actual_log = log_data['log_entry']
    
    # 提取 Dify 结构化字段
    dify_fields = extract_dify_fields(dify_response)
    
    # 获取规则匹配信息
    rule_match = actual_log.get('rule_match', {})
    
    # 优先从 @timestamp 获取，其次是 timestamp
    log_ts = actual_log.get('@timestamp') or actual_log.get('timestamp')
    
    # 构建扁平文档结构
    doc = {
        # 原始日志字段
        'event_id': actual_log.get('event_id', ''),
        'ip': actual_log.get('ip', ''),
        'path': actual_log.get('path', ''),
        'method': actual_log.get('method', ''),
        'status': actual_log.get('status', 0),
        'user_agent': actual_log.get('user_agent', ''),
        'attack_type': rule_match.get('matched_type', ''),
        'confidence': rule_match.get('confidence', 0.0),
        'severity': rule_match.get('severity', ''),
        
        # Dify 分析结果（扁平结构）
        'risk_level': dify_fields.get('risk_level', 'unknown'),
        'risk_score': dify_fields.get('risk_score', 0),
        'attack_type_ai': dify_fields.get('attack_type_ai', ''),
        'summary': dify_fields.get('summary', ''),
        'reasoning': dify_fields.get('reasoning', []),
        'recommendations': dify_fields.get('recommendations', []),
        
        # 时间戳（使用 epoch_millis 格式以确保正确的 date 类型映射）
        'log_timestamp': to_epoch_millis(log_ts),
        'analysis_timestamp': int(datetime.utcnow().timestamp() * 1000),
        'ingestion_time': to_epoch_millis(actual_log.get('ingestion_time')),
        
        # 原始数据（用于调试，不参与搜索）
        'dify_response': dify_response,
        'original_log': log_data
    }
    
    return doc
