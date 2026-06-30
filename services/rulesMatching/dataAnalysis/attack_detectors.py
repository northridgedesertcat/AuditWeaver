# 攻击检测器文件
from match_config import RULES_CONFIG, ATTACK_TYPES
from utils import match_patterns, match_keywords, calculate_confidence, format_detection_result

class AttackDetectors:
    """攻击检测器类"""
    
    @staticmethod
    def detect_sql_injection(log_entry):
        """检测SQL注入攻击"""
        config = RULES_CONFIG[ATTACK_TYPES['SQL_INJECTION']]
        features = AttackDetectors._extract_relevant_features(log_entry)
        text = ' '.join(features.values())
        
        matched_keywords = match_keywords(text, config['keywords'])
        matched_patterns = match_patterns(text, config['patterns'])
        
        matched_count = len(matched_keywords) + len(matched_patterns)
        total_patterns = len(config['keywords']) + len(config['patterns'])
        confidence = calculate_confidence(matched_count, total_patterns)
        
        if matched_count >= config['threshold']:
            matched_items = {
                'keywords': matched_keywords,
                'patterns': matched_patterns
            }
            return format_detection_result(log_entry, ATTACK_TYPES['SQL_INJECTION'], confidence, matched_items)
        
        return None
    
    @staticmethod
    def detect_xss(log_entry):
        """检测XSS攻击"""
        config = RULES_CONFIG[ATTACK_TYPES['XSS']]
        features = AttackDetectors._extract_relevant_features(log_entry)
        text = ' '.join(features.values())
        
        matched_keywords = match_keywords(text, config['keywords'])
        matched_patterns = match_patterns(text, config['patterns'])
        
        matched_count = len(matched_keywords) + len(matched_patterns)
        total_patterns = len(config['keywords']) + len(config['patterns'])
        confidence = calculate_confidence(matched_count, total_patterns)
        
        if matched_count >= config['threshold']:
            matched_items = {
                'keywords': matched_keywords,
                'patterns': matched_patterns
            }
            return format_detection_result(log_entry, ATTACK_TYPES['XSS'], confidence, matched_items)
        
        return None
    
    @staticmethod
    def detect_command_injection(log_entry):
        """检测命令注入攻击"""
        config = RULES_CONFIG[ATTACK_TYPES['COMMAND_INJECTION']]
        features = AttackDetectors._extract_relevant_features(log_entry)
        text = ' '.join(features.values())
        
        matched_keywords = match_keywords(text, config['keywords'])
        matched_patterns = match_patterns(text, config['patterns'])
        
        matched_count = len(matched_keywords) + len(matched_patterns)
        total_patterns = len(config['keywords']) + len(config['patterns'])
        confidence = calculate_confidence(matched_count, total_patterns)
        
        if matched_count >= config['threshold']:
            matched_items = {
                'keywords': matched_keywords,
                'patterns': matched_patterns
            }
            return format_detection_result(log_entry, ATTACK_TYPES['COMMAND_INJECTION'], confidence, matched_items)
        
        return None
    
    @staticmethod
    def detect_path_traversal(log_entry):
        """检测路径遍历攻击"""
        config = RULES_CONFIG[ATTACK_TYPES['PATH_TRAVERSAL']]
        features = AttackDetectors._extract_relevant_features(log_entry)
        text = ' '.join(features.values())
        
        matched_keywords = match_keywords(text, config['keywords'])
        matched_patterns = match_patterns(text, config['patterns'])
        
        matched_count = len(matched_keywords) + len(matched_patterns)
        total_patterns = len(config['keywords']) + len(config['patterns'])
        confidence = calculate_confidence(matched_count, total_patterns)
        
        if matched_count >= config['threshold']:
            matched_items = {
                'keywords': matched_keywords,
                'patterns': matched_patterns
            }
            return format_detection_result(log_entry, ATTACK_TYPES['PATH_TRAVERSAL'], confidence, matched_items)
        
        return None
    
    @staticmethod
    def detect_csrf(log_entry):
        """检测CSRF攻击"""
        config = RULES_CONFIG[ATTACK_TYPES['CSRF']]
        features = AttackDetectors._extract_relevant_features(log_entry)
        text = ' '.join(features.values())
        
        matched_keywords = match_keywords(text, config['keywords'])
        matched_patterns = match_patterns(text, config['patterns'])
        
        matched_count = len(matched_keywords) + len(matched_patterns)
        total_patterns = len(config['keywords']) + len(config['patterns'])
        confidence = calculate_confidence(matched_count, total_patterns)
        
        if matched_count >= config['threshold']:
            matched_items = {
                'keywords': matched_keywords,
                'patterns': matched_patterns
            }
            return format_detection_result(log_entry, ATTACK_TYPES['CSRF'], confidence, matched_items)
        
        return None

    @staticmethod
    def detect_sensitive_access(log_entry):
        """检测敏感访问"""
        config = RULES_CONFIG[ATTACK_TYPES['SENSITIVE_ACCESS']]
        features = AttackDetectors._extract_relevant_features(log_entry)
        path = features.get('path', '')
        
        matched_keywords = match_keywords(path, config['keywords'])
        matched_patterns = match_patterns(path, config['patterns'])
        
        matched_count = len(matched_keywords) + len(matched_patterns)
        total_patterns = len(config['keywords']) + len(config['patterns'])
        confidence = calculate_confidence(matched_count, total_patterns)
        
        if matched_count >= config['threshold']:
            matched_items = {
                'keywords': matched_keywords,
                'patterns': matched_patterns
            }
            return format_detection_result(log_entry, ATTACK_TYPES['SENSITIVE_ACCESS'], confidence, matched_items)
        
        return None
    
    @staticmethod
    def _extract_relevant_features(log_entry):
        """提取相关特征"""
        return {
            'path': log_entry.get('path', ''),
            'user_agent': log_entry.get('user_agent', ''),
            'referrer': log_entry.get('referrer', ''),
            'method': log_entry.get('method', '')
        }
    
    @staticmethod
    def detect_all(log_entry):
        """检测所有类型的攻击"""
        detectors = [
            AttackDetectors.detect_sql_injection,
            AttackDetectors.detect_xss,
            AttackDetectors.detect_command_injection,
            AttackDetectors.detect_path_traversal,
            AttackDetectors.detect_csrf,
            AttackDetectors.detect_sensitive_access
        ]
        
        results = []
        for detector in detectors:
            result = detector(log_entry)
            if result:
                results.append(result)
        
        return results
