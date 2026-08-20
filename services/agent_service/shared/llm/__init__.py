"""LLM 抽象层对外入口。"""
from .base import BaseLLMProvider
from .factory import get_llm

__all__ = ["BaseLLMProvider", "get_llm"]
