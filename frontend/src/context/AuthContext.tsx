/**
 * Holds "who is logged in" for the whole app.
 *
 * Startup:
 *  1. Try /auth/refresh (the httpOnly cookie proves a previous login).
 *  2. 'ok'      -> load /auth/me, status 'authenticated', save an offline snapshot.
 *     'invalid' -> status 'anonymous' (must log in).
 *     'network' -> if a snapshot from the last 72 h exists: status 'offline'
 *                  (intake only, no server access); otherwise 'anonymous'.
 *
 * OFFLINE SECURITY MODEL (be honest about limits):
 *  - Offline mode is a convenience, not real authentication. Anyone holding the
 *    unlocked device during those 72 h can use the intake screen.
 *  - No password or token is stored on the device; only a profile snapshot.
 *  - Real authorization happens at sync: the server re-checks the logged-in user,
 *    their permission and centre assignment for EVERY uploaded record.
 *  - Logging out clears the snapshot, ending offline access.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from '../api/client'
import { clearSessionSnapshot, db, loadValidSnapshot, prepareForUser, saveSessionSnapshot } from '../offline/db'
import type { Me } from '../types/auth'

type Status = 'loading' | 'authenticated' | 'offline' | 'anonymous'

interface AuthState {
  user: Me | null
  status: Status
  login: (email: string, password: string) => Promise<Me>
  logout: () => Promise<void>
  reload: () => Promise<void>
  /** Try to turn an offline session back into a real one (called when connectivity returns). */
  reconnect: () => Promise<void>
  can: (...permissions: string[]) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [status, setStatus] = useState<Status>('loading')

  const loadMe = useCallback(async () => {
    const me = await api<Me>('/auth/me')
    await prepareForUser(me).catch(() => {})
    await saveSessionSnapshot(me).catch(() => {})
    setUser(me)
    setStatus('authenticated')
    return me
  }, [])

  const restore = useCallback(async () => {
    const result = await refreshSession()
    if (result === 'ok') {
      try { await loadMe(); return } catch { /* fall through to offline check */ }
    }
    if (result !== 'invalid') {
      const snap = await loadValidSnapshot().catch(() => null)
      if (snap) { setUser(snap.user); setStatus('offline'); return }
    }
    setStatus('anonymous')
  }, [loadMe])

  useEffect(() => {
    setSessionExpiredHandler(() => { setUser(null); setStatus('anonymous') })
    restore()
  }, [restore])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api<{ access_token: string }>('/auth/login', { method: 'POST', json: { email, password } })
    setAccessToken(access_token)
    return loadMe()
  }, [loadMe])

  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }) } catch { /* offline logout still clears locally */ } finally {
      setAccessToken(null)
      await clearSessionSnapshot().catch(() => {})
      await db.farmers.clear().catch(() => {})
      setUser(null)
      setStatus('anonymous')
    }
  }, [])

  const reconnect = useCallback(async () => {
    if (status === 'offline') await restore()
  }, [status, restore])

  const can = useCallback(
    (...perms: string[]) => !!user && perms.every((p) => user.permissions.includes(p)),
    [user],
  )

  const value = useMemo(
    () => ({ user, status, login, logout, can, reconnect, reload: async () => { await loadMe() } }),
    [user, status, login, logout, can, reconnect, loadMe],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
