# 规则引擎核心文件
from .attack_detectors import AttackDetectors
from utils import validate_log_entry, aggregate_results, filter_results, log_detection, generate_alert_message
from match_config import DETECTION_CONFIG

class RuleEngine:
    """规则引擎类"""
    
    def __init__(self):
        """初始化规则引擎"""
        self.detectors = AttackDetectors()
        self.min_confidence = DETECTION_CONFIG['min_confidence']
        self.max_matches = DETECTION_CONFIG['max_matches']
    
    def detect(self, log_entry):
        """检测单条日志"""
        if not validate_log_entry(log_entry):
            return {
                'error': 'Invalid log entry format',
                'log_entry': log_entry
            }
        
        results = self.detectors.detect_all(log_entry)
        filtered_results = filter_results(results, self.min_confidence)
        aggregated_results = aggregate_results(filtered_results)
        
        if len(aggregated_results) > self.max_matches:
            aggregated_results.sort(key=lambda x: x['confidence'], reverse=True)
            aggregated_results = aggregated_results[:self.max_matches]
        
        for result in aggregated_results:
            log_detection(result)
            alert_message = generate_alert_message(result)
            print(alert_message)
        
        return {
            'log_entry': log_entry,
            'detections': aggregated_results,
            'total_detections': len(aggregated_results)
        }
    
    def detect_batch(self, log_entries):
        """批量检测日志"""
        results = []
        total_detections = 0
        
        for log_entry in log_entries:
            result = self.detect(log_entry)
            results.append(result)
            if 'detections' in result:
                total_detections += len(result['detections'])
        
        return {
            'results': results,
            'total_logs': len(log_entries),
            'total_detections': total_detections
        }
    
    def get_detection_summary(self, results):
        """获取检测摘要"""
        summary = {
            'total_logs': len(results),
            'total_detections': 0,
            'matched_types': {}
        }
        
        for result in results:
            if 'detections' in result:
                summary['total_detections'] += len(result['detections'])
                for detection in result['detections']:
                    matched_type = detection['matched_type']
                    if matched_type not in summary['matched_types']:
                        summary['matched_types'][matched_type] = 0
                    summary['matched_types'][matched_type] += 1
        
        return summary
    
    def validate_config(self):
        """验证配置"""
        try:
            test_log = {
                'ip': '127.0.0.1',
                'timestamp': '16/Apr/2026:10:00:00 +0000',
                'method': 'GET',
                'path': '/test',
                'http_version': 'HTTP/1.1',
                'status': 200,
                'bytes': 100,
                'referrer': '-',
                'user_agent': 'Mozilla/5.0'
            }
            self.detect(test_log)
            return True
        except Exception as e:
            print(f"配置验证失败: {str(e)}")
            return False
    
    def update_config(self, config):
        """更新配置"""
        if 'min_confidence' in config:
            self.min_confidence = config['min_confidence']
        if 'max_matches' in config:
            self.max_matches = config['max_matches']
        return True
