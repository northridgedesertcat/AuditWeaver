"""线性退避重试模块(基于 Tenacity 薄封装)。

对外 API:
- ``retry``: 声明式装饰器
- ``Retry``: 过程式执行器,``Retry(**config).call(fn, *args, **kwargs)``
- ``RetryConfig``: 重试配置(参数校验)
"""

from .retry import Retry, RetryConfig, retry

__all__ = ['retry', 'Retry', 'RetryConfig']
