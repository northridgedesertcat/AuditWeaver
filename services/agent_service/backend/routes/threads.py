"""会话历史路由:基于 checkpointer 的 thread_id 历史查询(对齐 §3.3 + §3.9)。

设计要点:
- checkpointer 是 Agent/Workflow 共用的会话状态存储(MemorySaver/RedisSaver,
  见 shared/memory/__init__.py)。thread_id 由 stream.py 命名空间为
  "{agent_type}:{raw_thread_id}",故本路由复用同一规则还原内部 key。
- 路径 ``/agent/{agent_type}/threads/{thread_id}/history``:agent_type 前缀
  保证不同 Agent 的会话隔离(对齐 §3.3 "thread_id 会话隔离")。设计文档原文
  写 ``/threads/{thread_id}/history``,但与现有命名空间规则冲突(无 agent_type
  无法定位),故加 agent_type 前缀(契约只增不改,不影响现有路由)。
- checkpointer 后端不可用(Redis 连不上)→ 503,不静默(对齐项目原则)。
- thread 不存在 → 404(显式 REST 语义,不返回空 200 误导前端)。
"""
import json

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    ThreadCheckpoint,
    ThreadHistoryResponse,
    ThreadMessage,
)
from shared.memory import get_checkpointer

router = APIRouter(prefix="/agent", tags=["thread-history"])


def _namespaced_thread(agent_type: str, thread_id: str) -> str:
    """与 stream.py._namespaced_thread 一致:agent_type 前缀做命名空间。"""
    return f"{agent_type}:{thread_id}"


def _serialize_message(m) -> ThreadMessage:
    """把 LangGraph BaseMessage 序列化为 ThreadMessage(截断 content 防爆)。

    role 映射:human→user / tool→tool / system→system / 其余→assistant。
    ToolMessage 的 name 字段保留(标记来自哪个工具)。
    AIMessage 的 tool_calls 保留(标记 LLM 决定调哪些工具)。
    """
    mtype = getattr(m, "type", None) or "assistant"
    role = {
        "human": "user",
        "tool": "tool",
        "system": "system",
    }.get(mtype, "assistant")
    content = getattr(m, "content", "")
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False, default=str)
        except Exception:
            content = str(content)
    # 截断到 500 字(对齐 schemas.ThreadMessage 描述)
    content = content[:500]
    out = ThreadMessage(role=role, content=content)
    tcs = getattr(m, "tool_calls", None)
    if tcs:
        out.tool_calls = [
            {"name": tc.get("name"), "args": tc.get("args") or {}}
            for tc in tcs
            if isinstance(tc, dict)
        ]
    name = getattr(m, "name", None)
    if name:
        out.name = str(name)
    return out


@router.get(
    "/{agent_type}/threads/{thread_id}/history",
    response_model=ThreadHistoryResponse,
)
async def thread_history(
    agent_type: str,
    thread_id: str,
    limit: int = Query(20, ge=1, le=100, description="返回最近 N 个 checkpoint"),
):
    """查询某 thread_id 的会话历史(checkpoint 序列 + 最新 messages)。

    - 返回该 thread 最近 ``limit`` 个 checkpoint 元信息(step / source / 写入节点)
      以及最新 checkpoint 的 messages 序列化列表。
    - thread 不存在 → 404;checkpointer 不可用 → 503。
    """
    checkpointer = get_checkpointer()
    ns_thread = _namespaced_thread(agent_type, thread_id)
    config = {"configurable": {"thread_id": ns_thread}}

    try:
        latest = await checkpointer.aget_tuple(config)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"checkpointer unavailable: {type(e).__name__}: {e}",
        )
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail=f"thread not found: {thread_id}",
        )

    # 历史 checkpoint 列表(新→旧);alist 失败降级为空列表(已有 latest 兜底)
    checkpoints: list[ThreadCheckpoint] = []
    try:
        async for item in checkpointer.alist(config, limit=limit):
            meta = item.metadata or {}
            writes = meta.get("writes") or {}
            node_names = list(writes.keys()) if isinstance(writes, dict) else []
            checkpoints.append(ThreadCheckpoint(
                step=meta.get("step"),
                source=meta.get("source"),
                nodes=node_names,
            ))
    except Exception:
        # alist 不可用(MemorySaver 部分版本/Redis 模式降级):不影响 latest messages
        checkpoints = []

    # 最新 checkpoint 的 messages(channel_values.messages)
    channel_values = (latest.checkpoint or {}).get("channel_values") or {}
    raw_messages = channel_values.get("messages") or []
    messages = [_serialize_message(m) for m in raw_messages]

    return ThreadHistoryResponse(
        agent_type=agent_type,
        thread_id=thread_id,
        exists=True,
        checkpoint_count=len(checkpoints),
        checkpoints=checkpoints,
        messages=messages,
    )