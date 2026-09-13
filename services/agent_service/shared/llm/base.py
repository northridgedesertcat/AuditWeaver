"""LLM 提供方抽象。

所有实现返回 langchain 的 ``BaseChatModel``,这样上层 agent 的
``bind_tools`` / ``astream`` 不感知具体厂商,按 ``.env`` 切换即可。
"""
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel


class BaseLLMProvider(ABC):
    """LLM 提供方抽象接口。

    v2 升级:每个 provider 实例绑定一个 role(analysis / light) + 该 role 的配置 dict,
    通过 validate_config 显式校验缺失字段,不静默降级。
    """

    # 子类可声明自己支持的 provider 类型(用于 factory 路由)
    PROVIDER_NAME: str = ""

    def __init__(self, role: str, config: dict, retry_config: dict | None = None, **overrides):
        self.role = role
        self.config = config
        self.retry_config = retry_config or {}
        self.overrides = overrides
        # 子类构造时应调用 validate_config,显式校验必填字段
        self.validate_config()

    @classmethod
    def validate_config(cls) -> None:
        """子类覆写:校验必填字段,缺失抛 LLMConfigError。"""
        return None

    @abstractmethod
    def build(self) -> BaseChatModel:
        """构造一个可被 agent 复用的 chat model 实例。"""

    def _get(self, key: str, default: Any = None) -> Any:
        """从 config 取值,允许 overrides 覆盖。"""
        if key in self.overrides and self.overrides[key] is not None:
            return self.overrides[key]
        return self.config.get(key, default)
