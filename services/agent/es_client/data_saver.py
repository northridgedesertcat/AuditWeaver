# 数据保存模块
import logging
from typing import Dict, Any, Optional
from .client import ESClient

# 添加项目路径
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.elastic_mapping_config import build_elastic_document

logger = logging.getLogger('data_saver')

class DataSaver:
    def __init__(self, es_host: str = 'localhost', es_port: int = 19200, es_index: str = 'log_analysis_reports'):
        self.es_client = ESClient(host=es_host, port=es_port)
        self.es_index = es_index
        self.es_client.index_name = es_index

    def connect(self) -> bool:
        return self.es_client.connect()

    def save_analysis_report(self, log_entry: Dict[str, Any], dify_response: Dict[str, Any]) -> Optional[str]:
        if not self.es_client.is_connected():
            logger.error('Elasticsearch not connected')
            return None

        # 使用配置文件中的函数构建文档
        report = build_elastic_document(log_entry, dify_response)
        doc_id = self.es_client.index_document(report)

        if doc_id:
            logger.info(f'Analysis report saved: {doc_id}')
            logger.debug(f'Saved document structure: {list(report.keys())}')
        else:
            logger.error('Failed to save analysis report')

        return doc_id

    def is_connected(self) -> bool:
        return self.es_client.is_connected()

    def close(self):
        self.es_client.close()
        logger.info('DataSaver closed')
