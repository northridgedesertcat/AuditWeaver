import os
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from common.time_utils import epoch_millis_now, format_for_filename, format_for_directory
from common.env import ES_HOST, ES_PORT, KAFKA_BROKERS, KAFKA_TOPIC_RISK, ES_INDEX_MATCHED_LOGS
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError, ConnectionError

logger = logging.getLogger('data_saver')

class DataSaver:
    def __init__(self, es_host=ES_HOST, es_port=ES_PORT, es_index=ES_INDEX_MATCHED_LOGS,
                 kafka_enabled=True, kafka_brokers=KAFKA_BROKERS, kafka_topic=KAFKA_TOPIC_RISK):
        self.es_host = es_host
        self.es_port = es_port
        self.es_index = es_index
        self.es_client = None
        self.kafka_enabled = kafka_enabled
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic
        self.kafka_producer = None
        self._connected = False

    def _connect(self):
        try:
            self.es_client = Elasticsearch(
                [{'host': self.es_host, 'port': self.es_port}],
                timeout=30,
                max_retries=3
            )
            
            if self.es_client.ping():
                logger.info(f"成功连接到Elasticsearch: {self.es_host}:{self.es_port}")
            else:
                logger.error(f"无法连接到Elasticsearch: {self.es_host}:{self.es_port}")
                self.es_client = None
        except Exception as e:
            logger.error(f"Elasticsearch连接错误: {str(e)}")
            self.es_client = None
        
        if self.kafka_enabled:
            try:
                from kafka import KafkaProducer
                self.kafka_producer = KafkaProducer(
                    bootstrap_servers=self.kafka_brokers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                logger.info(f"成功连接到Kafka: {self.kafka_brokers}")
            except Exception as e:
                logger.error(f"Kafka连接错误: {str(e)}")
                self.kafka_producer = None
                self.kafka_enabled = False

    def is_es_connected(self):
        if not self._connected:
            self._connect()
        return self.es_client is not None and self.es_client.ping()

    def save_attack_log_to_elasticsearch(self, log_entry, detection_result):
        if not self.es_client:
            self._connect()
            if not self.es_client:
                logger.error("Elasticsearch未连接")
                return None
        
        doc_id = log_entry.get('event_id', str(epoch_millis_now()))
        
        document = {
            'event_id': log_entry.get('event_id', doc_id),
            'ip': log_entry.get('ip', 'unknown'),
            'path': log_entry.get('path', 'unknown'),
            'method': log_entry.get('method', 'unknown'),
            'status': log_entry.get('status', 0),
            'user_agent': log_entry.get('user_agent', 'unknown'),
            'log_timestamp': log_entry.get('log_timestamp', epoch_millis_now()),
            'ingestion_time': epoch_millis_now(),
            'detection_result': detection_result,
            'matched_rules': detection_result.get('matched_rules', {})
        }
        
        try:
            response = self.es_client.index(
                index=self.es_index,
                id=doc_id,
                body=document,
                refresh=True
            )
            
            if self._verify_elasticsearch_write(doc_id):
                logger.info(f"攻击日志已成功保存到Elasticsearch: {self.es_index}/{doc_id}, event_id={log_entry.get('event_id')}")
                return doc_id
            else:
                logger.error(f"攻击日志写入Elasticsearch失败（验证未通过）: event_id={log_entry.get('event_id')}")
                return None
                
        except Exception as e:
            logger.error(f"保存攻击日志到Elasticsearch失败: {str(e)}, event_id={log_entry.get('event_id')}")
            return None

    def _verify_elasticsearch_write(self, doc_id):
        try:
            response = self.es_client.get(index=self.es_index, id=doc_id)
            if response.get('_source'):
                logger.debug(f"验证成功: Elasticsearch已确认收到文档 {self.es_index}/{doc_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"验证Elasticsearch写入失败: {str(e)}")
            return False

    def save_attack_log(self, log_entry, detections):
        if not isinstance(detections, list):
            detections = [detections]
        
        if not detections:
            return {'attack_logs': {'saved_es': 0, 'failed_es': 0}, 'kafka': {'sent': 0, 'failed': 0}}
        
        merged_detection = self._merge_detections(detections)
        
        result = {
            'attack_logs': {'saved_es': 0, 'failed_es': 0},
            'kafka': {'sent': 0, 'failed': 0}
        }
        
        doc_id = self.save_attack_log_to_elasticsearch(log_entry, merged_detection)
        if doc_id:
            result['attack_logs']['saved_es'] += 1
        else:
            result['attack_logs']['failed_es'] += 1
        
        if self.kafka_enabled and self.kafka_producer:
            try:
                message = {
                    'event_id': log_entry.get('event_id'),
                    'ip': log_entry.get('ip'),
                    'path': log_entry.get('path'),
                    'method': log_entry.get('method'),
                    'status': log_entry.get('status'),
                    'user_agent': log_entry.get('user_agent'),
                    'detection_time': epoch_millis_now(),
                    'detection_result': merged_detection
                }
                
                future = self.kafka_producer.send(self.kafka_topic, message)
                future.get(timeout=10)
                result['kafka']['sent'] += 1
                
            except Exception as e:
                logger.error(f"发送攻击日志到Kafka失败: {str(e)}")
                result['kafka']['failed'] += 1
        
        return result

    def _merge_detections(self, detections):
        if not detections:
            return {}
        
        merged = {
            'attack_type': [],
            'matched_rules': {'keywords': [], 'patterns': []},
            'detection_time': epoch_millis_now(),
            'is_attack': True
        }
        
        for det in detections:
            if det.get('attack_type') and det['attack_type'] not in merged['attack_type']:
                merged['attack_type'].append(det['attack_type'])
            
            det_rules = det.get('matched_rules', {})
            for keyword in det_rules.get('keywords', []):
                if keyword not in merged['matched_rules']['keywords']:
                    merged['matched_rules']['keywords'].append(keyword)
            for pattern in det_rules.get('patterns', []):
                if pattern not in merged['matched_rules']['patterns']:
                    merged['matched_rules']['patterns'].append(pattern)
        
        merged['attack_type'] = ','.join(merged['attack_type'])
        
        return merged

    def save_normal_log(self, log_entry):
        try:
            date_str, hour_str = format_for_directory()
            log_dir = os.path.join(
                str(Path(__file__).resolve().parent.parent / 'temporaryDatas' / 'unmatchDatas'),
                date_str,
                hour_str
            )
            os.makedirs(log_dir, exist_ok=True)
            
            filename = f"{format_for_filename()}.json"
            filepath = os.path.join(log_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"正常日志已保存: {filepath}")
            
        except Exception as e:
            logger.error(f"保存正常日志失败: {str(e)}")

    def close(self):
        if self.es_client:
            try:
                self.es_client.close()
                logger.info("Elasticsearch连接已关闭")
            except Exception as e:
                logger.error(f"关闭Elasticsearch连接失败: {str(e)}")
        
        if self.kafka_producer:
            try:
                self.kafka_producer.close()
                logger.info("Kafka连接已关闭")
            except Exception as e:
                logger.error(f"关闭Kafka连接失败: {str(e)}")
