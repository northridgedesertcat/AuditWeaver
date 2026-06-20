# Dify API 客户端
import requests
import json
import logging
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Optional
from config import (
    build_dify_payload,
    extract_log_fields,
)

logger = logging.getLogger('dify_client')

class DifyClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 60, endpoint: str = 'chat-messages'):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.endpoint = endpoint.lstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def send_message(self, query: str, conversation_id: Optional[str] = None,
                     user: str = 'agent_client', inputs: Optional[Dict[str, Any]] = None,
                     response_mode: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            'query': query,
            'inputs': inputs or {},
            'response_mode': response_mode or RESPONSE_MODE,
            'user': user
        }

        if conversation_id:
            payload['conversation_id'] = conversation_id

        endpoint_url = f'{self.base_url}/{self.endpoint}'

        try:
            logger.info(f'Sending request to Dify API: {endpoint_url}')
            logger.debug(f'Request payload: {json.dumps(payload, ensure_ascii=False)}')
            response = self.session.post(
                endpoint_url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f'Dify API error response: {response.status_code}')
                logger.error(f'Response body: {response.text}')
                response.raise_for_status()

            result = response.json()
            logger.info('Dify API response received successfully')
            return result

        except requests.exceptions.Timeout:
            logger.error('Dify API request timeout')
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f'Dify API request failed: {str(e)}')
            raise

    def analyze_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        # 使用配置文件构建 payload (Workflow 模式)
        try:
            payload = build_dify_payload(log_data)
            log_id = extract_log_fields(log_data).get('log_id', 'unknown')
            
            endpoint_url = f'{self.base_url}/{self.endpoint}'
            
            logger.info(f'Sending request to Dify Workflow API: {endpoint_url}')
            logger.debug(f'Request payload: {json.dumps(payload, ensure_ascii=False)}')
            
            response = self.session.post(
                endpoint_url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f'Dify API error response: {response.status_code}')
                logger.error(f'Response body: {response.text}')
                response.raise_for_status()
            
            result = response.json()
            logger.info('Dify Workflow API response received successfully')
            
            return {
                'status': 'success',
                'log_id': log_id,
                'response': result
            }
        except Exception as e:
            log_id = 'unknown'
            try:
                log_id = extract_log_fields(log_data).get('log_id', 'unknown')
            except:
                pass
                
            logger.error(f'Failed to analyze log {log_id}: {str(e)}')
            return {
                'status': 'failed',
                'log_id': log_id,
                'error': str(e)
            }

    def close(self):
        self.session.close()
        logger.info('Dify client closed')
