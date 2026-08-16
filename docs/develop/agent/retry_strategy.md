# agent 模块重试策略(接入线性退避重试)

> 状态:待评审
> 范围:为 [services/agent](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent) 接入统一线性退避重试模块 [core/stable/retry](../stable/retry/design.md),本次为**策略设计**,不落地代码。
> 前置结论:Dify 采用**方案 B(按返回值重试)**,不改 `analyze_log` 内部逻辑。

---

## 1. 背景(审计结论)

| # | 发现 | 说明 |
|---|---|---|
| 1 | `retry_times=3` / `retry_delay=2` 是**死配置** | [agent.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/yaml/agent.yaml#L26-L27) 声明、[settings.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/settings.py#L46-L51) 加载,但全项目无任何业务代码消费 |
| 2 | 各调用点**均无真实重试** | Dify 调用、Kafka send 失败均一次放弃 |
| 3 | 失败策略为**一次失败即进 DLQ** | [process_log](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py#L82-L123) 无"先重试再放弃"环节,DLQ `retry_count` 恒为 0 |

---

## 2. 目标

1. 接入 `core/stable/retry` 线性退避,为 Dify 分析与 Kafka 发送提供真实重试。
2. Dify 采用**方案 B**:按返回值(`status == 'failed'`)重试,**不修改** `analyze_log` 内部吞异常逻辑。
3. 重试**耗尽后**才进 DLQ,保持 `process_log` 现有分支结构不变。
4. 复用 [agent.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/yaml/agent.yaml) 现有 `retry_times` / `retry_delay` 配置,避免新增无关配置。

---

## 3. 接入点总览

| 接入点 | 位置 | 重试触发 | 耗尽行为 | 配置来源 |
|---|---|---|---|---|
| Dify 分析 | [main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py) `process_log` | 返回值 `status == 'failed'` | 返回最后失败 dict → 走 DLQ | `PROCESS_CONFIG` |
| Kafka 发送 | `process_log` 内 `send` 调用 | 返回值 `False` | 返回 `False` → 走 DLQ | `PROCESS_CONFIG` |

> 包装点统一放在 `process_log` **调用处**,而非 `client.py` / `producer.py` 内部——配置已在 `main.py` 作用域,改动最小、便于评审;`client.py` / `producer.py` 零改动。

---

## 4. 关键验证:方案 B 必须带 `retry_error_callback`(重要)

`core/stable/retry` 内部固定 `reraise=True`(为异常型重试设计)。当改用**按返回值重试**(`retry_if_result`)时,耗尽行为与异常型不同,已实测验证:

| 场景 | 耗尽时行为 | 结论 |
|---|---|---|
| 仅透传 `retry=retry_if_result(...)` | **抛 `RetryError`**(结果型 outcome 无法 re-raise) | ❌ 会破坏 `process_log` 现有分支,失败原因变成误导性的 `processing_exception` |
| 追加透传 `retry_error_callback=lambda rs: rs.outcome.result()` | **返回最后结果**(失败 dict / `False`) | ✅ `process_log` 原逻辑不变,正常走 DLQ |

**结论**:方案 B 的每次接入**必须**同时透传:

```python
retry_error_callback=lambda rs: rs.outcome.result(),
```

该回调对异常型 outcome 同样成立(调用 `Future.result()` 会重抛原始异常),两种重试语义下耗尽行为都正确。

---

## 5. 接入点 1:Dify 分析(方案 B)

### 5.1 现状

- `analyze_log` **吞掉所有异常**,返回 `{'status': 'success'|'failed', 'error': ...}` → 异常型 `@retry` 对它无效。
- 失败原因(网络异常、HTTP 非 200 等)已由 `analyze_log` 内部 `logger.error` 记录,可作为每次重试的原因日志。

### 5.2 接入方式(`main.py` 调用处)

```python
from tenacity import retry_if_result
from core.stable.retry import Retry

# AgentMain.__init__ 中预构建一次,避免每条消息重复构造
self.dify_retry = Retry(
    max_retries=PROCESS_CONFIG['retry_times'],       # 3
    base_delay=PROCESS_CONFIG['retry_delay'],        # 2.0
    max_delay=PROCESS_CONFIG['retry_max_delay'],     # 10.0
    retry=retry_if_result(lambda r: r.get('status') == 'failed'),
    retry_error_callback=lambda rs: rs.outcome.result(),
)

# process_log 内替换原直调
response = self.dify_retry.call(self.dify_client.analyze_log, raw_message)
```

### 5.3 行为

- `status == 'failed'`(含 Dify 业务失败、网络/超时等被吞异常)→ 线性退避重试,等待序列 **2s → 4s → 6s**。
- 耗尽后返回**最后失败 dict**,`process_log` 走既有 `else` 分支 → DLQ(`failure_reason='dify_analysis_failed: ...'`),**流程与现有一致**。
- 首次成功:零开销,仅一次调用。

---

## 6. 接入点 2:Kafka 发送

### 6.1 现状

- [producer.send()](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/broker/producer.py#L37-L53) 内部 `future.get(timeout=10)` 失败**返回 `False`**(异常也被吞)→ 同样需按返回值重试。
- `connect()` 的 `retries=3` 是 kafka-python 底层内部重试,与应用层重试叠加不冲突,保留不动。

### 6.2 接入方式(`main.py` 调用处)

```python
self.send_retry = Retry(
    max_retries=PROCESS_CONFIG['retry_times'],
    base_delay=PROCESS_CONFIG['retry_delay'],
    max_delay=PROCESS_CONFIG['retry_max_delay'],
    retry=retry_if_result(lambda sent: sent is False),
    retry_error_callback=lambda rs: rs.outcome.result(),
)

# process_log 内替换原直调
if self.send_retry.call(self.kafka_producer.send, document, key=event_id):
    ...
```

---

## 7. 接入点 3:DLQ 时机与 `retry_count`

### 7.1 时机(本次落地)

重试耗尽 → 返回失败结果 → 走 `process_log` 现有 DLQ 分支。**无需改动 DLQ 调用结构**,且天然满足"先重试、再进死信"。

### 7.2 `retry_count` 记录(可选优化,本次不做)

[dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py#L74-L89) 的 `send_dlq` 固定 `retry_count: 0`。可选增强:

- `send_dlq` 增加参数 `retry_count: int = 0`;
- 在 `retry_error_callback` 内通过闭包捕获 `rs.attempt_number`,耗尽时传给 `send_dlq`。

> 涉及 [core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py) 变更(ruleEngine 也在用),需单独评估,本次不纳入。

---

## 8. 配置设计

### 8.1 [agent.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/yaml/agent.yaml)(新增 1 键)

```yaml
process:
  batch_size: 5
  poll_interval_ms: 1000
  retry_times: 3        # → max_retries(不含首次执行)
  retry_delay: 2        # → base_delay(语义从"固定间隔"变为"线性基数":2s/4s/6s)
  retry_max_delay: 10   # 新增 → max_delay
```

### 8.2 [settings.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/settings.py)

```python
PROCESS_CONFIG = {
    'batch_size': _cfg['process']['batch_size'],
    'poll_interval_ms': _cfg['process']['poll_interval_ms'],
    'retry_times': _cfg['process']['retry_times'],
    'retry_delay': _cfg['process']['retry_delay'],
    'retry_max_delay': _cfg['process'].get('retry_max_delay', 10),
}
```

---

## 9. 日志与回调

| 场景 | 行为 |
|---|---|
| 每次重试 | 模块默认自动打 `warning`(logger 名 `retry`),含第几次、本次等待秒数 |
| 按返回值重试 | 默认日志的异常段为 `NoneType: None`(无异常对象)。**可接受**:失败原因已由 `analyze_log` 内部 `logger.error` 记录;如需更友好,可在接入点传 `on_retry` 自定义或传带 `NullHandler` 的 logger 关闭默认日志 |
| 业务告警 | 需要时通过 `on_retry=lambda a, e, d: ...` 接入监控/计数(本次可选) |

---

## 10. 边界与注意点

1. **`retry_if_result` 是覆盖而非叠加**:透传的 `retry` 会替换模块内部异常条件。对 agent 场景足够——`analyze_log` / `send` 都内部吞异常,异常型条件本就不触发;如未来要两者同时生效,用 `retry_any(retry_if_exception_type(...), retry_if_result(...))` 自行组合。
2. **幂等性**:Dify workflow 每次重试会重复执行并消耗 API 配额;Kafka `send` 重试重复投递同一条消息(offset 由 connect 端去重,当前 `enable_auto_commit=True` 下重复风险已在现有架构内)。接入前确认可接受。
3. **延迟代价**:单条消息最坏 `2+4+6=12s` 额外等待(批内 5 条串行)。如需降低,调小 `retry_times` / `retry_delay`。
4. **`Retry` 实例复用**:预构建一次放 `AgentMain.__init__`,避免每条消息重复构造。
5. **kafka-python 内部 `retries=3`** 保留,与应用层重试是两层语义,不冲突。

---

## 11. 测试与验证(落地阶段)

| 测试 | 内容 |
|---|---|
| Dify 重试成功 | mock `analyze_log` 前 2 次返回 failed、第 3 次成功 → `process_log` 返回 True,调用 3 次 |
| Dify 耗尽进 DLQ | mock 始终 failed → 重试 3 次后走 DLQ,`failure_reason` 以 `dify_analysis_failed` 开头 |
| 等待序列 | mock `time.sleep`,断言 2s / 4s / 6s |
| Kafka send 重试 | mock `send` 前 1 次返回 False → 重试后成功 |
| 发送耗尽进 DLQ | mock `send` 始终 False → 重试 3 次后进 DLQ(`kafka_send_failed`) |
| 首次成功零开销 | mock 首次成功 → 仅调用 1 次 |

---

## 12. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-15 | 初稿:审计结论 + 方案 B 接入设计 + `retry_error_callback` 关键验证 |
| 2026-08-15 | 落地实现:agent.yaml 新增 `retry_max_delay`;settings.py 加载该配置;main.py 预构建 `dify_retry`/`send_retry` 并接入 `process_log`;新增集成测试 [test_main_retry.py](../../../services/agent/tests/test_main_retry.py)(6 用例通过) |
