"""LangGraph 后端:HTTP 调用 agent_service 的 workflow 端点。

与 Dify 后端同为 HTTP 调用模式,Kafka 管线无感知。
"""
import logging

import requests

from preprocessor import extract_log_fields
from .base import AnalysisResult

logger = logging.getLogger('langgraph_backend')


class LangGraphAnalysisBackend:
    """通过 HTTP 调用 agent_service /workflow/analysis_workflow/run。"""

    def __init__(self, base_url: str, timeout: int = 60):
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})

    def analyze(self, raw_message: dict) -> AnalysisResult:
        log_fields = extract_log_fields(raw_message)
        log_id = log_fields.get('log_id', 'unknown')
        url = f'{self._base_url}/workflow/analysis_workflow/run'

        try:
            logger.info(f'LangGraph backend → {url} | log_id={log_id}')
            resp = self._session.post(
                url,
                json={'inputs': log_fields},
                timeout=self._timeout,
            )

            if resp.status_code != 200:
                logger.error(f'agent_service HTTP {resp.status_code}: {resp.text[:200]}')
                return AnalysisResult(
                    status='failed', log_id=log_id,
                    error=f'agent_service HTTP {resp.status_code}',
                )

            data = resp.json()
            outputs = data.get('outputs', {})

            return AnalysisResult(
                status='success',
                log_id=log_id,
                risk_level=outputs.get('risk_level', 'unknown'),
                risk_score=outputs.get('risk_score', 0),
                attack_type_ai=outputs.get('attack_type', ''),  # attack_type → attack_type_ai
                summary=outputs.get('summary', ''),
                reasoning=outputs.get('reasoning', []),
                recommendations=outputs.get('recommendations', []),
                raw_response=outputs,
            )

        except requests.exceptions.Timeout:
            logger.error(f'agent_service timeout | log_id={log_id}')
            return AnalysisResult(status='failed', log_id=log_id, error='timeout')
        except Exception as e:
            logger.error(f'agent_service request failed | log_id={log_id}: {e}')
            return AnalysisResult(status='failed', log_id=log_id, error=str(e))

    def close(self) -> None:
        self._session.close()
