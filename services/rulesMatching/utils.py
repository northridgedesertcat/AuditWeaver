# 工具函数文件
import re
import json
import logging
from datetime import datetime
from match_config import DETECTION_CONFIG

# 配置日志
logging.basicConfig(
    filename=DETECTION_CONFIG['log_file'],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 日志记录器
logger = logging.getLogger('rules_matching')

def log_detection(result):
    """记录检测结果到日志"""
    try:
        logger.info(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        logger.error(f"记录检测结果失败: {str(e)}")

def extract_features(log_entry):
    """从日志条目中提取特征"""
    features = {
        'ip': log_entry.get('ip', ''),
        'method': log_entry.get('method', '').lower(),
        'path': log_entry.get('path', ''),
        'user_agent': log_entry.get('user_agent', '').lower(),
        'referrer': log_entry.get('referrer', ''),
        'status': log_entry.get('status', 0),
        'bytes': log_entry.get('bytes', 0)
    }
    return features

def match_patterns(text, patterns):
    """匹配正则表达式模式"""
    matches = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(pattern)
    return matches

def match_keywords(text, keywords):
    """匹配关键词"""
    matched_keywords = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched_keywords.append(keyword)
    return matched_keywords

def calculate_confidence(matched_count, total_patterns):
    """计算置信度"""
    if total_patterns == 0:
        return 0.0
    return min(1.0, matched_count / total_patterns)

def format_detection_result(log_entry, attack_type, confidence, matched_items):
    """格式化检测结果"""
    result = {
        'timestamp': datetime.now().isoformat(),
        'original_log': log_entry,
        'attack_type': attack_type,
        'confidence': round(confidence, 2),
        'matched_items': matched_items,
        'severity': get_severity(confidence)
    }
    return result

def get_severity(confidence):
    """根据置信度获取严重程度"""
    if confidence >= 0.9:
        return 'critical'
    elif confidence >= 0.7:
        return 'high'
    elif confidence >= 0.5:
        return 'medium'
    else:
        return 'low'

def validate_log_entry(log_entry):
    """验证日志条目格式"""
    required_fields = ['ip', 'method', 'path', 'status']
    
    for field in required_fields:
        if field not in log_entry:
            return False
    
    # 检查时间戳字段（支持 @timestamp 和 timestamp 两种格式）
    if 'timestamp' not in log_entry and '@timestamp' not in log_entry:
        return False
    
    return True

def normalize_path(path):
    """标准化路径"""
    # 移除查询参数
    if '?' in path:
        path = path.split('?')[0]
    # 移除末尾斜杠
    if path.endswith('/'):
        path = path[:-1]
    return path

def parse_timestamp(timestamp):
    """解析时间戳"""
    try:
        # 尝试解析nginx日志格式的时间戳
        return datetime.strptime(timestamp, '%d/%b/%Y:%H:%M:%S %z')
    except Exception:
        try:
            # 尝试解析ISO格式的时间戳
            return datetime.fromisoformat(timestamp)
        except Exception:
            return None

def aggregate_results(results):
    """聚合检测结果"""
    aggregated = {}
    for result in results:
        attack_type = result['attack_type']
        if attack_type not in aggregated or result['confidence'] > aggregated[attack_type]['confidence']:
            aggregated[attack_type] = result
    return list(aggregated.values())

def filter_results(results, min_confidence):
    """过滤低置信度结果"""
    return [result for result in results if result['confidence'] >= min_confidence]

def generate_alert_message(result):
    """生成告警消息"""
    attack_type = result['attack_type']
    confidence = result['confidence']
    ip = result['original_log'].get('ip', 'Unknown')
    path = result['original_log'].get('path', 'Unknown')
    
    message = f"[ALERT] {attack_type.upper()} detected from {ip} with {confidence*100:.1f}% confidence. Path: {path}"
    return message
