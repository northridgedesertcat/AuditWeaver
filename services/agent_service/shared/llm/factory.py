"""LLM Gateway 工厂:多角色路由 + fallback 链 + token usage(对齐设计 §3.7)。

核心概念:
- role:任务角色,'analysis'(强模型,分析/规划) / 'light'(弱模型,门控/摘要/压缩)
- fallback 链:主 role 不可用 → 沿 LLM_FALLBACK_CHAIN 尝试下一 role → 全失败显式抛错

向后兼容:
- get_llm() 无参 → role='analysis',行为与 v1 一致
- get_llm(temperature=..., model=..., base_url=..., api_key=...) → role='analysis' + overrides
  (workflow nodes.py 的调用方式不变)
"""
import logging

from langchain_core.language_models import BaseChatModel

from shared.config.settings import LLM_CONFIGS, LLM_FALLBACK_CHAIN, LLM_RETRY_CONFIG
from .base import BaseLLMProvider
from .exceptions import LLMConfigError, LLMUnavailableError
from .openai_compat import OpenAICompatProvider

logger = logging.getLogger(__name__)


def _build_role_provider(role: str, **overrides) -> BaseLLMProvider:
    """为指定 role 构造 provider 实例,校验配置缺失。

    配置缺失/不合法 → LLMConfigError(显式报错,不静默降级)。
    """
    if role not in LLM_CONFIGS:
        raise LLMConfigError(
            f"未知 LLM 角色 '{role}',可用角色: {list(LLM_CONFIGS.keys())}。"
            f"请在 shared/config/settings.py 的 LLM_CONFIGS 中注册。"
        )
    config = LLM_CONFIGS[role]
    provider_name = config.get("provider", "openai_compat")

    if provider_name == "openai_compat":
        return OpenAICompatProvider(
            role=role,
            config=config,
            retry_config=LLM_RETRY_CONFIG,
            **overrides,
        )
    raise LLMConfigError(
        f"未知 provider 类型 '{provider_name}'(role={role}),"
        f"当前仅支持 'openai_compat'。"
    )


def get_llm(role: str = "analysis", **overrides) -> BaseChatModel:
    """按角色获取 LLM,带 fallback 链。

    流程:
    1. 尝试主 role 构建,配置缺失 → LLMConfigError(不进 fallback,配置错应改 .env)
    2. 主 role 构建成功但 ChatOpenAI 实例化时仍可能因 provider 切换问题失败,
       此时沿 LLM_FALLBACK_CHAIN 找下一个可用 role
    3. 全部失败 → LLMUnavailableError

    注意:fallback 是"主模型本身不可用"的兜底,不是"调用失败重试"
    (后者由 langchain max_retries 处理)。
    """
    # 第一步:尝试主 role
    last_err: Exception | None = None
    try:
        provider = _build_role_provider(role, **overrides)
        return provider.build()
    except LLMConfigError:
        # 配置错:不进 fallback,显式报错让用户改 .env(对齐项目原则)
        raise
    except Exception as primary_err:
        # 主 role 实例化失败(provider 切换/网络初始化等):走 fallback
        # 注意 Python 3 在 except 块结束后清理 as 绑定,需在块内转存
        last_err = primary_err
        logger.warning(
            "[llm.factory] 主 role='%s' 实例化失败: %s: %s,尝试 fallback 链 %s",
            role, type(primary_err).__name__, primary_err, LLM_FALLBACK_CHAIN,
        )

    # 第二步:沿 fallback 链找下一个可用 role
    # fallback 链从 role 之后开始(role 自己刚试过)
    try:
        role_idx = LLM_FALLBACK_CHAIN.index(role)
    except ValueError:
        role_idx = -1

    for next_role in LLM_FALLBACK_CHAIN[role_idx + 1:]:
        if next_role == role:
            continue
        try:
            logger.info("[llm.factory] fallback 到 role='%s'", next_role)
            provider = _build_role_provider(next_role, **overrides)
            return provider.build()
        except LLMConfigError as e:
            # 配置错:跳过这个 role 试下一个
            logger.info("[llm.factory] fallback role='%s' 配置缺失,跳过: %s", next_role, e)
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue

    raise LLMUnavailableError(
        f"LLM Gateway 全部不可用。主 role='{role}' 及 fallback 链 {LLM_FALLBACK_CHAIN} "
        f"均失败。最后错误: {type(last_err).__name__}: {last_err}。"
        f"请检查 .env 中的 AE_LLM_* 配置及网络连通性。"
    )
