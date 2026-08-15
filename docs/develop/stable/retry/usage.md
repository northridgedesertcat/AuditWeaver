# 线性退避重试模块功能文档

> 模块位置:[core/stable/retry](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/stable/retry)
> 设计文档:[design.md](./design.md)
> 依赖:Tenacity 9.x(见 [requirements.txt](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/requirements.txt))

---

## 1. 模块概述

基于 **Tenacity** 的薄封装,为全系统提供**统一的线性退避重试入口**。调用方只依赖项目 API,不直接接触 Tenacity,未来更换实现不影响调用点。

**默认行为**:最多重试 3 次,等待序列 **1s → 2s → 3s**(线性递增,封顶 10s),对 `Exception` 及其子类重试,耗尽后重抛**最后一次原始异常**。

---

## 2. 功能特性

| # | 特性 | 说明 |
|---|---|---|
| 1 | 线性退避 | 第 n 次重试等待 `base_delay × n`,超过 `max_delay` 封顶 |
| 2 | 双形态 API | 装饰器 `@retry(...)`(声明式)+ 类 `Retry(...).call(fn)`(过程式) |
| 3 | 异常白名单 | 只对 `exceptions` 指定的异常(含子类)重试,其余**立即抛出** |
| 4 | 重试回调 | `on_retry(attempt, exception, delay)`,用于日志/计数/告警 |
| 5 | 自动日志 | 每次重试自动打 `warning`,默认 logger 为 `retry` |
| 6 | 抖动 | `jitter` 叠加随机等待,分散集群请求防惊群(默认关闭) |
| 7 | 重抛原异常 | 耗尽后抛 `reraise` 原始异常实例,`try/except` 行为与无重试一致 |
| 8 | 透传能力 | 除项目参数外的 kwargs 直接传给 Tenacity,保留高级功能 |
| 9 | 参数校验 | 非法参数构造时抛 `ValueError`,错误尽早暴露 |
| 10 | 线程安全 | 每次调用独立状态,可安全并发使用 |
| 11 | 零侵入 | 保留函数元数据(`functools.wraps`) |

---

## 3. 快速开始

```python
from core.stable.retry import retry, Retry

# 方式一:装饰器(推荐)
@retry()
def call_dify(query: str) -> dict:
    return client.send_message(query)

# 方式二:类调用(临时包一层,不改函数定义)
result = Retry().call(kafka_producer.send, topic='log.analysis', value=msg)
```

以上均为默认参数:重试 3 次、1s/2s/3s、对所有 `Exception` 重试。

---

## 4. API 参考

### 4.1 `retry(**config)` — 声明式装饰器

等价于 `Retry(**config).call(fn)`。用在函数定义上,函数每次调用自动带重试。

```python
@retry(max_retries=3, base_delay=1.0, max_delay=10.0,
       exceptions=(TimeoutError, ConnectionError))
def fetch(url: str) -> dict:
    ...
```

### 4.2 `Retry(**config)` — 过程式执行器

适合不想改函数定义、或需要临时配置重试的场景。每次 `.call()` 独立状态。

```python
r = Retry(max_retries=2, base_delay=0.5)
result = r.call(some_func, arg1, kw=2)
```

### 4.3 `RetryConfig` — 参数说明

以下参数**均可在每个调用点单独传**;不传则用默认值。

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `max_retries` | `int` | `3` | 最大重试次数,**不含首次执行**;`0` 表示不重试 |
| `base_delay` | `float` | `1.0` | 线性退避基数(秒),第 1 次重试前等待 `base_delay` |
| `max_delay` | `float` | `10.0` | 单次等待上限(秒),超过后不再增长 |
| `exceptions` | `tuple[type[Exception], ...]` | `(Exception,)` | 命中这些异常(含子类)才重试;不在其中**立即抛出** |
| `on_retry` | `Callable` | `None` | 每次重试前回调,签名 `on_retry(attempt, exception, delay)` |
| `jitter` | `float` | `0.0` | 抖动比例 `[0, 1)`,叠加随机等待 `[0, base_delay × jitter)` |
| `logger` | `logging.Logger` | `None` | 自定义日志器,默认 `logging.getLogger('retry')` |

**参数校验规则**(不满足即抛 `ValueError`):

- `max_retries >= 0`
- `base_delay >= 0`
- `max_delay >= base_delay`
- `jitter` 在 `[0, 1)` 区间
- `exceptions` 非空,且均为 `Exception` 子类

---

## 5. 参数自定义能力(重点)

**支持。每个调用点都可以独立自定义参数,互不影响。**

- 装饰器与类调用的参数**只作用于当前函数/本次调用**,不产生任何全局状态或配置污染。
- 未指定的参数使用默认值;指定的参数完全覆盖默认值。
- 因此同样的函数,不同调用点可以有不同的重试策略:

```python
# 调用点 A:网络抖动场景,重试次数少、间隔短
@retry(max_retries=2, base_delay=0.5,
       exceptions=(TimeoutError,))
def call_a(): ...

# 调用点 B:外部服务不稳定,重试次数多、间隔长 + 抖动
@retry(max_retries=5, base_delay=2.0, max_delay=30.0, jitter=0.3,
       exceptions=(ConnectionError, TimeoutError))
def call_b(): ...
```

### 5.1 透传 Tenacity 原生参数

除上表 7 个参数外的 kwargs **直接透传给 Tenacity**,可组合出高级重试条件(透传参数优先级高于内部映射):

```python
from tenacity import retry_if_result

# 按返回值重试:返回 status=failed 也重试
@retry(max_retries=3,
       retry=retry_if_result(lambda r: r.get('status') == 'failed'))
def call_dify(...): ...
```

> 注意:`retry_if_result` 与异常重试是**叠加**关系(内部 `retry` 条件为 `retry_if_exception_type`,透传的 `retry` 会覆盖它——如想同时生效,需用 `retry_any` 自行组合)。透传参数列表以 [Tenacity 文档](https://tenacity.readthedocs.io/) 为准。

---

## 6. 使用示例

### 6.1 只重试指定异常

```python
import requests

@retry(max_retries=3, base_delay=1.0, max_delay=10.0,
       exceptions=(requests.exceptions.Timeout,
                   requests.exceptions.ConnectionError))
def call_dify(query: str) -> dict:
    return client.send_message(query)
```

### 6.2 带日志回调

```python
@retry(max_retries=3, base_delay=1.0, max_delay=10.0,
       on_retry=lambda a, e, d: logger.warning(
           f'Dify 第 {a} 次重试,{d:.1f}s 后重试: {e}'))
def call_dify(query: str) -> dict:
    ...
```

`on_retry` 参数说明:

| 参数 | 类型 | 含义 |
|---|---|---|
| `attempt` | `int` | 本次是第几次重试(1 起) |
| `exception` | `Exception` | 触发本次重试的异常对象 |
| `delay` | `float` | 本次重试前将等待的秒数(已含 jitter) |

### 6.3 快速失败探测(不等待)

```python
# base_delay=0:连续快速重试,适合本地探测场景
@retry(max_retries=3, base_delay=0)
def probe(): ...
```

### 6.4 指定自定义日志器

```python
import logging
log = logging.getLogger('my_module')

@retry(max_retries=3, logger=log)
def work(): ...
```

---

## 7. 边界行为

| 场景 | 行为 |
|---|---|
| `max_retries=0` | 仅执行一次,不重试 |
| 异常不在 `exceptions` 白名单 | 立即抛出,不重试不等待 |
| `base_delay=0` | 连续快速重试(等待 0) |
| `base_delay × n > max_delay` | 按 `max_delay` 等待 |
| 重试全部耗尽 | 重抛**最后一次原始异常**(非 Tenacity 的 `RetryError` 包装) |
| 参数非法 | 构造时抛 `ValueError` |
| `on_retry` 回调自身抛异常 | 不吞,直接向外抛出(不参与重试) |
| 并发调用同一 `Retry` 实例 | 安全,`.call()` 内状态均为局部变量 |

---

## 8. 注意事项

1. **幂等性由调用方保证**:重试意味着函数可能被执行多次,请确保被装饰函数**幂等**(如 Dify 请求、Kafka send 等重复执行无副作用)。
2. **依赖**:运行时环境需安装 `tenacity==9.1.4`(`pip install -r requirements.txt`)。模块基于 tenacity 9.x API(`Retrying(...)(fn)` 形式)实现,不兼容旧版 8.x 的 `.call` 写法(该差异已在封装层内部处理,调用方无感)。
3. **日志**:默认每次重试打 `warning`(logger 名 `retry`),如不想被打扰,传一个 `logging.NullHandler` 的 logger,或用 `on_retry` 自行控制。
4. **不要直接 import tenacity**:除非需要透传高级参数,否则一律走本模块入口,保持可替换性。

---

## 9. 运行测试

```bash
# 项目根目录下(需已安装 tenacity)
python -m unittest core.stable.retry.test_retry -v
```

共 22 个用例,覆盖:默认值、参数校验、首次成功、重试成功、耗尽重抛原实例、白名单过滤(含子类)、回调参数正确性、延迟序列与封顶、jitter 区间、装饰器元数据、透传、并发安全。
