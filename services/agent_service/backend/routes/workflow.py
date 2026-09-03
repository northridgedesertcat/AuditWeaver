"""Workflow 路由:批处理工作流(非对话型)。

与 /agent/{type}/chat(对话 SSE)分离,服务于 Kafka 管线的结构化输入/输出。
不经过 Django 反代,Kafka 管线直接访问 127.0.0.1:8001 内网。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_graph

router = APIRouter(prefix="/workflow", tags=["workflow"])


class WorkflowRequest(BaseModel):
    inputs: dict = Field(..., description="工作流输入变量(如结构化日志字段)")


class WorkflowResponse(BaseModel):
    agent_type: str
    outputs: dict


def _resolve_graph(agent_type: str):
    try:
        return get_graph(agent_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown agent_type: {agent_type}")


@router.post("/{agent_type}/run", response_model=WorkflowResponse)
async def run_workflow(agent_type: str, req: WorkflowRequest):
    """执行工作流,返回结构化输出。"""
    graph = _resolve_graph(agent_type)
    result = await graph.ainvoke({"log_data": req.inputs})
    return WorkflowResponse(
        agent_type=agent_type,
        outputs=result.get("analysis", {}),
    )
