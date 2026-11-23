import { Fragment, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, BadgeCheck, ChevronDown, ChevronRight, Search, XCircle } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import PayoutLinesTable from '../features/finance/PayoutLinesTable'
import { useApiMutation } from '../features/reference/api'
import { fmtDateTime, Textarea } from '../components/form'
import { Alert, Badge, Button, Field, Input, Modal, Skeleton } from '../components/ui'
import type { Run } from '../types/finance'
import { formatTZS } from '../utils/money'
import { formatKg } from '../utils/weight'

const P_TONE = { calculated: 'amber', approved: 'green', needs_review: 'red', paid: 'green', cancelled: 'slate' } as const

export default function PayoutRunPage() {
  const { id = '' } = useParams()
  const { can, user } = useAuth()
  const q = useQuery({ queryKey: ['payout-runs', id], queryFn: () => api<Run>(`/payout-runs/${id}`) })
  const [open, setOpen] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const approve = useApiMutation(() => api(`/payout-runs/${id}/approve`, { method: 'POST' }), ['payout-runs', 'loans'])
  const payouts = useMemo(() => (q.data?.payouts ?? [])
    .filter((p) => !search || p.farmer.full_name.toLowerCase().includes(search.toLowerCase()) || p.farmer.membership_no.toLowerCase().startsWith(search.toLowerCase()))
    .sort((a, b) => a.farmer.full_name.localeCompare(b.farmer.full_name)), [q.data, search])

  if (q.isLoading) return <Skeleton className="h-64" />
  if (q.error || !q.data) return <Alert>{(q.error as Error)?.message}</Alert>
  const r = q.data
  const review = r.payouts.filter((p) => p.status === 'needs_review').length
  const selfCalculated = r.calculated_by === user?.id

  return (
    <>
      <Link to="/payouts" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="size-4" />Payouts</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3"><h1 className="font-mono text-2xl font-bold">{r.run_no}</h1><Badge tone={r.status === 'approved' ? 'green' : r.status === 'cancelled' ? 'slate' : 'amber'}>{r.status}</Badge></div>
          <p className="mt-1 text-sm text-slate-500">{r.crop.name} · {r.season.name} · {r.loss_policy === 'shared' ? 'Warehouse loss shared by farmers' : 'Warehouse loss absorbed by the AMCOS'} · calculated {fmtDateTime(r.calculated_at)}</p>
        </div>
        {r.status === 'calculated' && <div className="flex gap-2">
          {can('payout.calculate') && <Button variant="secondary" onClick={() => setCancelling(true)}><XCircle className="size-4" />Cancel run</Button>}
          {can('payout.approve') && <Button disabled={selfCalculated} title={selfCalculated ? 'Must be approved by a different user' : undefined} onClick={() => setConfirm(true)}><BadgeCheck className="size-4" />Approve payouts</Button>}
        </div>}
      </div>
      {r.status === 'cancelled' && <div className="mb-4"><Alert>Cancelled: {r.cancelled_reason}</Alert></div>}
      {review > 0 && <div className="mb-4"><Alert tone="amber">{review} payout(s) are held for review because deductions exceed earnings. They will not be paid until resolved (adjust the deduction configuration, cancel and recalculate).</Alert></div>}
      {approve.error && <div className="mb-4"><Alert>{approve.error.message}</Alert></div>}

      <div className="mb-6 grid gap-3 sm:grid-cols-4">
        {[['Farmers', String(r.payouts.length)], ['Gross earnings', formatTZS(r.total_gross)], ['Deductions', formatTZS(r.total_deductions)], ['Net payable', formatTZS(r.total_net)]].map(([k, v]) => (
          <div key={k} className="rounded-lg bg-white p-4 ring-1 ring-slate-200"><p className="text-sm text-slate-500">{k}</p><p className="mt-0.5 text-lg font-semibold">{v}</p></div>
        ))}
      </div>

      <div className="relative mb-3 max-w-sm"><Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
        <Input className="pl-9" placeholder="Find farmer" aria-label="Find farmer" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
      <div className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="w-8" /><th className="px-3 py-2">Farmer</th><th className="px-3 py-2 text-right">Paid kg</th><th className="px-3 py-2 text-right">Gross</th>
              <th className="px-3 py-2 text-right">Deductions</th><th className="px-3 py-2 text-right">Net payable</th><th className="px-3 py-2">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {payouts.map((p) => (
              <Fragment key={p.id}>
                <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === p.id ? null : p.id)}>
                  <td className="pl-3 text-slate-400">{open === p.id ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</td>
                  <td className="px-3 py-2"><Link className="font-medium text-brand-700 hover:underline" to={`/farmers/${p.farmer.id}`} onClick={(e) => e.stopPropagation()}>{p.farmer.full_name}</Link>
                    <span className="block text-xs text-slate-500">{p.farmer.membership_no}</span></td>
                  <td className="px-3 py-2 text-right">{formatKg(p.eligible_weight)}</td><td className="px-3 py-2 text-right">{formatTZS(p.gross_amount)}</td>
                  <td className="px-3 py-2 text-right">{formatTZS(p.total_deductions)}</td><td className="px-3 py-2 text-right font-semibold">{formatTZS(p.net_payable)}</td>
                  <td className="px-3 py-2"><Badge tone={P_TONE[p.status]}>{p.status.replace('_', ' ')}</Badge></td>
                </tr>
                {open === p.id && (
                  <tr className="bg-slate-50/60"><td /><td colSpan={6} className="px-3 py-3">
                    <div className="max-w-3xl"><PayoutLinesTable lines={p.lines} gross={p.gross_amount} deductions={p.total_deductions} net={p.net_payable} shortfall={p.shortfall} /></div>
                    {p.flags.map((f) => <p key={f} className="mt-1 text-xs text-amber-700">⚑ {f}</p>)}
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="Approve this payout run?">
        <p className="text-sm text-slate-600">Net payable <b>{formatTZS(r.total_net)}</b> to {r.payouts.length - review} farmers{review ? ` (${review} held for review)` : ''}.
          Approval books the input-loan repayments and makes payouts available for payment batches. It cannot be edited afterwards.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button>
          <Button loading={approve.isPending} onClick={() => approve.mutate(undefined, { onSuccess: () => setConfirm(false) })}>Approve</Button></div>
      </Modal>
      {cancelling && <CancelModal id={r.id} onClose={() => setCancelling(false)} />}
    </>
  )
}

function CancelModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const save = useApiMutation(() => api(`/payout-runs/${id}/cancel`, { method: 'POST', json: { reason } }), ['payout-runs'])
  return (
    <Modal open onClose={onClose} title="Cancel payout run">
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <p className="text-sm text-slate-600">The run is kept for the record but the sold produce becomes available for a new calculation.</p>
        <Field label="Reason" htmlFor="cr"><Textarea id="cr" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Back</Button>
          <Button variant="danger" disabled={reason.trim().length < 5} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Cancel run</Button></div>
      </div>
    </Modal>
  )
}
