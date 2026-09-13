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

异步适配(langgraph-checkpoint-redis==0.1.3 实测):
- 0.1.3 的同步 ``RedisSaver`` 只实现了同步方法,
  ``aput`` / ``aget_tuple`` / ``alist`` / ``aput_writes`` / ``adelete_thread``
  全部继承基类默认 ``raise NotImplementedError``(空消息,难排查);
- 而 SSE 流式路径 ``graph.astream_events(...)`` 是异步执行,
  LangGraph 会调 ``checkpointer.aput`` → 直接 NotImplementedError;
- 修复:``AsyncCapableRedisSaver`` 子类把 5 个异步方法委托给同步方法
  (``run_in_executor``,redis-py 同步客户端线程安全,标准做法);
- ``aget`` 基类有默认实现(走 ``aget_tuple``),无需覆盖。
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple, RunnableConfig  # noqa: F401
from langgraph.checkpoint.redis import RedisSaver

from shared.config.settings import MEMORY_CONFIG

logger = logging.getLogger(__name__)


class AsyncCapableRedisSaver(RedisSaver):
    """补齐同步 RedisSaver(0.1.3)缺失的异步方法,委托同步实现到 executor。

    仅做线程委托,不改变任何持久化语义:同样的 Redis 连接、同样的索引、
    同样的数据格式;同步路径(graph.invoke)与异步路径(astream_events)共用。
    """

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict,
    ) -> RunnableConfig:
        return await asyncio.get_running_loop().run_in_executor(
            None, self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, object]],
        task_id: str,
    ) -> RunnableConfig:
        return await asyncio.get_running_loop().run_in_executor(
            None, self.put_writes, config, writes, task_id
        )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await asyncio.get_running_loop().run_in_executor(
            None, self.get_tuple, config
        )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ):
        # 同步 list 返回迭代器,executor 中物化为列表再逐条 yield(异步生成器契约)
        items = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: list(self.list(config, filter=filter, before=before, limit=limit)),
        )
        for item in items:
            yield item

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.get_running_loop().run_in_executor(
            None, self.delete_thread, thread_id
        )


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

        logger.info("初始化 RedisSaver singleton(AsyncCapableRedisSaver)")
        # ttl=None:方案 §8 checkpoint 持久保存,不主动 TTL
        # connection_args 透传给 redis-py Redis.from_url,设合理 socket 超时
        saver = AsyncCapableRedisSaver(
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
