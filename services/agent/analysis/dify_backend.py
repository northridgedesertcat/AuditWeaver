"""Dify 后端:封装现有 DifyClient,输出归一化 AnalysisResult。

行为与改造前 main.py 中的 dify 调用路径完全等价,仅外层包装为 AnalysisBackend。
"""
import logging

from dify import DifyClient
from preprocessor import extract_log_fields, extract_dify_fields
from .base import AnalysisResult

logger = logging.getLogger('dify_backend')


class DifyAnalysisBackend:
    """委托 DifyClient,解析响应为 AnalysisResult。"""

    def __init__(self, base_url: str, api_key: str, timeout: int, endpoint: str):
        self._client = DifyClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            endpoint=endpoint,
        )

    def analyze(self, raw_message: dict) -> AnalysisResult:
        log_id = extract_log_fields(raw_message).get('log_id', 'unknown')
        response = self._client.analyze_log(raw_message)

        if response.get('status') == 'success':
            fields = extract_dify_fields(response.get('response', {}))
            return AnalysisResult(
                status='success',
                log_id=log_id,
                risk_level=fields.get('risk_level', 'unknown'),
                risk_score=fields.get('risk_score', 0),
                attack_type_ai=fields.get('attack_type_ai', ''),
                summary=fields.get('summary', ''),
                reasoning=fields.get('reasoning', []),
                recommendations=fields.get('recommendations', []),
                raw_response=response.get('response', {}),
            )

        # DifyClient.analyze_log 失败时返回 {'status': 'failed', 'error': ...}
        return AnalysisResult(
            status='failed',
            log_id=log_id,
            error=response.get('error', 'unknown'),
        )

    def close(self) -> None:
        self._client.close()
