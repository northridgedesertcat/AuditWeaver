"""Redis 会话历史(预留扩展点,一版不实现)。

接口签名与 ``in_memory.get_memory_saver`` 对齐,后续接 LangGraph 官方
``RedisSaver`` 即可,业务代码不变。
"""
from langgraph.checkpoint.memory import MemorySaver


def get_redis_saver():
    """一版未实现:抛出明确异常,提示需要先配置 Redis 并实现。"""
    raise NotImplementedError(
        "Redis checkpointer 尚未实现;请在 .env 设置 AE_MEMORY_BACKEND=memory, "
        "或在此处接入 langgraph 的 RedisSaver。"
    )
