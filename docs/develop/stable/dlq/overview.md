# DLQ 系统总览(当前状态)

> 本文档反映数据模型对齐改动**落地后**的当前状态,用于日常运维对照与未来修改参考。
> 对齐前的问题分析与迁移过程见 [alingment.md](./alingment.md)。

---

## 1. 系统状态

| 项 | 状态 |
|---|---|
| 数据模型对齐 | ✅ 已完成(3 个生产者产出统一字段集) |
| Logstash 元数据剥离 | ✅ 已完成(`@version` / `log` 在 output 前 remove) |
| `original_payload` 类型防护 | ✅ 已完成(DlqProducer 非 dict 自动包装) |
| Kafka Connect 原生 DLQ 路由 | ⏳ 未配置(sink 写入 ES 失败时 connector 会挂,不自动进 DLQ) |
| `dynamic_templates` 防护 | ⏳ 未配置(未知字段走 ES 动态推断) |
| ingest pipeline 兜底 | ⏳ 未配置 |

---

## 2. 数据流

```
[采集器] ──► log.raw
                │
         ┌──────▼──────┐
         │  Logstash   │  grok 解析 nginx 日志
         └──────┬──────┘
                │
         ┌──────┴──────┐
     grok 成功     grok 失败
         │              │
   mutate convert   补齐统一 DLQ 字段集
   status/bytes→int  original_payload={"raw":message}
   @timestamp        tags=["dlq","logstash_parser"]
         │            remove @version / log
         ▼              │
   log.structured       ▼
         │          log.dlq  ◄── 生产者① Logstash
         │              ▲
         ├──────────────┤
         │              │
    ┌────▼─────┐   ┌───▼────────────┐
    │ruleEngine│   │    agent        │
    │消费      │   │ 消费 log.analysis│
    │log.      │   │                 │
    │structured│   │ Dify 分析失败 /  │
    │          │   │ Kafka 发送失败 / │
    │ 校验/    │   │ 处理异常        │
    │ 规则异常 │   │                 │
    └────┬─────┘   └───┬─────────────┘
         │              │
    DlqProducer    DlqProducer
    failed_stage=  failed_stage=
    "rule_engine"  "agent"
         │              │
         ▼              ▼
      log.dlq  ◄── 生产者②③ (DlqProducer 标准格式)
         │
         ▼
  ┌────────────────────────┐
  │ logs-dead-letter-sink  │  Kafka Connect ES Sink
  │ log.dlq ► logs_dead_   │
  │ letter (ES 索引)        │
  └────────────────────────┘
```

**关键路由点**:Logstash output 用 `[failed_stage] == "logstash_parser"` 判断路由到 `log.dlq`(不再依赖 `_grokparsefailure` tag,因为 tag 在 filter 阶段已被移除)。

---

## 3. 统一数据模型(当前)

所有 3 个生产者产出**完全相同**的字段集。生产者不填的字段用零值(`""` / `0` / `{}`)填充,确保字段始终存在。

| 字段 | ES 类型 | 必填 | 生产者初始值 | 说明 |
|---|---|---|---|---|
| `@timestamp` | date | ✓ | 当前时间 ISO8601 UTC | 事件进入 DLQ 的时间 |
| `event_id` | keyword | ✓ | 原始 event_id 或 uuid4 | 消息唯一标识 |
| `source_topic` | keyword | ✓ | 来源 topic | 失败消息的来源 |
| `failed_stage` | keyword | ✓ | `logstash_parser` / `rule_engine` / `agent` | 失败阶段 |
| `failure_reason` | text+keyword | ✓ | 机器可读简述 | 失败原因 |
| `error_type` | keyword | ✓ | 异常类名或 `""` | 无异常时填 `""` |
| `error_message` | text+keyword | ✓ | 异常 str 或 `""` | 无异常时填 `""` |
| `error_traceback` | text(index:false) | ✓ | traceback 或 `""` | 无异常时填 `""` |
| `original_payload` | **flattened** | ✓ | **必须是 object** | 原始消息体 |
| `message` | text+keyword | ✓ | 人类可读日志行 | 从 original_payload 派生 |
| `tags` | keyword | ✓ | `["dlq", failed_stage]` | DLQ 标识 + 阶段 |
| `log_source` | keyword | ✓ | 日志来源或 `""` | — |
| `dlq_status` | keyword | ✓ | `"pending"` | 运维后续改为 `replayed`/`resolved`/`ignored` |
| `retry_count` | integer | ✓ | `0` | 重试次数 |
| `resolved_at` | date | ✗ | 不填 | 运维填写 |
| `resolved_note` | text | ✗ | 不填 | 运维填写 |

**关键约束**:`original_payload` 为 `flattened` 类型,只接受 object。DlqProducer 已做类型校验(非 dict 时包装成 `{"raw": <value>}`);Logstash 用 `[original_payload][raw]` 嵌套字段确保是 object。

---

## 4. 生产者详解

### 生产者① Logstash

- **文件**:[logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/logstash/pipeline/logstash.conf)
- **failed_stage**:`logstash_parser`
- **触发条件**:grok 解析 nginx 日志失败
- **路由判断**:output 用 `[failed_stage] == "logstash_parser"`(非 tag)
- **产出字段**:
  - `message` = 原始 log.raw 字符串(input plain codec)
  - `event_id` = uuid filter 生成
  - `original_payload` = `{"raw": "<原始日志行>"}`(add_field `[original_payload][raw]`)
  - `error_type` = `"GrokParseFailure"`(固定)
  - `error_message` = `"log line did not match nginx combined pattern"`(固定)
  - `error_traceback` = `""`(Logstash 无 Python 堆栈)
  - `dlq_status` = `"pending"`
  - `retry_count` = `0`(add_field + convert integer)
  - `log_source` = `"nginx"`
  - `tags` = `["dlq", "logstash_parser"]`(remove `_grokparsefailure` + add 标准标签)
  - `@version` / `log` = **已剥离**(remove_field)

### 生产者② ruleEngine

- **文件**:[services/ruleEngine/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/ruleEngine/main.py)
- **failed_stage**:`rule_engine`
- **触发条件**:
  - `LogValidationError`(字段缺失 / status/bytes 类型转换失败)
  - 任意 `Exception`(处理错误)
- **调用点**:2 个,均通过 `DlqProducer.send_dlq()`
- `original_payload = raw_log if isinstance(raw_log, dict) else {}`
- `source_topic = settings.consumer_topic`(`log.structured`)

### 生产者③ agent

- **文件**:[services/agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py)
- **failed_stage**:`agent`
- **触发条件**(3 个调用点):
  - `kafka_send_failed`:Kafka producer send 返回 False(无异常对象,`error_*` 填 `""`)
  - `dify_analysis_failed`:Dify 返回非 success(`failure_reason` 带 Dify error 详情)
  - `processing_exception`:处理异常(传 `error=e`)
- `original_payload = raw_message`(dict)
- `source_topic = KAFKA_CONFIG['input_topic']`

### DlqProducer 标准化逻辑

- **文件**:[core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py)
- 所有 ruleEngine / agent 调用都经过此类的 `send_dlq()` 方法,产出固定字段集
- **防御逻辑**:
  - `original_payload` 非 dict 时自动包装成 `{"raw": <value>}`
  - `message` 字段从 `original_payload.message` 派生,无则用 JSON 摘要(截断 2048)

---

## 5. ES Mapping

- **文件**:[logs_dead_letter.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/mappings/logs_dead_letter.yaml)
- **索引名**:`logs_dead_letter`
- **创建脚本**:[creatMapping.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/creatMapping.py)
- **注意**:该 mapping **无 `dynamic_templates`**,未知字段走 ES 动态推断(遗留风险,见第 8 节)

---

## 6. Kafka Connect Sink

- **文件**:[logs-dead-letter-sink.json](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/kafka-connect/connectors/logs-dead-letter-sink.json)
- **消费**:`log.dlq` topic
- **写入**:ES `logs_dead_letter` 索引
- **关键配置**:`schema.ignore=true`、`key.ignore=true`、`write.method=INSERT`
- **⚠ 遗留**:未配置 `errors.tolerance` / `errors.deadletterqueue.topic.name`。若 ES 写入失败,connector task 会直接挂掉,不会自动路由到 DLQ。

---

## 7. 配置文件索引

| 用途 | 文件 |
|---|---|
| Logstash DLQ 生产者 | [logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/logstash/pipeline/logstash.conf) |
| DlqProducer 标准化逻辑 | [core/kafka/dlq.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/core/kafka/dlq.py) |
| ruleEngine 调用点 | [services/ruleEngine/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/ruleEngine/main.py) |
| agent 调用点 | [services/agent/main.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/agent/main.py) |
| ES 索引 mapping | [logs_dead_letter.yaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/mappings/logs_dead_letter.yaml) |
| ES 索引创建脚本 | [creatMapping.py](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/elasticsearch/creatMapping.py) |
| DLQ sink 连接器 | [logs-dead-letter-sink.json](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/kafka-connect/connectors/logs-dead-letter-sink.json) |
| 主日志 sink 连接器 | [log-structured-sink.json](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/config/kafka-connect/connectors/log-structured-sink.json) |
| ruleEngine Kafka 配置 | [app.licationyaml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/services/ruleEngine/config/app.licationyaml) |
| docker-compose(connect 服务) | [docker-compose.yml](file:///d:/tools/ProgrammeTools/python/正规项目/AuditWeaver/docker/docker-compose.yml) |

---

## 8. 运维操作

### 8.1 重启服务应用改动

```bash
# 重启 Logstash(加载新的 logstash.conf)
docker-compose restart logstash

# 重启 ruleEngine / agent(Python 服务,按实际部署方式重启)
# 加载新的 dlq.py / main.py
```

### 8.2 重建 ES 索引

若 `logs_dead_letter` 索引被旧数据污染(如之前 Logstash 的 `@version` 字段已动态映射),需重建:

```bash
# 强制删除并重建所有索引(含 logs_dead_letter)
python docker/config/elasticsearch/creatMapping.py --force
```

> `--force` 会删除**所有**索引并重建,历史数据会丢失。如只需重建单个索引,需手动调用 ES API。

### 8.3 查看 DLQ 记录

```bash
# 查看所有 DLQ 记录(按时间倒序)
curl -s "http://localhost:9200/logs_dead_letter/_search?size=20&sort=@timestamp:desc" | jq

# 按失败阶段筛选
curl -s "http://localhost:9200/logs_dead_letter/_search" -H 'Content-Type: application/json' -d '{
  "query": {"term": {"failed_stage": "rule_engine"}}
}' | jq

# 只看未处理的记录
curl -s "http://localhost:9200/logs_dead_letter/_search" -H 'Content-Type: application/json' -d '{
  "query": {"term": {"dlq_status": "pending"}}
}' | jq

# 按失败原因聚合统计
curl -s "http://localhost:9200/logs_dead_letter/_search" -H 'Content-Type: application/json' -d '{
  "size": 0,
  "aggs": {"reasons": {"terms": {"field": "failure_reason.keyword", "size": 20}}}
}' | jq
```

### 8.4 标记 DLQ 记录为已解决

```bash
# 将某条记录标记为 resolved
curl -X POST "http://localhost:9200/logs_dead_letter/_update/<_id>" -H 'Content-Type: application/json' -d '{
  "doc": {
    "dlq_status": "resolved",
    "resolved_at": "2026-08-10T12:00:00.000+00:00",
    "resolved_note": "修复了 grok 模式,重新解析成功"
  }
}'
```

### 8.5 查看.kafka-connect 状态

```bash
# 查看 DLQ sink connector 状态
curl -s "http://localhost:8083/connectors/logs-dead-letter-sink/status" | jq

# 查看 connector 配置
curl -s "http://localhost:8083/connectors/logs-dead-letter-sink" | jq
```

---

## 9. 故障排查

### 9.1 DLQ 记录写入 ES 失败

**现象**:`logs-dead-letter-sink` connector 状态为 FAILED,`log.dlq` topic 有消息但 ES 无数据。

**排查步骤**:
1. 查看 connector 状态:`curl http://localhost:8083/connectors/logs-dead-letter-sink/status`
2. 查看 connector 任务 trace:`curl http://localhost:8083/connectors/logs-dead-letter-sink/tasks/0/status`
3. 常见原因:
   - `original_payload` 传入了非 object → 检查生产者是否绕过了 DlqProducer 校验
   - 动态字段类型冲突 → 查 ES 日志,确认冲突字段名,用 `--force` 重建索引
   - ES 不可达 → 检查 `connection.url` 和 ES 服务状态

### 9.2 Logstash DLQ 消息路由到错误的 topic

**现象**:grok 失败的消息出现在 `log.structured` 而非 `log.dlq`。

**原因**:output 路由条件用 `_grokparsefailure` tag,但 tag 在 filter 阶段已被 remove。

**确认**:当前 logstash.conf output 已改为 `[failed_stage] == "logstash_parser"`。若仍出错,检查 filter 中 `failed_stage` add_field 是否正常执行。

### 9.3 Logstash 消息带 `@version` 字段污染索引

**现象**:ES `logs_dead_letter` 索引出现 `@version` 字段(mapping 未定义,动态映射为 text)。

**确认**:当前 logstash.conf 已在 grok 失败分支 `remove_field => ["@version", "log"]`。若仍出现,检查是否有其他 Logstash pipeline 或旧配置未更新。

### 9.4 DLQ 记录字段稀疏(Logstash 来源)

**现象**:Logstash 来源的 DLQ 记录缺少 `error_type` / `dlq_status` 等字段。

**确认**:当前 logstash.conf 已补齐全部字段。若仍缺字段,检查 Logstash 是否重启加载了新配置。

---

## 10. 已知遗留项(未来改进)

以下问题在本次对齐中**未处理**,记录备查:

| # | 遗留项 | 风险 | 建议优先级 |
|---|---|---|---|
| 1 | `log-structured-sink` 和 `logs-dead-letter-sink` 未配置 `errors.tolerance=ALL` + `errors.deadletterqueue.topic.name` | ES 写入失败时 connector 挂掉,数据卡住不进 DLQ | 高 |
| 2 | `logs_dead_letter` 和 `nginx-log-raw` mapping 无 `dynamic_templates` | 未知字段走动态推断,首条决定类型,后续可能不可恢复冲突 | 高 |
| 3 | `failure_reason` mapping 主类型为 text,实际用途是精确匹配聚合 | 聚合效率低,建议改 keyword 主类型 | 中 |
| 4 | DLQ sink 自身无 DLQ(写入失败时死信丢失) | 死信消息可能永久丢失 | 中 |
| 5 | 无 ILM 策略,`logs_dead_letter` 索引可能无限膨胀 | 磁盘空间风险 | 低 |
| 6 | 无 DLQ 监控告警(pending 记录堆积无感知) | 运维盲区 | 低 |

> 遗留项 1-2 的详细方案见本次对话的历史分析(工程化治理部分)。

---

## 11. 变更记录

| 日期 | 变更 | 涉及文件 |
|---|---|---|
| 2026-08-10 | Logstash grok 失败分支补齐 7 个字段 + 剥离 `@version`/`log` + 统一 tags + 包装 original_payload + output 路由条件改为 `[failed_stage]` | logstash.conf |
| 2026-08-10 | DlqProducer 加 `original_payload` 类型校验(非 dict 包装) + 补 `message` 字段 + import json | core/kafka/dlq.py |
| 2026-08-10 | agent `dify_analysis_failed` 调用点补充 Dify error 详情到 `failure_reason` | services/agent/main.py |
