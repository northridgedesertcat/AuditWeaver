# Elasticsearch 客户端封装
from elasticsearch import Elasticsearch, AsyncElasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch 客户端类"""
    
    def __init__(
        self,
        hosts: str = "http://localhost:19200",
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30
    ):
        self.hosts = hosts
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = None
    
    def connect(self) -> bool:
        """建立同步连接"""
        try:
            auth = (self.username, self.password) if self.username else None
            self.client = Elasticsearch(
                hosts=self.hosts,
                http_auth=auth,
                timeout=self.timeout,
                max_retries=3,
                retry_on_timeout=True
            )
            if self.client.ping():
                logger.info(f"成功连接到 Elasticsearch: {self.hosts}")
                return True
            logger.error(f"无法连接到 Elasticsearch: {self.hosts}")
            return False
        except Exception as e:
            logger.error(f"Elasticsearch 连接失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.error(f"关闭连接失败: {str(e)}")
    
    def search(self, query: Dict[str, Any], index: str, size: int = 1000) -> Optional[Dict]:
        """执行搜索查询"""
        try:
            return self.client.search(index=index, body=query, size=size)
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return None
    
    def index(self, index: str, body: Dict[str, Any], doc_id: Optional[str] = None) -> Optional[Dict]:
        """写入文档"""
        try:
            return self.client.index(index=index, body=body, id=doc_id)
        except Exception as e:
            logger.error(f"写入失败: {str(e)}")
            return None
    
    def bulk(self, actions: list) -> Optional[Dict]:
        """批量操作"""
        try:
            return self.client.bulk(body=actions)
        except Exception as e:
            logger.error(f"批量操作失败: {str(e)}")
            return None
    
    def update(self, index: str, doc_id: str, body: Dict[str, Any]) -> Optional[Dict]:
        """更新文档"""
        try:
            return self.client.update(index=index, id=doc_id, body=body)
        except Exception as e:
            logger.error(f"更新失败: {str(e)}")
            return None
    
    def indices(self):
        """获取索引操作对象"""
        return self.client.indices
