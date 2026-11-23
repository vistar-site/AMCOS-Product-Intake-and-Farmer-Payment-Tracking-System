/**
 * Runs synchronization in the background and exposes its state to the UI.
 * Triggers: app start, the browser 'online' event, every 60 s while online,
 * and the manual "Sync now" button. Failures back off: 1, 2, 4 … up to 15 min.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { liveQuery } from 'dexie'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from './AuthContext'
import { db } from '../offline/db'
import { refreshFarmerCache } from '../offline/cache'
import { pruneSynced, syncOutbox, type SyncSummary } from '../offline/syncEngine'

interface Counts { pending: number; rejected: number; conflict: number; synced: number }
interface SyncState {
  online: boolean
  syncing: boolean
  counts: Counts
  lastSync: { at: string; summary: SyncSummary } | null
  lastError: string | null
  syncNow: () => Promise<void>
}

const SyncContext = createContext<SyncState | null>(null)
const INTERVAL_MS = 60_000

export function SyncProvider({ children }: { children: ReactNode }) {
  const { user, status, reconnect } = useAuth()
  const qc = useQueryClient()
  const [online, setOnline] = useState(() => navigator.onLine)
  const [syncing, setSyncing] = useState(false)
  const [counts, setCounts] = useState<Counts>({ pending: 0, rejected: 0, conflict: 0, synced: 0 })
  const [lastSync, setLastSync] = useState<SyncState['lastSync']>(null)
  const [lastError, setLastError] = useState<string | null>(null)
  const failures = useRef(0)
  const nextAllowed = useRef(0)

  // Live counts: liveQuery re-runs whenever the outbox table changes.
  useEffect(() => {
    if (!user) return
    const sub = liveQuery(async () => {
      const rows = await db.outbox.where('userId').equals(user.id).toArray()
      return {
        pending: rows.filter((r) => r.status === 'pending' || r.status === 'syncing').length,
        rejected: rows.filter((r) => r.status === 'rejected').length,
        conflict: rows.filter((r) => r.status === 'conflict').length,
        synced: rows.filter((r) => r.status === 'synced').length,
      }
    }).subscribe({ next: setCounts, error: () => {} })
    return () => sub.unsubscribe()
  }, [user])

  const syncNow = useCallback(async (manual = true) => {
    if (!user || (!manual && Date.now() < nextAllowed.current)) return
    if (status === 'offline') await reconnect()
    if (status !== 'authenticated' && status !== 'offline') return
    setSyncing(true)
    try {
      const summary = await syncOutbox(user.id)
      setLastSync({ at: new Date().toISOString(), summary })
      if (summary.networkError) throw new Error('No connection')
      if (user.organization_id && user.permissions.includes('farmer.view')) {
        await refreshFarmerCache(user.organization_id).catch(() => {})
      }
      await pruneSynced().catch(() => {})
      if (summary.synced) qc.invalidateQueries({ queryKey: ['deliveries'] })
      failures.current = 0
      nextAllowed.current = 0
      setLastError(null)
    } catch (e) {
      failures.current += 1
      nextAllowed.current = Date.now() + Math.min(2 ** (failures.current - 1), 15) * 60_000
      setLastError((e as Error).message)
    } finally {
      setSyncing(false)
    }
  }, [user, status, reconnect, qc])

  useEffect(() => {
    const up = () => { setOnline(true); nextAllowed.current = 0; syncNow(false) }
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => { window.removeEventListener('online', up); window.removeEventListener('offline', down) }
  }, [syncNow])

  useEffect(() => {
    if (!user) return
    syncNow(false)
    const t = setInterval(() => { if (navigator.onLine) syncNow(false) }, INTERVAL_MS)
    return () => clearInterval(t)
  }, [user, syncNow])

  // Ask the browser not to evict our IndexedDB data under storage pressure.
  useEffect(() => { navigator.storage?.persist?.().catch(() => {}) }, [])

  return (
    <SyncContext.Provider value={{ online, syncing, counts, lastSync, lastError, syncNow: () => syncNow(true) }}>
      {children}
    </SyncContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSync() {
  const ctx = useContext(SyncContext)
  if (!ctx) throw new Error('useSync must be used inside SyncProvider')
  return ctx
}
