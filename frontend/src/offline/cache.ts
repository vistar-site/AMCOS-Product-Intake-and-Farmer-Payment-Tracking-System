/**
 * "Network first, cache fallback" for reference data and farmer lookup.
 * Online: fetch from the API and refresh the local copy.
 * Offline (network error): answer from IndexedDB instead.
 */
import { api } from '../api/client'
import type { Page } from '../types/auth'
import type { Farmer } from '../types/domain'
import { db, getMeta, setMeta, type CachedFarmer } from './db'
import { isNetworkError } from './network'

export async function cachedFetch<T>(key: string, organizationId: string, path: string): Promise<T> {
  try {
    const data = await api<T>(path)
    await db.reference.put({ key, organizationId, data, savedAt: new Date().toISOString() }).catch(() => {})
    return data
  } catch (e) {
    if (!isNetworkError(e)) throw e
    const hit = await db.reference.get(key)
    if (hit && hit.organizationId === organizationId) return hit.data as T
    throw e
  }
}

interface SyncFarmer {
  id: string; membership_no: string; full_name: string; phone: string | null
  village: string | null; home_centre_id: string | null; status: string
}

/** Download farmers changed since the last download (delta sync). */
export async function refreshFarmerCache(organizationId: string): Promise<number> {
  const since = await getMeta<string | null>('farmers-synced-at')
  const startedAt = new Date().toISOString()
  const rows = await api<SyncFarmer[]>(`/sync/farmers${since ? `?since=${encodeURIComponent(since)}` : ''}`)
  await db.farmers.bulkPut(rows.map((f): CachedFarmer => ({ ...f, organizationId, nameLower: f.full_name.toLowerCase() })))
  await setMeta('farmers-synced-at', startedAt)
  return rows.length
}

/** Offline farmer search, mirroring the server: name contains, member no. prefix, exact phone. */
export async function searchLocalFarmers(q: string, limit = 8): Promise<Farmer[]> {
  const term = q.trim().toLowerCase()
  const digits = term.replace(/\D/g, '')
  const phone = digits.startsWith('0') && digits.length === 10 ? `+255${digits.slice(1)}` : digits ? `+${digits.replace(/^\+/, '')}` : ''
  const rows = await db.farmers
    .filter((f) => f.status === 'active' && (f.nameLower.includes(term) || f.membership_no.toLowerCase().startsWith(term) || (!!phone && f.phone === phone)))
    .limit(limit).toArray()
  return rows.map(toFarmer)
}

export async function getLocalFarmer(id: string): Promise<Farmer | undefined> {
  const f = await db.farmers.get(id)
  return f && toFarmer(f)
}

function toFarmer(f: CachedFarmer): Farmer {
  return {
    id: f.id, membership_no: f.membership_no, full_name: f.full_name, phone: f.phone, village: f.village,
    status: f.status as Farmer['status'], gender: null, ward: null, district: null, region: null,
    home_centre: null, registration_date: '', notes: null, extra_fields: {}, created_at: '',
  }
}

export async function searchFarmersWithFallback(params: URLSearchParams): Promise<Page<Farmer>> {
  try {
    return await api<Page<Farmer>>(`/farmers?${params}`)
  } catch (e) {
    if (!isNetworkError(e)) throw e
    const items = await searchLocalFarmers(params.get('q') ?? '', Number(params.get('page_size') ?? 8))
    return { items, total: items.length, page: 1, page_size: items.length || 8 }
  }
}
