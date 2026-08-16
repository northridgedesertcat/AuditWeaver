"""熔断器模块(基于 PyBreaker 薄封装)。

提供项目统一的熔断入口:
- ``CircuitBreaker`` 类(过程式,``CircuitBreaker(**config).call(fn, ...)``)
- 熔断器实例可作装饰器(``@breaker``)

内部将项目参数映射到 PyBreaker:

===================  ==================================================
项目参数             PyBreaker 映射
===================  ==================================================
``fail_max``         ``fail_max``(连续失败次数阈值,达到即熔断)
``reset_timeout``    ``reset_timeout``(冷却秒数,熔断后放行探测的间隔)
``success_threshold`` ``success_threshold``(半开状态连续成功次数才关闭)
``exceptions``       ``exclude=[lambda e: not isinstance(e, ...)]``
                     (反向换算:白名单内计失败,白名单外不计失败)
``on_state_change``  ``listeners=[StateChangeListener]``(事件适配)
===================  ==================================================

与 PyBreaker 的关键差异(封装层处理):
1. PyBreaker 只认"抛异常"为失败;``result_is_failure`` 谓词通过内部
   异常桥接,把"返回值失败"也计入失败,且返回值原样返回调用方。
2. 熔断打开时不执行目标函数,抛项目统一的 ``CircuitOpenError``,
   或按 ``fallback`` 返回降级值。
3. ``fail_max=0`` 表示禁用熔断,直接透传执行,不计数。
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Any, Callable

import pybreaker

__all__ = ['CircuitBreakerConfig', 'CircuitBreaker', 'CircuitOpenError']


class CircuitOpenError(Exception):
    """熔断打开时抛出的项目统一异常。"""


class _ResultFailure(Exception):
    """内部异常:标记"返回值判定为失败",仅用于让 PyBreaker 计数失败。"""

    def __init__(self, result: Any) -> None:
        super().__init__('result judged as failure')
        self.result = result


class _StateChangeListener(pybreaker.CircuitBreakerListener):
    """把 PyBreaker 的 state_change 事件适配为项目回调与日志。"""

    def __init__(
        self,
        name: str,
        logger: logging.Logger,
        on_state_change: Callable[[str, str], None] | None,
    ) -> None:
        super().__init__()
        self._name = name
        self._logger = logger
        self._on_state_change = on_state_change

    def state_change(
        self, cb: Any, old_state: Any, new_state: Any
    ) -> None:
        old = old_state.name if old_state is not None else None
        new = new_state.name
        self._logger.warning('熔断器 [%s] 状态变化: %s -> %s', self._name, old, new)
        if self._on_state_change is not None:
            self._on_state_change(old, new)


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """熔断器配置,构造时校验参数非法值(抛 ValueError)。

    :param fail_max: 连续失败次数阈值,达到即熔断;0 表示禁用熔断
    :param reset_timeout: 冷却时间(秒),熔断后经过该时长才允许放行探测
    :param success_threshold: 半开状态下连续成功该次数才关闭
    :param exceptions: 命中这些异常(含子类)才计失败;其余不计失败、原样抛出
    :param on_state_change: 状态变化回调 ``on_state_change(old_state, new_state)``
    :param name: 熔断器名称,用于日志与多实例区分
    :param logger: 自定义日志器,默认 ``logging.getLogger('circuit_breaker')``
    """

    fail_max: int = 5
    reset_timeout: float = 30.0
    success_threshold: int = 2
    exceptions: tuple[type[Exception], ...] = (Exception,)
    on_state_change: Callable[[str, str], None] | None = None
    name: str = 'circuit_breaker'
    logger: logging.Logger | None = None

    def __post_init__(self) -> None:
        if self.fail_max < 0:
            raise ValueError(f'fail_max 必须 >= 0,实际为 {self.fail_max}')
        if self.reset_timeout <= 0:
            raise ValueError(f'reset_timeout 必须 > 0,实际为 {self.reset_timeout}')
        if self.success_threshold < 1:
            raise ValueError(
                f'success_threshold 必须 >= 1,实际为 {self.success_threshold}'
            )
        if not self.exceptions:
            raise ValueError('exceptions 不能为空')
        for exc in self.exceptions:
            if not (isinstance(exc, type) and issubclass(exc, Exception)):
                raise ValueError(f'exceptions 必须为 Exception 子类,实际为 {exc!r}')


class CircuitBreaker:
    """过程式熔断器执行器,内部映射到 PyBreaker。

    - ``call(fn, *args, result_is_failure=None, fallback=None, **kwargs)``:
      执行 fn,失败计数达到阈值后熔断;熔断打开期间不再执行目标函数。
    - 实例可作装饰器 ``@breaker``。
    """

    def __init__(self, **config: Any) -> None:
        self.config = CircuitBreakerConfig(**config)
        self._logger = self.config.logger or logging.getLogger('circuit_breaker')
        self._enabled = self.config.fail_max > 0
        if self._enabled:
            listener = _StateChangeListener(
                self.config.name, self._logger, self.config.on_state_change
            )
            # throw_new_error_on_trip=False:熔断瞬间重抛原始异常,
            # 保证 _ResultFailure 桥接异常能正常传播到封装层
            # exclude 反向换算:白名单外不计失败;_ResultFailure 为内部桥接异常,
            # 必须始终计为失败,不受用户 exceptions 白名单影响
            self._cb = pybreaker.CircuitBreaker(
                fail_max=self.config.fail_max,
                reset_timeout=self.config.reset_timeout,
                success_threshold=self.config.success_threshold,
                exclude=[
                    lambda e: not isinstance(e, self.config.exceptions)
                    and not isinstance(e, _ResultFailure)
                ],
                listeners=[listener],
                name=self.config.name,
                throw_new_error_on_trip=False,
            )
        else:
            self._cb = None

    # -- 状态监控 ---------------------------------------------------

    @property
    def state(self) -> str:
        """当前状态: 'closed' / 'open' / 'half-open'(禁用熔断时恒 'closed')。"""
        if not self._enabled:
            return pybreaker.STATE_CLOSED
        return self._cb.current_state

    @property
    def fail_counter(self) -> int:
        """当前连续失败次数。"""
        return self._cb.fail_counter if self._enabled else 0

    @property
    def success_counter(self) -> int:
        """当前连续成功次数。"""
        return self._cb.success_counter if self._enabled else 0

    # -- 执行入口 ---------------------------------------------------

    def call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        result_is_failure: Callable[[Any], bool] | None = None,
        fallback: Callable[..., Any] | Any = None,
        **kwargs: Any,
    ) -> Any:
        """执行 fn;失败计数达到阈值后熔断,打开期间不再执行目标函数。

        :param fn: 被保护的目标函数
        :param result_is_failure: 可选谓词,``result_is_failure(result)``
            为真时计一次失败,但返回值仍原样返回(适配吞异常返回状态码的场景)
        :param fallback: 可选降级值(或函数);熔断打开时返回它,不抛异常
        """
        if not self._enabled:
            # 禁用熔断:直接透传执行,不做任何计数
            return fn(*args, **kwargs)

        # 半开转换由 PyBreaker 在 calling() 内部完成(open 超时后自动放行),
        # 这里不做预检,只负责把熔断打开期的拒绝统一成项目语义
        try:
            with self._cb.calling():
                result = fn(*args, **kwargs)
                if result_is_failure is not None and result_is_failure(result):
                    raise _ResultFailure(result)
                return result
        except _ResultFailure as e:
            # 失败已计数,原结果原样返回给调用方
            return e.result
        except pybreaker.CircuitBreakerError:
            # 熔断打开且未到 reset_timeout:进入时即拒绝(不执行目标函数)
            if fallback is not None:
                return fallback(*args, **kwargs) if callable(fallback) else fallback
            raise CircuitOpenError(f'{self.config.name} 熔断打开,拒绝调用') from None
        except Exception:
            # fn 的真实异常:PyBreaker 已按白名单计失败或排除,原样向上抛出
            raise

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """声明式装饰器用法: ``@breaker``。"""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(fn, *args, **kwargs)

        return wrapper
