# Elasticsearch 客户端模块
import logging
from typing import Dict, Any, Optional
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError, ConnectionError as ESConnectionError

logger = logging.getLogger('elasticsearch_client')

class ESClient:
    def __init__(self, host: str = 'localhost', port: int = 19200):
        self.host = host
        self.port = port
        self.url = f'http://{host}:{port}'
        self.client: Optional[Elasticsearch] = None
        self.index_name = 'log_analysis_reports'

    def connect(self) -> bool:
        try:
            self.client = Elasticsearch([self.url])
            if self.client.ping():
                logger.info(f'Connected to Elasticsearch: {self.url}')
                self._ensure_index_exists()
                return True
            else:
                logger.error('Elasticsearch ping failed')
                return False
        except ESConnectionError as e:
            logger.error(f'Failed to connect to Elasticsearch: {str(e)}')
            return False

    def _ensure_index_exists(self):
        if not self.client:
            return

        # 添加项目路径导入新的 mapping 配置
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from config.elastic_mapping_config import ELASTICSEARCH_MAPPING

        if not self.client.indices.exists(index=self.index_name):
            try:
                self.client.indices.create(index=self.index_name, body=ELASTICSEARCH_MAPPING)
                logger.info(f'Created index: {self.index_name} with new mapping')
            except Exception as e:
                logger.error(f'Failed to create index: {str(e)}')
        else:
            logger.info(f'Index {self.index_name} already exists')

    def index_document(self, document: Dict[str, Any], refresh: bool = True) -> Optional[str]:
        if not self.client:
            logger.error('Elasticsearch client not connected')
            return None

        try:
            response = self.client.index(
                index=self.index_name,
                document=document,
                refresh=refresh
            )
            doc_id = response.get('_id')
            logger.info(f'Document indexed: {self.index_name}/{doc_id}')
            return doc_id
        except Exception as e:
            logger.error(f'Failed to index document: {str(e)}')
            return None

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        try:
            response = self.client.get(index=self.index_name, id=doc_id)
            return response.get('_source')
        except NotFoundError:
            logger.warning(f'Document not found: {self.index_name}/{doc_id}')
            return None
        except Exception as e:
            logger.error(f'Failed to get document: {str(e)}')
            return None

    def search(self, query: Dict[str, Any], size: int = 10) -> list:
        if not self.client:
            return []

        try:
            response = self.client.search(index=self.index_name, query=query, size=size)
            return response.get('hits', {}).get('hits', [])
        except Exception as e:
            logger.error(f'Failed to search: {str(e)}')
            return []

    def is_connected(self) -> bool:
        if not self.client:
            return False
        try:
            return self.client.ping()
        except:
            return False

    def close(self):
        if self.client:
            self.client.close()
            logger.info('Elasticsearch client closed')
