# Dify API 请求格式配置文件
# 用于灵活配置发送给 Dify 的数据格式

from typing import Dict, Any, Callable

# ========== 日志字段映射配置 ==========
# 定义从 Kafka 日志数据中提取字段的映射规则
LOG_FIELD_MAPPING = {
    # 字段名: 获取字段的函数或路径
    'log_id': lambda data: data.get('event_id', 'unknown'),
    'ip': lambda data: data.get('ip', 'unknown'),
    'path': lambda data: data.get('path', 'unknown'),
    'method': lambda data: data.get('method', 'unknown'),
    'status': lambda data: data.get('status', 'unknown'),
    'user_agent': lambda data: data.get('user_agent', 'unknown'),
    'matched_type': lambda data: data.get('detection_result', {}).get('attack_type', 'unknown'),
}

# ========== 查询提示词模板 ==========
# 用于生成发送给 Dify 的 query 字段
# 注意：提示词已在 Dify 中配置，这里只发送数据
QUERY_TEMPLATE = ""

# ========== Inputs 字段配置 ==========
# 定义哪些字段要放入 inputs 字典
INPUTS_FIELDS = [
    'log_id',
    'ip',
    'path',
    'method',
    'status',
    'user_agent',
    'matched_type',
]

# ========== 用户标识配置 ==========
USER_ID_TEMPLATE = 'log_{log_id}'

# ========== 响应模式配置 ==========
RESPONSE_MODE = 'blocking'  # 可选: 'blocking', 'streaming'

# ========== 自定义数据处理函数 ==========
def extract_log_fields(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    从原始日志数据中提取配置的字段
    
    Args:
        log_data: 从 Kafka 接收到的原始日志数据
        
    Returns:
        提取后的字段字典
    """
    result = {}
    
    # 处理嵌套的 log_entry 结构
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
    """
    根据日志字段构建查询提示词
    
    Args:
        log_fields: 提取后的日志字段
        
    Returns:
        格式化后的查询字符串
    """
    return ""

def build_inputs(log_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    构建 inputs 字典
    
    Args:
        log_fields: 提取后的日志字段
        
    Returns:
        inputs 字典
    """
    inputs = {}
    for field in INPUTS_FIELDS:
        if field in log_fields:
            inputs[field] = log_fields[field]
    return inputs

def build_user_id(log_fields: Dict[str, Any]) -> str:
    """
    构建用户标识
    
    Args:
        log_fields: 提取后的日志字段
        
    Returns:
        用户标识字符串
    """
    try:
        return USER_ID_TEMPLATE.format(**log_fields)
    except KeyError:
        return 'log_unknown'

def build_dify_payload(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    一站式构建完整的 Dify 请求 payload (Workflow 模式)
    
    Args:
        log_data: 从 Kafka 接收到的原始日志数据
        
    Returns:
        Dify 请求 payload 字典
    """
    import json
    
    # 提取字段
    log_fields = extract_log_fields(log_data)
    
    # 构建 payload - logDatas 放在 inputs 里面（Workflow API 要求）
    inputs_dict = build_inputs(log_fields)
    payload = {
        'inputs': {
            'logDatas': json.dumps(inputs_dict, ensure_ascii=False)
        },
        'user': build_user_id(log_fields)
    }
    
    return payload
