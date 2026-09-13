// 统一 fetch 封装:走相对路径(由 next.config.mjs rewrites 代理到 Django),
// 自动带 Authorization 头、401 自动 refresh、refresh 失败跳登录页。

const API_PREFIX = '/api/v1'
const TOKEN_KEY = 'aw_access'
const REFRESH_KEY = 'aw_refresh'

export const tokenStorage = {
  getAccess: () =>
    typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null,
  getRefresh: () =>
    typeof localStorage !== 'undefined' ? localStorage.getItem(REFRESH_KEY) : null,
  set: (access: string, refresh: string) => {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
    // 同步写 cookie 供 Edge middleware 读取(Edge 跑在 SSR,访问不到 localStorage)
    if (typeof document !== 'undefined') {
      document.cookie = `aw_access=${access}; path=/; max-age=3600`
    }
  },
  clear: () => {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_KEY)
    }
    if (typeof document !== 'undefined') {
      document.cookie = 'aw_access=; path=/; max-age=0'
    }
  },
}

async function refreshOnce(): Promise<boolean> {
  const r = tokenStorage.getRefresh()
  if (!r) return false
  try {
    const resp = await fetch(`${API_PREFIX}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: r }),
    })
    if (!resp.ok) return false
    const data = await resp.json()
    tokenStorage.set(data.access, r)
    return true
  } catch {
    return false
  }
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  // path 形如 '/auth/login/' 或 '/dashboard/stats/'
  const access = tokenStorage.getAccess()
  const headers = new Headers(init.headers)
  if (access) headers.set('Authorization', `Bearer ${access}`)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let resp = await fetch(`${API_PREFIX}${path}`, { ...init, headers })
  if (resp.status === 401) {
    const ok = await refreshOnce()
    if (ok) {
      headers.set('Authorization', `Bearer ${tokenStorage.getAccess()}`)
      resp = await fetch(`${API_PREFIX}${path}`, { ...init, headers })
    } else {
      tokenStorage.clear()
      // 已在登录页则不跳转,避免与 AuthProvider 的 fetchMe 形成无限刷新循环
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
  }
  return resp
}
