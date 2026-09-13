# 后端 API 接口明细

> 源码根目录: `services/website/backend/v1/`
> 根路由: [backend/urls.py](../../../services/website/backend/v1/backend/urls.py) → `path('api/v1/', include('api.urls'))`
> 业务路由表: [api/urls.py](../../../services/website/backend/v1/api/urls.py)

所有路径前缀均为 `/api/v1/`。下表「认证」列中，`是` 表示需要 JWT Bearer（全局默认 `IsAuthenticated`），`否` 表示 `AllowAny`。

## 接口速查表

| # | 方法 | 路径 | 认证 | 视图 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | GET | `/api/v1/health/` | 否 | `HealthCheckView` | 健康检查 |
| 2 | POST | `/api/v1/auth/login/` | 否 | `LoginView` | 登录获取 JWT |
| 3 | POST | `/api/v1/auth/refresh/` | 否 | `TokenRefreshView` | 刷新 access token |
| 4 | GET | `/api/v1/auth/me/` | 是 | `MeView` | 获取当前用户信息 |
| 5 | POST | `/api/v1/auth/logout/` | 是 | `LogoutView` | 登出（黑名单 refresh） |
| 6 | GET | `/api/v1/dashboard/stats/` | 是 | `DashboardStatsView` | 仪表盘统计卡片 |
| 7 | GET | `/api/v1/dashboard/threat-distribution/` | 是 | `ThreatDistributionView` | 威胁等级分布 |
| 8 | GET | `/api/v1/dashboard/recent-alerts/` | 是 | `RecentAlertsView` | 最近告警 |
| 9 | GET | `/api/v1/logs/` | 是 | `LogsView` | 日志分页查询 |
| 10 | GET | `/api/v1/logs/stats/` | 是 | `LogStatsView` | 日志统计 |
| 11 | GET | `/api/v1/logs/trend/` | 是 | `LogTrendView` | 日志量趋势 |
| 12 | GET | `/api/v1/alerts/` | 是 | `AlertsView` | 告警列表 |
| 13 | GET | `/api/v1/alerts/rules/` | 是 | `AlertRulesView` | 告警规则列表 |
| 14 | GET | `/api/v1/incidents/` | 是 | `IncidentsView` | 事件列表 |
| 15 | GET | `/api/v1/incidents/<incident_id>/` | 是 | `IncidentDetailView` | 事件详情 |
| 16 | GET | `/api/v1/anomalies/` | 是 | `AnomaliesView` | 异常列表 |
| 17 | GET | `/api/v1/anomalies/<anomaly_id>/` | 是 | `AnomalyDetailView` | 异常详情 |
| 18 | GET | `/api/v1/infrastructure/servers/` | 是 | `ServersView` | 服务器列表 |
| 19 | GET | `/api/v1/threats/` | 是 | `ThreatsView` | 威胁指标列表 |
| 20 | GET | `/api/v1/threats/feeds/` | 是 | `ThreatFeedsView` | 威胁情报源 |
| 21 | GET | `/api/v1/ai/models/` | 是 | `AIModelsView` | AI 模型列表 |
| 22 | GET | `/api/v1/ai/analyses/` | 是 | `RecentAnalysesView` | 最近 AI 分析 |
| 23 | GET | `/api/v1/reports/stats/` | 是 | `ReportStatsView` | 报告统计 |
| 24 | GET | `/api/v1/reports/list/` | 是 | `ReportListView` | 报告列表分页 |
| 25 | GET | `/api/v1/reports/<report_id>/` | 是 | `ReportDetailView` | 报告详情 |
| 26 | POST | `/api/v1/agent/<agent_type>/chat` | 是 | `AgentProxyView` | Agent 流式对话 (SSE) |
| 27 | POST | `/api/v1/agent/<agent_type>/chat/sync` | 是 | `AgentProxyView` | Agent 同步对话 (JSON) |
| 28 | GET | `/api/v1/agent/health` | 是 | `AgentProxyView` | Agent 服务健康 |
| 29 | GET | `/api/v1/agent/types` | 是 | `AgentProxyView` | Agent 类型列表 |

> Agent 路由本身**不带尾斜杠**，被 `ApiTrailingSlashMiddleware` 显式排除，详见 [auth-and-middleware.md](./auth-and-middleware.md)。

---

## 1. 健康检查

`GET /api/v1/health/` · `HealthCheckView` · [api/views.py:126](../../../services/website/backend/v1/api/views.py)

- 认证: `AllowAny`
- 参数: 无
- 数据源: `is_es_available()` ping Elasticsearch
- 响应:

```json
{
  "status": "ok",
  "elasticsearch": "available" | "unavailable"
}
```

---

## 2. 认证模块

路由: [accounts/urls.py](../../../services/website/backend/v1/accounts/urls.py) · 视图: [accounts/views.py](../../../services/website/backend/v1/accounts/views.py)

### 2.1 登录

`POST /api/v1/auth/login/` · `LoginView` · [accounts/views.py:10](../../../services/website/backend/v1/accounts/views.py)

- 认证: `AllowAny`
- 请求体:

```json
{ "username": "admin", "password": "admin123456" }
```

- 响应 (200):

```json
{ "access": "<JWT>", "refresh": "<JWT>" }
```

- 序列化器: `LoginSerializer`（复用 simplejwt `TokenObtainPairSerializer`，[accounts/serializers.py:7](../../../services/website/backend/v1/accounts/serializers.py)）
- 错误: 401 用户名/密码错误；400 字段缺失。

### 2.2 刷新 Token

`POST /api/v1/auth/refresh/` · `TokenRefreshView`（simplejwt 内置）

- 认证: `AllowAny`
- 请求体: `{ "refresh": "<JWT>" }`
- 响应: `{ "access": "<新 JWT>" }`（若开启 `ROTATE_REFRESH_TOKENS` 还会返回新 refresh）

### 2.3 当前用户

`GET /api/v1/auth/me/` · `MeView` · [accounts/views.py:22](../../../services/website/backend/v1/accounts/views.py)

- 认证: `IsAuthenticated`
- 响应 (`UserSerializer`):

```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin",
  "display_name": "",
  "is_active": true
}
```

### 2.4 登出

`POST /api/v1/auth/logout/` · `LogoutView` · [accounts/views.py:29](../../../services/website/backend/v1/accounts/views.py)

- 认证: `IsAuthenticated`
- 请求体: `{ "refresh": "<JWT>" }`（可选）
- 行为: 将 refresh token 加入黑名单（`rest_framework_simplejwt.token_blacklist`）
- 响应: `205 Reset Content`（无 body）

---

## 3. 仪表盘

### 3.1 仪表盘统计卡片

`GET /api/v1/dashboard/stats/` · `DashboardStatsView` · [api/views.py:258](../../../services/website/backend/v1/api/views.py)

- 数据源: Elasticsearch
  - `nginx-log-raw` 今日日志量、总日志量
  - `log_analysis_reports` 今日攻击日志数、今日高危告警数 (risk_level ∈ {Critical, High})
- 响应 (`DashboardStatsSerializer`):

```json
{
  "logVolume": "12.3K",     // 字符串，>=1M 显示 M，>=1K 显示 K
  "attackLogs": 28,          // 今日攻击日志
  "highSeverityAlerts": 5,   // 今日高危告警
  "riskIps": 0,              // 占位字段，恒为 0
  "totalLogs": 1847000,      // 总日志数
  "avgResponseTime": "0ms"   // 占位字段
}
```

### 3.2 威胁等级分布

`GET /api/v1/dashboard/threat-distribution/` · `ThreatDistributionView` · [api/views.py:136](../../../services/website/backend/v1/api/views.py)

- 数据源: Elasticsearch `log_analysis_reports`，按 `risk_level` 字段 terms 聚合
- 查询参数:
  - `range`: `all`(默认) | `today`（today 限定今日 `analysis_timestamp`）
- 响应: 五种风险等级（Critical/High/Medium/Low/Normal），每级返回 `{name, value, color}`

```json
{
  "data": {
    "Critical": { "name": "严重", "value": 3, "color": "oklch(0.5 0.25 25)" },
    "High":     { "name": "高危", "value": 5, "color": "oklch(0.65 0.2 60)" },
    "Medium":   { "name": "中危", "value": 12, "color": "oklch(0.75 0.15 95)" },
    "Low":      { "name": "低危", "value": 8, "color": "oklch(0.75 0.12 145)" },
    "Normal":   { "name": "正常", "value": 0, "color": "oklch(0.7 0.05 260)" }
  },
  "total": 28,
  "range": "all"
}
```

> ES 中 `unknown` 级别会映射为 `Low`，未知大小写自动归一化。

### 3.3 最近告警

`GET /api/v1/dashboard/recent-alerts/` · `RecentAlertsView` · [api/views.py:580](../../../services/website/backend/v1/api/views.py)

- 数据源: Elasticsearch `log_analysis_reports`，按 `ingestion_time` 倒序，仅取 10 条
- 参数: 无
- 响应:

```json
{
  "data": [
    {
      "id": "<ES _id>",
      "severity": "critical",                // risk_level 小写
      "message": "检测到可疑SQL注入",
      "source": "AI Security Analyzer",
      "time": "<ingestion_time>",
      "ip": "192.168.1.10"
    }
  ]
}
```

- 字段映射: severity←risk_level, message←`"检测到可疑"+attack_type_ai`, ip←original_log.ip, time←ingestion_time

---

## 4. 日志

### 4.1 日志列表

`GET /api/v1/logs/` · `LogsView` · [api/views.py:348](../../../services/website/backend/v1/api/views.py)

- 数据源: Elasticsearch `nginx-log-raw`，按 `@timestamp` 倒序
- 查询参数:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 1 | 页码 |
| `size` | int | 20 | 每页条数 |
| `ip` | string | - | 精确匹配 ip |
| `method` | string | - | 精确匹配 method |
| `status` | string | - | 精确匹配 status |
| `path` | string | - | wildcard 模糊匹配 path |

- 响应:

```json
{
  "data": [ /* _source 全字段原文 */ ],
  "total": 1847,
  "page": 1,
  "size": 20
}
```

### 4.2 日志统计

`GET /api/v1/logs/stats/` · `LogStatsView` · [api/views.py:401](../../../services/website/backend/v1/api/views.py)

- 数据源: Elasticsearch `nginx-log-raw`
- 响应:

```json
{
  "total": 1847000,
  "today": 12345,
  "top_ips":   [{ "ip": "1.2.3.4", "count": 880 }],
  "top_paths": [{ "path": "/login", "count": 760 }],
  "status_distribution": { "200": 1500, "404": 230 }
}
```

### 4.3 日志量趋势

`GET /api/v1/logs/trend/` · `LogTrendView` · [api/views.py:632](../../../services/website/backend/v1/api/views.py)

- 数据源: Elasticsearch `nginx-log-raw`，按 `@timestamp` 做小时级 `date_histogram`，覆盖最近 24 小时
- 响应:

```json
{ "data": [ { "time": 1700000000000, "logs": 1024 } /* 共 24 个桶 */ ] }
```

> ES 不可用时返回最近 24 小时全 0 兜底数据。

---

## 5. 告警 (Mock)

> 来源: `api/mock_data.py` 的 `MOCK_ALERTS` / `MOCK_ALERT_RULES`

### 5.1 告警列表

`GET /api/v1/alerts/` · `AlertsView` · [api/views.py:482](../../../services/website/backend/v1/api/views.py)

- 查询参数: `severity` (默认 all)、`status` (默认 all)
- 响应:

```json
{
  "data": [ /* AlertSerializer */ ],
  "stats": { /* ALERT_STATS */ }
}
```

### 5.2 告警规则

`GET /api/v1/alerts/rules/` · `AlertRulesView` · [api/views.py:499](../../../services/website/backend/v1/api/views.py)

- 参数: 无
- 响应: `AlertRuleSerializer[]`，字段见 [serializers-and-models.md](./serializers-and-models.md)

---

## 6. 事件 (Mock)

### 6.1 事件列表

`GET /api/v1/incidents/` · `IncidentsView` · [api/views.py:504](../../../services/website/backend/v1/api/views.py)

- 查询参数: `status` (默认 all)
- 响应: `{ "data": IncidentSerializer[], "stats": INCIDENT_STATS }`

### 6.2 事件详情

`GET /api/v1/incidents/<incident_id>/` · `IncidentDetailView` · [api/views.py:518](../../../services/website/backend/v1/api/views.py)

- 路径参数: `incident_id` (字符串)
- 响应: `IncidentSerializer` 或 404 `{ "error": "Incident not found" }`

---

## 7. 异常 (Mock)

### 7.1 异常列表

`GET /api/v1/anomalies/` · `AnomaliesView` · [api/views.py:526](../../../services/website/backend/v1/api/views.py)

- 查询参数: `severity` (默认 all)
- 响应: `{ "data": AnomalySerializer[], "stats": ANOMALY_STATS }`

### 7.2 异常详情

`GET /api/v1/anomalies/<anomaly_id>/` · `AnomalyDetailView` · [api/views.py:540](../../../services/website/backend/v1/api/views.py)

- 路径参数: `anomaly_id`
- 响应: `AnomalySerializer` 或 404

---

## 8. 基础设施 / 威胁情报 / AI (Mock)

### 8.1 服务器列表

`GET /api/v1/infrastructure/servers/` · `ServersView` · [api/views.py:548](../../../services/website/backend/v1/api/views.py)

- 响应: `{ "data": ServerSerializer[], "stats": INFRA_STATS }`

### 8.2 威胁指标

`GET /api/v1/threats/` · `ThreatsView` · [api/views.py:556](../../../services/website/backend/v1/api/views.py)

- 响应: `{ "data": ThreatSerializer[], "stats": THREAT_STATS }`

### 8.3 威胁情报源

`GET /api/v1/threats/feeds/` · `ThreatFeedsView` · [api/views.py:564](../../../services/website/backend/v1/api/views.py)

- 响应: 直接返回 `MOCK_THREAT_FEEDS`（裸数组/对象）

### 8.4 AI 模型列表

`GET /api/v1/ai/models/` · `AIModelsView` · [api/views.py:568](../../../services/website/backend/v1/api/views.py)

- 响应: `{ "data": AIModelSerializer[], "stats": AI_STATS }`

### 8.5 最近 AI 分析

`GET /api/v1/ai/analyses/` · `RecentAnalysesView` · [api/views.py:576](../../../services/website/backend/v1/api/views.py)

- 响应: 直接返回 `MOCK_RECENT_ANALYSES`

---

## 9. 报告

> 数据源: Elasticsearch `log_analysis_reports`，按 `analysis_timestamp` 倒序

### 9.1 报告统计

`GET /api/v1/reports/stats/` · `ReportStatsView` · [api/views.py:694](../../../services/website/backend/v1/api/views.py)

- 响应:

```json
{
  "total": 1024,         // log_analysis_reports 总数
  "highRisk": 28,        // risk_level ∈ [Critical, High]
  "mediumRisk": 56,      // risk_level = Medium
  "todayNew": 12         // 今日 analysis_timestamp
}
```

### 9.2 报告列表

`GET /api/v1/reports/list/` · `ReportListView` · [api/views.py:936](../../../services/website/backend/v1/api/views.py)

- 查询参数:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 1 | 页码 |
| `size` | int | 10 | 每页条数 |
| `risk_level` | string | all | `critical`/`high`/`medium`/`low`/`all` |
| `attack_type` | string | all | 精确匹配 `attack_type_ai` |
| `keyword` | string | - | `multi_match` 跨 `attack_type_ai`/`original_log.ip`/`original_log.path` |

- 响应:

```json
{
  "data": [
    {
      "id": "<ES _id>",
      "title": "检测到SQL注入",
      "riskLevel": "critical",      // 小写
      "attackType": "SQL注入",
      "sourceIp": "192.168.1.10",
      "targetPath": "/login",
      "generatedAt": "2026-08-25 12:34:56",   // 已转本地时区
      "aiConfidence": 95,
      "status": "pending"                      // 恒为 pending
    }
  ],
  "total": 1024,
  "page": 1,
  "size": 10
}
```

> `risk_level` 查询时若为 `critical`/`high`/`medium`/`low` 会被首字母大写后送入 ES（`Critical` 等）。

### 9.3 报告详情

`GET /api/v1/reports/<report_id>/` · `ReportDetailView` · [api/views.py:797](../../../services/website/backend/v1/api/views.py)

- 路径参数: `report_id` (ES 文档 `_id`)
- 行为: 先 `es.get` 拿分析报告；若报告含 `event_id`，再 `es.search` `nginx-log-raw` 取原始日志原文
- 响应:

```json
{
  "id": "<report_id>",
  "title": "检测到SQL注入",
  "riskLevel": "critical",
  "attackType": "SQL注入",
  "confidence": 95,                       // = risk_score
  "riskScore": 95,
  "generatedAt": "2026-08-25 12:34:56",
  "summary": "...",
  "reasoning": [ "..." ],                // 数组
  "recommendations": [ "..." ],           // 数组
  "originalRiskData": {
    "event_id": "...",
    "ip": "...",
    "log_timestamp": "...",
    "user_agent": "...",
    "status": 200,
    "path": "/login",
    "original_log": "GET /login HTTP/1.1 ..."
  }
}
```

- 时间字段统一通过 `format_timestamp()` 由 UTC 转本地时区，格式 `%Y-%m-%d %H:%M:%S`
- 找不到时: 404 `{ "error": "Report not found" }`

---

## 10. Agent 反代

路由: [api/urls.py:58-63](../../../services/website/backend/v1/api/urls.py) · 视图: `AgentProxyView` · [api/views.py:63](../../../services/website/backend/v1/api/views.py)

> Django 作为反向代理，将 `/api/v1/agent/*` 透传到内部 FastAPI（`settings.AGENT_FASTAPI_BASE`，默认 `:8001`）。
> 详细机制见 [auth-and-middleware.md](./auth-and-middleware.md)。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | `/api/v1/agent/<agent_type>/chat` | 透传请求体，以 `text/event-stream` 流式回传 SSE |
| POST | `/api/v1/agent/<agent_type>/chat/sync` | 透传请求体，以 `application/json` 同步回传 |
| GET | `/api/v1/agent/health` | 透传，超时 10s |
| GET | `/api/v1/agent/types` | 透传，超时 10s |

- 认证: `IsAuthenticated`（统一由 Django 校验 JWT，FastAPI 不再校验）
- `agent_type` 当前合法值: `analysis_explorer`；新增 agent 无需改此路由。
- 请求体（chat / chat/sync）:

```json
{
  "message": "分析过去 24 小时内的高危告警",
  "thread_id": "uuid 或 null",
  "history": []
}
```

- SSE 事件类型（由 FastAPI 产出，前端在 [lib/api/agent.ts](../../../services/website/frontend/v1/lib/api/agent.ts) 解析）:

```jsonc
{ "type": "token",       "content": "..." }
{ "type": "tool_call",   "tool": "search_logs", "args": { } }
{ "type": "tool_result", "tool": "search_logs", "summary": "命中 12 条" }
{ "type": "done" }
{ "type": "error",       "content": "..." }
```

- 错误: FastAPI 不可用时返回 `502 { "error": "agent service unavailable" }`，未知 `agent_type` 由 FastAPI 返回 404 透传。
- 响应头: `X-Accel-Buffering: no`、`Cache-Control: no-cache`（保证 SSE 实时）。
