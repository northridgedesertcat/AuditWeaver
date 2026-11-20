# LogSentinel 项目时间系统重构计划

## 目录

1. [项目时间问题概览](#1-项目时间问题概览)
2. [重构目标与原则](#2-重构目标与原则)
3. [修改文件清单](#3-修改文件清单)
4. [各模块详细重构方案](#4-各模块详细重构方案)
5. [新增工具模块](#5-新增工具模块)
6. [影响评估](#6-影响评估)
7. [实施顺序](#7-实施顺序)
8. [验证方案](#8-验证方案)

---

## 1. 项目时间问题概览

### 1.1 当前时间系统混乱现状

经过对整个项目的全面扫描，发现以下时间处理问题：

| 问题类型 | 出现次数 | 影响范围 | 严重程度 |
|---------|---------|---------|---------|
| `datetime.now()` (本地时间) | 8处 | rulesMatching, agent | **高** |
| `datetime.utcnow()` (无时区感知) | 7处 | website/backend, rulesMatching | **高** |
| ISO字符串存储 | 5处 | rulesMatching, agent | **中** |
| 硬编码UTC+8 | 2处 | website/backend | **高** |
| 服务端时间格式化 | 4处 | website/backend | **高** |
| ES Mapping不一致 | 2处 | creatMapping.py | **高** |

### 1.2 时间字段职责混乱

当前系统中时间字段的用途没有统一规范：

| 字段 | 当前用途 | 正确用途 |
|------|---------|---------|
| `@timestamp` | 日志时间 | ✅ 日志时间 |
| `ingestion_time` | 写入时间(本地) | ❌ 应为UTC |
| `analysis_timestamp` | AI分析时间 | ✅ AI分析时间 |
| `log_timestamp` | 日志时间(agent) | ✅ 日志时间 |

### 1.3 时间流转链路问题

```
日志生成 → Kafka → Logstash → ES(ISO) → rulesMatching(混合) → Kafka(ISO) → agent(混合) → ES(epoch) → Django(格式化) → Next.js(直接显示)
                                                                                                   ↑
                                                                                            问题集中区
```

---

## 2. 重构目标与原则

### 2.1 统一标准

**【UTC + epoch_millis】**

- 所有Python代码必须使用 `datetime.now(timezone.utc)` 获取当前时间
- 所有存入ES的时间字段必须转换为 `epoch_millis` (int)
- API层只返回 `epoch_millis`，不做任何时间格式化
- 前端负责所有时间显示的格式化和时区转换

### 2.2 时间字段职责

| 字段 | 含义 | 用途 |
|------|------|------|
| `log_timestamp` | 日志真正发生时间 | Dashboard统计、今日攻击、趋势图、时间过滤 |
| `ingestion_time` | 日志进入系统时间 | Kafka消费监控、系统监控 |
| `analysis_timestamp` | AI分析完成时间 | AI报告排序、AI耗时统计 |

### 2.3 禁止规则

- ❌ `datetime.now()`
- ❌ `datetime.utcnow()`
- ❌ 手动UTC+8计算
- ❌ `timezone(timedelta(hours=8))`
- ❌ 服务端 `strftime()` 格式化输出
- ❌ API返回格式化时间字符串

---

## 3. 修改文件清单

### 3.1 Python后端文件

| 文件路径 | 修改类型 | 修改原因 |
|---------|---------|---------|
| `services/common/time_utils.py` | **新增** | 统一时间工具类 |
| `services/rulesMatching/dataTransfer/data_saver.py` | 修改 | ingestion_time使用UTC+epoch_millis |
| `services/rulesMatching/utils.py` | 修改 | timestamp使用epoch_millis |
| `services/rulesMatching/main.py` | 修改 | 启动时间日志使用UTC |
| `services/agent/config/elastic_mapping_config.py` | 修改 | 统一使用timezone.utc |
| `services/website/backend/v1/api/views.py` | 修改 | API返回epoch_millis，移除格式化 |
| `services/website/backend/v1/backend/settings.py` | 修改 | TIME_ZONE改为UTC |
| `docker/config/elasticsearch/creatMapping.py` | 修改 | 统一时间字段格式 |
| `services/testdata/kafka_producer_from_logs.py` | 修改 | 使用UTC时间 |
| `services/testdata/generate_demo_logs.py` | 修改 | 使用UTC时间 |

### 3.2 Next.js前端文件

| 文件路径 | 修改类型 | 修改原因 |
|---------|---------|---------|
| `services/website/frontend/v1/lib/time.ts` | **新增** | 统一时间格式化工具 |
| `services/website/frontend/v1/components/dashboard/recent-alerts.tsx` | 修改 | 使用time.ts工具 |
| `services/website/frontend/v1/components/dashboard/report-detail-modal.tsx` | 修改 | 使用time.ts工具 |
| `services/website/frontend/v1/components/dashboard/log-volume-chart.tsx` | 修改 | 使用time.ts工具 |
| `services/website/frontend/v1/app/reports/page.tsx` | 修改 | 使用time.ts工具 |

---

## 4. 各模块详细重构方案

### 4.1 新增：统一时间工具模块

**文件**: `services/common/time_utils.py`

```python
from datetime import datetime, timezone
from typing import Optional, Union

def now_utc() -> datetime:
    """获取当前UTC时间（带时区信息）"""
    return datetime.now(timezone.utc)

def to_epoch_millis(dt: Union[datetime, int, float, str, None]) -> int:
    """
    将时间转换为 epoch_millis 格式
    
    Args:
        dt: datetime对象、时间戳(秒/毫秒)、ISO字符串或None
    
    Returns:
        epoch_millis (int)
    """
    if dt is None:
        return int(now_utc().timestamp() * 1000)
    
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    
    if isinstance(dt, (int, float)):
        if dt > 1e12:
            return int(dt)
        else:
            return int(dt * 1000)
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except:
            return int(now_utc().timestamp() * 1000)
    
    return int(now_utc().timestamp() * 1000)

def epoch_millis_now() -> int:
    """获取当前时间的 epoch_millis"""
    return int(now_utc().timestamp() * 1000)

def format_for_filename() -> str:
    """生成UTC时间格式的文件名"""
    return now_utc().strftime('%Y%m%d_%H%M%S_%f')

def format_for_directory() -> tuple[str, str]:
    """生成UTC时间格式的目录名 (日期, 小时)"""
    return (now_utc().strftime('%Y-%m-%d'), now_utc().strftime('%H'))
```

---

### 4.2 rulesMatching 模块

#### 4.2.1 data_saver.py

**修改内容**:

| 行号 | 原代码 | 修改后 |
|------|--------|--------|
| 115 | `datetime.now().strftime(...)` | `time_utils.format_for_filename()` |
| 128 | `datetime.now().isoformat()` | `time_utils.epoch_millis_now()` |
| 229 | `datetime.now().isoformat()` | `time_utils.epoch_millis_now()` |
| 367 | `datetime.utcnow().isoformat()` | `time_utils.epoch_millis_now()` |

**修改原因**: 
- `ingestion_time` 字段使用本地时间，与项目规范冲突
- 文件内 `timestamp` 和文件名使用本地时间，目录使用UTC，不一致
- Kafka消息 `timestamp` 使用ISO字符串，应改为epoch_millis

**影响**:
- ✅ 业务逻辑不变
- ❌ 影响ES `matched_logs` 索引的 `ingestion_time` 字段格式（需更新mapping）
- ❌ 影响本地JSON文件格式

#### 4.2.2 utils.py

**修改内容**:

| 行号 | 原代码 | 修改后 |
|------|--------|--------|
| 64 | `datetime.utcnow().isoformat()` | `time_utils.epoch_millis_now()` |

**修改原因**: 检测结果的timestamp字段使用ISO字符串，应统一为epoch_millis

#### 4.2.3 main.py

**修改内容**:

| 行号 | 原代码 | 修改后 |
|------|--------|--------|
| 179 | `datetime.now().strftime(...)` | `time_utils.now_utc().strftime(...)` |

**修改原因**: 启动时间日志使用本地时间，应使用UTC

---

### 4.3 agent 模块

#### 4.3.1 elastic_mapping_config.py

**修改内容**:

| 行号 | 原代码 | 修改后 |
|------|--------|--------|
| 88 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 111 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 122 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 125 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 192 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 210 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 211 | `datetime.now().timestamp() * 1000` | `time_utils.epoch_millis_now()` |
| 261 | `datetime.utcnow().timestamp() * 1000` | `time_utils.epoch_millis_now()` |

**修改原因**: 
- 多处使用 `datetime.now()` 获取本地时间作为默认值
- `datetime.utcnow()` 不携带时区信息，应使用 `datetime.now(timezone.utc)`

---

### 4.4 Django API 模块

#### 4.4.1 views.py

**修改内容**:

1. **移除所有服务端时间格式化函数**:
   - 删除 `format_timestamp()` (第857-886行)
   - 删除 `format_timestamp()` (第1013-1044行)
   - 删除 `format_time()` (第542-570行)

2. **修改时间字段返回**:
   - `generatedAt`: 返回 `analysis_timestamp` (epoch_millis)
   - `time`: 返回 `ingestion_time` (epoch_millis)
   - `log_timestamp`: 返回原始epoch_millis

3. **移除硬编码UTC+8**:
   - 删除 `timezone(timedelta(hours=8))` 相关代码
   - 删除 `astimezone()` 转换

4. **修改时间范围查询**:
   - 统一使用 epoch_millis 格式构建查询范围

**修改原因**:
- API层不负责格式化时间，应只返回epoch_millis
- 硬编码UTC+8破坏国际化能力
- `astimezone()` 转换导致时间显示与用户时区不一致

**影响**:
- ❌ **API契约变更** - 所有时间字段从字符串变为整数
- ❌ 影响前端所有页面（需要前端适配）
- ⚠️ Dashboard统计需要使用 `log_timestamp` 而非 `analysis_timestamp`

#### 4.4.2 settings.py

**修改内容**:

| 行号 | 原代码 | 修改后 |
|------|--------|--------|
| 95 | `TIME_ZONE = 'Asia/Shanghai'` | `TIME_ZONE = 'UTC'` |

**修改原因**: Django后端应使用UTC时区

---

### 4.5 Elasticsearch Mapping

#### 4.5.1 creatMapping.py

**修改内容**:

| 索引 | 字段 | 原格式 | 修改后 |
|------|------|--------|--------|
| `matched_logs` | `ingestion_time` | `strict_date_optional_time` | `epoch_millis` |
| `matched_logs` | `@timestamp` | `strict_date_optional_time` | `epoch_millis` |

**注意**: `nginx-log-raw` 的 `@timestamp` 由 Logstash 写入，Logstash 默认输出 ISO8601 格式。如需改为 epoch_millis，需要修改 `logstash.conf` 的输出配置。

**风险评估**:
- ⚠️ **HIGH RISK** - 修改 nginx-log-raw 的时间格式需要同时修改 Logstash pipeline
- ⚠️ 需要重新索引历史数据

---

### 4.6 Next.js 前端

#### 4.6.1 新增：lib/time.ts

```typescript
export function formatTimestamp(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const date = new Date(epochMs);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatRelative(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const now = Date.now();
  const diff = now - epochMs;
  
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;
  
  return formatDate(epochMs);
}

export function formatDate(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const date = new Date(epochMs);
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatTimeOnly(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "--:--";
  const date = new Date(epochMs);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
```

#### 4.6.2 修改前端组件

| 文件 | 修改内容 |
|------|---------|
| `recent-alerts.tsx` | `alert.time` 使用 `formatRelative()` |
| `report-detail-modal.tsx` | `generatedAt` 和 `log_timestamp` 使用 `formatTimestamp()` |
| `reports/page.tsx` | `generatedAt` 使用 `formatTimestamp()` |
| `log-volume-chart.tsx` | 时间标签使用 `formatTimeOnly()` |

---

## 5. 新增工具模块

### 5.1 Python 时间工具

**路径**: `services/common/time_utils.py`

提供统一的时间处理接口，替换所有分散的时间处理逻辑。

### 5.2 TypeScript 时间工具

**路径**: `services/website/frontend/v1/lib/time.ts`

提供前端统一的时间格式化函数，支持：
- 格式化完整时间戳
- 格式化相对时间
- 格式化日期
- 格式化仅时间部分

---

## 6. 影响评估

### 6.1 业务影响

| 影响项 | 评估 | 说明 |
|--------|------|------|
| Dashboard统计 | ⚠️ 需要确认 | 需确保使用 `log_timestamp` 而非 `analysis_timestamp` |
| 报告列表排序 | ✅ 不变 | 仍使用 `analysis_timestamp` |
| 告警时间显示 | ✅ 不变 | 前端格式化后显示效果一致 |
| 日志存储 | ⚠️ 需要确认 | 本地JSON文件格式变化 |

### 6.2 数据库影响

| 影响项 | 评估 | 说明 |
|--------|------|------|
| PostgreSQL | ✅ 无影响 | Django项目未使用数据库存储时间数据 |

### 6.3 ES Mapping 影响

| 索引 | 影响 | 处理方式 |
|------|------|---------|
| `log_analysis_reports` | ✅ 无影响 | 已使用 epoch_millis |
| `matched_logs` | ❌ 需更新 | 修改mapping + 重新索引 |
| `nginx-log-raw` | ⚠️ **高风险** | 需修改Logstash pipeline |

### 6.4 API 影响

| 影响项 | 评估 | 说明 |
|--------|------|------|
| 时间字段类型 | ❌ 全部变更 | 字符串 → 整数(epoch_millis) |
| 响应结构 | ✅ 不变 | 字段名称不变 |
| 前端适配 | ❌ 必须适配 | 所有页面需要使用新的时间工具 |

---

## 7. 实施顺序

```
Phase 1: 基础准备
├── 创建 services/common/time_utils.py
├── 创建 services/website/frontend/v1/lib/time.ts
└── 修改 Django settings.py TIME_ZONE

Phase 2: 后端重构（按数据流向）
├── 修改 rulesMatching/data_saver.py
├── 修改 rulesMatching/utils.py
├── 修改 rulesMatching/main.py
└── 修改 agent/config/elastic_mapping_config.py

Phase 3: ES Mapping 更新
├── 修改 creatMapping.py
└── 更新 ES 索引 mapping（需要手动执行）

Phase 4: Django API 重构
└── 修改 website/backend/v1/api/views.py

Phase 5: 前端适配
├── 修改 recent-alerts.tsx
├── 修改 report-detail-modal.tsx
├── 修改 reports/page.tsx
└── 修改 log-volume-chart.tsx

Phase 6: 测试数据更新
├── 修改 kafka_producer_from_logs.py
└── 修改 generate_demo_logs.py
```

---

## 8. 验证方案

### 8.1 单元测试

```bash
# 验证时间工具函数
python -m pytest services/common/tests/test_time_utils.py

# 验证规则匹配模块
python -m pytest services/rulesMatching/test/

# 验证 agent 模块
python -m pytest services/agent/tests/
```

### 8.2 集成测试

1. **时间链路验证**:
   - 发送测试日志 → Kafka → rulesMatching → agent → ES
   - 验证所有时间字段均为 epoch_millis 格式
   - 验证 API 返回 epoch_millis
   - 验证前端正确显示本地时间

2. **时区验证**:
   - 在不同时区环境下测试前端显示
   - 验证 UTC+8、UTC+9、UTC-5 等时区显示正确

3. **Dashboard统计验证**:
   - 验证今日攻击数使用 `log_timestamp`
   - 验证报告列表排序使用 `analysis_timestamp`
   - 验证趋势图时间正确

### 8.3 回归测试

- 确保所有原有功能不受影响
- 确保告警、报告、日志查询等核心功能正常

---

## 附录：高风险项说明

### A. nginx-log-raw 时间格式变更

**风险**: 修改此索引的 `@timestamp` 格式需要同步修改 Logstash pipeline 配置。

**建议方案**:
1. **方案A**（推荐）: 保持 nginx-log-raw 的 `@timestamp` 为 ISO8601 格式（由 Logstash 控制），仅在 rulesMatching 和 agent 层统一使用 epoch_millis
2. **方案B**: 修改 Logstash 输出配置，将 `@timestamp` 改为 epoch_millis，然后重新索引所有历史数据

### B. API 契约变更

**风险**: 所有前端页面依赖时间字段的字符串格式。

**缓解措施**:
1. 先完成前端时间工具函数开发
2. 同步更新所有前端组件
3. 在测试环境验证后再部署到生产环境

### C. ES 历史数据

**风险**: 修改 mapping 后，历史数据的时间格式不一致。

**缓解措施**:
1. 修改 mapping 使用 `epoch_millis`
2. 编写数据迁移脚本，将历史数据的时间字段转换为 epoch_millis
3. 或创建新索引，重新导入数据
