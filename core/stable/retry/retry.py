"""线性退避重试(基于 Tenacity 薄封装)。

提供项目统一的重试入口:
- ``retry`` 装饰器(声明式)
- ``Retry`` 类(过程式,``Retry(**config).call(fn, *args, **kwargs)``)

内部将项目参数映射到 Tenacity:

===================  ==================================================
项目参数             Tenacity 映射
===================  ==================================================
``max_retries``      ``stop_after_attempt(max_retries + 1)``(Tenacity
                     计数含首次调用)
``base_delay``/      ``wait_incrementing(start, increment, max)``
``max_delay``        (线性退避:第 n 次等待 ``base × n``,封顶 max)
``jitter``           ``wait_combine(线性, wait_random(0, base × jitter))``
``exceptions``       ``retry_if_exception_type``(白名单,isinstance 含子类)
``on_retry``         ``before_sleep``(签名适配为 ``(attempt, exception, delay)``)
用尽重抛             ``reraise=True``(抛出最后一次原始异常,非 RetryError)
===================  ==================================================

除上述项目参数外的其他 ``kwargs`` 直接透传给 Tenacity,保留其高级能力。
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Any, Callable

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_combine,
    wait_incrementing,
    wait_random,
)

__all__ = ['RetryConfig', 'Retry', 'retry']

#: 项目保留参数名,其余 kwargs 透传给 Tenacity
_PROJECT_PARAMS = frozenset(
    ('max_retries', 'base_delay', 'max_delay', 'exceptions', 'on_retry', 'jitter', 'logger')
)


@dataclass(frozen=True)
class RetryConfig:
    """重试配置,构造时校验参数非法值(抛 ValueError)。

    :param max_retries: 最大重试次数,不含首次执行;0 表示不重试
    :param base_delay: 线性退避基数(秒),第 1 次重试前等待 base_delay
    :param max_delay: 单次等待上限(秒),超过后不再增长
    :param exceptions: 命中这些异常(含子类)才重试,其余立即抛出
    :param on_retry: 每次重试前回调 ``on_retry(attempt, exception, delay)``
    :param jitter: 抖动比例 [0, 1),叠加随机等待 [0, base_delay × jitter)
    :param logger: 自定义日志器,默认 ``logging.getLogger('retry')``
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exceptions: tuple[type[Exception], ...] = (Exception,)
    on_retry: Callable[[int, Exception, float], None] | None = None
    jitter: float = 0.0
    logger: logging.Logger | None = None

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError(f'max_retries 必须 >= 0,实际为 {self.max_retries}')
        if self.base_delay < 0:
            raise ValueError(f'base_delay 必须 >= 0,实际为 {self.base_delay}')
        if self.max_delay < self.base_delay:
            raise ValueError(
                f'max_delay({self.max_delay}) 必须 >= base_delay({self.base_delay})'
            )
        if not 0 <= self.jitter < 1:
            raise ValueError(f'jitter 必须在 [0, 1) 区间,实际为 {self.jitter}')
        if not self.exceptions:
            raise ValueError('exceptions 不能为空')
        for exc in self.exceptions:
            if not (isinstance(exc, type) and issubclass(exc, Exception)):
                raise ValueError(f'exceptions 必须为 Exception 子类,实际为 {exc!r}')


class Retry:
    """过程式重试执行器,内部映射到 Tenacity 的 Retrying。

    每次 ``call()`` 独立状态,无共享可变成员,线程安全。
    """

    def __init__(self, **config: Any) -> None:
        project_kwargs = {k: v for k, v in config.items() if k in _PROJECT_PARAMS}
        self._extra = {k: v for k, v in config.items() if k not in _PROJECT_PARAMS}
        self.config = RetryConfig(**project_kwargs)
        self._logger = self.config.logger or logging.getLogger('retry')

    def _build_tenacity_kwargs(self) -> dict[str, Any]:
        cfg = self.config
        stop = stop_after_attempt(cfg.max_retries + 1)
        wait: Any = wait_incrementing(cfg.base_delay, increment=cfg.base_delay, max=cfg.max_delay)
        if cfg.jitter > 0:
            wait = wait_combine(wait, wait_random(0, cfg.base_delay * cfg.jitter))
        kwargs: dict[str, Any] = {
            'stop': stop,
            'wait': wait,
            'retry': retry_if_exception_type(cfg.exceptions),
            'before_sleep': self._make_before_sleep(),
            'reraise': True,
        }
        # 透传参数覆盖映射结果,保留 Tenacity 高级能力(如 retry=retry_if_result(...))
        kwargs.update(self._extra)
        return kwargs

    def _make_before_sleep(self) -> Callable[[Any], None]:
        on_retry = self.config.on_retry
        logger = self._logger
        max_retries = self.config.max_retries

        def before_sleep(retry_state: Any) -> None:
            # Tenacity 在 before_sleep 触发时 attempt_number 尚未 +1,
            # 该值即本次重试序号(第 1 次重试 = 1)
            attempt = retry_state.attempt_number
            exception = retry_state.outcome.exception()
            delay = retry_state.next_action.sleep
            logger.warning(
                '第 %d/%d 次重试,%.3f 秒后重试: %s: %s',
                attempt, max_retries, delay,
                type(exception).__name__, exception,
            )
            if on_retry is not None:
                on_retry(attempt, exception, delay)

        return before_sleep

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """执行 func,失败时按配置线性退避重试,用尽后重抛最后一次原始异常。"""
        return Retrying(**self._build_tenacity_kwargs())(func, *args, **kwargs)


def retry(**config: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """声明式重试装饰器,等价于 ``Retry(**config).call(fn)``。

    用法::

        @retry(max_retries=3, base_delay=1.0, max_delay=10.0,
               exceptions=(TimeoutError, ConnectionError))
        def fetch(...): ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return Retry(**config).call(func, *args, **kwargs)

        return wrapper

    return decorator
