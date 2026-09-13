"""健康检查与元信息路由:/agent/health、/agent/types。"""
from fastapi import APIRouter

from ..deps import list_agent_types

router = APIRouter(prefix="/agent", tags=["agent-meta"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/types")
async def types():
    """列出已注册的 agent_type。"""
    return {"types": list_agent_types()}
