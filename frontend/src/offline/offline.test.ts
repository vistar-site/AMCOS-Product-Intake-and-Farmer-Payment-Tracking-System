/**
 * Offline-first behaviour tests. fake-indexeddb gives Dexie a real IndexedDB
 * implementation in Node, and the "server" is a fake function we control.
 */
import 'fake-indexeddb/auto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { Me } from '../types/auth'
import { captureDelivery, type CaptureInput } from './capture'
import { db, loadValidSnapshot, OFFLINE_SESSION_HOURS, saveSessionSnapshot } from './db'
import { syncOutbox } from './syncEngine'

vi.mock('../api/client', async (orig) => {
  const mod = await orig<typeof import('../api/client')>()
  return { ...mod, api: vi.fn() }
})
const { api } = await import('../api/client')
const apiMock = vi.mocked(api)

const user = { id: 'user-1', organization_id: 'org-1', full_name: 'Juma Clerk', permissions: ['delivery.create'] } as unknown as Me

const input = (over: Partial<CaptureInput> = {}): CaptureInput => ({
  id: crypto.randomUUID(), farmerId: 'f1', centreId: 'c1', cropId: 'cr1', gradeId: null,
  gross: '82.5', tare: '0.5', net: '82.000', notes: null, capturedAt: new Date().toISOString(),
  display: { farmerName: 'Asha', membershipNo: 'M-1', centreName: 'Nanyamba', cropName: 'Cashew', gradeName: null },
  ...over,
})

const offline = () => new ApiError(0, 'Cannot reach the server')

beforeEach(async () => {
  await Promise.all([db.outbox.clear(), db.meta.clear()])
  apiMock.mockReset()
})
afterEach(() => vi.useRealTimers())

describe('captureDelivery', () => {
  it('saves to the outbox with a provisional receipt when the server is unreachable', async () => {
    apiMock.mockRejectedValueOnce(offline())
    const r = await captureDelivery(input(), user, false)
    expect(r.mode).toBe('offline')
    if (r.mode !== 'offline') return
    expect(r.record.provisionalReceiptNo).toMatch(/^OFF-[0-9A-F]{4}-0001$/)
    expect(r.record.status).toBe('pending')
    expect(await db.outbox.count()).toBe(1)
  })

  it('numbers offline receipts sequentially', async () => {
    const a = await captureDelivery(input(), user, true)
    const b = await captureDelivery(input(), user, true)
    if (a.mode !== 'offline' || b.mode !== 'offline') throw new Error('expected offline')
    expect(a.record.provisionalReceiptNo.endsWith('0001')).toBe(true)
    expect(b.record.provisionalReceiptNo.endsWith('0002')).toBe(true)
  })

  it('pressing Save twice offline does not create two records', async () => {
    const i = input()
    await captureDelivery(i, user, true)
    await captureDelivery(i, user, true)
    expect(await db.outbox.count()).toBe(1)
  })

  it('does NOT queue a delivery the server rejected (validation error is shown instead)', async () => {
    apiMock.mockRejectedValueOnce(new ApiError(422, 'Farmer is inactive'))
    await expect(captureDelivery(input(), user, false)).rejects.toThrow('Farmer is inactive')
    expect(await db.outbox.count()).toBe(0)
  })

  it('never stores passwords or tokens in the outbox', async () => {
    const r = await captureDelivery(input(), user, true)
    const json = JSON.stringify(r)
    expect(json).not.toMatch(/password|token/i)
  })
})

describe('syncOutbox', () => {
  async function queue(n: number, who = user) {
    const ids: string[] = []
    for (let k = 0; k < n; k++) {
      const i = input()
      ids.push(i.id)
      await captureDelivery(i, who, true)
    }
    return ids
  }

  it('marks records synced only when the server confirms each one', async () => {
    const [a, b, c, d] = await queue(4)
    apiMock.mockResolvedValueOnce({ results: [
      { id: a, status: 'created', receipt_no: 'TST-2026-000010', message: null, warnings: [] },
      { id: b, status: 'duplicate', receipt_no: 'TST-2026-000009', message: null, warnings: [] },
      { id: c, status: 'rejected', receipt_no: null, message: 'Farmer is inactive', warnings: [] },
      { id: d, status: 'conflict', receipt_no: null, message: 'Different delivery with this ID', warnings: [] },
    ] })
    const s = await syncOutbox(user.id)
    expect(s).toMatchObject({ synced: 2, rejected: 1, conflicts: 1, networkError: false })
    expect((await db.outbox.get(a))!.receiptNo).toBe('TST-2026-000010')
    expect((await db.outbox.get(b))!.status).toBe('synced')          // duplicate = already safe on server
    expect((await db.outbox.get(c))!.lastError).toBe('Farmer is inactive')
    expect((await db.outbox.get(d))!.status).toBe('conflict')          // kept, not deleted
  })

  it('keeps records pending when the network fails mid-sync', async () => {
    const [a] = await queue(1)
    apiMock.mockRejectedValueOnce(offline())
    const s = await syncOutbox(user.id)
    expect(s.networkError).toBe(true)
    const rec = (await db.outbox.get(a))!
    expect(rec.status).toBe('pending')
    expect(rec.attempts).toBe(1)
  })

  it('a record missing from the server response stays pending (online is not proof of sync)', async () => {
    const [a, b] = await queue(2)
    apiMock.mockResolvedValueOnce({ results: [{ id: a, status: 'created', receipt_no: 'X-1', message: null, warnings: [] }] })
    await syncOutbox(user.id)
    expect((await db.outbox.get(a))!.status).toBe('synced')
    expect((await db.outbox.get(b))!.status).toBe('pending')
  })

  it("never uploads another user's records", async () => {
    await queue(1, { ...user, id: 'someone-else' } as Me)
    const s = await syncOutbox(user.id)
    expect(apiMock).not.toHaveBeenCalled()
    expect(s.uploaded).toBe(0)
  })

  it('sends records in capture order with the device id', async () => {
    await queue(2)
    apiMock.mockResolvedValueOnce({ results: [] })
    await syncOutbox(user.id)
    const body = apiMock.mock.calls[0][1]!.json as { device_id: string; deliveries: { captured_at: string; provisional_receipt_no: string }[] }
    expect(body.device_id).toBeTruthy()
    expect(body.deliveries.map((d) => d.provisional_receipt_no.slice(-4))).toEqual(['0001', '0002'])
  })
})

describe('offline session snapshot', () => {
  it(`is valid for ${OFFLINE_SESSION_HOURS} hours after the last online login, then expires`, async () => {
    await saveSessionSnapshot(user)
    expect(await loadValidSnapshot()).not.toBeNull()
    const later = Date.now() + (OFFLINE_SESSION_HOURS + 1) * 3_600_000
    expect(await loadValidSnapshot(later)).toBeNull()
  })
})
