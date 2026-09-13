# 死信队列(DLQ)数据模型对齐文档

> 范围:仅聚焦 `log.dlq` topic 与 ES `logs_dead_letter` 索引的**数据模型**层面问题。
> 不涉及 Kafka Connect `errors.*` 路由、`dynamic_templates`、ingest pipeline 等工程化治理项(另行讨论)。

---

## 1. 概述

当前 `log.dlq` 由 **3 个生产者**写入,但只有 2 个走了统一的 `DlqProducer`,另 1 个(Logstash)使用原生 Logstash 格式直接产出。三者的字段集、字段语义、字段类型并不一致,是 DLQ 数据质量问题的根因,也是潜在 ES mapping 冲突的来源。

本文档梳理:
- ES `logs_dead_letter` 索引 mapping 期望的数据类型
- 3 个生产者当前的产出实况
- 不对齐点与潜在冲突
- 统一数据模型建议(方向性,不含代码改动)

---

## 2. DLQ 数据流总览

```
                      ┌──────────────────────────────────────────────┐
[采集器] ──► log.raw  │  Logstash (logstash.conf)                    │
                      │  grok 解析 nginx 日志                        │
                      └──────────────┬───────────────────────────────┘
                                     │
                ┌────────────────────┴───────────────────────┐
          grok 成功                                    grok 失败
                │                                     (_grokparsefailure)
        mutate convert                                     │
        status/bytes → int                          add_field(failure_reason,
        @timestamp (date filter)                     failed_stage, source_topic)
                │                                     保留 message 原文
                ▼                                     tags=["_grokparsefailure"]
        output ► log.structured                              │
                │                                            ▼
                │                                   output ► log.dlq   ◄── 生产者① Logstash
                │                                            ▲   (原生格式,不走 DlqProducer)
                │                                            │
    ┌───────────┴───────────────┐                            │
    ▼                           ▼                            │
[log-structured-sink]     [ruleEngine main.py]               │
log.structured             消费 log.structured                │
   ► ES nginx-log-raw      LogValidationError / Exception    │
                           ↓                                  │
                           DlqProducer.send_dlq()             │
                           failed_stage="rule_engine"         │
                           ► log.dlq  ◄── 生产者② ────────────┤
                                          (DlqProducer 标准格式)
                           │                                 │
                           ▼                                 │
                      [agent main.py]                        │
                      消费 log.analysis                       │
                      kafka_send_failed /                    │
                      dify_analysis_failed /                 │
                      processing_exception                   │
                      ↓                                      │
                      DlqProducer.send_dlq()                 │
                      failed_stage="agent"                   │
                      ► log.dlq  ◄── 生产者③ ────────────────┘
                                          (DlqProducer 标准格式)
                                │
                                ▼
                       [logs-dead-letter-sink]
                       log.dlq ► ES logs_dead_letter
```

---

## 3. ES `logs_dead_letter` Mapping 期望类型

来源:[logs_dead_letter.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/mappings/logs_dead_letter.yaml)

| 字段 | ES 类型 | 格式 / 约束 | 用途 |
|---|---|---|---|
| `@timestamp` | date | `epoch_millis\|\|strict_date_optional_time\|\|yyyy-MM-dd HH:mm:ss` | 事件进入 DLQ 的时间 |
| `event_id` | keyword | — | 消息唯一标识 |
| `source_topic` | keyword | — | 失败消息的来源 topic |
| `failed_stage` | keyword | — | 失败阶段(`rule_engine` / `agent` / `logstash_parser`) |
| `failure_reason` | text | 子字段 `keyword`(ignore_above 512) | 失败原因简述 |
| `error_type` | keyword | — | 异常类名 |
| `error_message` | text | 子字段 `keyword`(ignore_above 1024) | 异常消息 |
| `error_traceback` | text | `index: false` | 异常 traceback(仅存储不索引) |
| `original_payload` | **flattened** | **必须是 object** | 原始失败消息体 |
| `message` | text | 子字段 `keyword`(ignore_above 2048) | 原始日志行(兼容 Logstash grok 失败) |
| `tags` | keyword | 数组 | 标签 |
| `log_source` | keyword | — | 日志来源 |
| `dlq_status` | keyword | — | 运维状态:`pending` / `replayed` / `resolved` / `ignored` |
| `retry_count` | integer | — | 重试次数 |
| `resolved_at` | date | `epoch_millis\|\|strict_date_optional_time` | 解决时间(运维填写) |
| `resolved_note` | text | — | 解决备注(运维填写) |

**关键约束**:
- `original_payload` 为 `flattened` 类型 → **只接受 object**,传入字符串/数字会写入失败
- mapping **未定义** `@version`、`log` 等 Logstash 元数据字段 → 这些字段会走 ES 动态类型推断
- mapping **未设置** `dynamic: strict` 也**无 `dynamic_templates`** → 未知字段会被动态映射,类型由首条数据决定

---

## 4. 各生产者当前产出对照

### 4.1 生产者清单

| # | 生产者 | 文件 | failed_stage | 走 DlqProducer? | 触发条件 |
|---|---|---|---|---|---|
| ① | Logstash | [logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/logstash/pipeline/logstash.conf) | `logstash_parser` | ✗ 否(原生格式) | grok 解析失败 |
| ② | ruleEngine | [ruleEngine/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/ruleEngine/main.py) | `rule_engine` | ✓ 是 | `LogValidationError` / 任意 `Exception` |
| ③ | agent | [agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py) | `agent` | ✓ 是 | `kafka_send_failed` / `dify_analysis_failed` / `processing_exception` |

`DlqProducer` 标准格式定义在 [core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py)。

### 4.2 字段产出对照大表

图例:✓ = 产出且类型对齐;✗ = 缺失;△ = 产出但语义/类型有偏差;⚠ = 多余字段(mapping 未定义)

| 字段 (mapping 类型) | ① Logstash | ② ruleEngine | ③ agent |
|---|---|---|---|
| `@timestamp` (date) | ✓ Logstash 事件时间,ISO8601 | ✓ `datetime.now(utc).isoformat()` | ✓ 同② |
| `event_id` (keyword) | ✓ uuid filter 生成 | ✓ 原始 `event_id` 或 uuid | ✓ 同② |
| `source_topic` (keyword) | ✓ `"log.raw"`(环境变量插值) | ✓ `settings.consumer_topic`(`log.structured`) | ✓ `KAFKA_CONFIG['input_topic']` |
| `failed_stage` (keyword) | ✓ `"logstash_parser"` | ✓ `"rule_engine"` | ✓ `"agent"` |
| `failure_reason` (text) | ✓ `"grok_parse_failed"` | ✓ `str(error)` 或 `"processing_error"` | ✓ `"kafka_send_failed"` / `"dify_analysis_failed"` / `"processing_exception"` |
| `error_type` (keyword) | ✗ **缺** | △ 有异常填类名,无异常填 `""` | △ 同②(前两个调用点不传 `error` → 填 `""`) |
| `error_message` (text) | ✗ **缺** | △ 同上 | △ 同上 |
| `error_traceback` (text) | ✗ **缺** | △ 同上 | △ 同上 |
| `original_payload` (flattened) | ✗ **缺**(原始数据在顶层 `message`) | ✓ dict(`raw_log`) | ✓ dict(`raw_message`) |
| `message` (text) | ✓ 原始日志行字符串 | ✗ **缺** | ✗ **缺** |
| `tags` (keyword) | △ `["_grokparsefailure"]` | ✓ `["dlq", "rule_engine"]` | ✓ `["dlq", "agent"]` |
| `log_source` (keyword) | ✗ **缺** | ✓ `original_payload.get('log_source', '')` | ✓ 同② |
| `dlq_status` (keyword) | ✗ **缺** | ✓ `"pending"` | ✓ `"pending"` |
| `retry_count` (integer) | ✗ **缺**(null) | ✓ `0` | ✓ `0` |
| `resolved_at` (date) | —(运维字段) | — | — |
| `resolved_note` (text) | —(运维字段) | — | — |
| `@version` ⚠ | ⚠ `"1"`(Logstash 元数据) | ✗ | ✗ |
| `log` ⚠ | ⚠ 可能存在(kafka input 元数据) | ✗ | ✗ |

### 4.3 各生产者详细说明

#### 生产者① Logstash([logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/logstash/pipeline/logstash.conf))

grok 失败分支(`if "_grokparsefailure" in [tags]`)产出的字段:

```
message          = <原始 log.raw 消息字符串>   (input codec=plain)
event_id         = <uuid>                      (uuid filter)
tags             = ["_grokparsefailure"]       (grok 失败自动加)
failure_reason   = "grok_parse_failed"         (mutate add_field)
failed_stage     = "logstash_parser"           (mutate add_field)
source_topic     = "log.raw"                   (mutate add_field, 环境变量插值)
@timestamp       = <事件接收时间, ISO8601>      (Logstash 默认)
@version         = "1"                         (Logstash 默认)
log              = <kafka input 元数据>         (可能存在,未 remove_field)
```

**缺失**: `error_type` / `error_message` / `error_traceback` / `original_payload` / `dlq_status` / `retry_count` / `log_source`

#### 生产者② ruleEngine([ruleEngine/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/ruleEngine/main.py))

2 个调用点,均通过 `DlqProducer` 标准化:
- `LogValidationError`:`failure_reason=str(error)`,传 `error`
- 任意 `Exception`:`failure_reason="processing_error"`,传 `error`
- `original_payload = raw_log if isinstance(raw_log, dict) else {}`(非 dict 时填空 dict)
- `source_topic = settings.consumer_topic`(`log.structured`)

#### 生产者③ agent([agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py))

3 个调用点,均通过 `DlqProducer` 标准化:
- `kafka_send_failed`:**不传** `error`(无异常对象,`error_type/error_message/error_traceback` 填 `""`)
- `dify_analysis_failed`:**不传** `error`(同上)
- `processing_exception`:传 `error=e`
- `original_payload = raw_message`(始终是 dict)
- `source_topic = KAFKA_CONFIG['input_topic']`

#### DlqProducer 标准化逻辑([core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py))

无论哪个调用点,`DlqProducer.send_dlq()` 都会产出**固定字段集**:

```
@timestamp        = datetime.now(timezone.utc).isoformat()
event_id          = original_payload.get('event_id') or uuid4()
source_topic      = source_topic 参数 or self.topics[0]
failed_stage      = self.failed_stage (构造时传入)
failure_reason    = failure_reason 参数 or str(error) or "unknown"
error_type        = type(error).__name__ if error else ""
error_message     = str(error) if error else ""
error_traceback   = traceback.format_exc() if error else ""
original_payload  = original_payload 参数 (dict)
tags              = ["dlq", self.failed_stage]
dlq_status        = "pending"
retry_count       = 0
log_source        = original_payload.get('log_source', '')
```

---

## 5. 数据模型不对齐问题

### 5.1 字段缺失(Logstash ①)

Logstash 来源的 DLQ 记录**缺失 7 个 mapping 定义的字段**:

| 缺失字段 | mapping 类型 | 影响 |
|---|---|---|
| `error_type` | keyword | 无法按异常类名聚合 Logstash 失败原因 |
| `error_message` | text | 无人类可读的失败详情 |
| `error_traceback` | text | 无堆栈(本就难有,Logstash 无 Python 异常) |
| `original_payload` | flattened | **原始数据未结构化保存**,只在顶层 `message` 字符串里 |
| `dlq_status` | keyword | **无法做运维状态筛选**(pending/resolved 查不到 Logstash 记录) |
| `retry_count` | integer | 重试计数为 null,无法统一聚合 |
| `log_source` | keyword | 无法按日志来源筛选 |

> ES 对缺失字段不会直接报错(date/keyword/text 缺失允许),所以这不是 mapping 冲突,但是**数据质量缺陷**:同一索引内 Logstash 来源记录字段稀疏,无法用统一查询运维。

### 5.2 字段语义不一致

#### 5.2.1 `tags` 语义分裂
- ① Logstash:`["_grokparsefailure"]` — Logstash 内部的**解析失败标记**
- ②③ DlqProducer:`["dlq", failed_stage]` — **DLQ 标识 + 阶段**

后果:无法用 `tags: "dlq"` 一次性筛出所有 DLQ 记录(Logstash 的不带 `dlq` 标签);也无法用 `tags: "logstash_parser"` 统一按阶段筛选(DlqProducer 的 failed_stage 在 `failed_stage` 字段,而 Logstash 的解析失败信息在 `tags`)。

#### 5.2.2 `message` vs `original_payload` 二选一
- ① Logstash:原始数据在 **`message`**(字符串),无 `original_payload`
- ②③ DlqProducer:原始数据在 **`original_payload`**(object),无 `message`

mapping 同时定义了两个字段,意图是兼容两种来源,但实际造成:**查询原始数据时必须按 `failed_stage` 分支判断去哪个字段取**,数据模型不统一。

#### 5.2.3 `error_*` 字段的"空字符串 vs 缺失"
- ②③ DlqProducer:无异常时填 `""`(空字符串),字段**存在但为空**
- ① Logstash:完全缺失,字段**不存在**

ES 中 `""` 和 `null`(缺失)在 `exists` 查询里行为不同:`exists` 会匹配到 `""` 但匹配不到缺失。这导致 `error_type` 字段的 `exists` 查询结果在 Logstash 和 DlqProducer 来源间不一致。

### 5.3 字段类型隐患

#### 5.3.1 `original_payload` flattened 类型风险(高危)
- mapping:`flattened` → **只接受 object**
- ②③ 当前都传 dict,安全
- ① 不传,安全(缺失)
- **风险**:未来任何生产者若传入字符串/数字/数组,会直接 `mapper_parsing_exception` 写入失败。当前无任何代码层防护(`DlqProducer` 未校验 `original_payload` 是否为 dict)。

#### 5.3.2 `@version` / `log` 动态映射隐患(中危)
- ① Logstash 带 `@version="1"`(字符串)、可能的 `log`(object) → mapping 未定义 → **动态推断**
- 首条 Logstash DLQ 写入时:`@version` 推断为 text(值 `"1"`),`log` 推断为 object
- **风险**:若未来某条 DLQ 消息(例如某次 DlqProducer 的 `original_payload` 误把 `@version` 提到顶层,或某次重构)带了 `@version=1`(数字),触发**不可恢复的 mapping 冲突**,只能 reindex。

#### 5.3.3 `retry_count` 类型不一致(低危)
- ① 缺失 → null
- ②③ → integer 0
- ES 允许 null 和 integer 共存,不冲突。但聚合时 null 会被忽略,统计重试分布会漏掉 Logstash 来源。

### 5.4 潜在 mapping 冲突汇总

| 冲突点 | 触发条件 | 严重度 | 当前是否触发 |
|---|---|---|---|
| `original_payload` 收到非 object | 某生产者传入字符串/数字 | **致命**(写入失败) | 否(当前都传 dict 或缺失) |
| `@version` 动态推断后类型漂移 | 后续 `@version` 传数字 | **致命**(不可恢复) | 否(当前只有 Logstash 传字符串 `"1"`) |
| `log` 字段动态推断后类型漂移 | 后续 `log` 传非 object | **致命**(不可恢复) | 否 |
| 任意未知字段动态推断冲突 | 脏数据带入 mapping 未定义的同名字段,首条决定类型 | **致命**(不可恢复) | 取决于脏数据内容 |

> 注:以上"致命"冲突目前**均未实际触发**(因为 Logstash 元数据字段恰好都被推断为兼容类型)。但模型层面无任何防护,属于"目前没出事,下次脏数据可能出事"的脆弱状态。

---

## 6. 统一数据模型建议

### 6.1 设计原则

1. **字段集统一**:所有生产者产出**完全相同**的字段集,不允许多产或少产。
2. **缺失用零值填充**:缺失字段用类型零值(`""` / `0` / `{}`)而非省略,确保字段始终存在。
3. **原始数据统一载体**:所有原始数据统一放入 `original_payload`(object),废弃顶层 `message` 作为原始数据载体。
4. **tags 语义统一**:`tags = ["dlq", failed_stage]`,阶段信息同时存在于 `failed_stage` 字段(主)和 `tags`(辅助筛选)。
5. **Logstash 元数据剥离**:Logstash 产出的 `@version` / `log` 等元数据字段必须在 output 前剥离,不允许流入 `log.dlq`。
6. **`original_payload` 强制 object**:任何生产者在发送前校验 `original_payload` 为 dict,非 dict 时包装成 `{"raw": <value>}`。

### 6.2 统一字段规范(建议)

所有 DLQ 消息必须包含以下完整字段集,**无一例外**:

| 字段 | 类型 | 必填 | 取值规范 | 初始值(无数据时) |
|---|---|---|---|---|
| `@timestamp` | date | ✓ | ISO8601 UTC,如 `2026-08-10T12:34:56.789+00:00` | 当前时间 |
| `event_id` | keyword | ✓ | 原始消息的 `event_id`,无则 uuid4 | uuid4 字符串 |
| `source_topic` | keyword | ✓ | 失败消息的来源 topic | — |
| `failed_stage` | keyword | ✓ | `logstash_parser` / `rule_engine` / `agent` | — |
| `failure_reason` | keyword(建议优化,见 6.4) | ✓ | 机器可读的简短标识,如 `grok_parse_failed` | `"unknown"` |
| `error_type` | keyword | ✓ | 异常类名,无异常填 `""` | `""` |
| `error_message` | text | ✓ | 异常 str,无异常填 `""` | `""` |
| `error_traceback` | text | ✓ | traceback 字符串,无异常填 `""` | `""` |
| `original_payload` | flattened | ✓ | **必须是 object**,原始消息体 | `{}` |
| `message` | text | ✓ | 人类可读的原始日志行(冗余字段,从 `original_payload` 派生) | `""` |
| `tags` | keyword | ✓ | 固定 `["dlq", failed_stage]` | `["dlq", failed_stage]` |
| `log_source` | keyword | ✓ | 日志来源,无则 `""` | `""` |
| `dlq_status` | keyword | ✓ | 初始 `pending`,运维后续改 `replayed`/`resolved`/`ignored` | `"pending"` |
| `retry_count` | integer | ✓ | 初始 `0` | `0` |
| `resolved_at` | date | ✗ | 运维填写 | 不填(缺失) |
| `resolved_note` | text | ✗ | 运维填写 | 不填(缺失) |

> `resolved_at` / `resolved_note` 是**运维侧**字段,生产者不填,允许缺失。

### 6.3 各生产者对齐要求

#### 生产者① Logstash — 需补齐 7 个字段 + 剥离元数据

Logstash 的 grok 失败分支需要改造为产出完整字段集(在 [logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/logstash/pipeline/logstash.conf) 的 `_grokparsefailure` 分支):

- **补** `error_type = "GrokParseFailure"`(Logstash 无 Python 异常,用固定标识)
- **补** `error_message = "log line did not match nginx combined pattern"`(或包含原始 message 摘要)
- **补** `error_traceback = ""`(Logstash 无堆栈,填空字符串保持字段一致)
- **补** `original_payload`:把顶层 `message` 包装成 object,如 `{"raw": "<原始日志行>", "log_source": "nginx"}`,**移除顶层 message**(或保留作冗余,见下)
- **补** `dlq_status = "pending"`
- **补** `retry_count = 0`(mutate convert 成 integer)
- **补** `log_source = "nginx"`(或从原始消息取)
- **改** `tags`:从 `["_grokparsefailure"]` 改为 `["dlq", "logstash_parser"]`(把 `_grokparsefailure` 信息移入 `failure_reason` 或 `error_type`)
- **补** `message`:若保留作冗余字段,从 `original_payload.raw` 派生;否则填 `""`
- **剥离** `@version`、`log` 等 Logstash 元数据字段(mutate remove_field)

#### 生产者② ruleEngine — 基本对齐,微调即可

当前已通过 `DlqProducer` 产出完整字段集,仅两点微调:
- `original_payload` 在 `raw_log` 非 dict 时已填 `{}`(✓ 已合规)
- 可选:在 `LogValidationError` 分支补充 `error_type` 已经由 `DlqProducer` 自动从 `error` 提取(✓ 已合规)
- **建议**:确认 `raw_log` 一定是 dict(当前 `kafka_consumer.py` 的 `value_deserializer` 用 `json.loads`,若原始消息非合法 JSON 会反序列化失败,根本到不了这里,故安全)

#### 生产者③ agent — 基本对齐,空异常场景需明确

当前已通过 `DlqProducer` 产出完整字段集。注意 3 个调用点中 2 个不传 `error`:
- `kafka_send_failed`:无异常对象 → `error_type/error_message/error_traceback` 填 `""`(✓ 字段存在,语义为"无异常,业务级失败")
- `dify_analysis_failed`:同上
- **建议**:在 `failure_reason` 中携带足够信息(如把 Dify 返回的 error 字段拼进 `failure_reason` 或单独加字段),避免 `error_message=""` 时无法排查

### 6.4 Mapping 优化建议(可选,方向性)

以下为 mapping 层面的优化建议,**属于配置变更,需单独评估**,此处仅记录方向:

1. **`failure_reason` 主类型改 keyword**:当前是 text+keyword。实际取值是机器生成的简短标识(`grok_parse_failed` / `processing_error` 等),主要用途是精确匹配和聚合,主类型用 keyword 更合适。可保留 text 子字段做全文搜索。
2. **`message` 字段定位明确化**:若统一模型后所有原始数据都在 `original_payload`,`message` 退化为冗余的人类可读字段,可考虑 `index: false` 或保留现状。
3. **`original_payload` 增加文档约束**:在 mapping 注释中明确"必须为 object,生产者需校验"。
4. **补充 `dynamic_templates`**:把未知字段统一映射为 keyword,杜绝动态类型推断冲突(此项属于工程化治理,本文档不展开)。

---

## 7. 迁移路径(方向性,不含代码改动)

按"影响范围从小到大"排序:

| 步骤 | 动作 | 涉及组件 | 风险 |
|---|---|---|---|
| 1 | Logstash grok 失败分支补齐 7 个缺失字段 | logstash.conf | 低,纯配置 |
| 2 | Logstash 剥离 `@version` / `log` 元数据字段 | logstash.conf | 低 |
| 3 | Logstash `tags` 改为 `["dlq", "logstash_parser"]` | logstash.conf | 低,但需同步调整任何依赖 `_grokparsefailure` tag 的下游查询 |
| 4 | Logstash 把 `message` 包装进 `original_payload` object | logstash.conf | 中,需测试 flattened 字段写入 |
| 5 | DlqProducer 增加 `original_payload` 类型校验(非 dict 时包装) | core/kafka/dlq.py | 低,防御性增强 |
| 6 | agent 服务:无异常的 2 个调用点在 `failure_reason` 中补充业务信息 | agent/main.py | 低 |
| 7 | (可选)mapping:`failure_reason` 主类型改 keyword | logs_dead_letter.yaml | 中,需 `--force` 重建索引,历史数据需 reindex |

> 步骤 1-4 是**对齐工作的核心**,完成后 3 个生产者将产出统一字段集,数据模型层面的问题(5.1 / 5.2 / 5.3)全部消除。
> 步骤 5-6 是防御性增强。
> 步骤 7 是 mapping 优化,可延后。

---

## 8. 验收标准

统一数据模型落地后,以下查询在所有来源的 DLQ 记录上应行为一致:

1. `SELECT count(*) GROUP BY failed_stage` — 三个阶段均可聚合
2. `dlq_status: "pending"` — 能筛出所有未处理的 DLQ 记录(含 Logstash 来源)
3. `tags: "dlq"` — 能筛出**所有** DLQ 记录(含 Logstash 来源)
4. `exists: original_payload` — 所有记录都有 `original_payload` 字段
5. `retry_count` 聚合 — 所有记录都有整数值,无 null
6. `error_type` 字段的 `exists` 查询 — 行为一致(全部为 `""` 或全部有值,不存在"缺失"与"`""`"混用)

---

## 附录 A:相关文件索引

| 用途 | 文件 |
|---|---|
| DLQ 索引 mapping | [logs_dead_letter.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/mappings/logs_dead_letter.yaml) |
| DLQ sink 连接器 | [logs-dead-letter-sink.json](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/kafka-connect/connectors/logs-dead-letter-sink.json) |
| DlqProducer 标准化逻辑 | [core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py) |
| 生产者① Logstash | [logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/logstash/pipeline/logstash.conf) |
| 生产者② ruleEngine | [services/ruleEngine/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/ruleEngine/main.py) |
| 生产者③ agent | [services/agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py) |
| 主日志索引 mapping(参考) | [nginx-log-raw.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/mappings/nginx-log-raw.yaml) |
| ES 索引创建脚本 | [creatMapping.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/creatMapping.py) |
