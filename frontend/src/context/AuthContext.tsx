/**
 * Holds "who is logged in" for the whole app.
 *
 * On startup: try /auth/refresh (the httpOnly cookie proves a previous login),
 * then load /auth/me. The permissions from /me drive which menu items and
 * pages are shown — but the BACKEND still checks every request.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, refreshAccessToken, setAccessToken, setSessionExpiredHandler } from '../api/client'
import type { Me } from '../types/auth'

interface AuthState {
  user: Me | null
  status: 'loading' | 'authenticated' | 'anonymous'
  login: (email: string, password: string) => Promise<Me>
  logout: () => Promise<void>
  reload: () => Promise<void>
  can: (...permissions: string[]) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [status, setStatus] = useState<AuthState['status']>('loading')

  const loadMe = useCallback(async () => {
    const me = await api<Me>('/auth/me')
    setUser(me)
    setStatus('authenticated')
    return me
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(() => { setUser(null); setStatus('anonymous') })
    refreshAccessToken().then((ok) => (ok ? loadMe() : Promise.reject()))
      .catch(() => setStatus('anonymous'))
  }, [loadMe])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api<{ access_token: string }>('/auth/login', {
      method: 'POST', json: { email, password },
    })
    setAccessToken(access_token)
    return loadMe()
  }, [loadMe])

  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }) } finally {
      setAccessToken(null)
      setUser(null)
      setStatus('anonymous')
    }
  }, [])

  const can = useCallback(
    (...perms: string[]) => !!user && perms.every((p) => user.permissions.includes(p)),
    [user],
  )

  const value = useMemo(
    () => ({ user, status, login, logout, can, reload: async () => { await loadMe() } }),
    [user, status, login, logout, can, loadMe],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
