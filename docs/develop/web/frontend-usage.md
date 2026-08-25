# 前端 ↔ 后端 接口调用对照表

> 前端根目录: `services/website/frontend/v1/`
> 统一请求封装: [lib/api/client.ts](../../../services/website/frontend/v1/lib/api/client.ts) (`apiFetch`)
> 业务接口前缀: `/api/v1`（由 `apiFetch` 自动拼接）

## 1. 调用全景图

| 前端位置 | 调用方式 | 请求方法 | 后端路径 | 触发场景 | 刷新策略 |
| --- | --- | --- | --- | --- | --- |
| [lib/api/auth.ts:20](../../../services/website/frontend/v1/lib/api/auth.ts) | `apiFetch('/auth/login/')` | POST | `/api/v1/auth/login/` | 登录页提交 | 单次 |
| [lib/api/auth.ts:31](../../../services/website/frontend/v1/lib/api/auth.ts) | `apiFetch('/auth/me/')` | GET | `/api/v1/auth/me/` | AuthProvider 启动 / 登录后 | 启动 1 次 |
| [lib/api/auth.ts:39](../../../services/website/frontend/v1/lib/api/auth.ts) | `apiFetch('/auth/logout/')` | POST | `/api/v1/auth/logout/` | Header 退出登录 | 单次 |
| [lib/api/client.ts:37](../../../services/website/frontend/v1/lib/api/client.ts) | `fetch('/api/v1/auth/refresh/')` | POST | `/api/v1/auth/refresh/` | 401 自动续签 | 失败时跳登录 |
| [app/page.tsx:38](../../../services/website/frontend/v1/app/page.tsx) | `apiFetch('/dashboard/stats/')` | GET | `/api/v1/dashboard/stats/` | 仪表盘首屏 | 每 10s |
| [components/dashboard/threat-distribution-chart.tsx:41](../../../services/website/frontend/v1/components/dashboard/threat-distribution-chart.tsx) | `apiFetch('/dashboard/threat-distribution/?range=all')` | GET | `/api/v1/dashboard/threat-distribution/` | 仪表盘图表 | 每 10s |
| [components/dashboard/recent-alerts.tsx:78](../../../services/website/frontend/v1/components/dashboard/recent-alerts.tsx) | `apiFetch('/dashboard/recent-alerts/')` | GET | `/api/v1/dashboard/recent-alerts/` | 仪表盘最近告警 | 定时刷新 |
| [components/dashboard/log-volume-chart.tsx:29](../../../services/website/frontend/v1/components/dashboard/log-volume-chart.tsx) | `apiFetch('/logs/trend/')` | GET | `/api/v1/logs/trend/` | 仪表盘日志量图 | 定时刷新 |
| [app/reports/page.tsx:252](../../../services/website/frontend/v1/app/reports/page.tsx) | `apiFetch('/reports/stats/')` | GET | `/api/v1/reports/stats/` | 报告页加载 | 单次 |
| [app/reports/page.tsx:289](../../../services/website/frontend/v1/app/reports/page.tsx) | `apiFetch('/reports/list/?...')` | GET | `/api/v1/reports/list/` | 报告页筛选/分页 | 依赖项变化时 |
| [components/dashboard/report-detail-modal.tsx:66](../../../services/website/frontend/v1/components/dashboard/report-detail-modal.tsx) | `apiFetch(\`/reports/${reportId}/\`)` | GET | `/api/v1/reports/<report_id>/` | 点击报告行打开弹窗 | 单次 |
| [lib/api/agent.ts:74](../../../services/website/frontend/v1/lib/api/agent.ts) | `fetch('/api/v1/agent/<type>/chat')` | POST (SSE) | `/api/v1/agent/<agent_type>/chat` | Agent 页发送消息 | 流式 |
| [lib/api/agent.ts:124](../../../services/website/frontend/v1/lib/api/agent.ts) | `fetch('/api/v1/agent/<type>/chat/sync')` | POST | `/api/v1/agent/<agent_type>/chat/sync` | （预留同步调用） | 单次 |

## 2. 页面 → 接口映射

### 2.1 `/` 仪表盘（首页）

源码: [app/page.tsx](../../../services/website/frontend/v1/app/page.tsx) · 子组件 [components/dashboard/](../../../services/website/frontend/v1/components/dashboard/)

| 组件 | 接口 |
| --- | --- |
| `app/page.tsx` | `GET /dashboard/stats/` (每 10s) |
| `<ThreatDistributionChart>` | `GET /dashboard/threat-distribution/?range=all` (每 10s) |
| `<RecentAlerts>` | `GET /dashboard/recent-alerts/` (定时) |
| `<LogVolumeChart>` | `GET /logs/trend/` (定时) |
| `<SystemStatus>` `<StatCard>` `<AIInsights>` | 无后端调用（静态占位） |

### 2.2 `/login` 登录页

源码: [app/login/page.tsx](../../../services/website/frontend/v1/app/login/page.tsx)

- 表单提交 → `useAuth().login(username, password)` → 内部依次:
  1. `POST /auth/login/` → 拿到 access/refresh，写入 localStorage + cookie
  2. `GET /auth/me/` → 拉取用户信息回填 `AuthProvider`
- 成功后 `router.push('/')`

### 2.3 `/reports` 报告页

源码: [app/reports/page.tsx](../../../services/website/frontend/v1/app/reports/page.tsx)

| 时机 | 接口 | 参数 |
| --- | --- | --- |
| 页面挂载 | `GET /reports/stats/` | 无 |
| 筛选/分页变化 | `GET /reports/list/?<params>` | `page`, `size`, `risk_level`, `attack_type`, `keyword` |
| 点击列表行 | `GET /reports/<report_id>/` | 路径参数 |

筛选参数构造: [app/reports/page.tsx:276-287](../../../services/website/frontend/v1/app/reports/page.tsx)（`URLSearchParams` 拼接）

### 2.4 `/agent` AI 智能体页

源码: [app/agent/page.tsx](../../../services/website/frontend/v1/app/agent/page.tsx) · 封装 [lib/api/agent.ts](../../../services/website/frontend/v1/lib/api/agent.ts)

- 发送消息 → `streamAgentChat(message, threadId, 'analysis_explorer', callbacks)`
  - `POST /api/v1/agent/analysis_explorer/chat`，`Accept: text/event-stream`
  - 请求体: `{ message, thread_id, history: [] }`
  - SSE 事件回调: `onToken / onToolCall / onToolResult / onDone / onError`
- 不走 `apiFetch`，手动注入 `Authorization`（因为要拿 ReadableStream），不自动 refresh。

### 2.5 其他页面（暂无后端调用）

下列页面当前为静态占位，未对接后端 API（后端对应的 mock 接口已存在，可直接接入）：

| 页面 | 后端已有接口（待接入） |
| --- | --- |
| [app/alerts/page.tsx](../../../services/website/frontend/v1/app/alerts/page.tsx) | `GET /alerts/`, `/alerts/rules/` |
| [app/anomaly/page.tsx](../../../services/website/frontend/v1/app/anomaly/page.tsx) | `GET /anomalies/`, `/anomalies/<id>/` |
| [app/incidents/page.tsx](../../../services/website/frontend/v1/app/incidents/page.tsx) | `GET /incidents/`, `/incidents/<id>/` |
| [app/infrastructure/page.tsx](../../../services/website/frontend/v1/app/infrastructure/page.tsx) | `GET /infrastructure/servers/` |
| [app/threat-intel/page.tsx](../../../services/website/frontend/v1/app/threat-intel/page.tsx) | `GET /threats/`, `/threats/feeds/` |
| [app/ai-analysis/page.tsx](../../../services/website/frontend/v1/app/ai-analysis/page.tsx) | `GET /ai/models/`, `/ai/analyses/` |
| [app/settings/page.tsx](../../../services/website/frontend/v1/app/settings/page.tsx) | 暂无 |

> 这些页面的 mock 数据直接写死在组件中，等后端切换到真实数据源后再接入。

## 3. 通用机制（所有页面共享）

### 3.1 apiFetch 行为

源码: [lib/api/client.ts](../../../services/website/frontend/v1/lib/api/client.ts)

- 自动注入 `Authorization: Bearer <access>`
- 自动注入 `Content-Type: application/json`（仅当有 body 时）
- 401 → 调用 `POST /auth/refresh/`，成功后重试原请求一次；失败则清 token 并跳 `/login`
- 在 `/login` 路径下不跳转，避免循环

### 3.2 Token 存储

| Key | 位置 | 用途 |
| --- | --- | --- |
| `aw_access` | localStorage | access token，`apiFetch` 取用 |
| `aw_refresh` | localStorage | refresh token，401 时取用 |
| `aw_access` | cookie (max-age=3600) | Edge middleware 读取（SSR） |

- 登录时由 [lib/api/auth.ts:26](../../../services/website/frontend/v1/lib/api/auth.ts) 的 `tokenStorage.set(access, refresh)` 同时写入。
- refresh 成功后由 [lib/api/client.ts:44](../../../services/website/frontend/v1/lib/api/client.ts) 更新 access（若返回新 refresh 也一并更新）。
- 登出/失败时由 `tokenStorage.clear()` 同时清空 localStorage + cookie。

### 3.3 路由保护

- [middleware.ts](../../../services/website/frontend/v1/middleware.ts) 在 Edge 层检查 `aw_access` cookie，无则跳 `/login?next=<原路径>`。
- 仅 `/login` 放行，其余所有页面（含 `/`）均要求 cookie 存在。
- 注意：Edge middleware **不校验 JWT 有效性**，只校验存在；真正的鉴权在 Django。

## 4. 待办对照

如需补充对接，可按下表逐一接入：

- [ ] alerts → `/alerts/`, `/alerts/rules/`
- [ ] anomaly → `/anomalies/`, `/anomalies/<id>/`
- [ ] incidents → `/incidents/`, `/incidents/<id>/`
- [ ] infrastructure → `/infrastructure/servers/`
- [ ] threat-intel → `/threats/`, `/threats/feeds/`
- [ ] ai-analysis → `/ai/models/`, `/ai/analyses/`
- [ ] settings → 暂无后端
