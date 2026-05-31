# 数据保存传输模块
import os
import json
import logging
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError, ConnectionError

logger = logging.getLogger('data_saver')

class DataSaver:
    """数据保存传输类，负责将检测结果分别保存到Elasticsearch、Kafka和本地JSON文件"""
    
    def __init__(self, es_host=None, es_port=None, es_hosts=None, es_index=None, attack_index='matched_logs', 
                 source_index='nginx-log', normal_data_path=None, kafka_enabled=True, 
                 kafka_brokers='localhost:9092', kafka_topic='log.risk'):
        """初始化数据保存器"""
        # 支持新的参数格式 (es_host, es_port) 和旧格式 (es_hosts)
        if es_host and es_port:
            self.es_hosts = [f"http://{es_host}:{es_port}"]
        elif es_hosts:
            self.es_hosts = es_hosts
        else:
            self.es_hosts = ['http://localhost:19200']
        
        # 支持新的参数名 es_index 和旧参数名 attack_index
        self.attack_index = es_index or attack_index
        self.source_index = source_index
        # 使用相对路径，基于项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_normal_path = os.path.join(project_root, 'temporaryDatas', 'unmatchDatas')
        self.normal_data_path = normal_data_path or default_normal_path
        self.es_client = None
        self.kafka_producer = None
        self.kafka_enabled = kafka_enabled
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        self._ensure_normal_data_directory()
        self.connect()
    
    def connect(self):
        """连接到Elasticsearch和Kafka"""
        # 连接Elasticsearch
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
        
        # 连接Kafka
        if self.kafka_enabled:
            try:
                from .kafka_producer import KafkaProducerClient
                self.kafka_producer = KafkaProducerClient(
                    bootstrap_servers=self.kafka_brokers,
                    topic=self.kafka_topic
                )
                logger.info(f"成功连接到Kafka: {self.kafka_brokers}, topic: {self.kafka_topic}")
            except Exception as e:
                logger.error(f"Kafka连接错误: {str(e)}")
                self.kafka_producer = None
    
    def is_connected(self):
        """检查是否连接成功（至少一个存储后端可用）"""
        es_connected = self.es_client is not None
        kafka_connected = not self.kafka_enabled or self.kafka_producer is not None
        
        # 至少一个后端可用即视为连接成功
        return es_connected or kafka_connected
    
    def is_es_connected(self):
        """检查Elasticsearch是否连接成功"""
        return self.es_client is not None
    
    def is_kafka_connected(self):
        """检查Kafka是否连接成功"""
        return not self.kafka_enabled or self.kafka_producer is not None
    
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
            
            # 清理检测结果中的重复日志数据
            clean_detection_result = None
            if detection_result:
                clean_detection_result = {
                    'detections': detection_result.get('detections', []),
                    'total_detections': detection_result.get('total_detections', 0)
                }
            
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'log_entry': log_entry,
                'detection_result': clean_detection_result
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
    
    def _update_source_status(self, event_id, status):
        """更新源索引中文档的状态"""
        if not self.es_client:
            logger.error("Elasticsearch未连接")
            return False
        
        try:
            # 使用 event_id 查询源文档并更新状态
            query = {
                "query": {
                    "term": {
                        "event_id.keyword": event_id
                    }
                }
            }
            
            update_body = {
                "script": {
                    "source": """
                        ctx._source.pipeline = ctx._source.pipeline ?: [:];
                        ctx._source.pipeline.rule_matching = ctx._source.pipeline.rule_matching ?: [:];
                        ctx._source.pipeline.rule_matching.status = params.status;
                    """,
                    "params": {
                        "status": status
                    }
                }
            }
            
            response = self.es_client.update_by_query(
                index=self.source_index,
                body={**query, **update_body},
                refresh=True
            )
            
            if response.get('updated', 0) > 0:
                logger.debug(f"更新源索引状态成功: event_id={event_id}, status={status}")
                return True
            else:
                logger.debug(f"未找到匹配的源文档: event_id={event_id}")
                return False
        except Exception as e:
            logger.error(f"更新源索引状态失败: {str(e)}")
            return False
    
    def _enrich_log_with_detection(self, log_entry, detection_result):
        """为日志条目添加检测结果字段"""
        rule_match_field = {
            "is_matched": False,
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
                "is_matched": True,
                "rule_id": self._generate_rule_id(top_detection['attack_type']),
                "attack_type": top_detection['attack_type'],
                "confidence": top_detection['confidence'],
                "severity": top_detection.get('severity', 'low'),
                "matched_items": top_detection.get('matched_items', {})
            }
        
        enriched_log = log_entry.copy()
        enriched_log['rule_match'] = rule_match_field
        
        # 添加 ingestion_time 字段，记录写入 Elasticsearch 的时间
        enriched_log['ingestion_time'] = datetime.now().isoformat()
        
        # 设置 pipeline.rule_matching.status 为 completed（因为已经完成规则匹配）
        enriched_log['pipeline'] = {
            "rule_matching": {
                "status": "completed"
            },
            "agent_analysis": {
                "status": "pending"
            }
        }
        
        return enriched_log
    
    def _ensure_attack_index_exists(self):
        """确保攻击日志索引存在"""
        try:
            if not self.es_client.indices.exists(index=self.attack_index):
                index_mapping = {
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "@version": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "bytes": {"type": "long"},
                            "event": {
                                "properties": {
                                    "original": {
                                        "type": "text",
                                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                                    }
                                }
                            },
                            "event_id": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "http_version": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "ip": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "message": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "method": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "path": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "pipeline": {
                                "properties": {
                                    "rule_matching": {
                                        "properties": {
                                            "status": {
                                                "type": "text",
                                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                                            }
                                        }
                                    },
                                    "agent_analysis": {
                                        "properties": {
                                            "status": {
                                                "type": "text",
                                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                                            }
                                        }
                                    }
                                }
                            },
                            "referrer": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "rule_match": {
                                "properties": {
                                    "is_matched": {"type": "boolean"},
                                    "rule_id": {"type": "keyword"},
                                    "attack_type": {"type": "keyword"},
                                    "confidence": {"type": "float"},
                                    "severity": {"type": "keyword"},
                                    "matched_items": {"type": "object"}
                                }
                            },
                            "status": {"type": "long"},
                            "timestamp": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                            },
                            "user_agent": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
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
    
    def _verify_elasticsearch_write(self, doc_id):
        """验证数据是否成功写入Elasticsearch"""
        try:
            # 尝试获取刚写入的文档
            response = self.es_client.get(index=self.attack_index, id=doc_id)
            if response and response.get('_source'):
                logger.debug(f"验证成功: Elasticsearch已确认收到文档 {self.attack_index}/{doc_id}")
                return True
            else:
                logger.warning(f"验证失败: 无法获取文档 {self.attack_index}/{doc_id}")
                return False
        except Exception as e:
            logger.error(f"验证Elasticsearch写入失败: {str(e)}")
            return False
    
    def _send_to_kafka(self, log_entry, detection_result):
        """发送攻击日志到Kafka"""
        if not self.kafka_enabled or not self.kafka_producer:
            return False
        
        try:
            enriched_log = self._enrich_log_with_detection(log_entry, detection_result)
            
            kafka_message = {
                'timestamp': datetime.now().isoformat(),
                'log_entry': enriched_log,
                'detection_result': detection_result
            }
            
            # 使用event_id作为key，如果没有则使用ip
            key = log_entry.get('event_id') or log_entry.get('ip')
            
            success = self.kafka_producer.send_message(kafka_message, key=key)
            
            # 强制刷新确保消息发送
            if self.kafka_producer.producer:
                self.kafka_producer.producer.flush()
            
            if success:
                logger.info(f"攻击日志已发送到Kafka: topic={self.kafka_topic}, event_id={log_entry.get('event_id')}")
            return success
        except Exception as e:
            logger.error(f"发送攻击日志到Kafka失败: {str(e)}")
            return False
    
    def save_attack_log_to_elasticsearch(self, log_entry, detection_result):
        """保存攻击日志到Elasticsearch（带验证）"""
        if not self.es_client:
            logger.error("Elasticsearch未连接")
            return None
        
        try:
            self._ensure_attack_index_exists()
            
            enriched_log = self._enrich_log_with_detection(log_entry, detection_result)
            
            response = self.es_client.index(
                index=self.attack_index,
                body=enriched_log,
                refresh=True  # 确保数据立即刷新
            )
            
            doc_id = response.get('_id')
            
            # 验证写入是否成功
            if self._verify_elasticsearch_write(doc_id):
                logger.info(f"攻击日志已成功保存到Elasticsearch: {self.attack_index}/{doc_id}, event_id={log_entry.get('event_id')}")
                
                # 获取 event_id 并更新源索引状态
                event_id = log_entry.get('event_id')
                if event_id:
                    self._update_source_status(event_id, 'completed')
                
                return doc_id
            else:
                logger.error(f"攻击日志写入Elasticsearch失败（验证未通过）: event_id={log_entry.get('event_id')}")
                return None
                
        except Exception as e:
            logger.error(f"保存攻击日志到Elasticsearch失败: {str(e)}, event_id={log_entry.get('event_id')}")
            return None
    
    def save_attack_log_to_kafka(self, log_entry, detection_result):
        """发送攻击日志到Kafka"""
        return self._send_to_kafka(log_entry, detection_result)
    
    def save_normal_log_to_json(self, log_entry, detection_result=None):
        """保存正常日志到JSON文件"""
        # 更新源索引中正常日志的状态
        event_id = log_entry.get('event_id')
        if event_id and self.es_client:
            self._update_source_status(event_id, 'completed')
        
        return self._save_to_json(log_entry, detection_result)
    
    def process_and_save(self, log_entries, detection_results):
        """处理并保存所有日志"""
        attack_count = 0
        normal_count = 0
        attack_saved_es = 0
        attack_failed_es = 0
        attack_saved_kafka = 0
        attack_failed_kafka = 0
        normal_saved = 0
        normal_failed = 0
        
        for i, log_entry in enumerate(log_entries):
            detection_result = detection_results['results'][i] if i < len(detection_results.get('results', [])) else None
            
            is_attack = (detection_result and 
                        'detections' in detection_result and 
                        detection_result['detections'])
            
            if is_attack:
                attack_count += 1
                
                # 保存到Elasticsearch
                if self.is_es_connected():
                    doc_id = self.save_attack_log_to_elasticsearch(log_entry, detection_result)
                    if doc_id:
                        attack_saved_es += 1
                    else:
                        attack_failed_es += 1
                else:
                    attack_failed_es += 1
                    logger.warning("跳过保存到Elasticsearch: 未连接")
                
                # 发送到Kafka
                if self.is_kafka_connected():
                    success = self.save_attack_log_to_kafka(log_entry, detection_result)
                    if success:
                        attack_saved_kafka += 1
                    else:
                        attack_failed_kafka += 1
                else:
                    attack_failed_kafka += 1
                    logger.warning("跳过发送到Kafka: 未连接或已禁用")
            else:
                normal_count += 1
                filepath = self.save_normal_log_to_json(log_entry, detection_result)
                if filepath:
                    normal_saved += 1
                else:
                    normal_failed += 1
        
        result = {
            'attack_logs': {
                'total': attack_count, 
                'saved_es': attack_saved_es, 
                'failed_es': attack_failed_es,
                'saved_kafka': attack_saved_kafka,
                'failed_kafka': attack_failed_kafka
            },
            'normal_logs': {'total': normal_count, 'saved': normal_saved, 'failed': normal_failed}
        }
        
        logger.info(f"处理完成: 攻击日志 ES:{attack_saved_es}/{attack_count}, Kafka:{attack_saved_kafka}/{attack_count}, 正常日志 {normal_saved}/{normal_count}")
        return result
    
    def close(self):
        """关闭连接"""
        # 关闭Elasticsearch连接
        if self.es_client:
            try:
                self.es_client.close()
                logger.info("Elasticsearch连接已关闭")
            except Exception as e:
                logger.error(f"关闭Elasticsearch连接失败: {str(e)}")
            finally:
                self.es_client = None
        
        # 关闭Kafka生产者
        if self.kafka_producer:
            try:
                self.kafka_producer.close()
                logger.info("Kafka生产者已关闭")
            except Exception as e:
                logger.error(f"关闭Kafka生产者失败: {str(e)}")
            finally:
                self.kafka_producer = None