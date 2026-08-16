# 线性退避重试模块设计方案(基于 Tenacity 薄封装)

> 状态:待评审
> 范围:新建 `core/stable/retry`,基于第三方库 **Tenacity** 做**薄封装**,供全系统调用。本文档为设计稿,不含落地代码。
> 版本:V2(由"自研线性退避"改为"Tenacity 薄封装")

---

## 1. 背景与决策

### 1.1 现状问题

项目目前的重试逻辑分散且不统一:

| 位置 | 现状 | 问题 |
|---|---|---|
| [scripts/utils.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/scripts/utils.py) | `wait_for_http_service` / `wait_for_tcp_service` 固定延时重试 | 固定间隔无退避、异常不可配置、无回调钩子 |
| [services/agent/config/settings.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/settings.py) | `retry_times` / `retry_delay` 固定延时 | 仅 agent 内部配置,无法复用 |
| 各服务调用点 | 散落的 try/except + time.sleep | 无统一规范 |

### 1.2 决策:采用 Tenacity + 薄封装

**为什么选 Tenacity**:
- 功能全:多种退避策略(`wait_incrementing` 即线性退避)、`stop` / `wait` / `retry` 条件可任意组合、`before_sleep` / `after_attempt` 回调、默认重抛原异常。
- 成熟稳定、社区广泛使用,无需自研轮子。

**为什么还要薄封装一层**(不直接散用):
- **统一入口与默认配置**:默认值(重试 3 次、1s/2s/3s)只在一处定义,改一处全系统生效;直接散用则每个调用点重复写配置。
- **可换实现**:调用方只依赖项目 API,未来 Tenacity 换掉或自研,调用点零改动。
- **语义坑集中处理**:`stop_after_attempt` 含首次调用、`reraise` 默认包装 `RetryError` 等坑在封装层一次性解决,调用方不感知。
- **与现有架构一致**:[core/kafka](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py) 本就是包装 `kafka-python` 的模式,`core/stable/retry` 同样定位。

---

## 2. 目标与非目标

### 2.1 目标

1. 基于 Tenacity 提供项目统一的线性退避重试入口。
2. 参数化配置:`max_retries` / `base_delay` / `max_delay` / `exceptions` / `on_retry`。
3. 双形态 API(装饰器 + 类调用),支持透传 Tenacity 原生参数保留高级能力。

### 2.2 非目标

- **不直接散用 Tenacity**:调用方不直接 `import tenacity`(透传参数除外)。
- **不封装 Tenacity 全部能力**:只封装本项目需要的子集,高级场景走透传。
- **不改造现有固定延时重试点**:旧代码不动,后续可选择性迁移。
- **不支持异步**:当前系统全同步(`kafka-python` / `requests`),Tenacity 的 async 能力用不上。

---

## 3. 设计原则

1. **薄封装**:只做三件事——参数映射、项目默认值、`on_retry` 签名适配。不引入额外框架逻辑。
2. **双形态 API**:`@retry(**config)` 装饰器 + `Retry(**config).call(fn)` 类调用。
3. **白名单异常**:只对 `exceptions` 指定的异常重试,其余异常立即抛出。
4. **用尽重抛原异常**:通过 `reraise=True` 保证抛出的是最后一次原始异常,而非 Tenacity 的 `RetryError` 包装,调用方 `try/except` 行为与不加重试一致。
5. **透传机制**:封装层无法覆盖的高级场景,可通过 `**kwargs` 直接透传 Tenacity 原生参数。
6. **线程安全**:每次调用独立状态,无共享可变成员。

---

## 4. 参数设计

### 4.1 必选参数(用户指定)

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `max_retries` | `int` | `3` | 最大重试次数,**不含首次执行**。`0` 表示不重试 |
| `base_delay` | `float` | `1.0` | 线性退避基数(秒),第 1 次重试前等待 `base_delay` |
| `max_delay` | `float` | `10.0` | 单次等待上限(秒),超过后不再增长 |
| `exceptions` | `tuple[type[Exception], ...]` | `(Exception,)` | 命中这些异常(含子类)才重试;不在其中立即抛出 |
| `on_retry` | `Callable` | `None` | 每次重试前回调,签名 `on_retry(attempt, exception, delay)`,用于日志/计数/告警 |

### 4.2 可选参数(酌情优化)

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `jitter` | `float` | `0.0` | 抖动比例(`0`~`1`),叠加随机等待 `[0, base_delay × jitter)` 分散集群请求防惊群 |
| `logger` | `logging.Logger` | `None` | 自定义日志器,默认 `logging.getLogger('retry')` |

### 4.3 参数校验(`__post_init__` 抛 `ValueError`)

- `max_retries >= 0`
- `base_delay >= 0`
- `max_delay >= base_delay`
- `jitter` 在 `[0, 1)` 区间
- `exceptions` 非空且均为 `Exception` 子类

---

## 5. Tenacity 映射设计

### 5.1 参数映射表

| 项目参数 | Tenacity 原生 | 说明 |
|---|---|---|
| `max_retries=3` | `stop_after_attempt(4)` | **`stop_after_attempt` 的计数包含首次调用**,故 +1 |
| `base_delay` / `max_delay` | `wait_incrementing(start=base, increment=base, max=max)` | `wait_incrementing` 即线性退避:第 n 次等待 `start + (n-1) × increment`,封顶 `max` |
| `jitter > 0` | `wait_combine(线性, wait_random(0, base × jitter))` | 在确定性线性等待上叠加随机量 |
| `exceptions` | `retry_if_exception_type(exceptions)` | 白名单(isinstance,含子类) |
| `on_retry` | `before_sleep` | 见 5.2 签名适配 |
| 用尽重抛 | `reraise=True` | **Tenacity 默认 `reraise=False`,耗尽抛 `RetryError` 包装**,必须显式开启才重抛原异常 |

### 5.2 关键语义差异与处理

1. **`stop_after_attempt` 含首次调用**:`max_retries=3` → `stop_after_attempt(4)`;`max_retries=0` → `stop_after_attempt(1)`。此换算集中在封装层,调用方无需关心。
2. **`reraise=True`**:保证耗尽后抛出的是最后一次原始异常实例(非 `RetryError`),与"不加重试时 try/except 行为一致"的设计目标对齐。
3. **`on_retry` 签名适配**:Tenacity 回调接收 `RetryCallState` 对象,封装层转换为项目签名 `(attempt, exception, delay)`:
   - `attempt = retry_state.attempt_number`(`before_sleep` 触发时 Tenacity 尚未 +1,该值即本次重试序号,1 起:第 1 次重试 = 1)
   - `exception = retry_state.outcome.exception()`
   - `delay = retry_state.next_action.sleep`(`before_sleep` 触发时已计算好本次等待)

### 5.3 透传机制

`retry(**config)` 和 `Retry(**config)` 中,除项目参数外的其他 `kwargs` 直接传给 Tenacity,保留其高级能力(如 `retry=retry_if_result(...)` 按返回值重试、`after_attempt` 等)。

```python
@retry(max_retries=3, retry=retry_if_result(lambda r: r.get('status') == 'failed'))
def call_dify(...): ...
```

---

## 6. 模块结构

```
core/stable/retry/
├── __init__.py     # 对外导出: retry / Retry / RetryConfig
└── retry.py        # RetryConfig 数据类 + Retry 执行器 + retry 装饰器(内部映射 Tenacity)
```

> 相较 V1 移除了 `backoff.py`(退避策略改由 Tenacity `wait_incrementing` 承担,无需自研)。
> 需同时创建 `core/stable/__init__.py`(空),保证 `core.stable.retry` 可被全系统 `import`。

### 6.1 关键代码设计(伪代码)

```python
from tenacity import (
    Retrying, stop_after_attempt, wait_incrementing,
    wait_random, wait_combine, retry_if_exception_type,
)

@dataclass(frozen=True)
class RetryConfig:
    """重试配置,参数见第 4 节;__post_init__ 做参数校验。"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exceptions: tuple[type[Exception], ...] = (Exception,)
    on_retry: Callable[[int, Exception, float], None] | None = None
    jitter: float = 0.0
    logger: logging.Logger | None = None


class Retry:
    """过程式重试执行器,内部映射到 Tenacity 的 Retrying。每次 call() 独立状态。"""

    def __init__(self, **config) -> None:
        self.config = RetryConfig(**config)

    def _build_tenacity_kwargs(self) -> dict:
        """项目参数 → Tenacity 参数(见 5.1 映射表)。"""
        stop = stop_after_attempt(self.config.max_retries + 1)
        wait = wait_incrementing(self.config.base_delay,
                                 increment=self.config.base_delay,
                                 max=self.config.max_delay)
        if self.config.jitter > 0:
            wait = wait_combine(wait, wait_random(0, self.config.base_delay * self.config.jitter))
        return {
            'stop': stop,
            'wait': wait,
            'retry': retry_if_exception_type(self.config.exceptions),
            'before_sleep': self._make_before_sleep(),
            'reraise': True,
        }

    def call(self, func, *args, **kwargs):
        """执行 func,失败时按配置线性退避重试,用尽后重抛最后异常。"""
        # tenacity 9.x 使用 __call__,旧版 .call 已被移除
        return Retrying(**self._build_tenacity_kwargs())(func, *args, **kwargs)

    @staticmethod
    def _make_before_sleep():
        """把项目签名 (attempt, exception, delay) 适配为 Tenacity before_sleep 回调。"""


def retry(**config):
    """声明式装饰器,等价于 Retry(**config).call(fn)。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return Retry(**config).call(func, *args, **kwargs)
        return wrapper
    return decorator
```

---

## 7. 使用示例

### 7.1 装饰器(声明式)

```python
from core.stable.retry import retry

@retry(
    max_retries=3, base_delay=1.0, max_delay=10.0,
    exceptions=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
    on_retry=lambda attempt, exception, delay: logger.warning(
        f'Dify 调用第 {attempt} 次重试,{delay:.1f}s 后重试: {exception}'
    ),
)
def call_dify(query: str) -> dict:
    return client.send_message(query)
```

### 7.2 类调用(过程式)

```python
from core.stable.retry import Retry

result = Retry(max_retries=3, base_delay=1.0, max_delay=10.0).call(
    kafka_producer.send, topic='log.analysis', value=message
)
```

### 7.3 默认参数最小用法

```python
@retry()
def fetch_config():
    ...   # 默认:最多重试 3 次,等待 1s/2s/3s,对所有 Exception 重试
```

---

## 8. 边界与防御

| 场景 | 行为 |
|---|---|
| `max_retries=0` | `stop_after_attempt(1)`,仅执行一次 |
| 异常不在 `exceptions` 白名单 | `retry_if_exception_type` 判定不命中,立即抛出 |
| `base_delay=0` | 线性等待为 0,连续快速重试 |
| `base_delay × attempt > max_delay` | `wait_incrementing` 按 `max` 封顶 |
| 重试全部耗尽 | `reraise=True`,重抛最后一次**原始异常** |
| 参数非法 | `RetryConfig` 构造时抛 `ValueError` |
| 并发调用 | 安全,`call()` 内状态均为局部变量 |
| 回调 `on_retry` 自身抛异常 | 不吞,直接向外抛出(不参与重试) |
| 被装饰函数为幂等函数 | 默认假设调用方自行保证幂等(重试语义要求) |

---

## 9. 依赖变更(已落地)

- [requirements.txt](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/requirements.txt) 已增加 `tenacity==9.1.4`。
- **注意**:tenacity 9.x 移除了 `Retrying.call`,统一使用 `Retrying(...)(fn, ...)`(`__call__`)。封装层已按 9.x API 实现。
- 影响面:仅新增依赖,无版本冲突风险(纯标准库依赖的独立包)。
- 运行时环境需执行 `pip install tenacity`(开发机沙箱限制系统目录写入,已临时装至项目内 `.test_deps` 用于测试)。

---

## 10. 测试方案(落地阶段)

| 测试 | 内容 | 手段 |
|---|---|---|
| 成功路径 | 首次即成功,`func` 只调用 1 次 | mock 计数 |
| 重试成功 | 失败 N 次(N<max_retries)后成功 | 测试用 `base_delay=0` 免等待,断言调用总次数 = N+1 |
| 耗尽重抛 | 始终失败,重抛**原异常实例**(非 `RetryError`) | 断言 `raises` 且异常为同一实例 |
| 白名单过滤 | 非白名单异常立即抛出、不重试 | `raises` + 调用计数为 1 |
| 回调触发 | `on_retry` 收到正确的 attempt/exception/delay | mock 断言参数 |
| stop 语义 | `max_retries=3` 时实际最多执行 4 次 | 断言调用计数 |
| jitter | 开启后等待为 `[线性, 线性+随机)` 区间 | mock `Retrying` 或校验映射参数 |

> 测试文件已落地至 [core/stable/retry/test_retry.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/stable/retry/test_retry.py),共 22 个用例全部通过;通过 mock `time.sleep` 记录延迟序列,避免真实等待。Tenacity 本身无需测试,只测封装层行为与映射正确性。

---

## 11. 与现有代码的关系

- **不替换**现有固定延时重试([scripts/utils.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/scripts/utils.py)、agent `PROCESS_CONFIG`),避免影响启动脚本与存量行为。
- **新增代码优先使用**新模块,作为统一重试入口。
- **潜在应用点**(本次不落地,记录备查):
  - agent Dify 网络调用([services/agent/dify/client.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/dify/client.py) 的 `send_message`)
  - Kafka producer `send` 失败重试
  - 后续其他网络/外部依赖调用

---

## 12. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-15 | V1:自研线性退避方案(已废弃,仅存档) |
| 2026-08-15 | V2:改为基于 Tenacity 薄封装,新增参数映射表、语义差异处理、透传机制;移除自研 backoff.py |
| 2026-08-15 | V3:落地实现。修正两点与 tenacity 9.x 实际的差异:`attempt = attempt_number`(非 -1)、`Retrying(...)(fn)`(非 `.call`);requirements 增加 `tenacity==9.1.4`;新增 22 个测试用例全部通过 |
