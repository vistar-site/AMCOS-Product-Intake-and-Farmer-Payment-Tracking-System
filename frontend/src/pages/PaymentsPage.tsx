import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Plus } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation } from '../features/reference/api'
import { fmtDateTime, Select } from '../components/form'
import { Alert, Badge, Button, EmptyState, Modal, PageHeader, Skeleton } from '../components/ui'
import { BATCH_PAY_TONE, METHOD_LABEL, type EligiblePayout, type PaymentBatch } from '../types/finance'
import { formatTZS } from '../utils/money'

export default function PaymentsPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const list = useQuery({ queryKey: ['payment-batches'], queryFn: () => api<PaymentBatch[]>('/payment-batches') })
  const [open, setOpen] = useState(false)
  return (
    <>
      <PageHeader title="Payments" description="Bulk payment batches: prepare, approve, export to the bank or mobile money, then record results."
        actions={can('payment_batch.prepare') && <Button onClick={() => setOpen(true)}><Plus className="size-4" />New payment batch</Button>} />
      <div className="mb-4"><Alert tone="amber">Payment files are exported for upload to the bank or mobile-money portal. The system does not send money itself, and nothing is marked paid until you record the provider’s results.</Alert></div>
      {list.isLoading && <Skeleton className="h-32" />}
      {list.data?.length === 0 && <EmptyState title="No payment batches" description="Approved payouts can be grouped into a batch here." />}
      {!!list.data?.length && (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Batch</th><th className="px-4 py-3">Method</th><th className="px-4 py-3 text-right">Payments</th>
                <th className="px-4 py-3 text-right">Total</th><th className="px-4 py-3 text-right">Paid</th><th className="px-4 py-3">Prepared by</th><th className="px-4 py-3">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.data.map((b) => {
                const live = b.status === 'cancelled' ? [] : b.payments
                return (
                  <tr key={b.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/payments/${b.id}`)}>
                    <td className="px-4 py-3"><Link to={`/payments/${b.id}`} className="font-mono text-xs text-brand-700 hover:underline">{b.batch_no}</Link><p className="text-xs text-slate-500">{fmtDateTime(b.created_at)}</p></td>
                    <td className="px-4 py-3">{METHOD_LABEL[b.method]}</td><td className="px-4 py-3 text-right">{b.payments.length}</td>
                    <td className="px-4 py-3 text-right">{formatTZS(live.reduce((s, p) => s + Number(p.amount), 0))}</td>
                    <td className="px-4 py-3 text-right">{formatTZS(b.payments.filter((p) => p.status === 'paid').reduce((s, p) => s + Number(p.amount), 0))}</td>
                    <td className="px-4 py-3">{b.preparer.full_name}</td>
                    <td className="px-4 py-3"><Badge tone={BATCH_PAY_TONE[b.status]}>{b.status.replace('_', ' ')}</Badge></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {open && <CreateBatchModal onClose={() => setOpen(false)} onCreated={(id) => navigate(`/payments/${id}`)} />}
    </>
  )
}

function CreateBatchModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [method, setMethod] = useState<'mobile_money' | 'bank' | 'cash'>('mobile_money')
  const elig = useQuery({ queryKey: ['payment-batches', 'eligible', method], queryFn: () => api<EligiblePayout[]>(`/payment-batches/eligible?method=${method}`) })
  const [sel, setSel] = useState<Set<string>>(new Set())
  const save = useApiMutation(() => api<PaymentBatch>('/payment-batches', { method: 'POST', json: { method, payout_ids: [...sel] } }), ['payment-batches'])
  const ready = useMemo(() => (elig.data ?? []).filter((e) => !e.problem), [elig.data])
  const blocked = useMemo(() => (elig.data ?? []).filter((e) => e.problem), [elig.data])
  const total = ready.filter((e) => sel.has(e.payout_id)).reduce((s, e) => s + Number(e.net_payable), 0)
  const toggle = (id: string) => { const n = new Set(sel); if (n.has(id)) n.delete(id); else n.add(id); setSel(n) }
  return (
    <Modal open onClose={onClose} title="New payment batch">
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <Select aria-label="Payment method" value={method} onChange={(e) => { setMethod(e.target.value as typeof method); setSel(new Set()) }}>
          <option value="mobile_money">Mobile money</option><option value="bank">Bank transfer</option><option value="cash">Cash</option></Select>
        {elig.isLoading && <Skeleton className="h-20" />}
        {ready.length > 0 && <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600" checked={sel.size === ready.length}
          onChange={(e) => setSel(e.target.checked ? new Set(ready.map((r) => r.payout_id)) : new Set())} />Select all ready ({ready.length})</label>}
        <ul className="max-h-72 divide-y divide-slate-100 overflow-y-auto rounded-md ring-1 ring-slate-200 empty:hidden">
          {ready.map((e) => (
            <li key={e.payout_id}><label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-slate-50">
              <input type="checkbox" className="size-4 accent-brand-600" checked={sel.has(e.payout_id)} onChange={() => toggle(e.payout_id)} />
              <span className="flex-1">{e.farmer.full_name}<span className="block text-xs text-slate-500">{e.farmer.membership_no} · {e.run_no}</span></span>
              <span className="font-medium">{formatTZS(e.net_payable)}</span></label></li>
          ))}
        </ul>
        {ready.length === 0 && !elig.isLoading && <p className="text-sm text-slate-500">No approved payouts are ready for {METHOD_LABEL[method].toLowerCase()} payment.</p>}
        {blocked.length > 0 && (
          <details className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
            <summary className="flex cursor-pointer items-center gap-1 font-medium"><AlertTriangle className="size-4" />{blocked.length} payout(s) cannot be paid this way</summary>
            <ul className="mt-2 space-y-0.5">{blocked.map((e) => <li key={e.payout_id}><Link className="underline" to={`/farmers/${e.farmer.id}`}>{e.farmer.full_name}</Link>: {e.problem}</li>)}</ul>
          </details>
        )}
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-600">{sel.size} selected · <b>{formatTZS(total)}</b></span>
          <div className="flex gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button disabled={!sel.size} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: (b) => onCreated(b.id) })}>Create draft batch</Button></div>
        </div>
      </div>
    </Modal>
  )
}
