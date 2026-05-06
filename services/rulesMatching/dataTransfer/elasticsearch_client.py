# Elasticsearch连接模块
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('elasticsearch_client')

class ElasticsearchClient:
    """Elasticsearch客户端类"""
    
    def __init__(self, hosts=['http://localhost:9200'], index='nginx-log'):
        """初始化Elasticsearch客户端"""
        self.hosts = hosts
        self.index = index
        self.client = None
        self.connect()
    
    def connect(self):
        """连接到Elasticsearch"""
        try:
            self.client = Elasticsearch(
                self.hosts,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            # 测试连接
            try:
                response = self.client.info()
                logger.info(f"成功连接到Elasticsearch: {self.hosts}")
                logger.info(f"Elasticsearch版本: {response['version']['number']}")
            except Exception as e:
                logger.error(f"Elasticsearch ping失败: {str(e)}")
                self.client = None
        except ConnectionError as e:
            logger.error(f"Elasticsearch连接错误: {str(e)}")
            self.client = None
        except RequestError as e:
            logger.error(f"Elasticsearch请求错误: {str(e)}")
            self.client = None
        except Exception as e:
            logger.error(f"Elasticsearch初始化错误: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            self.client = None
    
    def is_connected(self):
        """检查是否连接成功"""
        return self.client is not None
    
    def search(self, query=None, size=100, scroll='1m'):
        """搜索Elasticsearch数据"""
        if not self.is_connected():
            logger.error("Elasticsearch未连接")
            return None
        
        try:
            if query is None:
                query = {
                    "query": {
                        "match_all": {}
                    }
                }
            
            response = self.client.search(
                index=self.index,
                body=query,
                size=size,
                scroll=scroll
            )
            
            logger.info(f"搜索完成，找到 {response['hits']['total']['value']} 条记录")
            return response
        except RequestError as e:
            logger.error(f"Elasticsearch请求错误: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Elasticsearch搜索错误: {str(e)}")
            return None
    
    def get_latest_logs(self, minutes=5, size=100):
        """获取最近几分钟的日志"""
        if not self.is_connected():
            logger.error("Elasticsearch未连接")
            return []
        
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
                        }
                    ]
                }
            },
            "sort": [
                {
                    "@timestamp": {
                        "order": "desc"
                    }
                }
            ]
        }
        
        response = self.search(query, size)
        if response:
            return [hit['_source'] for hit in response['hits']['hits']]
        return []
    
    def get_logs_by_ip(self, ip, size=100):
        """根据IP获取日志"""
        if not self.is_connected():
            logger.error("Elasticsearch未连接")
            return []
        
        query = {
            "query": {
                "match": {
                    "ip": ip
                }
            }
        }
        
        response = self.search(query, size)
        if response:
            return [hit['_source'] for hit in response['hits']['hits']]
        return []
    
    def get_logs_by_status(self, status, size=100):
        """根据状态码获取日志"""
        if not self.is_connected():
            logger.error("Elasticsearch未连接")
            return []
        
        query = {
            "query": {
                "match": {
                    "status": status
                }
            }
        }
        
        response = self.search(query, size)
        if response:
            return [hit['_source'] for hit in response['hits']['hits']]
        return []
    
    def close(self):
        """关闭Elasticsearch连接"""
        if self.client:
            try:
                self.client.close()
                logger.info("Elasticsearch连接已关闭")
            except Exception as e:
                logger.error(f"关闭Elasticsearch连接错误: {str(e)}")
            finally:
                self.client = None
