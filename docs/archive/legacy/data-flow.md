# LogSentinel 数据流转结构文档

## 概述

本文档梳理 LogSentinel 系统中四个核心模块的数据流转结构：

1. **rulesMatching** - 规则匹配模块
2. **agent** - AI分析代理模块
3. **services/website** - 后端API模块
4. **services/website/frontend** - 前端展示模块

---

## 1. rulesMatching 模块

### 1.1 数据处理流程

| 步骤 | 处理内容 | 说明 |
|------|---------|------|
| 1 | 从 Kafka 消费日志 | 消费 `log.structured` topic，JSON 反序列化 |
| 2 | 验证消息格式 | 检查必需字段 `ip`, `path`, `method`, `status` |
| 3 | 单条攻击检测 | RuleEngine.detect() 调用 AttackDetectors 进行多类型攻击检测 |
| 4 | 合并检测结果 | 将同一日志的多个攻击类型检测结果合并为单个 detection_result |
| 5 | 分流处理 | 攻击日志 → ES + Kafka；正常日志 → 本地 JSON |

> **说明**: rulesMatching 模块仅负责规则匹配，不进行风险评估。风险等级和置信度由 Dify AI 分析模块生成。

### 1.2 输入数据结构（来自 Kafka）

**数据来源**: `log.structured` topic（经过 Logstash 清洗）

**必需字段**: `ip`, `path`, `method`, `status`（验证时检查这四个字段）

```json
{
   "event_id": "uuid-string",                    // string (日志唯一标识)
   "ip": "192.168.164.29",                       // string (IP地址)
   "method": "GET",                              // string (HTTP方法)
   "path": "/profile",                           // string (请求路径)
   "http_version": "1.1",                        // string (HTTP版本)
   "status": 200,                                // integer (HTTP状态码)
   "bytes": 557,                                 // integer (响应字节数)
   "referrer": "http://example.com/index.html",  // string (来源URL)
   "user_agent": "Mozilla/5.0 (...)",            // string (用户代理)
   "log_timestamp": 1719763200000                // integer (epoch_millis, 日志时间戳)
}
```

### 1.3 中间处理数据结构（检测结果）

**规则引擎单条检测返回结果** (`RuleEngine.detect()`):

```json
{
  "log_entry": { ... },               // 原始日志条目
  "detections": [                     // 检测到的攻击列表
    {
      "event_id": "uuid-string",              // string (日志唯一标识)
      "attack_type": "sql_injection",         // string (攻击类型)
      "matched_rules": {                      // object (匹配详情)
        "keywords": ["UNION", "SELECT"],      // array[string] - 匹配的关键字
        "patterns": ["UNION SELECT"]          // array[string] - 匹配的正则模式
      },
      "detection_time": 1719763201000,        // integer (epoch_millis)
      "is_attack": true                       // boolean
    }
  ],
  "total_detections": 1               // integer (检测到的攻击类型数量)
}
```

> **说明**: rulesMatching 模块不计算置信度和严重程度，仅记录匹配的攻击类型和规则。

**规则引擎批量检测返回结果** (`RuleEngine.detect_batch()`):

```json
{
  "results": [ ... ],                 // array - 单条检测结果列表
  "total_logs": 100,                  // integer
  "total_detections": 15              // integer
}
```

### 1.4 输出数据结构

#### 1.4.1 攻击日志（发送到 Kafka）

**输出 Topic**: `log.analysis`

```json
{
  "event_id": "uuid-string",              // string (日志唯一标识)
  "ip": "192.168.164.29",                 // string (IP地址)
  "path": "/profile",                     // string (请求路径)
  "method": "GET",                        // string (HTTP方法)
  "status": 200,                          // integer (HTTP状态码)
  "user_agent": "Mozilla/5.0 (...)",      // string (用户代理)
  "log_timestamp": 1719763200000,          // integer (epoch_millis，优先从 log_entry 获取，其次是 @timestamp/timestamp，最后使用当前时间)
  "detection_time": 1719763201000,        // integer (epoch_millis)
  "detection_result": {                   // object (合并后的检测结果)
    "attack_type": "sql_injection",       // string (攻击类型，多个用逗号分隔)
    "matched_rules": {                    // object (匹配规则详情)
      "keywords": ["UNION", "SELECT"],    // array[string]
      "patterns": ["UNION SELECT"]        // array[string]
    },
    "detection_time": 1719763201000,      // integer (epoch_millis)
    "is_attack": true                     // boolean
  }
}
```

> **说明**: rulesMatching 模块不输出 risk_level 和 confidence，这些字段由 Dify AI 分析模块生成。

#### 1.4.2 攻击日志（存储到 Elasticsearch，索引: `matched_logs`）

```json
{
  "event_id": "uuid-string",              // keyword (日志唯一标识)
  "ip": "192.168.164.29",                 // ip (IP地址)
  "path": "/profile",                     // keyword (请求路径)
  "method": "GET",                        // keyword (HTTP方法)
  "status": 200,                          // integer (HTTP状态码)
  "user_agent": "Mozilla/5.0 (...)",      // text + keyword (用户代理)
  "log_timestamp": 1719763200000,         // date (epoch_millis, 日志时间)
  "ingestion_time": 1719763201000,        // date (epoch_millis, 入库时间)
  "detection_result": {                   // object (合并后的检测结果)
    "attack_type": "sql_injection",
    "matched_rules": {
      "keywords": ["UNION", "SELECT"],
      "patterns": ["UNION SELECT"]
    },
    "detection_time": 1719763201000,
    "is_attack": true
  },
  "matched_rules": {                      // keyword (匹配规则快捷访问)
    "keywords": ["UNION", "SELECT"],
    "patterns": ["UNION SELECT"]
  }
}
```

#### 1.4.3 正常日志（保存到本地 JSON 文件）

**存储路径**: `services/rulesMatching/temporaryDatas/unmatchDatas/YYYY-MM-DD/HH/normal_log_{timestamp}.json`

**说明**: 正常日志直接保存原始日志 JSON 内容，不做额外包装。

```json
{
  "event_id": "uuid-string",
  "ip": "192.168.164.29",
  "method": "GET",
  "path": "/index.html",
  "status": 200,
  "bytes": 557,
  "user_agent": "Mozilla/5.0 (...)",
  "log_timestamp": 1719763200000,
  ...
}
```

---

## 2. agent 模块

### 2.1 数据处理流程

| 步骤 | 处理内容 | 说明 |
|------|---------|------|
| 1 | 从 Kafka 消费攻击日志 | 消费 `log.analysis` topic，处理扁平化结构 |
| 2 | 提取日志字段 | 从扁平化结构中提取关键字段，兼容嵌套 `log_entry` 结构 |
| 3 | 构建 Dify 请求 | 组装 `inputs.logDatas`（JSON字符串，包含 `matched_type` 字段）和 `user` 字段 |
| 4 | 调用 Dify API | 发送 POST 请求到 Dify Workflow API |
| 5 | 解析 Dify 响应 | 从 `data.outputs.structured_output`、`outputs.structured_output`、`result` 或 `answer` 提取结构化结果 |
| 6 | 构建 ES 文档 | 扁平化数据结构，时间戳优先从 `@timestamp` 获取，其次是 `timestamp` |
| 7 | 存储到 Elasticsearch | 写入 `log_analysis_reports` 索引 |

### 2.2 接收数据结构（来自 Kafka）

```json
{
  "event_id": "uuid-string",
  "ip": "192.168.164.29",
  "path": "/profile",
  "method": "GET",
  "status": 200,
  "user_agent": "Mozilla/5.0 (...)",
  "log_timestamp": 1719763200000,
  "detection_time": 1719763201000,
  "detection_result": {
    "attack_type": "sql_injection",
    "matched_rules": {
      "keywords": ["UNION", "SELECT"],
      "patterns": ["UNION SELECT"]
    },
    "detection_time": 1719763201000,
    "is_attack": true
  }
}
```

### 2.3 发送到 Dify 的数据结构

**API 端点**: `POST {base_url}/chat-messages`

```json
{
  "inputs": {
    "logDatas": "{\"log_id\":\"uuid-string\",\"ip\":\"192.168.164.29\",\"path\":\"/profile\",\"method\":\"GET\",\"status\":200,\"user_agent\":\"Mozilla/5.0 (...)\",\"matched_type\":\"sql_injection\"}"
  },
  "user": "log_uuid-string"
}
```

**logDatas 展开结构**:

```json
{
  "log_id": "uuid-string",              // string - event_id
  "ip": "192.168.164.29",               // string
  "path": "/profile",                   // string
  "method": "GET",                      // string
  "status": 200,                        // integer
  "user_agent": "Mozilla/5.0 (...)",    // string
  "matched_type": "sql_injection"       // string - 规则匹配的攻击类型（来自 detection_result.attack_type）
}
```

> **说明**: 不再发送 confidence 和 severity 到 Dify，避免影响 AI 分析判断。风险评估完全由 Dify 负责。

### 2.4 从 Dify 接收的数据结构

**提取优先级**: agent 模块会尝试从多个位置提取结构化输出：
1. `data.outputs.structured_output`（Workflow 模式）
2. `data.outputs`（直接 outputs 字段）
3. `outputs.structured_output`（另一种 Workflow 响应格式）
4. `outputs`（另一种格式）
5. `result` 字段
6. `answer` 字段（可能是 JSON 字符串或字典）

**字段回退规则**: 每个字段支持多个别名：
- `risk_level` → `threat_level`（默认值: `unknown`）
- `risk_score` → `score`（默认值: `0`）
- `attack_type_ai` → `attack_type` → `attack_category`（默认值: `''`）
- `summary` → `event_summary` → `analysis_summary`（默认值: `''`）
- `reasoning` → `analysis_reasoning`（默认值: `[]`）
- `recommendations` → `suggestions` → `mitigation_steps`（默认值: `[]`）

```json
{
  "data": {
    "outputs": {
      "structured_output": {
        "risk_level": "High",               // string (Critical/High/Medium/Low/Normal)
        "risk_score": 85,                   // integer (0-100)
        "attack_type": "SQL注入攻击",        // string
        "summary": "检测到SQL注入攻击...",    // string
        "reasoning": [                      // array[string]
          "请求路径包含SQL关键字",
          "符合已知攻击模式"
        ],
        "recommendations": [               // array[string]
          "阻止该IP访问",
          "检查WAF规则"
        ]
      }
    }
  }
}
```

### 2.5 存储到 Elasticsearch 的数据结构（索引: `log_analysis_reports`）

```json
{
  "event_id": "uuid-string",                 // keyword
  "ip": "192.168.164.29",                    // ip
  "path": "/profile",                        // keyword
  "method": "GET",                           // keyword
  "status": 200,                             // integer
  "user_agent": "Mozilla/5.0 (...)",         // text + keyword
  "attack_type": "sql_injection",            // keyword - 规则匹配结果（来自 detection_result.attack_type）
  "risk_level": "High",                      // keyword - AI分析结果
  "risk_score": 85,                          // integer
  "attack_type_ai": "SQL注入攻击",            // keyword
  "summary": "检测到SQL注入攻击...",           // text + keyword
  "reasoning": ["请求路径包含SQL关键字", ...], // text + keyword
  "recommendations": ["阻止该IP访问", ...],   // text + keyword
  "log_timestamp": 1719763200000,            // date (epoch_millis，优先从 @timestamp 获取，其次是 timestamp)
  "analysis_timestamp": 1719763201000,       // date (epoch_millis，AI分析时间)
  "ingestion_time": 1719763201000,           // date (epoch_millis，入库时间)
  "dify_response": { ... },                  // object (禁用搜索，完整Dify响应)
  "original_log": { ... }                    // object (禁用搜索，原始日志数据)
}
```

> **说明**: 不再存储 rulesMatching 模块的 confidence 和 severity。风险等级 (risk_level) 和风险分数 (risk_score) 完全来自 Dify AI 分析结果。

---

## 3. services/website 模块（后端API）

### 3.1 数据处理流程

| 步骤 | 处理内容 | 说明 |
|------|---------|------|
| 1 | 查询 Elasticsearch | 根据不同接口查询 `log_analysis_reports` 或 `nginx-log-raw` 索引 |
| 2 | 聚合/过滤数据 | 使用 ES 聚合查询统计数据，支持时间范围、风险等级等筛选 |
| 3 | 转换时间格式 | 将 epoch_millis 或 ISO8601 转换为本地时间字符串 |
| 4 | 格式化响应 | 构建前端所需的扁平化数据结构 |
| 5 | 序列化输出 | 使用 Django REST Framework Serializer 验证并序列化 |

### 3.2 各接口数据结构

> **接口数据来源说明**: 
> - ✅ **真实 ES 数据**: DashboardStats, ThreatDistribution, Logs, LogStats, ReportStats, ReportList, ReportDetail, RecentAlerts, LogTrend
> - 📋 **Mock 数据**: AlertsView, AlertRulesView, IncidentsView, IncidentDetailView, AnomaliesView, AnomalyDetailView, ServersView, ThreatsView, ThreatFeedsView, AIModelsView, RecentAnalysesView

#### 3.2.1 DashboardStats (`/api/v1/dashboard/stats/`)

**从 ES 获取**:
- `nginx-log-raw`: 今日日志量、总日志数（ISO8601时间戳）
- `log_analysis_reports`: 今日攻击日志数、高危告警数（epoch_millis时间戳）

**给前端**:

```json
{
  "logVolume": "2.3M",       // string (格式化后的数字)
  "attackLogs": 28,          // integer
  "highSeverityAlerts": 174, // integer
  "riskIps": 0,              // integer (当前为0，预留字段)
  "totalLogs": 1847,         // integer
  "avgResponseTime": "0ms"   // string
}
```

#### 3.2.2 ThreatDistribution (`/api/v1/threat-distribution/`)

**从 ES 获取**: `log_analysis_reports` 的 `risk_level.keyword` 聚合

**给前端**:

```json
{
  "data": {
    "Critical": {
      "name": "严重",
      "value": 5,
      "color": "oklch(0.5 0.25 25)"
    },
    "High": {
      "name": "高危",
      "value": 12,
      "color": "oklch(0.65 0.2 60)"
    },
    "Medium": {
      "name": "中危",
      "value": 28,
      "color": "oklch(0.75 0.15 95)"
    },
    "Low": {
      "name": "低危",
      "value": 45,
      "color": "oklch(0.75 0.12 145)"
    },
    "Normal": {
      "name": "正常",
      "value": 8,
      "color": "oklch(0.7 0.05 260)"
    }
  },
  "total": 98,
  "range": "today"
}
```

#### 3.2.3 Logs (`/api/v1/logs/`)

**从 ES 获取**: `nginx-log-raw` 原始日志

**给前端**:

```json
{
  "data": [
    {
      "@timestamp": "2026-06-30T08:00:00.000Z",
      "event_id": "uuid-string",
      "ip": "192.168.164.29",
      "method": "GET",
      "path": "/profile",
      "status": 200,
      "bytes": 557,
      "user_agent": "Mozilla/5.0 (...)",
      ...
    }
  ],
  "total": 1000,
  "page": 1,
  "size": 20
}
```

#### 3.2.4 LogStats (`/api/v1/log-stats/`)

**从 ES 获取**: `nginx-log-raw` 的聚合统计

**给前端**:

```json
{
  "total": 100000,           // integer - 总日志数
  "today": 5000,             // integer - 今日日志数
  "top_ips": [               // array[object]
    {"ip": "192.168.1.1", "count": 1200},
    {"ip": "192.168.1.2", "count": 800}
  ],
  "top_paths": [             // array[object]
    {"path": "/index.html", "count": 500},
    {"path": "/api/data", "count": 300}
  ],
  "status_distribution": {   // object
    "200": 80000,
    "404": 15000,
    "500": 5000
  }
}
```

#### 3.2.5 ReportStats (`/api/v1/report-stats/`)

**从 ES 获取**: `log_analysis_reports` 的统计数据

**给前端**:

```json
{
  "total": 150,              // integer - 总报告数
  "highRisk": 25,            // integer - 高危报告数 (Critical + High)
  "mediumRisk": 45,          // integer - 中危报告数 (Medium)
  "todayNew": 10             // integer - 今日新增报告数
}
```

#### 3.2.6 ReportList (`/api/v1/reports/`)

**从 ES 获取**: `log_analysis_reports` 的文档列表

**给前端**:

```json
{
  "data": [
    {
      "id": "ES文档ID",
      "title": "检测到SQL注入攻击",
      "riskLevel": "high",           // string (小写)
      "attackType": "SQL注入攻击",
      "sourceIp": "192.168.164.29",
      "targetPath": "/profile",
      "generatedAt": "2026-06-30 16:00:00",  // string (本地时间)
      "aiConfidence": 85,                     // integer (使用 Dify 的 risk_score)
      "status": "pending"
    }
  ],
  "total": 150,
  "page": 1,
  "size": 10
}
```

#### 3.2.7 ReportDetail (`/api/v1/reports/{report_id}/`)

**从 ES 获取**: `log_analysis_reports` 单条文档 + `nginx-log-raw` 原始日志

**给前端**:

```json
{
  "id": "ES文档ID",
  "title": "检测到SQL注入攻击",
  "riskLevel": "high",
  "attackType": "SQL注入攻击",
  "confidence": 85,              // integer (使用 Dify 的 risk_score)
  "riskScore": 85,               // integer
  "generatedAt": "2026-06-30 16:00:00",
  "summary": "检测到SQL注入攻击，请求路径包含恶意SQL语句...",
  "reasoning": [
    "请求路径包含SQL关键字",
    "符合已知攻击模式"
  ],
  "recommendations": [
    "阻止该IP访问",
    "检查WAF规则配置"
  ],
  "originalRiskData": {
    "event_id": "uuid-string",
    "ip": "192.168.164.29",
    "log_timestamp": "2026-06-30 16:00:00",
    "user_agent": "Mozilla/5.0 (...)",
    "status": 200,
    "path": "/profile",
    "original_log": ""           // string - 原始日志文本
  }
}
```

> **说明**: confidence 字段现在使用 Dify 返回的 risk_score 值，不再使用 rulesMatching 模块的置信度。

#### 3.2.8 RecentAlerts (`/api/v1/recent-alerts/`)

**从 ES 获取**: `log_analysis_reports` 最近10条记录

**给前端**:

```json
{
  "data": [
    {
      "id": "ES文档ID",
      "severity": "high",              // string (小写，来自 risk_level)
      "message": "检测到可疑SQL注入攻击",        // string ("检测到可疑" + attack_type_ai)
      "source": "AI Security Analyzer",         // string (固定值)
      "time": 1719763201000,           // integer (epoch_millis，来自 ingestion_time)
      "ip": "192.168.164.29"           // string (来自 original_log.ip)
    }
  ]
}
```

#### 3.2.9 LogTrend (`/api/v1/log-trend/`)

**从 ES 获取**: `nginx-log-raw` 最近24小时按小时聚合

**给前端**:

```json
{
  "data": [
    {"time": 1719763200000, "logs": 1200},    // time: epoch_millis
    {"time": 1719766800000, "logs": 800},
    {"time": 1719770400000, "logs": 500},
    ...
  ]
}
```

---

## 4. services/website/frontend 模块

### 4.1 数据处理流程

| 步骤 | 处理内容 | 说明 |
|------|---------|------|
| 1 | 发起 API 请求 | 使用 `fetch` 调用后端 API |
| 2 | 解析响应数据 | JSON 解析，类型断言 |
| 3 | 状态管理 | 使用 React `useState`/`useEffect` 管理数据 |
| 4 | 格式化展示 | 格式化数字、时间、风险等级颜色 |
| 5 | 渲染组件 | 使用 UI 组件展示数据 |

### 4.2 获取的后端数据结构

#### 4.2.1 Dashboard 页面 (`app/page.tsx`)

**API**: `GET /api/v1/dashboard/stats/`

```typescript
interface DashboardStats {
  logVolume: string       // "2.3M" | "12K" | "500"（格式化后的数字）
  attackLogs: string      // "28"（后端返回 integer，前端转为 string）
  highSeverityAlerts: string // "174"（后端返回 integer，前端转为 string）
  riskIps: string         // "12"（后端返回 integer，前端转为 string）
  totalLogs: string       // "1847"（后端返回 integer，前端转为 string）
  avgResponseTime: string // "1.2s" | "0ms"
}
```

#### 4.2.2 ThreatDistributionChart 组件 (`components/dashboard/threat-distribution-chart.tsx`)

**API**: `GET /api/v1/dashboard/threat-distribution/?range=all`

```typescript
interface ThreatLevelData {
  name: string            // "严重" | "高危" | "中危" | "低危" | "信息"
  value: number           // 数量
  color: string           // oklch颜色值
}

interface ThreatDistributionResponse {
  data: {
    Critical: ThreatLevelData
    High: ThreatLevelData
    Medium: ThreatLevelData
    Low: ThreatLevelData
    Normal: ThreatLevelData
  }
  total: number
  range: string
}
```

#### 4.2.3 RecentAlerts 组件 (`components/dashboard/recent-alerts.tsx`)

**API**: `GET /api/v1/dashboard/recent-alerts/`

```typescript
interface Alert {
  id: string              // ES文档ID
  severity: string        // "critical" | "high" | "medium" | "low"
  message: string         // "检测到可疑SQL注入攻击"
  source: string          // "AI Security Analyzer"
  time: number            // epoch_millis
  ip: string              // "192.168.164.29"
}

interface RecentAlertsResponse {
  data: Alert[]
}
```

#### 4.2.4 LogVolumeChart 组件 (`components/dashboard/log-volume-chart.tsx`)

**API**: `GET /api/v1/logs/trend/`

```typescript
interface TrendData {
  time: number            // epoch_millis
  logs: number            // 该小时日志数量
}

interface LogTrendResponse {
  data: TrendData[]
}
```

#### 4.2.5 AI Analysis 页面 (`app/ai-analysis/page.tsx`)

**静态数据结构（待接入API）**:

```typescript
interface AIModel {
  id: string
  name: string
  type: string
  status: "running" | "training" | "stopped" | "error"
  accuracy: number        // 0-100
  latency: string         // "45ms"
  lastTrained: string     // "2024-01-14"
  tasksProcessed: number
}

interface AnalysisTask {
  id: number
  type: string            // "威胁检测" | "行为分析" | "异常检测"
  input: string
  result: string
  confidence: number      // 0-100
  status: "completed" | "processing"
  time: string            // "2 分钟前" | "进行中"
}
```

#### 4.2.6 AI Insights 组件 (`components/dashboard/ai-insights.tsx`)

**静态数据结构（待接入API）**:

```typescript
interface AIInsight {
  id: number
  type: "pattern" | "anomaly" | "prediction" | "recommendation"
  title: string
  description: string
  confidence: number      // 0-100
  time: string            // "5 分钟前"
}
```

---

## 数据流转总览

```
Kafka (log.structured)
    │
    ▼
┌─────────────────────────────────────────────┐
│           rulesMatching 模块                │
│  输入: Logstash清洗后的JSON日志              │
│  处理: 规则引擎攻击检测（单条）              │
│  输出:                                     │
│    ├─ 攻击日志 → Kafka (log.analysis)      │
│    ├─ 攻击日志 → ES (matched_logs)         │
│    └─ 正常日志 → 本地JSON文件               │
└─────────────────────────────────────────────┘
    │
    ▼ Kafka (log.analysis)
┌─────────────────────────────────────────────┐
│              agent 模块                     │
│  输入: 扁平化攻击日志（含detection_result）   │
│  处理:                                     │
│    ├─ 提取字段构建Dify请求                  │
│    ├─ 调用Dify API获取AI分析结果            │
│    └─ 构建ES文档存储                        │
│  输出: ES (log_analysis_reports)           │
└─────────────────────────────────────────────┘
    │
    ▼ Elasticsearch
┌─────────────────────────────────────────────┐
│         services/website 模块               │
│  输入: ES查询结果                           │
│  处理:                                     │
│    ├─ 聚合/过滤数据                         │
│    ├─ 时间戳转换 (epoch_millis → 本地时间)  │
│    └─ 格式化响应结构                        │
│  输出: REST API 响应                        │
└─────────────────────────────────────────────┘
    │
    ▼ HTTP API
┌─────────────────────────────────────────────┐
│      services/website/frontend 模块         │
│  输入: API响应JSON                          │
│  处理:                                     │
│    ├─ 状态管理 (useState/useEffect)        │
│    ├─ 数据格式化                           │
│    └─ 组件渲染                             │
│  输出: 可视化界面                           │
└─────────────────────────────────────────────┘
```

---

## 时间戳格式对照表

| 索引/模块 | 时间戳格式 | 字段名 |
|----------|-----------|--------|
| nginx-log-raw | ISO8601 | `@timestamp` |
| matched_logs | epoch_millis | `log_timestamp`, `ingestion_time` |
| log_analysis_reports | epoch_millis | `log_timestamp`, `analysis_timestamp`, `ingestion_time` |
| 后端响应 | 本地时间字符串 | `generatedAt`, `log_timestamp` |
| 前端展示 | 相对时间/本地时间 | `time`, `generatedAt` |

---

## 风险等级映射表

| Dify 返回值 | 后端存储 | 前端展示 | 颜色 |
|------------|---------|---------|------|
| Critical | Critical | critical | 红色 oklch(0.5 0.25 25) |
| High | High | high | 橙色 oklch(0.65 0.2 60) |
| Medium | Medium | medium | 黄色 oklch(0.75 0.15 95) |
| Low | Low | low | 绿色 oklch(0.75 0.12 145) |
| Normal | Normal | normal | 灰色 oklch(0.7 0.05 260) |
| unknown | unknown → Low | low | 绿色 |