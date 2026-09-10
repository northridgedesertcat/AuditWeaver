'use client'

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  login as apiLogin,
  fetchMe,
  logout as apiLogout,
  type UserInfo,
} from './api/auth'

interface AuthCtx {
  user: UserInfo | null
  ready: boolean
  login: (u: string, p: string) => Promise<void>
  logout: () => Promise<void>
}

const Ctx = createContext<AuthCtx>(null!)

export function useAuth() {
  return useContext(Ctx)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const value: AuthCtx = {
    user,
    ready,
    login: async (u, p) => {
      await apiLogin(u, p)
      setUser(await fetchMe())
    },
    logout: async () => {
      await apiLogout()
      setUser(null)
    },
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
