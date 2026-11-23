import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Lock, Plus, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation } from '../features/reference/api'
import { fmtDateTime } from '../components/form'
import { Alert, Badge, Button, Modal, Skeleton } from '../components/ui'
import { BATCH_TONE, STAGE_LABEL, type Batch, type EligibleDelivery, type Reconciliation } from '../types/warehouse'
import { formatTZS, sumKg } from '../utils/money'
import { formatKg } from '../utils/weight'

export default function BatchDetailPage() {
  const { id = '' } = useParams()
  const { can } = useAuth()
  const batch = useQuery({ queryKey: ['batches', id], queryFn: () => api<Batch>(`/batches/${id}`) })
  const rec = useQuery({ queryKey: ['batches', id, 'rec'], queryFn: () => api<Reconciliation>(`/batches/${id}/reconciliation`) })
  const [adding, setAdding] = useState(false)
  const [confirmClose, setConfirmClose] = useState(false)
  const remove = useApiMutation((deliveryId: string) => api(`/batches/${id}/deliveries/${deliveryId}`, { method: 'DELETE' }), ['batches'])
  const close = useApiMutation(() => api(`/batches/${id}/close`, { method: 'POST' }), ['batches'])

  if (batch.isLoading) return <Skeleton className="h-64" />
  if (batch.error || !batch.data) return <Alert>{(batch.error as Error)?.message}</Alert>
  const b = batch.data
  const editable = b.status === 'open' && can('batch.manage')
  const total = sumKg(b.members.map((m) => m.net_weight))

  return (
    <>
      <Link to="/batches" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="size-4" />Batches</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3"><h1 className="font-mono text-2xl font-bold">{b.batch_no}</h1>
            <Badge tone={BATCH_TONE[b.status]}>{b.status.replace('_', ' ')}</Badge></div>
          <p className="mt-1 text-sm text-slate-500">{b.crop.name} · {b.season.name} · {b.centre.name}</p>
        </div>
        {editable && <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setAdding(true)}><Plus className="size-4" />Add deliveries</Button>
          <Button disabled={!b.members.length} onClick={() => setConfirmClose(true)}><Lock className="size-4" />Close batch</Button>
        </div>}
      </div>
      {(remove.error || close.error) && <div className="mb-4"><Alert>{(remove.error || close.error)!.message}</Alert></div>}

      {rec.data && <ReconciliationPanel r={rec.data} />}

      <h2 className="mb-3 mt-8 font-semibold">Farmer deliveries in this batch ({b.members.length} · {formatKg(total)})</h2>
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-4 py-2">Receipt</th><th className="px-4 py-2">Farmer</th><th className="px-4 py-2">Date</th><th className="px-4 py-2 text-right">Net</th><th className="px-4 py-2 text-right">Share</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {b.members.map((m) => (
              <tr key={m.delivery_id}>
                <td className="px-4 py-2 font-mono text-xs"><Link className="text-brand-700 hover:underline" to={`/deliveries/${m.delivery_id}`}>{m.delivery.receipt_no}</Link></td>
                <td className="px-4 py-2">{m.delivery.farmer.full_name} <span className="text-slate-500">{m.delivery.farmer.membership_no}</span></td>
                <td className="px-4 py-2">{fmtDateTime(m.delivery.captured_at)}</td>
                <td className="px-4 py-2 text-right font-medium">{formatKg(m.net_weight)}</td>
                <td className="px-4 py-2 text-right text-slate-500">{Number(total) ? ((Number(m.net_weight) / Number(total)) * 100).toFixed(2) : '0'}%</td>
                <td className="px-4 py-2 text-right">{editable &&
                  <button className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Remove from batch"
                    onClick={() => remove.mutate(m.delivery_id)}><Trash2 className="size-4" /></button>}</td>
              </tr>
            ))}
            {b.members.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">No deliveries yet. Use “Add deliveries”.</td></tr>}
          </tbody>
        </table>
      </div>

      {adding && <AddDeliveriesModal batchId={b.id} onClose={() => setAdding(false)} />}
      <Modal open={confirmClose} onClose={() => setConfirmClose(false)} title="Close this batch?">
        <p className="text-sm text-slate-600">The batch total will be fixed at <b>{formatKg(total)}</b> from {b.members.length} deliveries.
          Its deliveries can no longer be corrected or voided, and no deliveries can be added or removed.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setConfirmClose(false)}>Cancel</Button>
          <Button loading={close.isPending} onClick={() => close.mutate(undefined, { onSuccess: () => setConfirmClose(false) })}>Close batch</Button></div>
      </Modal>
    </>
  )
}

export function ReconciliationPanel({ r }: { r: Reconciliation }) {
  const stages: [string, string | null][] = [
    ['Farmer deliveries', r.delivered_weight], ['Dispatched', r.dispatched_weight], ['Received at warehouse', r.received_weight],
    ['Accepted (after rejects)', r.accepted_weight], ['Sold at auction', r.sold_weight],
  ]
  return (
    <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
      <h2 className="mb-3 font-semibold">Reconciliation</h2>
      <div className="grid gap-3 sm:grid-cols-5">
        {stages.map(([label, v], i) => (
          <div key={label} className="rounded-md bg-slate-50 p-3">
            <p className="text-xs text-slate-500">{i + 1}. {label}</p>
            <p className="mt-0.5 font-semibold">{v === null ? '—' : formatKg(v)}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
        {r.warehouse_receipt_no && <span>Warehouse receipt <b>{r.warehouse_receipt_no}</b></span>}
        {r.unsold_weight !== null && <span>Unsold: <b>{formatKg(r.unsold_weight)}</b></span>}
        {Number(r.sold_value) > 0 && <span>Sale value: <b>{formatTZS(r.sold_value)}</b></span>}
      </div>
      {r.discrepancies.length > 0 && (
        <ul className="mt-4 space-y-2">
          {r.discrepancies.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm">
              <span>{STAGE_LABEL[d.stage]}: expected {formatKg(d.expected_weight)}, actual {formatKg(d.actual_weight)}
                {' '}<b className={Number(d.difference) < 0 ? 'text-red-600' : 'text-blue-700'}>({Number(d.difference) > 0 ? '+' : ''}{formatKg(d.difference)})</b></span>
              <Badge tone={d.status === 'open' ? 'red' : 'green'}>{d.status}</Badge>
              {d.explanation && <p className="w-full text-xs text-slate-500">{d.explanation}</p>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-slate-500">Differences are recorded here; farmer delivery records are never adjusted.</p>
    </section>
  )
}

function AddDeliveriesModal({ batchId, onClose }: { batchId: string; onClose: () => void }) {
  const eligible = useQuery({ queryKey: ['batches', batchId, 'eligible'], queryFn: () => api<EligibleDelivery[]>(`/batches/${batchId}/eligible-deliveries`) })
  const [sel, setSel] = useState<Set<string>>(new Set())
  const add = useApiMutation((ids: string[]) => api(`/batches/${batchId}/deliveries`, { method: 'POST', json: { delivery_ids: ids } }), ['batches'])
  const rows = eligible.data ?? []
  const selectedKg = useMemo(() => sumKg(rows.filter((r) => sel.has(r.id)).map((r) => r.net_weight)), [rows, sel])
  const toggle = (id: string) => { const n = new Set(sel); if (n.has(id)) n.delete(id); else n.add(id); setSel(n) }
  return (
    <Modal open onClose={onClose} title="Add deliveries to batch">
      <div className="space-y-3">
        {add.error && <Alert>{add.error.message}</Alert>}
        <p className="text-sm text-slate-500">Recorded deliveries of the same crop, season and centre that are not yet in a batch.</p>
        {eligible.isLoading && <Skeleton className="h-24" />}
        {rows.length === 0 && !eligible.isLoading && <p className="text-sm text-slate-500">No eligible deliveries.</p>}
        {rows.length > 0 && (
          <>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600"
              checked={sel.size === rows.length} onChange={(e) => setSel(e.target.checked ? new Set(rows.map((r) => r.id)) : new Set())} />Select all ({rows.length})</label>
            <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-md ring-1 ring-slate-200">
              {rows.map((r) => (
                <li key={r.id}><label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-slate-50">
                  <input type="checkbox" className="size-4 accent-brand-600" checked={sel.has(r.id)} onChange={() => toggle(r.id)} />
                  <span className="flex-1">{r.farmer.full_name}<span className="block font-mono text-xs text-slate-500">{r.receipt_no} · {fmtDateTime(r.captured_at)}</span></span>
                  <span className="font-medium">{formatKg(r.net_weight)}</span>
                </label></li>
              ))}
            </ul>
          </>
        )}
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-slate-600">{sel.size} selected · {formatKg(selectedKg)}</span>
          <div className="flex gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button disabled={!sel.size} loading={add.isPending} onClick={() => add.mutate([...sel], { onSuccess: onClose })}>Add to batch</Button></div>
        </div>
      </div>
    </Modal>
  )
}
