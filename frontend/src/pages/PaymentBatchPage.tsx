import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, BadgeCheck, FileSpreadsheet, FileText, Send, Undo2, XCircle } from 'lucide-react'
import { api, downloadFile } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation } from '../features/reference/api'
import { fmtDateTime, Textarea } from '../components/form'
import { Alert, Badge, Button, Field, Input, Modal, Skeleton } from '../components/ui'
import { BATCH_PAY_TONE, METHOD_LABEL, PAY_TONE, type Payment, type PaymentBatch } from '../types/finance'
import { formatTZS } from '../utils/money'

type Result = { status: '' | 'paid' | 'failed'; ref: string; reason: string }

export default function PaymentBatchPage() {
  const { id = '' } = useParams()
  const { can, user } = useAuth()
  const q = useQuery({ queryKey: ['payment-batches', id], queryFn: () => api<PaymentBatch>(`/payment-batches/${id}`) })
  const [results, setResults] = useState<Record<string, Result>>({})
  const [cancelling, setCancelling] = useState(false)
  const [reversing, setReversing] = useState<Payment | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const keys = ['payment-batches', 'payout-runs']
  const submit = useApiMutation(() => api(`/payment-batches/${id}/submit`, { method: 'POST' }), keys)
  const approve = useApiMutation(() => api(`/payment-batches/${id}/approve`, { method: 'POST' }), keys)
  const record = useApiMutation((body: object) => api(`/payment-batches/${id}/results`, { method: 'POST', json: body }), keys)

  if (q.isLoading) return <Skeleton className="h-64" />
  if (q.error || !q.data) return <Alert>{(q.error as Error)?.message}</Alert>
  const b = q.data
  const err = submit.error || approve.error || record.error
  const total = b.payments.reduce((s, p) => s + Number(p.amount), 0)
  const paid = b.payments.filter((p) => p.status === 'paid').reduce((s, p) => s + Number(p.amount), 0)
  const awaiting = b.payments.filter((p) => p.status === 'exported')
  const entered = Object.entries(results).filter(([, r]) => r.status)
  const resultsValid = entered.length > 0 && entered.every(([, r]) => (r.status === 'paid' ? r.ref.trim() : r.reason.trim()))
  const exportable = ['approved', 'exported', 'partially_completed'].includes(b.status) && b.payments.some((p) => ['pending', 'exported'].includes(p.status))
  const doExport = (fmt: 'csv' | 'xlsx') => { setFileError(null); downloadFile(`/payment-batches/${id}/export?format=${fmt}`, 'POST').then(() => q.refetch()).catch((e) => setFileError(e.message)) }
  const setR = (pid: string, patch: Partial<Result>) => setResults({ ...results, [pid]: { ...(results[pid] ?? { status: '', ref: '', reason: '' }), ...patch } })

  return (
    <>
      <Link to="/payments" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="size-4" />Payments</Link>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3"><h1 className="font-mono text-2xl font-bold">{b.batch_no}</h1><Badge tone={BATCH_PAY_TONE[b.status]}>{b.status.replace('_', ' ')}</Badge></div>
          <p className="mt-1 text-sm text-slate-500">{METHOD_LABEL[b.method]} · prepared by {b.preparer.full_name} · {fmtDateTime(b.created_at)}
            {b.exported_at && ` · exported ${b.export_count}× (last ${fmtDateTime(b.exported_at)})`}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {b.status === 'draft' && can('payment_batch.prepare') && <Button loading={submit.isPending} onClick={() => submit.mutate(undefined)}><Send className="size-4" />Submit for approval</Button>}
          {b.status === 'awaiting_approval' && can('payment_batch.approve') && (
            <Button disabled={b.prepared_by === user?.id} loading={approve.isPending} onClick={() => approve.mutate(undefined)}><BadgeCheck className="size-4" />Approve</Button>)}
          {exportable && can('payment_batch.prepare') && <>
            <Button variant="secondary" onClick={() => doExport('csv')}><FileText className="size-4" />Export CSV</Button>
            <Button variant="secondary" onClick={() => doExport('xlsx')}><FileSpreadsheet className="size-4" />Export Excel</Button></>}
          {['draft', 'awaiting_approval', 'approved'].includes(b.status) && can('payment_batch.prepare') &&
            <Button variant="ghost" onClick={() => setCancelling(true)}><XCircle className="size-4" />Cancel batch</Button>}
        </div>
      </div>
      {(err || fileError) && <div className="mb-4"><Alert>{err?.message ?? fileError}</Alert></div>}
      {b.status === 'awaiting_approval' && b.prepared_by === user?.id && <div className="mb-4"><Alert tone="amber">You prepared this batch, so a different authorized user must approve it.</Alert></div>}

      <div className="mb-6 grid gap-3 sm:grid-cols-4">
        {[['Payments', String(b.payments.length)], ['Batch total', formatTZS(total)], ['Confirmed paid', formatTZS(paid)], ['Awaiting result', String(awaiting.length)]].map(([k, v]) => (
          <div key={k} className="rounded-lg bg-white p-4 ring-1 ring-slate-200"><p className="text-sm text-slate-500">{k}</p><p className="mt-0.5 text-lg font-semibold">{v}</p></div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-3 py-2">Farmer</th><th className="px-3 py-2">Destination</th><th className="px-3 py-2 text-right">Amount</th><th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">{awaiting.length && can('payment.reconcile') ? 'Record result' : 'Reference / reason'}</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {b.payments.map((p) => {
              const r = results[p.id]
              return (
                <tr key={p.id} className="align-top">
                  <td className="px-3 py-2"><Link className="text-brand-700 hover:underline" to={`/farmers/${p.farmer.id}`}>{p.farmer.full_name}</Link><span className="block text-xs text-slate-500">{p.farmer.membership_no}</span></td>
                  <td className="px-3 py-2 font-mono text-xs">{p.destination ?? '—'}{p.destination_bank && <span className="block font-sans text-slate-500">{p.destination_bank}</span>}</td>
                  <td className="px-3 py-2 text-right font-medium">{formatTZS(p.amount)}</td>
                  <td className="px-3 py-2"><Badge tone={PAY_TONE[p.status]}>{p.status}</Badge></td>
                  <td className="px-3 py-2">
                    {p.status === 'exported' && can('payment.reconcile') ? (
                      <div className="flex flex-wrap gap-2">
                        <div className="flex rounded-md ring-1 ring-slate-300">
                          {(['paid', 'failed'] as const).map((s) => (
                            <button key={s} type="button" onClick={() => setR(p.id, { status: r?.status === s ? '' : s })}
                              className={`px-2.5 py-1 text-xs capitalize ${r?.status === s ? (s === 'paid' ? 'bg-green-600 text-white' : 'bg-red-600 text-white') : ''}`}>{s}</button>
                          ))}
                        </div>
                        {r?.status === 'paid' && <Input className="w-44" placeholder="Transaction ref." aria-label="Transaction reference" value={r.ref} onChange={(e) => setR(p.id, { ref: e.target.value })} />}
                        {r?.status === 'failed' && <Input className="w-56" placeholder="Failure reason" aria-label="Failure reason" value={r.reason} onChange={(e) => setR(p.id, { reason: e.target.value })} />}
                      </div>
                    ) : <span className="text-xs">{p.transaction_ref ?? p.failure_reason ?? '—'}{p.paid_at && <span className="block text-slate-500">{fmtDateTime(p.paid_at)}</span>}</span>}
                  </td>
                  <td className="px-3 py-2 text-right">{p.status === 'paid' && can('payment_batch.approve') && <Button variant="ghost" onClick={() => setReversing(p)}><Undo2 className="size-4" />Reverse</Button>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {awaiting.length > 0 && can('payment.reconcile') && (
        <div className="mt-4 flex items-center justify-end gap-3">
          <span className="text-sm text-slate-500">{entered.length} of {awaiting.length} results entered</span>
          <Button disabled={!resultsValid} loading={record.isPending} onClick={() => record.mutate({
            results: entered.map(([payment_id, r]) => ({ payment_id, status: r.status, transaction_ref: r.ref || null, failure_reason: r.reason || null })),
          }, { onSuccess: () => setResults({}) })}>Save results</Button>
        </div>
      )}
      {cancelling && <ReasonModal title="Cancel payment batch" action="Cancel batch" path={`/payment-batches/${id}/cancel`}
        note="The payouts return to the eligible list and can be added to another batch." onClose={() => setCancelling(false)} />}
      {reversing && <ReasonModal title={`Reverse payment to ${reversing.farmer.full_name}`} action="Reverse payment"
        path={`/payment-batches/${id}/payments/${reversing.id}/reverse`}
        note={`Use only when the money (${formatTZS(reversing.amount)}, ref ${reversing.transaction_ref}) did not reach the farmer or was recovered. The payout becomes payable again.`}
        onClose={() => setReversing(null)} />}
    </>
  )
}

function ReasonModal({ title, action, path, note, onClose }: { title: string; action: string; path: string; note: string; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const save = useApiMutation(() => api(path, { method: 'POST', json: { reason } }), ['payment-batches', 'payout-runs'])
  return (
    <Modal open onClose={onClose} title={title}>
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <p className="text-sm text-slate-600">{note}</p>
        <Field label="Reason (recorded in the audit trail)" htmlFor="rsn"><Textarea id="rsn" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Back</Button>
          <Button variant="danger" disabled={reason.trim().length < 5} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>{action}</Button></div>
      </div>
    </Modal>
  )
}
