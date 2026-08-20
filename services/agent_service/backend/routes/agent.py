"""Agent 对话路由:/agent/{agent_type}/chat(流式)/ chat/sync(非流式)。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import get_graph
from ..schemas import ChatRequest, ChatSyncResponse
from ..stream import run_agent_sync, stream_agent_chat

router = APIRouter(prefix="/agent", tags=["agent"])


def _resolve_graph(agent_type: str):
    try:
        return get_graph(agent_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown agent_type: {agent_type}")


@router.post("/{agent_type}/chat")
async def chat(agent_type: str, req: ChatRequest):
    """流式对话(SSE),Django 主用。"""
    graph = _resolve_graph(agent_type)
    return StreamingResponse(
        stream_agent_chat(graph, agent_type, req.message, req.thread_id, req.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{agent_type}/chat/sync", response_model=ChatSyncResponse)
async def chat_sync(agent_type: str, req: ChatRequest):
    """非流式对话,返回完整 JSON。"""
    graph = _resolve_graph(agent_type)
    return await run_agent_sync(graph, agent_type, req.message, req.thread_id, req.history)
