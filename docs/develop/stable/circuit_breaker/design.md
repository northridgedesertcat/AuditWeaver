# 熔断器模块设计方案(基于 PyBreaker 薄封装)

> 状态:待评审
> 范围:新建 `core/stable/circuit_breaker`,基于第三方库 **PyBreaker** 做**薄封装**,供全系统调用。本文档为设计稿,不含落地代码。
> 版本:V1
> 首个接入点:agent 模块的 Dify 调用(线性退避重试 + 熔断组合,给 Dify 过载时的喘息机会)

---

## 1. 背景与决策

### 1.1 现状问题

agent 模块目前对 Dify 的调用逻辑([services/agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py) 的 `process_log`):

1. 单条日志消息通过 `Retry`(线性退避,2s/4s/6s,最多重试 3 次)调用 Dify `analyze_log`;
2. 重试耗尽仍失败 → 消息直接进 DLQ。

**缺少"整体保护"**:当 Dify 过载或不可用时:

- 每条消息都要完整走完 3 次重试(最多 3 次真实请求)才放弃,加剧 Dify 压力;
- 下一批消息继续同样的流程,形成"排队重试风暴",Dify 无喘息机会;
- 重试只管单次调用的节奏,不关心"系统整体是否已连续失败多时"。

### 1.2 决策:采用 PyBreaker + 薄封装

**为什么选 PyBreaker**:

| 维度 | PyBreaker | circuitbreaker(fabfuel) |
|---|---|---|
| 依赖 | **零依赖**(纯标准库) | 无硬依赖,但生态较重 |
| 维护活跃度 | 2025-09 发布 v1.4.1,2026 仍在维护 | 更新较慢 |
| API 形态 | 装饰器 / `cb.call()` / `with cb.calling()` 三种 | 以装饰器为主 |
| 状态机 | CLOSED / OPEN / HALF_OPEN,`success_threshold` 支持半开多探针(1.4.0 新增) | 基础三态 |
| 事件监听 | `CircuitBreakerListener`(before_call / state_change / failure / success),便于日志与告警 | 无 |
| 线程安全 | 内置 | 内置 |

- **成熟稳定**:自 2009 年维护至今,生产使用多年,930+ 依赖方。
- **薄封装契合**:与现有 `core/stable/retry`(Tenacity 薄封装)同一模式——统一入口、项目默认值、语义坑集中处理、可换实现。
- **同步够用**:项目当前全同步(`requests` / `kafka-python`),PyBreaker 同步支持完备,Tornado/Redis 能力用不上但不碍事。

**为什么还要薄封装一层**(不直接散用):

1. **统一入口与默认配置**:默认值(熔断阈值、冷却时间)只在一处定义。
2. **返回值失败判定适配**:PyBreaker 只认"抛异常"为失败,而 `analyze_log` 的约定是**吞异常返回 `{'status': 'failed'}`**。封装层必须把"返回值失败"转为失败计数,调用方无感知。
3. **熔断打开时的行为归一**:熔断打开时 PyBreaker 抛 `CircuitBreakerError`,封装层统一转成项目语义(可选 `fallback` 或统一异常),调用方 `try/except` 行为一致。
4. **可换实现**:调用方只依赖项目 API,未来换库调用点零改动。

---

## 2. 目标与非目标

### 2.1 目标

1. 基于 PyBreaker 提供项目统一的熔断器入口。
2. 参数化配置:`fail_max` / `reset_timeout` / `success_threshold` / `exceptions`(排除) / `on_state_change`。
3. 支持"按返回值判定失败"(`result_is_failure` 谓词),覆盖 `analyze_log` 吞异常返回 dict 的场景。
4. 与 `core/stable/retry` 可组合使用,成为 agent Dify 调用的外层保护。

### 2.2 非目标

- **不封装 PyBreaker 全部能力**:Redis 集群共享状态、Tornado 异步等本项目用不到,不封装。
- **不替代 retry**:重试管"单次调用的节奏",熔断管"整体开关",两者互补不重叠。
- **不改动现有散落的失败处理**:DLQ 流程、Kafka 发送逻辑不在本次改造范围(除 agent Dify 调用点接入外)。
- **不做异步**:当前系统全同步。

---

## 3. 设计原则

1. **薄封装**:只做四件事——参数映射、项目默认值、返回值失败适配、熔断打开行为归一。
2. **类调用为主、装饰器为辅**:与 `Retry(**config).call(fn)` 一致的风格。
3. **失败白名单**:`exceptions` 指定的异常才计入失败(默认全部 `Exception`);业务异常可通过排除机制不计数。
4. **返回值失败适配**:`result_is_failure(result) -> bool` 为真时计一次失败,但**仍把原始结果返回给调用方**,不改变调用约定。
5. **熔断打开默认快速失败**:不再调用目标函数,抛 `CircuitOpenError`(或按 `fallback` 返回默认值)。
6. **线程安全**:PyBreaker 实例本身线程安全,全局单例复用一个实例。

---

## 4. 参数设计

### 4.1 参数表

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `fail_max` | `int` | `5` | 连续失败次数阈值,达到即熔断(OPEN)。`0` 禁用熔断 |
| `reset_timeout` | `float` | `30.0` | 冷却时间(秒),熔断后经过该时长才允许进入 HALF_OPEN 放行探测 |
| `success_threshold` | `int` | `2` | HALF_OPEN 状态下连续成功该次数才 CLOSED(防抖动,1.4.0+ 支持) |
| `exceptions` | `tuple[type[Exception], ...]` | `(Exception,)` | 命中这些异常(含子类)才计失败;不在其中不计失败、原样抛出 |
| `on_state_change` | `Callable[[str, str], None]` | `None` | 状态变化回调 `on_state_change(old_state, new_state)`,用于日志/告警 |
| `name` | `str` | `'circuit_breaker'` | 熔断器名称,用于日志与多实例区分 |
| `logger` | `logging.Logger` | `None` | 自定义日志器,默认 `logging.getLogger('circuit_breaker')` |

### 4.2 参数校验(构造时抛 `ValueError`)

- `fail_max >= 0`
- `reset_timeout > 0`
- `success_threshold >= 1`
- `exceptions` 非空且均为 `Exception` 子类

---

## 5. 状态机与 PyBreaker 映射

### 5.1 三态状态机

```
CLOSED --连续 fail_max 次失败--> OPEN
OPEN   --经过 reset_timeout--> HALF_OPEN(下一次调用放行)
HALF_OPEN --成功--> 连续成功 success_threshold 次 -> CLOSED
HALF_OPEN --失败--> OPEN(重新计时)
```

### 5.2 参数映射表

| 项目参数 | PyBreaker 原生 | 说明 |
|---|---|---|
| `fail_max` | `fail_max` | 连续失败计数,与 `retry` 的 `max_retries` 语义不同(那是单次调用内) |
| `reset_timeout` | `reset_timeout` | 冷却秒数 |
| `success_threshold` | `success_threshold` | **PyBreaker 默认只放行 1 次探测即关闭**(旧版语义);1.4.0 起可配多探针 |
| `exceptions` | `exclude`(反向) | PyBreaker 是"排除白名单",封装层换算:计失败 = 抛出的异常**不在** `exceptions` 之外,等价于只对 `exceptions` 计失败 |
| `on_state_change` | `listeners=[StateChangeListener]` | 监听器适配为项目回调 |
| 失败判定(异常) | `cb.call(fn)` 捕获异常 | PyBreaker 原生:抛异常即失败 |
| 失败判定(返回值) | **不支持** | 封装层引入内部 `_ResultFailure` 异常桥接(见 6.2) |
| 熔断打开 | 抛 `CircuitBreakerError` | 封装层转成项目 `CircuitOpenError` 或 `fallback` |

### 5.3 关键语义差异与处理

1. **`success_threshold` 语义**:PyBreaker 1.4.0 前 HALF_OPEN 放行 1 次成功后即关闭;配置 `success_threshold=2` 可避免"放行一次恰好成功就关闭,紧接着又失败"的抖动。默认取 2。
2. **`exclude` 反向换算**:PyBreaker 的 `exclude` 是"这些异常不计失败";项目语义是"`exceptions` 白名单内才计失败"。封装层构造时传 `exclude = 除 exceptions 外的 Exception 全集`(即 `[e for e in (Exception,) if not issubclass(...)]` 思路的补集)。对默认 `(Exception,)`,`exclude` 为空即可。
3. **熔断打开不执行目标函数**:PyBreaker 直接抛 `CircuitBreakerError`,此时**重试层不会执行**,消息快速失败,达到"给 Dify 喘息"的目的。

---

## 6. 模块结构

```
core/stable/circuit_breaker/
├── __init__.py              # 对外导出: CircuitBreaker / CircuitBreakerConfig / CircuitOpenError
└── circuit_breaker.py       # CircuitBreakerConfig 数据类 + CircuitBreaker 执行器
```

### 6.1 核心 API(伪代码)

```python
@dataclass(frozen=True)
class CircuitBreakerConfig:
    """熔断器配置,参数见第 4 节;__post_init__ 做参数校验。"""
    fail_max: int = 5
    reset_timeout: float = 30.0
    success_threshold: int = 2
    exceptions: tuple[type[Exception], ...] = (Exception,)
    on_state_change: Callable[[str, str], None] | None = None
    name: str = 'circuit_breaker'
    logger: logging.Logger | None = None


class CircuitOpenError(Exception):
    """熔断打开时抛出的项目统一异常(封装自 pybreaker.CircuitBreakerError)。"""


class CircuitBreaker:
    def __init__(self, **config): ...
        # 内部持有 pybreaker.CircuitBreaker 实例

    def call(self, fn, *args, result_is_failure=None, fallback=None, **kwargs):
        """执行 fn;熔断打开时快速失败。"""
```

### 6.2 返回值失败桥接(核心适配)

```python
class _ResultFailure(Exception):
    """内部异常:标记"返回值判定为失败",仅用于让 PyBreaker 计数失败。"""

    def __init__(self, result): 
        self.result = result

def call(self, fn, *args, result_is_failure=None, fallback=None, **kwargs):
    def _wrapper():
        result = fn(*args, **kwargs)
        if result_is_failure is not None and result_is_failure(result):
            raise _ResultFailure(result)   # 抛异常 -> PyBreaker 计失败
        return result

    try:
        return self._pybreaker.call(_wrapper)
    except _ResultFailure as e:
        return e.result                    # 失败已计数,原结果原样返回给调用方
    except pybreaker.CircuitBreakerError:
        if fallback is not None:
            return fallback(*args, **kwargs)  # 熔断打开:走降级
        raise CircuitOpenError(f'{self.config.name} 熔断打开,拒绝调用') from None
```

关键点:

- `analyze_log` 返回 `{'status': 'failed'}` 时,`result_is_failure` 命中 → 内部异常 → PyBreaker 计数失败 → 捕获后仍返回原 dict,`process_log` 的既有分支逻辑零改动;
- 熔断打开期间 `_wrapper` 不会被调用(PyBreaker 直接抛 `CircuitBreakerError`),即**不再发请求到 Dify**;
- `fallback` 可选,agent 场景可用它返回 `{'status': 'failed', 'error': 'circuit_open'}` 保持"永不抛异常"的客户端约定,也可不传让异常向上传播。

---

## 7. 使用示例

### 7.1 与 Retry 组合(agent Dify 接入,目标形态)

熔断器包在重试**外层**:单条消息的 3 次重试整体计 1 次成败,连续 `fail_max` 条消息失败才熔断——符合"几个数据都不行之后,就熔断"的语义。

```python
from core.stable.circuit_breaker import CircuitBreaker
from core.stable.retry import Retry
from tenacity import retry_if_result

# 重试:单条消息内的线性退避(2s/4s/6s)
self.dify_retry = Retry(
    max_retries=PROCESS_CONFIG['retry_times'],
    base_delay=PROCESS_CONFIG['retry_delay'],
    max_delay=PROCESS_CONFIG['retry_max_delay'],
    retry=retry_if_result(lambda r: r.get('status') == 'failed'),
    retry_error_callback=lambda rs: rs.outcome.result(),
)

# 熔断:连续 5 条消息失败 -> 熔断 30s,半开需 2 次成功才恢复
self.dify_breaker = CircuitBreaker(
    fail_max=CIRCUIT_CONFIG['fail_max'],
    reset_timeout=CIRCUIT_CONFIG['reset_timeout'],
    success_threshold=CIRCUIT_CONFIG['success_threshold'],
    name='dify',
    on_state_change=lambda old, new: logger.warning(
        f'Dify 熔断器状态变化: {old} -> {new}'),
)

# process_log 中:
response = self.dify_breaker.call(
    lambda msg: self.dify_retry.call(self.dify_client.analyze_log, msg),
    raw_message,
    result_is_failure=lambda r: r.get('status') == 'failed',
)
```

时序效果:

| 阶段 | 行为 |
|---|---|
| CLOSED 期 | 每条消息走完整线性退避重试;单条彻底失败计 1 次失败 |
| 连续 5 条失败 | 熔断 OPEN,后续消息**不再调用 Dify**,快速失败 |
| OPEN 30s 后 | HALF_OPEN 放行 1 条消息走真实调用 |
| 半开期成功 | 连续 2 条成功 → CLOSED 恢复;任一条失败 → 重新 OPEN 计时 |

### 7.2 熔断打开时的消息去向(agent 落地决策点)

熔断打开后 `process_log` 会收到 `CircuitOpenError`(或 fallback 的 failed dict),走现有 except/DLQ 分支。**注意**:熔断期每条消息都会快速失败,可能打爆 DLQ。落地时可选的三个策略(本次封装不实现,记录备查):

1. 熔断期消息照常进 DLQ(简单,但 DLQ 量激增);
2. 熔断期暂停消费(pause consumer),恢复后重新消费(推荐,Kafka offset 天然支持);
3. 熔断期消息发送回原 topic 延迟重投。

### 7.3 装饰器用法(声明式,其余模块可选用)

```python
from core.stable.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(fail_max=3, reset_timeout=10)

@breaker
def fetch_config():
    ...   # 熔断打开时抛 CircuitOpenError
```

### 7.4 按异常计失败(默认场景,无需 result_is_failure)

```python
# 对抛异常的目标函数,默认即"抛异常计失败"
result = CircuitBreaker(fail_max=5, reset_timeout=60).call(
    requests.get, url, timeout=10,
    exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
)
```

---

## 8. 边界与防御

| 场景 | 行为 |
|---|---|
| `fail_max=0` | 禁用熔断,恒 CLOSED,PyBreaker `fail_max=0` 等效不计数(落地时确认,必要时直接不用封装) |
| 异常不在 `exceptions` 白名单 | 不计失败、原样抛出,不参与熔断 |
| `analyze_log` 返回 failed | `result_is_failure` 命中 → 计失败,但返回值原样返回 |
| 熔断打开 | 目标函数不执行,抛 `CircuitOpenError`(或 `fallback`) |
| HALF_OPEN 探测失败 | 立即重新 OPEN,`reset_timeout` 重新计时 |
| HALF_OPEN 连续成功 `< success_threshold` | 保持 HALF_OPEN,继续放行探测(注意:期间仍有真实调用) |
| 参数非法 | `CircuitBreakerConfig` 构造抛 `ValueError` |
| 并发调用 | PyBreaker 线程安全;同一实例全局复用 |
| 回调 `on_state_change` 自身抛异常 | 不吞,直接向外抛出(不参与熔断) |
| 目标函数自身抛 `CircuitBreakerError` | 极罕见;封装层不预检,统一经 `except CircuitBreakerError` 分支处理,不影响失败计数 |

---

## 9. 依赖变更(已落地)

- [requirements.txt](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/requirements.txt) 已增加 `pybreaker==1.4.1`。
- PyBreaker 要求 Python 3.10+(项目满足)。
- 纯标准库依赖的独立包,无版本冲突风险。
- 运行时环境需执行 `pip install pybreaker`。

---

## 10. 测试方案(已落地)

| 测试 | 内容 | 手段 |
|---|---|---|
| 成功路径 | 首次即成功,目标函数只调 1 次 | mock 计数 |
| 失败计数 | 连续失败 N 次(< fail_max)不熔断 | 断言 `current_state == CLOSED` 与 `fail_counter` |
| 熔断触发 | 连续 `fail_max` 次失败后 OPEN | 断言状态 + 后续调用不再执行目标函数 |
| 熔断恢复 | 冷却后 HALF_OPEN 放行,成功 → CLOSED | mock 时钟或缩短 `reset_timeout` |
| 半开多探针 | `success_threshold=2`,1 次成功不关闭 | 断言状态仍 HALF_OPEN |
| 返回值失败 | `result_is_failure` 命中计失败且返回原结果 | 断言返回 dict 原样 + 失败计数 |
| 熔断打开异常 | OPEN 期调用抛 `CircuitOpenError` | `raises` + 目标函数零调用 |
| fallback | OPEN 期调用返回 fallback 结果 | 断言返回值 |
| 白名单过滤 | 白名单外异常不计失败、立即抛出 | `raises` + `fail_counter` 不变 |
| 状态回调 | `on_state_change` 收到正确的 old/new | mock 断言参数 |

> 测试文件已落地至 [core/stable/circuit_breaker/test_circuit_breaker.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/stable/circuit_breaker/test_circuit_breaker.py),共 23 个用例全部通过;熔断恢复相关用例通过缩短 `reset_timeout` 避免真实等待。PyBreaker 本身无需测试,只测封装层行为与映射正确性。

---

## 11. 与现有代码的关系

- **新增** `core/stable/circuit_breaker`,与 `core/stable/retry` 并列。
- **组合关系**:重试 = 单次调用节奏(线性退避),熔断 = 整体保护开关,两模块独立、可组合、不互相依赖。
- **agent 接入改动**(已落地):
  - [services/agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py):`__init__` 新增 `self.dify_breaker`,`process_log` 中把 `self.dify_retry.call(...)` 改为熔断包重试的组合调用;
  - [services/agent/config/yaml/agent.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/yaml/agent.yaml):新增 `circuit_breaker` 配置段(环境敏感值仍走 `common.env` 注入);

```yaml
circuit_breaker:
  fail_max: 5
  reset_timeout: 30
  success_threshold: 2
```

  - [services/agent/config/settings.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/settings.py) 与 [services/agent/config/__init__.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/__init__.py):读取并导出 `CIRCUIT_CONFIG`。
- **不改造**现有 DLQ / Kafka 发送 / 其他模块;后续其他网络调用可复用本模块。

---

## 12. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-16 | V1:确定选型 PyBreaker 1.4.1 + 薄封装;确定"熔断在重试外层"的组合语义;设计返回值失败桥接与熔断打开行为归一;文档待评审 |
| 2026-08-16 | V2:落地实现。核心模块 + 23 个测试用例全部通过;agent 接入(agent.yaml / settings.py / config __init__ / main.py);requirements 增加 `pybreaker==1.4.1`。落地时修正两点与 PyBreaker 实际的差异:`state_change` 回调收到状态对象(取 `.name` 转字符串)、半开转换由 `calling()` 内部完成(封装层不做 open 预检);`fail_max=0` 实现为禁用熔断直接透传 |
