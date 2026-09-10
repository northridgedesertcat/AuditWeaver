"""Redis 会话历史(LangGraph RedisSaver,进程级 singleton)。

基于 ``langgraph-checkpoint-redis==0.1.3`` 实际验证的 API(见
``document/develop/web/Redis接入_规划方案.md`` §3 / §4):
- ``RedisSaver(redis_url=..., connection_args=..., ttl=None)``
- ``saver.setup()`` 幂等,创建 RediSearch 索引,启动时调一次
- 不使用 ``from_conn_string``(其为 contextmanager,退出会关闭连接,不适合 singleton)
- 不调用 ``prune()``(0.1.3 不存在该方法)

设计要点(方案 §4.3 §8 §10.2 §11):
- 进程级 singleton:一个进程一个 RedisSaver,多请求复用。
- ``ttl=None``:checkpoint 持久保存,不主动 TTL。
- Redis 模式下 Redis 不可用 → ``setup()`` 抛错,快速失败,
  **不偷偷 fallback 到 MemorySaver**(避免 session state 不一致)。
- ``thread_id`` 会话隔离由 LangGraph 天然保证(thread_id 为主键)。
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from langgraph.checkpoint.redis import RedisSaver

from shared.config.settings import MEMORY_CONFIG

logger = logging.getLogger(__name__)

# 进程级 singleton;惰性初始化(构造 + setup 需要 Redis 在线)
_redis_saver: Optional[RedisSaver] = None
_init_lock = threading.Lock()


def get_redis_saver() -> RedisSaver:
    """返回进程级 singleton ``RedisSaver``。

    ``AE_MEMORY_BACKEND=redis`` 时由 ``get_checkpointer()`` 工厂调用。
    首次调用构造 saver 并执行 ``setup()`` 创建 RediSearch 索引;
    Redis 不可用 / 密码错误 / URL 未配置 → 此处抛错,快速失败,
    不降级到 MemorySaver(方案 §10.2:避免 session state 不一致)。
    """
    global _redis_saver
    if _redis_saver is not None:
        return _redis_saver

    with _init_lock:
        if _redis_saver is not None:  # double-checked locking
            return _redis_saver

        redis_url = MEMORY_CONFIG.get('redis_url')
        if not redis_url:
            raise RuntimeError(
                "AE_MEMORY_BACKEND=redis 但 AE_MEMORY_REDIS_URL 未配置; "
                "请在 .env 设置 AE_MEMORY_REDIS_URL(如 redis://:密码@localhost:16379/0)"
            )

        logger.info("初始化 RedisSaver singleton")
        # ttl=None:方案 §8 checkpoint 持久保存,不主动 TTL
        # connection_args 透传给 redis-py Redis.from_url,设合理 socket 超时
        saver = RedisSaver(
            redis_url=redis_url,
            connection_args={
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
                'health_check_interval': 30,
            },
            ttl=None,
        )
        # setup() 幂等:创建 RediSearch 索引,同时触发首次连接。
        # Redis 不可用 / 密码错误 / 缺 RedisJSON/RediSearch 模块 → 此处抛错,fast fail,不 fallback。
        saver.setup()
        _redis_saver = saver

    logger.info("RedisSaver 初始化完成(checkpoint 持久化已就绪)")
    return _redis_saver
