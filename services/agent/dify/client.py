# Dify API 客户端
import requests
from typing import Dict, Optional
from time import sleep
import logging

logger = logging.getLogger(__name__)


class DifyClient:
    """Dify API 客户端"""
    
    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.dify.ai/v1",
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def process(self, data: Dict) -> Dict:
        """调用 Dify API 处理数据"""
        url = f"{self.api_url}/workflows/run"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": {
                "log_entry": data
            },
            "response_mode": "blocking"
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Dify API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    sleep(self.retry_delay * (2 ** attempt))
        
        logger.error("Dify API 调用失败，已达到最大重试次数")
        return {"error": "max_retries_exceeded", "message": "无法连接到 Dify API"}
    
    def get_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        url = f"{self.api_url}/workflows/tasks/{task_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"获取任务状态失败: {str(e)}")
            return None
    
    def health_check(self) -> bool:
        """检查 Dify API 健康状态"""
        url = f"{self.api_url}/health"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Dify API 健康检查失败: {str(e)}")
            return False
