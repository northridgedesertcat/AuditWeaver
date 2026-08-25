# 认证、权限、中间件与 Agent 反代

## 1. 认证体系概览

| 维度 | 配置 |
| --- | --- |
| 认证类 | `rest_framework_simplejwt.authentication.JWTAuthentication` |
| 默认权限 | `rest_framework.permissions.IsAuthenticated` |
| Token 类型 | JWT access + refresh |
| 用户模型 | `accounts.User` (extends `AbstractUser`) |
| 黑名单 | `rest_framework_simplejwt.token_blacklist` |
| 配置位置 | [backend/settings.py:153-172](../../../services/website/backend/v1/backend/settings.py) |

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'SIGNING_KEY': JWT_SECRET_KEY,                         # 回退到 DJANGO_SECRET_KEY
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=JWT_ACCESS_TTL_MINUTES),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=JWT_REFRESH_TTL_DAYS),
    'ROTATE_REFRESH_TOKENS':  JWT_ROTATE_REFRESH,
    'BLACKLIST_AFTER_ROTATION': JWT_BLACKLIST_AFTER_ROTATE,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

## 2. 自定义用户模型

源码: [accounts/models.py](../../../services/website/backend/v1/accounts/models.py)

```python
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN    = 'admin',    '管理员'
        ANALYST  = 'analyst',  '分析师'
        VIEWER   = 'viewer',   '只读'

    role         = CharField(max_length=16, choices=Role.choices, default=Role.ADMIN)
    display_name = CharField(max_length=64, blank=True)
    updated_at   = DateTimeField(auto_now=True)
```

- 在 [settings.py:73](../../../services/website/backend/v1/backend/settings.py) 设置 `AUTH_USER_MODEL = 'accounts.User'`
- 初始管理员由管理命令幂等创建: [accounts/management/commands/init_admin.py](../../../services/website/backend/v1/accounts/management/commands/init_admin.py)
  - 默认账号: `admin` / `admin123456`（来自 `common.env` 的 `INITIAL_ADMIN_*` 环境变量）
  - 重复执行会跳过已存在的账号

## 3. 匿名放行清单

以下视图显式覆盖默认权限为 `AllowAny`：

| 路径 | 视图 | 位置 |
| --- | --- | --- |
| `GET /api/v1/health/` | `HealthCheckView` | [api/views.py:126](../../../services/website/backend/v1/api/views.py) |
| `POST /api/v1/auth/login/` | `LoginView` | [accounts/views.py:10](../../../services/website/backend/v1/accounts/views.py) |
| `POST /api/v1/auth/refresh/` | `TokenRefreshView` (simplejwt 内置) | [accounts/urls.py:8](../../../services/website/backend/v1/accounts/urls.py) |

> 其余所有接口（含全部 `/dashboard/*`、`/logs/*`、`/reports/*`、`/agent/*`）均强制 `IsAuthenticated`。

## 4. JWT 生命周期

```
1. 登录
   POST /api/v1/auth/login/  { username, password }
     → 返回 { access, refresh }
     → access TTL:  JWT_ACCESS_TTL_MINUTES (默认分钟级)
     → refresh TTL: JWT_REFRESH_TTL_DAYS   (默认天级)

2. 携带 access 访问业务接口
   GET /api/v1/xxx
   Authorization: Bearer <access>

3. access 过期 → 401
   POST /api/v1/auth/refresh/  { refresh }
     → 返回 { access }（若 ROTATE_REFRESH_TOKENS=true，旧 refresh 进黑名单，同时返回新 refresh）

4. 主动登出
   POST /api/v1/auth/logout/  { refresh }
     → RefreshToken(refresh).blacklist()  → 205
```

环境变量（位于 `services/common/env.py`，由 `.env` 注入）：

| 变量 | 说明 |
| --- | --- |
| `JWT_SECRET_KEY` | JWT 签名密钥；为空时回退 `DJANGO_SECRET_KEY` |
| `JWT_ACCESS_TTL_MINUTES` | access 有效期（分钟） |
| `JWT_REFRESH_TTL_DAYS` | refresh 有效期（天） |
| `JWT_ROTATE_REFRESH` | 刷新时是否签发新 refresh |
| `JWT_BLACKLIST_AFTER_ROTATE` | 旧 refresh 是否加入黑名单 |

## 5. Django 中间件链

源码: [backend/settings.py:75-85](../../../services/website/backend/v1/backend/settings.py)

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'backend.middleware.ApiTrailingSlashMiddleware',   # ← 自定义:补尾斜杠
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### 5.1 ApiTrailingSlashMiddleware

源码: [backend/middleware.py](../../../services/website/backend/v1/backend/middleware.py)

**背景**: 前端 Next.js rewrites 在转发时会丢掉 URL 尾斜杠（`trailingSlash` 对 rewrites 不生效），导致 Django 收到 `/api/v1/auth/login`（无斜杠）。Django 默认 `APPEND_SLASH=True` 对 GET 会 301 重定向加斜杠，但对 POST 不能重定向（会丢 body），直接抛 `RuntimeError 500`。

**方案**: 在 URL 解析前直接重写 `request.path_info` 补上尾斜杠（不重定向，不丢 POST）。

```python
class ApiTrailingSlashMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if (
            path.startswith('/api/')
            and not path.startswith('/api/v1/agent')   # Agent 路由本身无斜杠，跳过
            and not path.endswith('/')
        ):
            request.path_info = path + '/'
        return self.get_response(request)
```

**排除范围**: 所有 `/api/v1/agent/*` 路径不补斜杠（路由定义本身无尾斜杠）。

## 6. CORS 配置

源码: [backend/settings.py:151, 175-178](../../../services/website/backend/v1/backend/settings.py)

```python
CORS_ALLOW_ALL_ORIGINS = DJANGO_CORS_ALLOW_ALL_ORIGINS      # 由 .env 控制
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]
```

> 由于前端走 Next.js rewrites 同源代理（见下节），实际浏览器请求都是同源 `/api/v1/*`，CORS 通常不触发；该配置仅在直连 Django 端口时生效。

## 7. 前端 → Next.js → Django 链路

### 7.1 Next.js rewrites

源码: [next.config.mjs](../../../services/website/frontend/v1/next.config.mjs)

```js
const nextConfig = {
  trailingSlash: true,             // 保留 URL 尾斜杠
  async rewrites() {
    return [{
      source: '/api/v1/:path*',
      destination: 'http://localhost:8000/api/v1/:path*',
    }]
  },
}
```

- 前端只发**相对路径** `/api/v1/...`，由 Next.js dev/server 代理到 Django `:8000`，天然同源，免去 CORS。
- `trailingSlash: true` + Django `ApiTrailingSlashMiddleware` 双重保障尾斜杠。

### 7.2 apiFetch 封装

源码: [lib/api/client.ts](../../../services/website/frontend/v1/lib/api/client.ts)

```ts
const API_PREFIX = '/api/v1'
const TOKEN_KEY  = 'aw_access'
const REFRESH_KEY = 'aw_refresh'

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const access = tokenStorage.getAccess()
  const headers = new Headers(init.headers)
  if (access) headers.set('Authorization', `Bearer ${access}`)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let resp = await fetch(`${API_PREFIX}${path}`, { ...init, headers })
  if (resp.status === 401) {
    const ok = await refreshOnce()              // 调用 /auth/refresh/
    if (ok) {
      headers.set('Authorization', `Bearer ${tokenStorage.getAccess()}`)
      resp = await fetch(`${API_PREFIX}${path}`, { ...init, headers })
    } else {
      tokenStorage.clear()
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'         // 避免在登录页跳转形成循环
      }
    }
  }
  return resp
}
```

要点：
- Token 同时写入 `localStorage`（供 `apiFetch` 取用）和 `aw_access` cookie（供 Edge middleware 取用，见 7.3）。
- 401 仅触发一次自动 refresh，失败则清 token 并跳 `/login`；**在登录页不跳转**，避免与 `AuthProvider.fetchMe` 形成无限循环。
- `trailingSlash: true` 让浏览器在导航跳转时也保留尾斜杠，配合 `ApiTrailingSlashMiddleware` 双保险。

### 7.3 Edge Middleware（路由保护）

源码: [middleware.ts](../../../services/website/frontend/v1/middleware.ts)

```ts
const PUBLIC = ['/login']

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl
  if (PUBLIC.some((p) => pathname.startsWith(p))) return NextResponse.next()
  const token = req.cookies.get('aw_access')?.value     // Edge 无法读 localStorage
  if (!token) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('next', pathname)              // 登录后回跳
    return NextResponse.redirect(url)
  }
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon|icon|api).*)'],
}
```

- 仅放行 `/login`；其余页面无 `aw_access` cookie 一律跳 `/login?next=<原路径>`。
- matcher 排除 `_next/static`、`_next/image`、`favicon`、`icon`、`api`（API 请求由后端校验，不在此拦截）。
- **此 middleware 不校验 JWT 有效性**，仅做存在性检查；真正的鉴权在 Django。

### 7.4 AuthProvider

源码: [lib/auth.tsx](../../../services/website/frontend/v1/lib/auth.tsx)

```tsx
export function AuthProvider({ children }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    fetchMe()                  // 启动时调用 /auth/me/
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const value = {
    user, ready,
    login: async (u, p) => { await apiLogin(u, p); setUser(await fetchMe()) },
    logout: async () => { await apiLogout(); setUser(null) },
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
```

- 在 [app/layout.tsx](../../../services/website/frontend/v1/app/layout.tsx) 顶层包裹，所有页面共享 `useAuth()`。
- 登录页 [app/login/page.tsx](../../../services/website/frontend/v1/app/login/page.tsx) 通过 `useAuth().login(username, password)` 触发 `/auth/login/` + `/auth/me/`。

## 8. Agent 反代链路

源码: `AgentProxyView` · [api/views.py:63-123](../../../services/website/backend/v1/api/views.py)

### 8.1 路由

```python
path('agent/<str:agent_type>/chat',      AgentProxyView.as_view()),   # SSE
path('agent/<str:agent_type>/chat/sync', AgentProxyView.as_view()),   # JSON
path('agent/health', AgentProxyView.as_view()),
path('agent/types',  AgentProxyView.as_view()),
```

- 注意：**所有 agent 路由均无尾斜杠**，被 `ApiTrailingSlashMiddleware` 跳过。
- 新增 agent 类型无需改路由，只需在 FastAPI 端注册。

### 8.2 反代逻辑

```python
permission_classes = [IsAuthenticated]                        # JWT 在 Django 校验
renderer_classes   = [EventStreamRenderer, JSONRenderer]      # 让 DRF 接受 text/event-stream

def _build_target(self, request):
    # /api/v1/agent/analysis_explorer/chat  →  <AGENT_FASTAPI_BASE>/agent/analysis_explorer/chat
    prefix = "/api/v1"
    tail   = request.path_info[len(prefix):]
    return f"{django_settings.AGENT_FASTAPI_BASE}{tail}"
```

- **POST**: 用 `httpx.Client(timeout=None)` 流式透传请求体与上游响应字节。
  - `/chat` 上游 `Content-Type: text/event-stream`
  - `/chat/sync` 上游 `Content-Type: application/json`
  - 响应头注入 `X-Accel-Buffering: no`、`Cache-Control: no-cache`，保证 SSE 实时性。
- **GET**: `httpx.get(target, timeout=10)`，直接 `JsonResponse` 透传上游 JSON。
- **失败兜底**: 上游异常一律返回 `502 { "error": "agent service unavailable" }`，不抛栈。

### 8.3 EventStreamRenderer

```python
class EventStreamRenderer(BaseRenderer):
    """占位 renderer：仅用于通过 DRF 内容协商。
    实际响应均为手动构造的 StreamingHttpResponse / JsonResponse，不走 renderer 渲染。"""
    media_type = 'text/event-stream'
    format     = 'event-stream'
```

> DRF 默认 renderer 不接受 `Accept: text/event-stream`，会在进入视图前返回 406。这个占位 renderer 仅为通过内容协商。

### 8.4 前端 Agent 封装

源码: [lib/api/agent.ts](../../../services/website/frontend/v1/lib/api/agent.ts)

- `DEFAULT_AGENT_TYPE = "analysis_explorer"`
- `streamAgentChat(message, threadId, agentType, opts)`：直接用原生 `fetch` 发 POST，`Accept: text/event-stream`，按 `\n\n` 切分 SSE block，`data:` 行 JSON.parse 后分发到 `onToken / onToolCall / onToolResult / onDone / onError` 回调。
- `chatSync(message, threadId, agentType)`：返回 `{ answer, toolCalls, threadId }`。
- 这里**不经过 `apiFetch`**（要拿 ReadableStream），需要手动注入 `Authorization` 头，且不做 401 自动 refresh。

## 9. 鉴权排查清单

| 现象 | 排查方向 |
| --- | --- |
| 401 Unauthorized | access 过期 → 前端应自动 refresh；若 refresh 也过期则跳登录 |
| 401 且未自动 refresh | 检查 `JWT_SECRET_KEY` 是否为空（应回退 `DJANGO_SECRET_KEY`）；检查 `aw_refresh` 是否还在 localStorage |
| 500 RuntimeError on POST | 检查 `ApiTrailingSlashMiddleware` 是否生效（中间件顺序、`/api/v1/agent` 排除规则） |
| 406 Not Acceptable | Agent 路径缺少 `EventStreamRenderer` 占位（仅 agent 路由会出现） |
| Edge 跳转 /login 死循环 | `aw_access` cookie 未写入；或 `/login` 路径未被 PUBLIC 命中 |
| 502 agent service unavailable | 内部 FastAPI `:8001` 不可达；检查 `AGENT_FASTAPI_BASE` |
| 重定向到 /login 后未回跳 | `?next=` 参数丢失；检查 middleware redirect 是否构造了 searchParams |
