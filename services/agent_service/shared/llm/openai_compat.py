"""OpenAI 兼容厂商实现(覆盖 DeepSeek / Qwen / GLM / Kimi / OpenAI 官方)。

差异只在 ``base_url`` / ``model`` / ``api_key``,由 ``LLM_CONFIG`` 注入。
"""
from langchain_openai import ChatOpenAI

from shared.config.settings import LLM_CONFIG
from .base import BaseLLMProvider


class OpenAICompatProvider(BaseLLMProvider):
    """所有 OpenAI 兼容厂商走这一份实现。"""

    def __init__(self, **overrides):
        self._overrides = overrides

    def build(self):
        params = {
            'model': LLM_CONFIG['model'],
            'base_url': LLM_CONFIG['base_url'],
            'api_key': LLM_CONFIG['api_key'],
            'temperature': LLM_CONFIG['temperature'],
            'streaming': True,
        }
        params.update(self._overrides)
        return ChatOpenAI(**params)
