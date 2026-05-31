# 数据写入器
from .client import ElasticsearchClient
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataWriter:
    """将处理结果写入 Elasticsearch"""
    
    def __init__(self, client: ElasticsearchClient, output_index: str = "agent_analysis_logs"):
        self.client = client
        self.output_index = output_index
    
    def write_processed_log(
        self,
        log_entry: Dict,
        dify_result: Dict,
        doc_id: Optional[str] = None
    ) -> bool:
        """写入处理后的日志到输出索引"""
        try:
            enriched_log = self._enrich_with_result(log_entry, dify_result)
            response = self.client.index(self.output_index, enriched_log, doc_id)
            if response:
                logger.info(f"日志已写入 {self.output_index}: {response.get('_id')}")
                return True
            return False
        except Exception as e:
            logger.error(f"写入日志失败：{str(e)}")
            return False
    
    def bulk_write(
        self,
        entries: List[Dict],
        results: List[Dict]
    ) -> Dict[str, int]:
        """批量写入处理结果到输出索引"""
        actions = []
        for entry, result in zip(entries, results):
            enriched = self._enrich_with_result(entry, result)
            action = {
                "index": {
                    "_index": self.output_index,
                    "_id": entry.get("event_id")
                }
            }
            actions.append(action)
            actions.append(enriched)
        
        try:
            response = self.client.bulk(actions)
            if response:
                items = response.get("items", [])
                success = sum(1 for item in items if item.get("index", {}).get("status") == 201)
                logger.info(f"批量写入完成：{success}/{len(entries)}")
                return {"success": success, "failed": len(entries) - success}
            return {"success": 0, "failed": len(entries)}
        except Exception as e:
            logger.error(f"批量写入失败：{str(e)}")
            return {"success": 0, "failed": len(entries)}
    
    def update_status(
        self,
        index: str,
        event_id: str,
        status: str
    ) -> bool:
        """更新日志的 agent_analysis 状态"""
        try:
            body = {
                "doc": {
                    "pipeline": {
                        "rule_matching": {
                            "status": "completed"
                        },
                        "agent_analysis": {
                            "status": status,
                            "updated_at": datetime.now().isoformat()
                        }
                    }
                }
            }
            response = self.client.update(index, event_id, body)
            if response:
                logger.info(f"已更新日志 agent_analysis 状态: {event_id} -> {status}")
                return True
            return False
        except Exception as e:
            logger.error(f"更新状态失败: {str(e)}")
            return False
    
    def _enrich_with_result(self, log_entry: Dict, dify_result: Dict) -> Dict:
        """为日志添加处理结果"""
        enriched = log_entry.copy()
        enriched["dify_result"] = dify_result
        enriched["processed_at"] = datetime.now().isoformat()
        
        # 更新 agent_analysis 状态为 completed
        if "pipeline" not in enriched:
            enriched["pipeline"] = {}
        if "agent_analysis" not in enriched["pipeline"]:
            enriched["pipeline"]["agent_analysis"] = {}
        enriched["pipeline"]["agent_analysis"]["status"] = "completed"
        enriched["pipeline"]["agent_analysis"]["updated_at"] = datetime.now().isoformat()
        
        return enriched
    
    def ensure_index_exists(self, index: str):
        """确保索引存在"""
        try:
            if not self.client.indices().exists(index=index):
                self._create_index(index)
        except Exception as e:
            logger.error(f"检查索引失败: {str(e)}")
    
    def _create_index(self, index: str):
        """创建索引"""
        mapping = {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "event_id": {"type": "keyword"},
                    "dify_result": {"type": "object"},
                    "processed_at": {"type": "date"},
                    "pipeline": {
                        "properties": {
                            "rule_matching": {
                                "properties": {
                                    "status": {"type": "keyword"}
                                }
                            },
                            "agent_analysis": {
                                "properties": {
                                    "status": {"type": "keyword"},
                                    "updated_at": {"type": "date"}
                                }
                            }
                        }
                    }
                }
            }
        }
        try:
            self.client.indices().create(index=index, body=mapping)
            logger.info(f"创建索引: {index}")
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
