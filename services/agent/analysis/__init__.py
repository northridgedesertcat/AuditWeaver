"""分析后端抽象层:统一协议 + 工厂切换。"""
from .base import AnalysisBackend, AnalysisResult
from .factory import get_analysis_backend

__all__ = ['AnalysisBackend', 'AnalysisResult', 'get_analysis_backend']
