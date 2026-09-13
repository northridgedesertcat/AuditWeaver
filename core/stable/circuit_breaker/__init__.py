"""熔断器模块(基于 PyBreaker 薄封装)。

对外 API:
- ``CircuitBreaker``: 过程式熔断器,``CircuitBreaker(**config).call(fn, ...)``
- ``CircuitBreakerConfig``: 熔断器配置(参数校验)
- ``CircuitOpenError``: 熔断打开时抛出的统一异常
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitOpenError

__all__ = ['CircuitBreaker', 'CircuitBreakerConfig', 'CircuitOpenError']
