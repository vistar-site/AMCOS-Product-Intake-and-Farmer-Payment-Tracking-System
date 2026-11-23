/**
 * The on-device database (IndexedDB, via Dexie).
 *
 * WHAT IS STORED HERE — and deliberately nothing more:
 *  - outbox:    deliveries captured on this device until the server confirms them
 *  - farmers:   lookup fields only (name, member no., phone, village, centre, status)
 *  - reference: crops/grades, centres, seasons, organization name (for receipts)
 *  - meta:      device id, offline receipt counter, profile snapshot of the last user
 * NEVER stored: passwords, access/refresh tokens, payout amounts, loan balances,
 * bank or mobile-money numbers.
 *
 * PostgreSQL remains the source of truth. This is a temporary holding area.
 */
import Dexie, { type Table } from 'dexie'
import type { Me } from '../types/auth'

export type OutboxStatus = 'pending' | 'syncing' | 'synced' | 'rejected' | 'conflict'

export interface OutboxDelivery {
  id: string                       // client UUID = server primary key (idempotency key)
  userId: string                   // only this user may upload it
  organizationId: string
  provisionalReceiptNo: string     // OFF-<device>-<n>, printed on the offline receipt
  receiptNo: string | null         // official number once synced
  status: OutboxStatus
  attempts: number
  lastError: string | null
  capturedAt: string               // ISO, device clock
  syncedAt: string | null
  warnings: string[]
  // Payload sent to POST /sync/deliveries
  payload: {
    id: string; farmer_id: string; centre_id: string; crop_id: string; grade_id: string | null
    gross_weight: string; tare_weight: string; captured_at: string; notes: string | null
    provisional_receipt_no: string
  }
  // Snapshot for showing the receipt offline
  display: { farmerName: string; membershipNo: string; centreName: string; cropName: string; gradeName: string | null; net: string; recorderName: string }
}

export interface CachedFarmer {
  id: string; organizationId: string; membership_no: string; full_name: string; phone: string | null
  village: string | null; home_centre_id: string | null; status: string; nameLower: string
}

export interface ReferenceEntry { key: string; organizationId: string; data: unknown; savedAt: string }
export interface MetaEntry { key: string; value: unknown }

class AmcosDB extends Dexie {
  outbox!: Table<OutboxDelivery, string>
  farmers!: Table<CachedFarmer, string>
  reference!: Table<ReferenceEntry, string>
  meta!: Table<MetaEntry, string>

  constructor() {
    super('amcos')
    // Version 1 schema. Listed fields are INDEXES (searchable), not all columns.
    this.version(1).stores({
      outbox: 'id, userId, status, capturedAt, [userId+status]',
      farmers: 'id, organizationId, membership_no, phone, nameLower',
      reference: 'key',
      meta: 'key',
    })
  }
}

export const db = new AmcosDB()

export async function getMeta<T>(key: string): Promise<T | undefined> {
  return (await db.meta.get(key))?.value as T | undefined
}
export const setMeta = (key: string, value: unknown) => db.meta.put({ key, value })

/** A random id per browser install; the short code goes into offline receipt numbers. */
export async function getDevice(): Promise<{ id: string; code: string }> {
  let id = await getMeta<string>('device-id')
  if (!id) {
    id = crypto.randomUUID()
    await setMeta('device-id', id)
  }
  return { id, code: id.replace(/-/g, '').slice(0, 4).toUpperCase() }
}

/** Next provisional receipt number, e.g. OFF-3F2A-0007. Atomic via a Dexie transaction. */
export async function nextProvisionalReceipt(): Promise<string> {
  const { code } = await getDevice()
  const n = await db.transaction('rw', db.meta, async () => {
    const current = (await getMeta<number>('offline-seq')) ?? 0
    await setMeta('offline-seq', current + 1)
    return current + 1
  })
  return `OFF-${code}-${String(n).padStart(4, '0')}`
}

// ---- Offline session snapshot ----
export const OFFLINE_SESSION_HOURS = 72

export interface SessionSnapshot { user: Me; lastOnlineAt: string }

export const saveSessionSnapshot = (user: Me) =>
  setMeta('session', { user, lastOnlineAt: new Date().toISOString() } satisfies SessionSnapshot)

export async function loadValidSnapshot(now = Date.now()): Promise<SessionSnapshot | null> {
  const s = await getMeta<SessionSnapshot>('session')
  if (!s) return null
  const ageHours = (now - new Date(s.lastOnlineAt).getTime()) / 3_600_000
  return ageHours <= OFFLINE_SESSION_HOURS ? s : null
}

export const clearSessionSnapshot = () => db.meta.delete('session')

/** When a different user signs in on this device, drop the previous user's cached lookups. */
export async function prepareForUser(user: Me): Promise<void> {
  const previous = await getMeta<SessionSnapshot>('session')
  if (previous && previous.user.id !== user.id) {
    await db.farmers.clear()
    await db.reference.clear()
    await setMeta('farmers-synced-at', null)
  }
}
