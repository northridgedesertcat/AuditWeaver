"""会话历史对外入口:统一 ``get_checkpointer()`` 工厂。"""
from common.env import get_env


def get_checkpointer():
    """返回会话历史 checkpointer。

    一版进程内 ``MemorySaver``;在 ``.env`` 设 ``AE_MEMORY_BACKEND=redis``
    即切换到 Redis(预留)。
    """
    backend = get_env('AE_MEMORY_BACKEND', 'memory')
    if backend == 'redis':
        from .redis import get_redis_saver
        return get_redis_saver()
    from .in_memory import get_memory_saver
    return get_memory_saver()
