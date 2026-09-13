"""OpenAI 兼容厂商实现(覆盖 DeepSeek / Qwen / GLM / Kimi / OpenAI 官方 / ollama)。

差异只在 ``base_url`` / ``model`` / ``api_key``,由 ``LLM_CONFIGS[role]`` 注入。

v2 升级要点(对齐设计 §3.7):
- 显式校验必填字段(api_key / base_url / model),缺失抛 LLMConfigError 不静默
- max_retries 从 LLM_RETRY_CONFIG 注入(429/5xx 指数退避由 SDK 处理)
- 挂 TokenUsageCallbackHandler,自动记录每次调用的 token 用量
- 保留 overrides 形参,workflow 可用 temperature/model/base_url/api_key/streaming 覆盖
"""
import logging

from langchain_openai import ChatOpenAI

from .base import BaseLLMProvider
from .exceptions import LLMConfigError
from .token_usage import TokenUsageCallbackHandler

logger = logging.getLogger(__name__)


class OpenAICompatProvider(BaseLLMProvider):
    """所有 OpenAI 兼容厂商走这一份实现。"""

    PROVIDER_NAME = "openai_compat"

    @classmethod
    def validate_config_for_role(cls, role: str, config: dict) -> None:
        """显式校验:必填字段缺失抛 LLMConfigError,不静默降级。"""
        missing: list[str] = []
        # api_key:OpenAI 官方要求;ollama 可为 'ollama'(任何非空串)。空字符串视为未配。
        if not config.get("api_key"):
            missing.append("api_key")
        if not config.get("base_url"):
            missing.append("base_url")
        if not config.get("model"):
            missing.append("model")
        if missing:
            raise LLMConfigError(
                f"LLM 角色 '{role}' 配置缺失字段: {missing}。"
                f"请在 .env 中配置对应的 AE_LLM_* 环境变量(角色专用字段或全局默认)。"
            )

    def build(self) -> ChatOpenAI:
        # 显式校验(冗余一次防御,确保不会用 None / '' 拼出无效 client)
        self.validate_config_for_role(self.role, self.config)

        params = {
            "model": self._get("model"),
            "base_url": self._get("base_url"),
            "api_key": self._get("api_key"),
            "temperature": self._get("temperature", 0.2),
            "streaming": self._get("streaming", True),
            # 429/5xx 重试交给 langchain/OpenAI SDK 自带的指数退避
            "max_retries": self.retry_config.get("max_retries", 3),
        }
        # 挂 token usage callback:记录每次调用 token 用量
        callbacks = [TokenUsageCallbackHandler(
            role=self.role,
            model=params["model"],
        )]
        params["callbacks"] = callbacks

        # overrides 兜底(workflow 用此机制覆盖 temperature/model 等)
        params.update(self.overrides)
        # overrides 里的 callbacks 也要并入,不覆盖
        if "callbacks" in self.overrides:
            params["callbacks"] = list(callbacks) + list(self.overrides["callbacks"])

        logger.debug(
            "[llm.openai_compat] 构建 ChatOpenAI role=%s model=%s base_url=%s",
            self.role, params["model"], params["base_url"],
        )
        return ChatOpenAI(**params)
