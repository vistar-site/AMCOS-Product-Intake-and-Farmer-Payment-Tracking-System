/**
 * Saving a delivery: online when possible, otherwise into the outbox.
 *
 * Why this is safe: the delivery id is generated BEFORE the first attempt and
 * reused for the queued copy. If the online request actually reached the server
 * but the response was lost, the later sync returns "duplicate" for that id and
 * the record is marked synced — no double delivery, no lost delivery.
 */
import { api } from '../api/client'
import type { Me } from '../types/auth'
import type { Delivery } from '../types/domain'
import { db, nextProvisionalReceipt, type OutboxDelivery } from './db'
import { isNetworkError } from './network'

export interface CaptureInput {
  id: string; farmerId: string; centreId: string; cropId: string; gradeId: string | null
  gross: string; tare: string; net: string; notes: string | null; capturedAt: string
  display: Omit<OutboxDelivery['display'], 'net' | 'recorderName'>
}

export type CaptureResult =
  | { mode: 'online'; delivery: Delivery; created: boolean; warnings: string[] }
  | { mode: 'offline'; record: OutboxDelivery }

export async function captureDelivery(input: CaptureInput, user: Me, forceOffline: boolean): Promise<CaptureResult> {
  const body = {
    id: input.id, farmer_id: input.farmerId, centre_id: input.centreId, crop_id: input.cropId,
    grade_id: input.gradeId, gross_weight: input.gross, tare_weight: input.tare || '0',
    captured_at: input.capturedAt, notes: input.notes,
  }
  if (!forceOffline) {
    try {
      const r = await api<{ delivery: Delivery; created: boolean; warnings: string[] }>('/deliveries', { method: 'POST', json: body })
      return { mode: 'online', ...r }
    } catch (e) {
      if (!isNetworkError(e)) throw e // validation/permission errors are shown, not queued
    }
  }
  const existing = await db.outbox.get(input.id) // pressing Save twice offline
  if (existing) return { mode: 'offline', record: existing }
  const provisional = await nextProvisionalReceipt()
  const record: OutboxDelivery = {
    id: input.id, userId: user.id, organizationId: user.organization_id ?? '', provisionalReceiptNo: provisional,
    receiptNo: null, status: 'pending', attempts: 0, lastError: null, capturedAt: input.capturedAt,
    syncedAt: null, warnings: [],
    payload: { ...body, provisional_receipt_no: provisional },
    display: { ...input.display, net: input.net, recorderName: user.full_name },
  }
  await db.outbox.add(record)
  return { mode: 'offline', record }
}
