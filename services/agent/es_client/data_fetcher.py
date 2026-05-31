# 数据采集器
from .client import ElasticsearchClient
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataFetcher:
    """从 Elasticsearch 采集数据"""
    
    def __init__(self, client: ElasticsearchClient):
        self.client = client
    
    def fetch_pending_logs(
        self,
        index: str,
        minutes: int = 10,
        size: int = 1000,
        status_field: str = "pipeline.agent_analysis.status"
    ) -> List[Dict]:
        """获取待分析的日志（pipeline.agent_analysis.status 为 pending）"""
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": f"now-{minutes}m"
                                }
                            }
                        },
                        {
                            "term": {
                                f"{status_field}.keyword": "pending"
                            }
                        }
                    ]
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}]
        }
        
        try:
            response = self.client.search(query, index, size)
            if response:
                hits = response.get("hits", {}).get("hits", [])
                logger.info(f"从 {index} 获取到 {len(hits)} 条待分析日志")
                return [hit["_source"] for hit in hits]
            return []
        except Exception as e:
            logger.error(f"获取待分析日志失败: {str(e)}")
            return []
    
    def fetch_by_event_ids(
        self,
        index: str,
        event_ids: List[str]
    ) -> List[Dict]:
        """根据 event_id 批量获取日志"""
        query = {
            "query": {
                "terms": {
                    "event_id.keyword": event_ids
                }
            }
        }
        
        try:
            response = self.client.search(query, index, size=len(event_ids))
            if response:
                hits = response.get("hits", {}).get("hits", [])
                return [hit["_source"] for hit in hits]
            return []
        except Exception as e:
            logger.error(f"根据 event_id 获取日志失败: {str(e)}")
            return []
    
    def get_index_stats(self, index: str) -> Optional[Dict]:
        """获取索引统计信息"""
        try:
            return self.client.indices.stats(index=index)
        except Exception as e:
            logger.error(f"获取索引统计失败: {str(e)}")
            return None
