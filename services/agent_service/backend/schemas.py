"""FastAPI 请求 / 响应模型(Pydantic)。

FastAPI 只做协议层,不含任何 LLM 调用逻辑(职责边界)。
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入")
    thread_id: str | None = Field(None, description="会话 ID,用于保持多轮上下文")
    history: list[dict] = Field(default_factory=list, description="可选历史消息(role/content)")


class ChatSyncResponse(BaseModel):
    agent_type: str
    answer: str
    tool_calls: list[dict] = Field(default_factory=list, description="本轮调用的工具及摘要")
    thread_id: str | None = None
