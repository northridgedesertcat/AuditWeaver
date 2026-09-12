# agent 模块稳定性策略

> 状态:已落地(重试 / 熔断 / DLQ 三层防护均已接入)
> 范围:汇总 agent 模块(Dify 分析 → ES 入库管道)的**稳定性设计**,作为日后配置调整、故障排查、二次开发的参照手册。
> 适用版本:重试(2026-08-15)+ 熔断(2026-08-16)接入后

---

## 1. 稳定性三层防护(总览)

agent 消费 `log.analysis` topic,调 Dify 分析,结果写回 Kafka → ES。为应对 Dify 抖动/过载、Kafka 故障、代码异常,采用**三层递进防护**:

| 层 | 机制 | 粒度 | 目标 |
|---|---|---|---|
| ① 消息级 | **线性退避重试**(Retry) | 单条消息内的单次调用 | 消化瞬时抖动(偶发超时、网络闪断) |
| ② 系统级 | **熔断**(CircuitBreaker) | 连续多条消息(整体健康度) | Dify 持续失败时"刹车",给它喘息机会 |
| ③ 兜底 | **死信队列**(DLQ) | 处理失败的消息 | 重试耗尽 / 熔断 / 异常的消息不丢失 |

```
log.analysis
   │  consume(batch_size=5)
   ▼
┌─────────────────────────────────────────────────────────┐
│ process_log(单条消息)                                      │
│   ┌────────────┐   ┌────────────┐   ┌──────────────────┐ │
│   │ ② 熔断外层  │ → │ ① 重试内层  │ → │ Dify analyze_log │ │
│   │ (可放行才进)│   │ 2s/4s/6s   │   │ (吞异常返回 dict) │ │
│   └────────────┘   └────────────┘   └──────────────────┘ │
│        │ 成功                              │ 重试耗尽失败   │
│        ▼                                   ▼              │
│  build_elastic_document ──► send_retry ──► Kafka send      │
│        │ success                              │ send 耗尽  │
│        ▼                                       ▼           │
│     返回 True                               ③ DLQ(见第 5 节)│
│  任意异常(CircuitOpenError / 其他)──────────►③ DLQ           │
└─────────────────────────────────────────────────────────┘
```

**分层语义**:重试管"单次调用的节奏",熔断管"整体开/关",DLQ 管"失败消息的归宿"。三者独立模块、可组合、互不依赖([core/stable/retry](../stable/retry/design.md) 与 [core/stable/circuit_breaker](../stable/circuit_breaker/design.md))。

---

## 2. 重试策略(Retry,基于 Tenacity 薄封装)

### 2.1 接入点

两个重试实例在 `AgentMain.__init__` **预构建一次**(避免每条消息重复构造),见 [main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py#L39-L55):

| 实例 | 目标 | 重试触发(按返回值) | 耗尽行为 |
|---|---|---|---|
| `dify_retry` | Dify 分析 | `status == 'failed'` | 返回最后失败 dict → DLQ |
| `send_retry` | Kafka 发送 | `send()` 返回 `False` | 返回 `False` → DLQ |

> 包装点放在 `process_log` **调用处**,`client.py` / `producer.py` 零改动。

### 2.2 配置与等待序列

- `retry_times=3` → 最多重试 3 次(首次 + 3 次重试 = 最多 4 次真实调用)
- `base_delay=2` → 第 n 次重试前等待 `2n` 秒,封顶 `max_delay=10`
- `retry_jitter=0.5` → 叠加 `wait_random(0, base×jitter=1)`,防多消费者并发重试惊群
- 实际等待序列:**2s+jitter → 4s+jitter → 6s+jitter**(jitter ∈ [0,1),单条最坏 ≈13s)

### 2.3 关键语义(易踩坑)

1. **必须带 `retry_error_callback=lambda rs: rs.outcome.result()`**:`core/stable/retry` 内部固定 `reraise=True` 是为异常型重试设计;改为按返回值重试后,若不带此回调,耗尽时抛 `RetryError` 而非返回结果,`process_log` 会误走 `processing_exception` 分支。**该回调对异常型同样成立**(调 `Future.result()` 会重抛原异常)。
2. **返回值重试与异常重试互斥**:透传 `retry=retry_if_result(...)` 会**替换**模块内部异常条件。agent 场景够用(两个目标函数都内部吞异常);如需两者同时生效,用 `retry_any(...)` 组合。
3. **每次重试自动打 warning 日志**(logger 名 `retry`):按返回值重试时异常段显示 `NoneType: None`,属正常——失败原因已由 `analyze_log` 内部 `logger.error` 记录。

---

## 3. 熔断策略(CircuitBreaker,基于 PyBreaker 薄封装)

### 3.1 位置与组合

熔断**包在重试外层**,见 [main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py#L118-L125):

```python
response = self.dify_breaker.call(
    lambda msg: self.dify_retry.call(self.dify_client.analyze_log, msg),
    raw_message,
    result_is_failure=lambda r: r.get('status') == 'failed',
)
```

**语义**:单条消息走完整个重试序列才算 1 次成败——连续 `fail_max` 条消息彻底失败才熔断。熔断打开期间**完全不再调用 Dify**(重试也不再触发)。

### 3.2 状态机与配置

| 配置(agent.yaml) | 默认值 | 含义 |
|---|---|---|
| `fail_max` | 3 | 连续失败条数阈值(每条重试耗尽计 1 次),达到即熔断 |
| `reset_timeout` | 30 | 冷却秒数,熔断 30s 后才放行探测 |
| `success_threshold` | 2 | 半开状态连续成功 2 条才恢复(防抖动) |

```
CLOSED ──连续 3 条彻底失败(每条重试耗尽)──► OPEN(走 fallback 降级落库)
OPEN   ──30s 后下一次调用──► HALF_OPEN(放行 1 条真实调用,含重试,不走 fallback)
HALF_OPEN ──连续 2 条成功──► CLOSED
HALF_OPEN ──1 条最终失败──► OPEN(重新计时,继续降级)
```

> 计数语义:熔断器按"一次完整 analyze 调用最终结果"计 1 次,不按 Retry 内部每次尝试计数。单条消息 Retry 3 次全失败只计 1 次熔断失败,需 3 条消息连续彻底失败才 OPEN。

状态变化经 `on_state_change` 回调打 warning 日志(`Dify 熔断器状态变化: closed -> open`),便于监控。

### 3.3 返回值失败桥接(result_is_failure)

`analyze_log` 吞异常返回 `{'status': 'failed'}`,而 PyBreaker 只认"抛异常"为失败。封装层用内部桥接异常实现:`result_is_failure` 命中 → 计 1 次熔断失败,**但返回值仍原样返回**,`process_log` 既有分支零改动。

熔断打开时走 `fallback=build_degraded_result` 返回降级结果(不抛 `CircuitOpenError`),降级报告走落库路径不进 DLQ(见 3.4)。仅在未传 `fallback` 时才抛 `CircuitOpenError`。

### 3.4 熔断期消息去向(降级落库)

熔断打开期消息**照常消费**,走 `dify_breaker.call(fallback=...)` 的降级路径:不调用分析后端,由 `build_degraded_result` 产出**仅规则匹配**的降级报告(`AnalysisResult(status='degraded')`,AI 字段全空,`raw_response={'degraded': True, 'reason': 'circuit_open'}`),经 `build_report_record` 落 MySQL,offset 正常提交。

- **不丢数据**:降级报告进了 `analysis_report` 表(规则字段完整,AI 字段空缺);
- **不积压 offset**:降级走成功路径,offset 天然推进;
- **DLQ 不激增**:降级报告不进 DLQ(降级是"产出报告",非"失败")。

> 取代了旧方案"熔断期快速失败进 DLQ"。降级已覆盖"熔断期仍产出报告"的诉求,且实现更简单,无需 pause/resume 消费者。降级唯一标识:`raw_response.degraded=True`(risk_score=0 是 NOT NULL 占位,非"低风险",消费者须先查 degraded 标记再用 risk_score)。

备选方案(已被降级取代,记录备查):
1. 熔断期暂停消费(pause consumer)——降级方案更简单,无需 pause/resume;
2. 熔断期消息送回原 topic 延迟重投;
3. 维持快速失败进 DLQ——已被降级取代。

---

## 4. DLQ(死信队列)

### 4.1 agent 的三个 DLQ 调用点

均在 [process_log](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py#L114-L161) 内,统一经 [core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py) 的 `DlqProducer.send_dlq()`(`failed_stage='agent'`):

| 分支 | `failure_reason` | 触发 |
|---|---|---|
| 发送失败 | `kafka_send_failed` | `send_retry` 耗尽仍 `False`(无异常,error 字段为空) |
| 分析失败 | `dify_analysis_failed: <error>` | Dify 重试耗尽返回 failed dict |
| 异常兜底 | `processing_exception` | 任意异常(含熔断打开 `CircuitOpenError`) |

### 4.2 统一字段集(与 ruleEngine / Logstash 一致)

`send_dlq` 自动包装:`@timestamp` / `event_id` / `source_topic` / `failed_stage` / `failure_reason` / `error_type|message|traceback` / `original_payload`(flattened,非 dict 自动包装)/ `message` / `tags=["dlq","agent"]` / `dlq_status="pending"` / `retry_count=0` / `log_source`。

### 4.3 下游

`log.dlq` → Kafka Connect Sink([logs-dead-letter-sink](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/kafka-connect/connectors/logs-dead-letter-sink.json)) → ES `logs_dead_letter` 索引。DLQ 系统完整说明见 [DLQ 总览](../stable/dlq/overview.md)。

---

## 5. 三层协同时序(典型场景)

### 场景 A:Dify 瞬时抖动(单条消息内恢复)

```
msg-1 首次 failed → 重试 2s → 成功
→ 熔断计成功,消息正常入库。无 DLQ、无熔断。
```

### 场景 B:Dify 持续过载(熔断 + 降级全流程)

```
msg-1..3 每条重试 3 次(jitter)全失败 → 熔断计 3 次失败 → OPEN(真实调用 3×4=12 次)
msg-4..N 熔断 OPEN 期:走 fallback → 降级报告(仅规则匹配)落库 → offset 正常提交
                     (后端零调用,DLQ 不激增)
30s 后 HALF_OPEN:放行 1 条真实探测调用(走重试,不走 fallback)
   ├─ 成功 → 再放行 1 条,连续 2 条成功 → CLOSED(恢复全量 AI)
   └─ 最终失败 → 重新 OPEN,继续降级,再等 30s
```

### 场景 C:Kafka 不可用

```
Dify 分析成功 → send 失败 → send_retry 2s/4s/6s → 仍 False
→ DLQ(failure_reason='kafka_send_failed')。熔断器不受影响(只保护 Dify)。
```

---

## 6. 配置索引

[agent.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/yaml/agent.yaml) → [settings.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/config/settings.py) 加载为 `PROCESS_CONFIG` / `CIRCUIT_CONFIG`。环境敏感值(brokers / api_key / timeout 等)由 `common.env` 注入,不入 yaml。

```yaml
process:
  batch_size: 5
  poll_interval_ms: 1000
  retry_times: 3        # → 重试次数(不含首次)
  retry_delay: 2        # → 线性退避基数(s)
  retry_max_delay: 10   # → 单次等待上限(s)
  retry_jitter: 0.5     # → 抖动比例 [0,1),叠加 wait_random(0, base×jitter)

circuit_breaker:
  fail_max: 3           # → 连续失败条数阈值(每条重试耗尽计 1 次)
  reset_timeout: 30     # → 冷却秒数
  success_threshold: 2  # → 半开恢复所需连续成功条数
```

---

## 7. 关键语义与注意点(运维参照)

| # | 事项 | 说明 |
|---|---|---|
| 1 | **幂等性** | Dify 重试会重复执行 workflow 并消耗 API 配额;Kafka send 重试会重复投递同一条消息(connect 端去重由 offset 保证)。接入新调用前确认幂等可接受 |
| 2 | **延迟代价** | 单条消息最坏 12s(Dify)+ 12s(Kafka send),批内 5 条串行。调低 `retry_times` / `retry_delay` 可压缩 |
| 3 | **kafka-python 内部 retries** | `connect()`/`send_dlq` 底层 `retries=3` 是 broker 层重试,与应用层重试是两层语义,不冲突 |
| 4 | **熔断白名单语义** | 若给熔断器配 `exceptions` 白名单,注意 PyBreaker 对白名单外异常是**重置失败计数**(视为业务异常/服务健康),而非简单忽略 |
| 5 | **熔断器生成器限制** | 封装层 `call()` 面向普通同步函数;传入生成器函数时其内容不会被消费(设计目标内不适用 agent) |
| 6 | **熔断期降级产出** | 见 3.4,熔断打开期走 fallback 产出降级报告(仅规则匹配)落库,不进 DLQ;监控上需关注降级报告占比(查 `raw_response.degraded=True`) |
| 7 | **`Retry`/`CircuitBreaker` 实例复用** | 均在 `__init__` 预构建,线程安全,可全局单例复用 |

---

## 8. 故障排查速查

| 现象 | 日志/字段 | 原因与处置 |
|---|---|---|
| 消息持续进 DLQ 且 `failure_reason=dify_analysis_failed` | 前有 `第 N/M 次重试` warning | Dify 业务/网络失败,重试耗尽。查 Dify 服务状态 |
| 消息落库但 `raw_response.degraded=True` | `熔断器状态变化: closed -> open` + `降级产出(仅规则匹配)` | 熔断打开中走 fallback 降级,等待 30s 冷却后半开探测恢复,或人工检查 Dify 健康 |
| 消息进 DLQ 且 `failure_reason=kafka_send_failed` | `Kafka send failed` | Kafka broker 不可达,查 broker / 网络 |
| 重试耗尽却报 `RetryError` | `RetryError` 堆栈 | 新增的重试接入点**漏了 `retry_error_callback`**,补上(见 2.3) |
| 熔断从不触发 | `fail_counter` 恒 0 | 检查 `result_is_failure` 是否配置(返回值桥接),或 exceptions 白名单误排除了桥接异常 |

---

## 9. 测试与验证

| 类型 | 位置 | 覆盖 |
|---|---|---|
| 单元测试 | [test_circuit_breaker.py](../../../core/stable/circuit_breaker/test_circuit_breaker.py) | 熔断器 23 用例(unittest) |
| 单元测试 | [test_retry.py](../../../core/stable/retry/test_retry.py) | 重试 22 用例(unittest) |
| agent 集成 | [test_main_retry.py](../../../services/agent/tests/test_main_retry.py) | 重试接入 process_log(6 用例) |
| agent 集成 | [test_main_degradation.py](../../../services/agent/tests/test_main_degradation.py) | 降级 + 熔断计数语义 + Half-Open + risk_score 契约(21 用例) |
| 场景脚本 | [test_circuit_breaker_scenarios.py](../../../devtools/test/stable/test_circuit_breaker_scenarios.py) | 状态机全流程 34 项 |
| 场景脚本 | [test_breaker_retry_integration.py](../../../devtools/test/stable/test_breaker_retry_integration.py) | 重试+熔断组合(agent 场景)18 项 |
| 场景脚本 | [test_edge_cases.py](../../../devtools/test/stable/test_edge_cases.py) | 边界与缺陷回归 15 项 |

运行方式:`python devtools/test/stable/<script>.py` 或 `python -m unittest core.stable.circuit_breaker.test_circuit_breaker -v`。

---

## 10. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-15 | 接入线性退避重试:dify_retry / send_retry,agent.yaml 新增 `retry_max_delay`(详见 [retry_strategy.md](./retry_strategy.md)) |
| 2026-08-16 | 接入 Dify 熔断:dify_breaker 包在重试外层,agent.yaml 新增 `circuit_breaker` 段,settings.py 新增 `CIRCUIT_CONFIG` |
| 2026-08-16 | 修复熔断缺陷:`exceptions` 白名单不含 Exception 时 `result_is_failure` 桥接失效(桥接异常被误排除);补充 devtools 场景测试 |
| 2026-08-16 | 本文档创建,汇总三层稳定性策略 |
| 2026-09-11 | 接入熔断降级:`dify_breaker.call` 传 `fallback=build_degraded_result`,熔断打开期产出仅规则匹配的降级报告落库(不进 DLQ);`fail_max` 5→3;重试启用 `jitter=0.5` 防惊群;3.4 节熔断期去向改"降级落库";新增 [test_main_degradation.py](../../../services/agent/tests/test_main_degradation.py)(21 用例,含熔断计数语义、Half-Open+Retry、risk_score 消费者契约)。详见 [agent_degradation_plan.md](../stable/agent_degradation_plan.md) |
