"""LLM 工厂:按 ``AE_LLM_PROVIDER`` 选择提供方。

一版只支持 ``openai_compat``(覆盖大多数国产 OpenAI 兼容 API)。
后续如要接 Anthropic / Bedrock / 自部署 vLLM,在此分支即可,
上层 agent 代码不变。
"""
from shared.config.settings import LLM_CONFIG
from .base import BaseLLMProvider
from .openai_compat import OpenAICompatProvider


def get_llm():
    """按配置构造一个 BaseChatModel。"""
    provider = LLM_CONFIG['provider']
    impl: BaseLLMProvider
    if provider == 'openai_compat':
        impl = OpenAICompatProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return impl.build()
