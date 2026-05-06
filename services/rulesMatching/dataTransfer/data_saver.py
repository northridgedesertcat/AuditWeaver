# 数据保存传输模块
import logging
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError, ConnectionError

logger = logging.getLogger('data_saver')

class DataSaver:
    """数据保存传输类，负责将检测结果保存到Elasticsearch"""
    
    def __init__(self, es_hosts=['http://localhost:9200'], output_index='nginx-log-enriched'):
        """初始化数据保存器"""
        self.es_hosts = es_hosts
        self.output_index = output_index
        self.es_client = None
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
    
    def enrich_log_with_detection(self, log_entry, detection_result):
        """为日志条目添加检测结果字段"""
        # 初始化规则匹配字段
        rule_match_field = {
            "rule_match": False,
            "rule_id": None,
            "attack_type": None,
            "confidence": 0.0,
            "severity": None,
            "matched_items": {}
        }
        
        # 如果有检测结果，更新字段
        if detection_result and 'detections' in detection_result and detection_result['detections']:
            # 获取置信度最高的检测结果
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
        
        # 添加检测字段到日志条目
        enriched_log = log_entry.copy()
        enriched_log['rule_match'] = rule_match_field
        
        return enriched_log
    
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
    
    def save_to_elasticsearch(self, enriched_log, doc_id=None):
        """将增强后的日志保存到Elasticsearch"""
        if not self.es_client:
            logger.error("Elasticsearch未连接")
            return None
        
        try:
            # 确保索引存在
            self._ensure_index_exists()
            
            # 保存文档
            response = self.es_client.index(
                index=self.output_index,
                id=doc_id,
                body=enriched_log
            )
            
            logger.info(f"日志已保存到Elasticsearch: {self.output_index}/{response.get('_id')}")
            return response.get('_id')
        except RequestError as e:
            logger.error(f"保存日志到Elasticsearch失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"保存日志到Elasticsearch异常: {str(e)}")
            return None
    
    def save_batch(self, log_entries, detection_results):
        """批量保存日志和检测结果"""
        saved_count = 0
        failed_count = 0
        
        for i, log_entry in enumerate(log_entries):
            # 获取对应的检测结果
            detection_result = detection_results['results'][i] if i < len(detection_results.get('results', [])) else None
            
            # 增强日志
            enriched_log = self.enrich_log_with_detection(log_entry, detection_result)
            
            # 保存到Elasticsearch
            doc_id = self.save_to_elasticsearch(enriched_log)
            
            if doc_id:
                saved_count += 1
            else:
                failed_count += 1
        
        logger.info(f"批量保存完成: 成功 {saved_count}, 失败 {failed_count}")
        return {'saved': saved_count, 'failed': failed_count}
    
    def _ensure_index_exists(self):
        """确保输出索引存在"""
        try:
            if not self.es_client.indices.exists(index=self.output_index):
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
                    }
                }
                self.es_client.indices.create(index=self.output_index, body=index_mapping)
                logger.info(f"创建输出索引: {self.output_index}")
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
    
    def update_original_log(self, original_index, doc_id, detection_result):
        """更新原始日志，添加检测结果字段"""
        if not self.es_client:
            logger.error("Elasticsearch未连接")
            return False
        
        try:
            # 生成检测字段
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
            
            # 更新文档
            self.es_client.update(
                index=original_index,
                id=doc_id,
                body={"doc": {"rule_match": rule_match_field}}
            )
            
            logger.info(f"已更新原始日志: {original_index}/{doc_id}")
            return True
        except Exception as e:
            logger.error(f"更新原始日志失败: {str(e)}")
            return False
    
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