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


# ---- thread history(对齐 §3.3 + §3.9 P0-8)----

class ThreadCheckpoint(BaseModel):
    """checkpointer 中单个 checkpoint 的元信息(对齐 LangGraph CheckpointMetadata)。"""
    step: int | None = Field(None, description="superstep 序号")
    source: str | None = Field(None, description="checkpoint 来源(loop/loop/...) ")
    nodes: list[str] = Field(default_factory=list, description="该 step 写入的节点名(writes 的 key)")


class ThreadMessage(BaseModel):
    """会话历史中单条消息的序列化视图(截断 content 防爆)。"""
    role: str = Field(..., description="user/assistant/tool/system")
    content: str = Field(..., description="消息内容(截断至 500 字)")
    tool_calls: list[dict] | None = Field(None, description="AIMessage 的 tool_calls(若有)")
    name: str | None = Field(None, description="ToolMessage 的工具名(若有)")


class ThreadHistoryResponse(BaseModel):
    """``GET /agent/{agent_type}/threads/{thread_id}/history`` 响应。

    返回该 thread 的最近 N 个 checkpoint 元信息 + 最新 checkpoint 的 messages。
    thread_id 命名空间规则与 stream.py 一致(对齐 §3.3 "thread_id 会话隔离"):
    内部存储 key 为 "{agent_type}:{thread_id}",故 agent_type 是必填路径参数。
    """
    agent_type: str
    thread_id: str
    exists: bool
    checkpoint_count: int = Field(0, description="checkpointer 中该 thread 的 checkpoint 总数(实际返回受 limit 截断)")
    checkpoints: list[ThreadCheckpoint] = Field(default_factory=list, description="最近 N 个 checkpoint 元信息(新→旧)")
    messages: list[ThreadMessage] = Field(default_factory=list, description="最新 checkpoint 的消息序列(role/content)")
