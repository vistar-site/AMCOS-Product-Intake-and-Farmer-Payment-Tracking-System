/**
 * The synchronization engine: uploads the outbox to POST /sync/deliveries.
 *
 * Rules (see docs/ARCHITECTURE.md §6):
 * 1. A record becomes "synced" ONLY when the server returns a per-record result
 *    of "created" or "duplicate" for its id. Being online proves nothing.
 * 2. "duplicate" is success: the server already had this exact delivery
 *    (e.g. an earlier upload whose response was lost).
 * 3. "conflict" and "rejected" are kept on the device, visible, never deleted silently.
 * 4. A network failure leaves records "pending" for the next attempt.
 * 5. Only one sync runs at a time (the `running` lock).
 */
import { api } from '../api/client'
import { db, getDevice, type OutboxDelivery } from './db'
import { isNetworkError } from './network'

const BATCH_SIZE = 50

interface SyncItemResult {
  id: string; status: 'created' | 'duplicate' | 'conflict' | 'rejected'
  receipt_no: string | null; message: string | null; warnings: string[]
}

export interface SyncSummary { uploaded: number; synced: number; rejected: number; conflicts: number; networkError: boolean }

type Poster = (body: unknown) => Promise<{ results: SyncItemResult[] }>
const defaultPoster: Poster = (body) => api('/sync/deliveries', { method: 'POST', json: body })

let running: Promise<SyncSummary> | null = null

export function syncOutbox(userId: string, post: Poster = defaultPoster): Promise<SyncSummary> {
  running ??= runSync(userId, post).finally(() => { running = null })
  return running
}

async function runSync(userId: string, post: Poster): Promise<SyncSummary> {
  const summary: SyncSummary = { uploaded: 0, synced: 0, rejected: 0, conflicts: 0, networkError: false }
  const { id: deviceId } = await getDevice()
  // Recover records stuck in "syncing" (e.g. the tab was closed mid-upload).
  await db.outbox.where({ userId, status: 'syncing' }).modify({ status: 'pending' })

  for (;;) {
    const batch = await db.outbox.where({ userId, status: 'pending' }).sortBy('capturedAt')
    const chunk = batch.slice(0, BATCH_SIZE)
    if (chunk.length === 0) break
    const ids = chunk.map((r) => r.id)
    await db.outbox.where('id').anyOf(ids).modify((r) => { r.status = 'syncing'; r.attempts += 1 })

    let results: SyncItemResult[]
    try {
      results = (await post({ device_id: deviceId, deliveries: chunk.map((r) => r.payload) })).results
    } catch (e) {
      const message = isNetworkError(e) ? 'No connection — will retry automatically' : (e as Error).message
      await db.outbox.where('id').anyOf(ids).modify({ status: 'pending', lastError: message })
      summary.networkError = isNetworkError(e)
      break // stop on any whole-request failure; try again later
    }

    summary.uploaded += chunk.length
    const byId = new Map(results.map((r) => [r.id, r]))
    await db.transaction('rw', db.outbox, async () => {
      for (const record of chunk) {
        const r = byId.get(record.id)
        const patch: Partial<OutboxDelivery> = !r
          ? { status: 'pending', lastError: 'Server did not confirm this record' }
          : r.status === 'created' || r.status === 'duplicate'
            ? { status: 'synced', receiptNo: r.receipt_no, syncedAt: new Date().toISOString(), lastError: null, warnings: r.warnings }
            : { status: r.status, lastError: r.message }
        await db.outbox.update(record.id, patch)
        if (patch.status === 'synced') summary.synced++
        if (patch.status === 'rejected') summary.rejected++
        if (patch.status === 'conflict') summary.conflicts++
      }
    })
    if (results.length < chunk.length) break // avoid looping on unconfirmed records
  }
  return summary
}

/** Put a rejected record back in the queue (e.g. after the farmer was reactivated). */
export const retryRecord = (id: string) => db.outbox.update(id, { status: 'pending', lastError: null })

/** Remove synced records older than `days` from the device (they're safe on the server). */
export async function pruneSynced(days = 7): Promise<number> {
  const cutoff = new Date(Date.now() - days * 86_400_000).toISOString()
  return db.outbox.filter((r) => r.status === 'synced' && !!r.syncedAt && r.syncedAt < cutoff).delete()
}
