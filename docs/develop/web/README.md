# AuditWeaver Web 接口文档

本目录梳理 `services/website`（Django + Next.js）的所有接口与请求链路，便于日后对照查阅。

## 目录结构

- [README.md](./README.md) — 总览、架构、目录导航（本文）
- [backend-api.md](./backend-api.md) — 后端全部 API 接口明细（路由 / 方法 / 参数 / 响应 / 认证 / 视图位置）
- [auth-and-middleware.md](./auth-and-middleware.md) — 认证、JWT、权限、中间件、Agent 反代链路
- [frontend-usage.md](./frontend-usage.md) — 前端页面/组件 ↔ 后端接口调用对照表
- [serializers-and-models.md](./serializers-and-models.md) — 序列化器字段与数据模型清单

## 源码定位

| 模块 | 路径 |
| --- | --- |
| Django 根路由 | [services/website/backend/v1/backend/urls.py](../../../services/website/backend/v1/backend/urls.py) |
| 业务 API 路由 | [services/website/backend/v1/api/urls.py](../../../services/website/backend/v1/api/urls.py) |
| 业务 API 视图 | [services/website/backend/v1/api/views.py](../../../services/website/backend/v1/api/views.py) |
| 账号认证路由 | [services/website/backend/v1/accounts/urls.py](../../../services/website/backend/v1/accounts/urls.py) |
| 账号认证视图 | [services/website/backend/v1/accounts/views.py](../../../services/website/backend/v1/accounts/views.py) |
| Django 配置 | [services/website/backend/v1/backend/settings.py](../../../services/website/backend/v1/backend/settings.py) |
| 尾斜杠中间件 | [services/website/backend/v1/backend/middleware.py](../../../services/website/backend/v1/backend/middleware.py) |
| ES 客户端 | [services/website/backend/v1/api/es_client.py](../../../services/website/backend/v1/api/es_client.py) |
| 前端 fetch 封装 | [services/website/frontend/v1/lib/api/client.ts](../../../services/website/frontend/v1/lib/api/client.ts) |
| 前端认证封装 | [services/website/frontend/v1/lib/api/auth.ts](../../../services/website/frontend/v1/lib/api/auth.ts) |
| 前端 Agent 封装 | [services/website/frontend/v1/lib/api/agent.ts](../../../services/website/frontend/v1/lib/api/agent.ts) |
| 前端 Edge 中间件 | [services/website/frontend/v1/middleware.ts](../../../services/website/frontend/v1/middleware.ts) |
| Next.js 配置(rewrites) | [services/website/frontend/v1/next.config.mjs](../../../services/website/frontend/v1/next.config.mjs) |

## 总体架构

```
浏览器
  │  相对路径 /api/v1/...
  ▼
Next.js (3000) ── next.config.mjs rewrites ──► Django (8000)
  │                                              │
  │ Edge middleware(middleware.ts)               │ 请求链路:
  │  - 读 aw_access cookie                       │   SecurityMiddleware
  │  - 无 token 跳转 /login                      │ → SessionMiddleware
  │                                              │ → CorsMiddleware
  │ 页面侧:                                       │ → ApiTrailingSlashMiddleware(补尾斜杠)
  │  apiFetch (lib/api/client.ts)                │ → CommonMiddleware
  │   - 注入 Bearer                               │ → CsrfViewMiddleware
  │   - 401 自动 refresh                          │ → AuthenticationMiddleware
  │   - refresh 失败跳 /login                     │ → 视图分发
  │                                              │
  │                                              ├── /api/v1/auth/*  (accounts)
  │                                              ├── /api/v1/dashboard/* /logs/* /alerts/*
  │                                              │   /incidents/* /anomalies/* /infrastructure/*
  │                                              │   /threats/* /ai/* /reports/*
  │                                              │   → api.views.* (查 ES 或返回 mock)
  │                                              │
  │                                              └── /api/v1/agent/<type>/*
  │                                                      ↓ 反代 (httpx)
  │                                                  FastAPI :8001 (agent_service)
  │                                                      → SSE / JSON 透传回前端
```

## 关键约定速查

- **API 前缀**: 所有业务接口统一为 `/api/v1/`，由根路由 `path('api/v1/', include('api.urls'))` 注入。
- **认证方式**: JWT Bearer。全局默认 `IsAuthenticated`，仅 `health/`、`auth/login/`、`auth/refresh/` 放行匿名访问。
- **数据来源**:
  - Elasticsearch 索引（`nginx-log-raw`、`log_analysis_reports`）→ 仪表盘/日志/报告/告警/威胁分布
  - 内存 Mock 数据（`api/mock_data.py`）→ 告警规则、事件、异常、服务器、威胁、AI 模型等占位接口
- **尾斜杠**: 业务接口必须以 `/` 结尾；`/api/v1/agent/*` 路由本身不带斜杠。前端通过 `trailingSlash: true` + Django 中间件双重保障。
- **Agent 反代**: Django 用 `httpx` 透传 SSE 流到内部 FastAPI `:8001`，前端通过 `EventStream` 渲染 token。

## 详细内容

- 想查某个接口的入参/响应/位置 → 看 [backend-api.md](./backend-api.md)
- 想查认证流程、JWT 失效、中间件行为 → 看 [auth-and-middleware.md](./auth-and-middleware.md)
- 想查前端某个页面调用了哪些接口 → 看 [frontend-usage.md](./frontend-usage.md)
- 想查响应字段结构 → 看 [serializers-and-models.md](./serializers-and-models.md)
