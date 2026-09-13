"""Agent Service 启动期配置校验(provider-agnostic)。

设计原则(对齐项目约定 + 本次改造):
- 配置错 fast fail,不拖到运行时(避免 400/404 才暴露)。
- provider-agnostic:不写死 DeepSeek/OpenAI 的模型名白名单,
  只做通用校验(非空、URL 格式、配置完整性)。
- embedding 允许不配置(三项全空 → RAG 降级),不视为错误。

校验规则:
1. LLM 各角色(analysis / light / report):
   - model / base_url / api_key 必须非空。
   - base_url 必须是合法 HTTP/HTTPS URL(scheme + netloc)。
2. RAG embedding:
   - 三项(base_url / api_key / model)全空 → 跳过(允许降级)。
   - 任一非空 → 三项必须齐全,且 base_url 为合法 URL。
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from shared.config.settings import LLM_CONFIGS, RAG_CONFIG
from shared.llm.exceptions import LLMConfigError

logger = logging.getLogger(__name__)

# LLM 角色必填字段
_REQUIRED_LLM_FIELDS = ("model", "base_url", "api_key")
# embedding 必填字段(任一非空时三项必须齐全)
_EMBED_FIELDS = ("embedding_model", "embedding_base_url", "embedding_api_key")


def _is_valid_url(url: str) -> bool:
    """校验 URL 是否为合法 HTTP/HTTPS URL(scheme + netloc 非空)。"""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_llm_configs() -> None:
    """校验所有 LLM 角色配置。

    Raises:
        LLMConfigError: 任一角色配置缺失或 base_url 不合法。
    """
    errors: list[str] = []
    for role, config in LLM_CONFIGS.items():
        for field in _REQUIRED_LLM_FIELDS:
            value = (config.get(field) or "").strip()
            if not value:
                errors.append(
                    f"LLM 角色 '{role}' 缺少必填字段 '{field}'。"
                    f"请在 .env 中配置对应的环境变量(model 必须显式指定,不硬编码默认值)。"
                )
        base_url = (config.get("base_url") or "").strip()
        if base_url and not _is_valid_url(base_url):
            errors.append(
                f"LLM 角色 '{role}' 的 base_url='{base_url}' 不是合法的 HTTP/HTTPS URL。"
            )

    if errors:
        raise LLMConfigError(
            "LLM 配置校验失败:\n  - " + "\n  - ".join(errors)
            + "\n请修正 .env 后重启服务。"
        )
    logger.info(
        "[config.validate] LLM 配置校验通过: roles=%s",
        list(LLM_CONFIGS.keys()),
    )


def validate_rag_embedding_config() -> None:
    """校验 RAG embedding 配置。

    - 三项全空 → 跳过(允许 RAG 降级)。
    - 任一非空 → 三项必须齐全,且 base_url 合法。

    Raises:
        LLMConfigError: 配置不完整或 base_url 不合法。
    """
    values = {
        field: (RAG_CONFIG.get(field) or "").strip()
        for field in _EMBED_FIELDS
    }

    # 三项全空 → 允许降级,不报错
    if not any(values.values()):
        logger.info(
            "[config.validate] RAG embedding 未配置,RAG 将降级为空 EvidencePack。"
        )
        return

    # 任一非空 → 三项必须齐全
    missing = [f for f, v in values.items() if not v]
    if missing:
        raise LLMConfigError(
            f"RAG embedding 配置不完整,缺少: {missing}。"
            f"embedding 的 base_url / api_key / model 必须同时配置(或同时留空以降级)。"
        )

    base_url = values["embedding_base_url"]
    if not _is_valid_url(base_url):
        raise LLMConfigError(
            f"RAG embedding 的 base_url='{base_url}' 不是合法的 HTTP/HTTPS URL。"
        )

    logger.info(
        "[config.validate] RAG embedding 配置校验通过: model=%s base_url=%s",
        values["embedding_model"], base_url,
    )


def validate_runtime_config() -> None:
    """启动期统一配置校验入口。

    供 backend/main.py 在服务启动时调用,校验失败抛 LLMConfigError 阻止启动。
    """
    validate_llm_configs()
    validate_rag_embedding_config()
    logger.info("[config.validate] 全部配置校验通过。")
