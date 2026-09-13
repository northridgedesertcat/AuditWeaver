"""会话历史对外入口:统一 ``get_checkpointer()`` 工厂。"""
from common.env import get_env


def get_checkpointer():
    """返回会话历史 checkpointer。

    按 ``.env`` 的 ``AE_MEMORY_BACKEND`` 切换后端:
    - ``memory``(默认):进程内 ``MemorySaver``,重启丢历史,不依赖 Redis。
    - ``redis``:``RedisSaver`` singleton,checkpoint 持久化到 Redis;
      Redis 不可用则快速失败,**不** fallback 到 MemorySaver(避免 session state 不一致)。
    """
    backend = get_env('AE_MEMORY_BACKEND', 'memory')
    if backend == 'redis':
        from .redis import get_redis_saver
        return get_redis_saver()
    from .in_memory import get_memory_saver
    return get_memory_saver()
