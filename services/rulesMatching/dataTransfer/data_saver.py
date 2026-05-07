# 数据保存传输模块
import os
import json
import logging
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError, ConnectionError

logger = logging.getLogger('data_saver')

class DataSaver:
    """数据保存传输类，负责将检测结果分别保存到Elasticsearch和本地JSON文件"""
    
    def __init__(self, es_hosts=['http://localhost:9200'], attack_index='attack_logs', normal_data_path=None):
        """初始化数据保存器"""
        self.es_hosts = es_hosts
        self.attack_index = attack_index
        # 使用相对路径，基于项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_normal_path = os.path.join(project_root, 'temporaryDatas', 'unmatchDatas')
        self.normal_data_path = normal_data_path or default_normal_path
        self.es_client = None
        self._ensure_normal_data_directory()
        self.connect()
    
    def connect(self):
        """连接到Elasticsearch"""
        try:
            self.es_client = Elasticsearch(
                self.es_hosts,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            if self.es_client.ping():
                logger.info(f"成功连接到Elasticsearch: {self.es_hosts}")
            else:
                logger.error(f"无法连接到Elasticsearch: {self.es_hosts}")
                self.es_client = None
        except ConnectionError as e:
            logger.error(f"Elasticsearch连接错误: {str(e)}")
            self.es_client = None
        except Exception as e:
            logger.error(f"Elasticsearch初始化错误: {str(e)}")
            self.es_client = None
    
    def is_connected(self):
        """检查是否连接成功"""
        return self.es_client is not None
    
    def _ensure_normal_data_directory(self):
        """确保正常数据存储目录存在"""
        try:
            if not os.path.exists(self.normal_data_path):
                os.makedirs(self.normal_data_path)
                logger.info(f"创建正常数据存储目录: {self.normal_data_path}")
        except Exception as e:
            logger.error(f"创建目录失败: {str(e)}")
    
    def _get_date_folder(self):
        """获取当前日期和小时的文件夹路径 (格式: YYYY-MM-DD/HH)"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        hour_str = datetime.now().strftime('%H')
        date_folder = os.path.join(self.normal_data_path, date_str, hour_str)
        if not os.path.exists(date_folder):
            os.makedirs(date_folder)
            logger.info(f"创建日期小时文件夹: {date_folder}")
        return date_folder
    
    def _save_to_json(self, log_entry, detection_result=None):
        """保存正常日志到JSON文件"""
        try:
            date_folder = self._get_date_folder()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"normal_log_{timestamp}.json"
            filepath = os.path.join(date_folder, filename)
            
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'log_entry': log_entry,
                'detection_result': detection_result
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"正常日志已保存到JSON: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存JSON文件失败: {str(e)}")
            return None
    
    def _generate_rule_id(self, attack_type):
        """生成规则ID"""
        rule_id_mapping = {
            'sql_injection': 'SQL_INJECTION_001',
            'xss': 'XSS_001',
            'command_injection': 'COMMAND_INJECTION_001',
            'path_traversal': 'PATH_TRAVERSAL_001',
            'csrf': 'CSRF_001',
            'bot': 'BOT_001',
            'sensitive_access': 'SENSITIVE_ACCESS_001'
        }
        return rule_id_mapping.get(attack_type, f"CUSTOM_{attack_type.upper()}_001")
    
    def _enrich_log_with_detection(self, log_entry, detection_result):
        """为日志条目添加检测结果字段"""
        rule_match_field = {
            "rule_match": False,
            "rule_id": None,
            "attack_type": None,
            "confidence": 0.0,
            "severity": None,
            "matched_items": {}
        }
        
        if detection_result and 'detections' in detection_result and detection_result['detections']:
            detections = detection_result['detections']
            detections.sort(key=lambda x: x['confidence'], reverse=True)
            top_detection = detections[0]
            
            rule_match_field = {
                "rule_match": True,
                "rule_id": self._generate_rule_id(top_detection['attack_type']),
                "attack_type": top_detection['attack_type'],
                "confidence": top_detection['confidence'],
                "severity": top_detection.get('severity', 'low'),
                "matched_items": top_detection.get('matched_items', {})
            }
        
        enriched_log = log_entry.copy()
        enriched_log['rule_match'] = rule_match_field
        return enriched_log
    
    def _ensure_attack_index_exists(self):
        """确保攻击日志索引存在"""
        try:
            if not self.es_client.indices.exists(index=self.attack_index):
                index_mapping = {
                    "mappings": {
                        "properties": {
                            "ip": {"type": "ip"},
                            "timestamp": {"type": "text"},
                            "@timestamp": {"type": "date"},
                            "method": {"type": "keyword"},
                            "path": {"type": "text"},
                            "http_version": {"type": "keyword"},
                            "status": {"type": "integer"},
                            "bytes": {"type": "integer"},
                            "referrer": {"type": "text"},
                            "user_agent": {"type": "text"},
                            "rule_match": {
                                "properties": {
                                    "rule_match": {"type": "boolean"},
                                    "rule_id": {"type": "keyword"},
                                    "attack_type": {"type": "keyword"},
                                    "confidence": {"type": "float"},
                                    "severity": {"type": "keyword"},
                                    "matched_items": {"type": "object"}
                                }
                            }
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                }
                self.es_client.indices.create(index=self.attack_index, body=index_mapping)
                logger.info(f"创建攻击日志索引: {self.attack_index}")
        except Exception as e:
            logger.error(f"创建攻击日志索引失败: {str(e)}")
    
    def save_attack_log_to_elasticsearch(self, log_entry, detection_result):
        """保存攻击日志到Elasticsearch"""
        if not self.es_client:
            logger.error("Elasticsearch未连接")
            return None
        
        try:
            self._ensure_attack_index_exists()
            
            enriched_log = self._enrich_log_with_detection(log_entry, detection_result)
            
            response = self.es_client.index(
                index=self.attack_index,
                body=enriched_log
            )
            
            logger.info(f"攻击日志已保存到Elasticsearch: {self.attack_index}/{response.get('_id')}")
            return response.get('_id')
        except Exception as e:
            logger.error(f"保存攻击日志到Elasticsearch失败: {str(e)}")
            return None
    
    def save_normal_log_to_json(self, log_entry, detection_result=None):
        """保存正常日志到JSON文件"""
        return self._save_to_json(log_entry, detection_result)
    
    def process_and_save(self, log_entries, detection_results):
        """处理并保存所有日志"""
        attack_count = 0
        normal_count = 0
        attack_saved = 0
        attack_failed = 0
        normal_saved = 0
        normal_failed = 0
        
        for i, log_entry in enumerate(log_entries):
            detection_result = detection_results['results'][i] if i < len(detection_results.get('results', [])) else None
            
            is_attack = (detection_result and 
                        'detections' in detection_result and 
                        detection_result['detections'])
            
            if is_attack:
                attack_count += 1
                doc_id = self.save_attack_log_to_elasticsearch(log_entry, detection_result)
                if doc_id:
                    attack_saved += 1
                else:
                    attack_failed += 1
            else:
                normal_count += 1
                filepath = self.save_normal_log_to_json(log_entry, detection_result)
                if filepath:
                    normal_saved += 1
                else:
                    normal_failed += 1
        
        result = {
            'attack_logs': {'total': attack_count, 'saved': attack_saved, 'failed': attack_failed},
            'normal_logs': {'total': normal_count, 'saved': normal_saved, 'failed': normal_failed}
        }
        
        logger.info(f"处理完成: 攻击日志 {attack_saved}/{attack_count}, 正常日志 {normal_saved}/{normal_count}")
        return result
    
    def close(self):
        """关闭连接"""
        if self.es_client:
            try:
                self.es_client.close()
                logger.info("Elasticsearch连接已关闭")
            except Exception as e:
                logger.error(f"关闭连接失败: {str(e)}")
            finally:
                self.es_client = None