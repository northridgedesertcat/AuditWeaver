# LogSentinel 项目时间分析文档

## 概述

本文档详细分析 LogSentinel 项目中各个模块对时间的处理方式，包括时间格式、时区转换、时间字段的创建和修改等。

---

## 1. 日志生成模块 (kafka_producer_from_logs.py)

### 1.1 文件路径
[services/testdata/kafka_producer_from_logs.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/testdata/kafka_producer_from_logs.py)

### 1.2 时间处理逻辑

| 函数 | 时间操作 | 格式 | 时区 |
|------|---------|------|------|
| `replace_log_date()` | `datetime.now()` 获取当前日期 | `%d/%b/%Y` | **本地时区** |

### 1.3 时间字段转换

原始日志格式：
```
192.168.1.1 - - [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.0" 200 2326
```

替换后的日期部分：
```
[30/Jun/2026:13:55:36 -0700]  # 日期被替换为当前日期，时间和时区保持不变
```

### 1.4 关键代码分析

```python
def replace_log_date(log_line):
    today = datetime.now()  # 获取本地时间
    today_str = today.strftime("%d/%b/%Y")
    return re.sub(r"\[\d{2}/\w{3}/\d{4}:", f"[{today_str}:", log_line)
```

**注意**：该函数只替换日期部分，保留原始的时间和时区偏移量（如 `-0700`）。

---

## 2. Logstash 处理模块 (logstash.conf)

### 2.1 文件路径
[docker/config/logstash/pipeline/logstash.conf](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/docker/config/logstash/pipeline/logstash.conf)

### 2.2 时间处理流程

| 阶段 | 操作 | 字段 |
|------|------|------|
| **Grok解析** | 从原始日志提取时间戳 | `timestamp` (字符串) |
| **Date转换** | 将字符串解析为日期对象 | `@timestamp` (UTC datetime) |
| **Mutate删除** | 删除原始timestamp字段 | - |

### 2.3 Grok 时间提取

```ruby
grok {
    match => {
        "message" => '%{IP:ip} - - \[%{HTTPDATE:timestamp}\] "%{WORD:method} %{DATA:path} HTTP/%{NUMBER:http_version}" %{NUMBER:status} %{NUMBER:bytes} "%{DATA:referrer}" "%{DATA:user_agent}"'
    }
}
```

`%{HTTPDATE:timestamp}` 提取的时间格式：`30/Jun/2026:13:55:36 +0800`

### 2.4 Date 过滤器（核心时间转换）

```ruby
date {
    match => ["timestamp", "dd/MMM/yyyy:HH:mm:ss Z"]
    target => "@timestamp"
}
```

**关键参数解析**：
- `match`: 指定输入格式为 `dd/MMM/yyyy:HH:mm:ss Z`
- `target`: 输出到 `@timestamp` 字段
- **时区处理**: Logstash 的 date 过滤器会自动解析输入中的时区偏移量（如 `+0800`），并将其转换为 **UTC 时间**后存储

### 2.5 Mutate 删除原始字段

```ruby
mutate {
    remove_field => ["message", "timestamp", "log"]
}
```

原始 `timestamp` 字符串字段被删除，只保留 `@timestamp` 字段。

### 2.6 输出时间格式

输出到 Elasticsearch 的时间格式：
```json
{
    "@timestamp": "2026-06-30T05:55:36.000Z"  // UTC 时间，ISO8601 格式
}
```

---

## 3. 规则匹配模块 (rulesMatching)

### 3.1 相关文件

| 文件 | 时间处理内容 |
|------|------------|
| [main.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/rulesMatching/main.py) | 消息验证检查时间戳字段 |
| [data_saver.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/rulesMatching/data_saver.py) | 创建时间相关字段、本地文件存储 |
| [config.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/rulesMatching/config.py) | 日志格式配置 |

### 3.2 时间字段验证

```python
# main.py - validate_kafka_message()
if 'timestamp' not in message and '@timestamp' not in message:
    logger.debug(f"[VALIDATION] 缺少时间戳字段")
    return False
```

支持两种时间戳字段：`timestamp` 或 `@timestamp`。

### 3.3 本地文件存储时间

```python
# data_saver.py - _get_date_folder()
def _get_date_folder(self):
    date_str = datetime.utcnow().strftime('%Y-%m-%d')  # UTC 日期
    hour_str = datetime.utcnow().strftime('%H')         # UTC 小时
    date_folder = os.path.join(self.normal_data_path, date_str, hour_str)
    ...
```

文件路径格式：
```
temporaryDatas/unmatchDatas/2026-06-30/12/normal_log_20260630_123000_123456.json
```

### 3.4 正常日志本地存储时间

```python
# data_saver.py - _save_to_json()
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # 本地时间
log_data = {
    'timestamp': datetime.now().isoformat(),  # 本地时间，ISO8601格式
    'log_entry': log_entry,
    'detection_result': clean_detection_result
}
```

**注意**：此处使用的是 `datetime.now()`（本地时间），而非 UTC。

### 3.5 日志丰富处理时间

```python
# data_saver.py - _enrich_log_with_detection()
# 添加 ingestion_time 字段，记录写入 Elasticsearch 的时间
enriched_log['ingestion_time'] = datetime.now().isoformat()  # 本地时间
```

### 3.6 Kafka 消息时间戳

```python
# data_saver.py - _send_to_kafka()
kafka_message = {
    'timestamp': datetime.utcnow().isoformat(),  # UTC 时间
    'log_entry': enriched_log,
    'detection_result': detection_result
}
```

### 3.7 时间字段汇总（rulesMatching）

| 字段 | 格式 | 时区 | 说明 |
|------|------|------|------|
| `@timestamp` | ISO8601 | UTC | 从 Logstash 继承 |
| `ingestion_time` | ISO8601 | **本地时间** | 写入时间 |
| Kafka message `timestamp` | ISO8601 | UTC | 发送时间 |
| 本地文件路径 | `YYYY-MM-DD/HH` | UTC | 存储目录 |
| 本地文件 `timestamp` | ISO8601 | **本地时间** | 文件内时间字段 |

---

## 4. Agent 模块

### 4.1 相关文件

| 文件 | 时间处理内容 |
|------|------------|
| [elastic_mapping_config.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/agent/config/elastic_mapping_config.py) | 时间格式转换、ES文档构建 |
| [data_saver.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/agent/es_client/data_saver.py) | 调用时间转换函数 |

### 4.2 时间转换函数

#### 4.2.1 `normalize_datetime()`

```python
def normalize_datetime(date_str: str) -> int:
    """将日期字符串转换为 epoch_millis 格式"""
    if not date_str:
        return int(datetime.now().timestamp() * 1000)
    
    # 尝试匹配 ISO8601 格式
    iso8601_pattern = r'(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(\.\d+)?(Z)?'
    match = re.match(iso8601_pattern, date_str)
    
    if match:
        date_part = match.group(1)
        time_part = match.group(2)
        is_utc = match.group(4) == 'Z'
        
        if is_utc:
            utc_dt = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M:%S')
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            return int(utc_dt.timestamp() * 1000)
        else:
            dt = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M:%S')
            return int(dt.timestamp() * 1000)  # 无时区信息时按本地时间处理
    
    # 其他格式处理...
```

#### 4.2.2 `to_epoch_millis()`

```python
def to_epoch_millis(ts):
    """将时间戳转换为 epoch_millis 格式"""
    if ts is None:
        return int(datetime.now().timestamp() * 1000)
    if isinstance(ts, (int, float)):
        if ts > 1e12:  # 已经是毫秒
            return int(ts)
        else:  # 是秒
            return int(ts * 1000)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except:
            # 其他格式处理...
            return int(datetime.now().timestamp() * 1000)
```

### 4.3 ES 文档时间字段构建

```python
# elastic_mapping_config.py - build_elastic_document()
doc = {
    # ... 其他字段 ...
    
    # 时间戳（使用 epoch_millis 格式以确保正确的 date 类型映射）
    'log_timestamp': to_epoch_millis(log_ts),
    'analysis_timestamp': int(datetime.utcnow().timestamp() * 1000),
    'ingestion_time': to_epoch_millis(actual_log.get('ingestion_time')),
    
    # ...
}
```

### 4.4 时间字段汇总（agent）

| 字段 | 格式 | 时区 | 说明 |
|------|------|------|------|
| `log_timestamp` | epoch_millis | UTC | 原始日志时间 |
| `analysis_timestamp` | epoch_millis | UTC | AI分析时间 |
| `ingestion_time` | epoch_millis | **取决于输入** | 继承自 rulesMatching |

### 4.5 Dify API 时间处理

Dify 平台在工作流中处理时间字段，但 Agent 模块仅传递 `log_id`、`ip`、`path` 等字段，**不直接传递时间戳到 Dify**。

---

## 5. Website 后端模块

### 5.1 相关文件
[website/backend/v1/api/views.py](file:///d:/tools/ProgrammeTools/python/正规项目/LogSentinel/services/website/backend/v1/api/views.py)

### 5.2 时间处理策略

后端采用**双索引时间格式策略**：

| 索引 | 时间字段 | 格式 | 查询方式 |
|------|---------|------|---------|
| `nginx-log-raw` | `@timestamp` | ISO8601 | 使用 ISO8601 字符串范围查询 |
| `log_analysis_reports` | `analysis_timestamp` | epoch_millis | 使用毫秒数值范围查询 |

### 5.3 查询时间范围构建

#### 5.3.1 nginx-log-raw 查询（ISO8601 格式）

```python
now = datetime.utcnow()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
today_start_str = today_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
now_str = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

query = {
    "range": {
        "@timestamp": {
            "gte": today_start_str,
            "lte": now_str
        }
    }
}
```

#### 5.3.2 log_analysis_reports 查询（epoch_millis 格式）

```python
now = datetime.utcnow()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
today_start_ms = int(today_start.timestamp() * 1000)
now_ms = int(now.timestamp() * 1000)

query = {
    "range": {
        "analysis_timestamp": {
            "gte": today_start_ms,
            "lte": now_ms
        }
    }
}
```

### 5.4 时间戳转换函数

#### 5.4.1 `format_timestamp()` - 报告详情/列表

```python
def format_timestamp(self, timestamp):
    """格式化时间戳（UTC转本地时间）"""
    if isinstance(timestamp, str):
        # 尝试多种 ISO8601 格式
        for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(timestamp.replace('+00:00', 'Z').rstrip('Z'), fmt.replace('Z', ''))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                local_dt = dt.astimezone()  # 转换为本地时区
                return local_dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                continue
    elif isinstance(timestamp, (int, float)):
        # epoch_millis 转换
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
```

#### 5.4.2 `format_time()` - 最近告警

```python
def format_time(self, timestamp):
    """格式化时间为相对时间"""
    if isinstance(timestamp, str):
        if timestamp.endswith('Z'):
            timestamp = timestamp[:-1] + '+00:00'
        dt = datetime.fromisoformat(timestamp)
    else:
        dt = datetime.fromtimestamp(timestamp / 1000)  # epoch_millis
    
    now = datetime.now(timezone.utc)
    diff = now - dt.replace(tzinfo=timezone.utc)
    
    if diff.days > 0:
        return f"{diff.days} 天前"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours} 小时前"
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"{minutes} 分钟前"
    else:
        return "刚刚"
```

### 5.5 时区转换（LogTrendView）

```python
china_tz = timezone(timedelta(hours=8))
for bucket in buckets:
    key_str = bucket['key_as_string']
    utc_dt = datetime.fromisoformat(key_str.replace('Z', '+00:00'))
    china_dt = utc_dt.astimezone(china_tz)  # UTC → UTC+8
    time_part = china_dt.strftime("%H:%M")
```

---

## 6. Website 前端模块

### 6.1 时间处理特点

前端**不进行时间转换**，直接使用后端返回的格式化字符串：

| 字段 | 后端返回格式 | 前端展示 |
|------|------------|---------|
| `generatedAt` | `2026-06-30 16:00:00` | 直接显示 |
| `time` | `5 分钟前` / `刚刚` | 直接显示 |
| `log_timestamp` | `2026-06-30 16:00:00` | 直接显示 |

### 6.2 时间筛选

```typescript
const timeRanges = [
  { value: "today", label: "今天" },
  { value: "week", label: "最近7天" },
  { value: "month", label: "最近30天" },
  { value: "quarter", label: "最近3个月" },
  { value: "year", label: "最近1年" },
  { value: "all", label: "全部时间" },
];
```

前端传递时间范围参数到后端，由后端计算具体时间范围。

---

## 7. Elasticsearch 索引时间格式汇总

### 7.1 nginx-log-raw

| 字段 | 类型 | 格式 | 时区 |
|------|------|------|------|
| `@timestamp` | date | `strict_date_optional_time\| \|yyyy-MM-dd HH:mm:ss` | UTC |

### 7.2 matched_logs

| 字段 | 类型 | 格式 | 时区 |
|------|------|------|------|
| `@timestamp` | date | `strict_date_optional_time\| \|yyyy-MM-dd HH:mm:ss` | UTC |
| `ingestion_time` | date | `strict_date_optional_time\| \|yyyy-MM-dd HH:mm:ss` | **本地时间** |

### 7.3 log_analysis_reports

| 字段 | 类型 | 格式 | 时区 |
|------|------|------|------|
| `log_timestamp` | date | `epoch_millis` | UTC |
| `analysis_timestamp` | date | `epoch_millis` | UTC |
| `ingestion_time` | date | `epoch_millis` | **取决于输入** |

---

## 8. 时间流转完整链路

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. kafka_producer_from_logs.py                                        │
│    输入: 原始日志文件 (日期为历史日期)                                   │
│    处理: datetime.now() → 替换日期为当前本地日期                        │
│    输出: "[30/Jun/2026:13:55:36 +0800]" (保留原始时区偏移)            │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼ Kafka (log.raw)
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Logstash (logstash.conf)                                           │
│    输入: "[30/Jun/2026:13:55:36 +0800]"                               │
│    处理: date filter → 解析时区偏移 → 转换为 UTC                         │
│    输出: "@timestamp": "2026-06-30T05:55:36.000Z" (ISO8601, UTC)       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
          ES (nginx-log-raw)              Kafka (log.audit)
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. rulesMatching                                                       │
│    输入: "@timestamp": "2026-06-30T05:55:36.000Z" (UTC, ISO8601)       │
│    处理:                                                               │
│      - datetime.now().isoformat() → "ingestion_time" (本地时间)         │
│      - datetime.utcnow().isoformat() → Kafka消息"timestamp" (UTC)       │
│    输出:                                                               │
│      - ES (matched_logs): @timestamp(UTC), ingestion_time(本地)        │
│      - Kafka (log.risk): timestamp(UTC), log_entry                     │
│      - 本地JSON: timestamp(本地时间)                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼ Kafka (log.risk)
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. agent                                                               │
│    输入: "@timestamp": "2026-06-30T05:55:36.000Z" (UTC, ISO8601)       │
│    处理:                                                               │
│      - to_epoch_millis() → log_timestamp (epoch_millis, UTC)           │
│      - datetime.utcnow().timestamp()*1000 → analysis_timestamp (UTC)   │
│      - to_epoch_millis(ingestion_time) → ingestion_time (原值转换)      │
│    输出: ES (log_analysis_reports) - 所有时间字段为 epoch_millis       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼ Elasticsearch
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. website/backend                                                     │
│    输入: epoch_millis / ISO8601 (UTC)                                  │
│    处理:                                                               │
│      - format_timestamp(): UTC → 本地时间字符串 "YYYY-MM-DD HH:MM:SS"   │
│      - format_time(): UTC → 相对时间 "5分钟前"                          │
│      - LogTrendView: UTC → UTC+8 时间字符串                             │
│    输出: REST API 响应 (本地时间字符串)                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼ HTTP API
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. website/frontend                                                    │
│    输入: 本地时间字符串                                                 │
│    处理: 直接展示，不做时间转换                                         │
│    输出: 可视化界面                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 时间问题分析与建议

### 9.1 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| **rulesMatching 使用本地时间** | `data_saver.py` 第115、128行 | `ingestion_time` 存储为本地时间，与其他字段不一致 |
| **normal_log 本地存储时间不一致** | `data_saver.py` 第115、128行 | 文件内 `timestamp` 和文件名使用本地时间，目录使用 UTC |
| **ingestion_time 时区不确定** | `log_analysis_reports` 索引 | 继承自 rulesMatching 的本地时间，但存储为 epoch_millis |
| **缺少统一的时间规范** | 全项目 | 不同模块使用不同时区和格式 |

### 9.2 建议

根据项目记忆中的约束：**"All timestamps must be stored in UTC"**

1. **统一 rulesMatching 的时间使用 UTC**：
   - 将 `data_saver.py` 中的 `datetime.now()` 改为 `datetime.utcnow()`
   - 保持所有时间字段一致为 UTC

2. **统一日志文件名和目录格式**：
   - 使用 UTC 时间创建文件名和目录

3. **文档化时间规范**：
   - 在项目文档中明确所有时间字段的时区和格式要求

4. **添加时间字段注释**：
   - 在代码中添加注释说明每个时间字段的时区和用途

---

## 10. 时间格式对照表

| 阶段 | 模块 | 时间字段 | 格式 | 时区 |
|------|------|---------|------|------|
| 日志生成 | kafka_producer | - | `dd/MMM/yyyy:HH:mm:ss Z` | 原始日志时区 |
| Logstash | logstash.conf | `@timestamp` | ISO8601 | UTC |
| 规则匹配 | rulesMatching | `@timestamp` | ISO8601 | UTC |
| 规则匹配 | rulesMatching | `ingestion_time` | ISO8601 | **本地时间** |
| 规则匹配 | rulesMatching | Kafka message `timestamp` | ISO8601 | UTC |
| AI分析 | agent | `log_timestamp` | epoch_millis | UTC |
| AI分析 | agent | `analysis_timestamp` | epoch_millis | UTC |
| AI分析 | agent | `ingestion_time` | epoch_millis | **取决于输入** |
| 后端响应 | website/backend | `generatedAt` | `YYYY-MM-DD HH:MM:SS` | **本地时间** |
| 后端响应 | website/backend | `time` | 相对时间 | - |
| 前端展示 | website/frontend | 所有时间字段 | 字符串 | 直接展示 |