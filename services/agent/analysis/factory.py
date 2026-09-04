"""分析后端工厂:按 ANALYSIS_BACKEND 环境变量选择实现。

未知值在启动期抛 ValueError(由 main.py 暴露),不静默 fallback。
"""
import logging

from common.env import (
    ANALYSIS_BACKEND,
    DIFY_BASE_URL, DIFY_API_KEY, DIFY_TIMEOUT,
    AGENT_SERVICE_BASE_URL, AGENT_SERVICE_TIMEOUT,
)
from config import DIFY_CONFIG
from .base import AnalysisBackend
from .dify_backend import DifyAnalysisBackend
from .langgraph_backend import LangGraphAnalysisBackend

logger = logging.getLogger('analysis_factory')


def get_analysis_backend() -> AnalysisBackend:
    """按 ANALYSIS_BACKEND 构造对应后端实例。"""
    backend = ANALYSIS_BACKEND

    if backend == 'dify':
        logger.info('Analysis backend: Dify')
        return DifyAnalysisBackend(
            base_url=DIFY_BASE_URL,
            api_key=DIFY_API_KEY,
            timeout=DIFY_TIMEOUT,
            endpoint=DIFY_CONFIG['endpoint'],
        )

    if backend == 'langgraph':
        logger.info('Analysis backend: LangGraph (agent_service)')
        return LangGraphAnalysisBackend(
            base_url=AGENT_SERVICE_BASE_URL,
            timeout=AGENT_SERVICE_TIMEOUT,
        )

    raise ValueError(f'Unknown ANALYSIS_BACKEND: {backend!r} (expected: dify | langgraph)')
