"""进程内会话历史(LangGraph MemorySaver)。

一版可接受:进程重启会丢历史。所有 agent 共用同一个 MemorySaver,
通过 ``thread_id``(含 agent_type 前缀,见 FastAPI 层)做命名空间隔离,
避免不同 Agent / 不同会话的对话串。
"""
from langgraph.checkpoint.memory import MemorySaver

_saver = MemorySaver()


def get_memory_saver() -> MemorySaver:
    """返回进程内单例 MemorySaver。"""
    return _saver
