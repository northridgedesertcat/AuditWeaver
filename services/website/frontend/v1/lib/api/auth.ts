import { apiFetch, tokenStorage } from './client'

export interface LoginResp {
  access: string
  refresh: string
}

export interface UserInfo {
  id: number
  username: string
  email: string
  role: string
  display_name: string
  is_active: boolean
  is_root_admin: boolean
}

export async function login(
  username: string,
  password: string,
): Promise<LoginResp> {
  const resp = await apiFetch('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  if (!resp.ok) throw new Error('用户名或密码错误')
  const data = await resp.json()
  tokenStorage.set(data.access, data.refresh)
  return data
}

export async function fetchMe(): Promise<UserInfo> {
  const resp = await apiFetch('/auth/me/')
  if (!resp.ok) throw new Error('未登录')
  return resp.json()
}

export async function logout(): Promise<void> {
  const refresh = tokenStorage.getRefresh()
  try {
    await apiFetch('/auth/logout/', {
      method: 'POST',
      body: JSON.stringify({ refresh }),
    })
  } finally {
    tokenStorage.clear()
    if (typeof window !== 'undefined') window.location.href = '/login'
  }
}

// ============ Root Admin 用户管理（后端 IsRootAdmin 兜底，非 Root 返回 403） ============

export interface AdminInfo {
  id: number
  username: string
  email: string
  role: string
  display_name: string
  is_active: boolean
  is_root_admin: boolean
}

/** 把 DRF 错误体（detail 字符串或字段数组）摊平成一条中文消息 */
export async function extractError(resp: Response): Promise<string> {
  try {
    const data = await resp.json()
    if (typeof data === 'string') return data
    if (data.detail) return String(data.detail)
    const parts = Object.entries(data).map(([k, v]) => {
      const msg = Array.isArray(v) ? v.join('；') : String(v)
      return k === 'non_field_errors' ? msg : `${k}: ${msg}`
    })
    return parts.join('；') || `请求失败(${resp.status})`
  } catch {
    return `请求失败(${resp.status})`
  }
}

/** 列出普通管理员（后端只返回 role=admin，Root 不会出现） */
export async function listAdmins(): Promise<AdminInfo[]> {
  const resp = await apiFetch('/auth/admins/')
  if (!resp.ok) throw new Error(await extractError(resp))
  return resp.json()
}

export async function createAdmin(input: {
  username: string
  password: string
  display_name?: string
  email?: string
}): Promise<AdminInfo> {
  const resp = await apiFetch('/auth/admins/', {
    method: 'POST',
    body: JSON.stringify(input),
  })
  if (!resp.ok) throw new Error(await extractError(resp))
  return resp.json()
}

export async function setAdminActive(id: number, active: boolean): Promise<AdminInfo> {
  const resp = await apiFetch(`/auth/admins/${id}/${active ? 'enable' : 'disable'}/`, {
    method: 'PATCH',
  })
  if (!resp.ok) throw new Error(await extractError(resp))
  return resp.json()
}

export async function resetAdminPassword(id: number, newPassword: string): Promise<void> {
  const resp = await apiFetch(`/auth/admins/${id}/reset-password/`, {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  })
  if (!resp.ok) throw new Error(await extractError(resp))
}

export async function deleteAdmin(id: number): Promise<void> {
  const resp = await apiFetch(`/auth/admins/${id}/`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(await extractError(resp))
}

/** 修改当前登录用户自己的密码（需旧密码，成功后需重新登录） */
export async function changeMyPassword(
  oldPassword: string,
  newPassword: string,
): Promise<void> {
  const resp = await apiFetch('/auth/change-password/', {
    method: 'POST',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
  if (!resp.ok) throw new Error(await extractError(resp))
}
