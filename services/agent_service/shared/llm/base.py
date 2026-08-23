"""LLM 提供方抽象。

所有实现返回 langchain 的 ``BaseChatModel``,这样上层 agent 的
``bind_tools`` / ``astream`` 不感知具体厂商,按 ``.env`` 切换即可。
"""
from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


class BaseLLMProvider(ABC):
    """LLM 提供方抽象接口。"""

    @abstractmethod
    def build(self) -> BaseChatModel:
        """构造一个可被 agent 复用的 chat model 实例。"""
