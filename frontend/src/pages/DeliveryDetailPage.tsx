import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Ban, FileDown, PencilLine } from 'lucide-react'
import { api, openFile } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useDelivery } from '../features/deliveries/api'
import { useApiMutation, useCrops } from '../features/reference/api'
import { fmtDateTime, Select, Textarea } from '../components/form'
import { Alert, Badge, Button, Field, Input, Modal, Skeleton } from '../components/ui'
import type { DeliveryDetail } from '../types/domain'
import { formatKg, isValidWeight, netWeight } from '../utils/weight'

export default function DeliveryDetailPage() {
  const { id = '' } = useParams()
  const { can, user } = useAuth()
  const { data: d, isLoading, error } = useDelivery(id)
  const [amending, setAmending] = useState(false)
  const [voiding, setVoiding] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const review = useApiMutation(({ aid, decision }: { aid: string; decision: 'approve' | 'reject' }) =>
    api(`/deliveries/${id}/amendments/${aid}/review`, { method: 'POST', json: { decision } }), ['deliveries', 'farmers'])

  if (isLoading) return <Skeleton className="h-64" />
  if (error || !d) return <Alert>{(error as Error)?.message ?? 'Not found'}</Alert>
  const pendingAmendment = d.amendments.find((a) => a.status === 'pending')

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/deliveries" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="size-4" />Deliveries</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Receipt</p>
          <div className="flex items-center gap-3"><h1 className="font-mono text-2xl font-bold">{d.receipt_no}</h1>
            <Badge tone={d.status === 'voided' ? 'red' : 'green'}>{d.status}</Badge></div>
          {d.provisional_receipt_no && <p className="text-sm text-slate-500">Offline receipt: {d.provisional_receipt_no}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => openFile(`/deliveries/${d.id}/receipt.pdf`).catch((e) => setFileError(e.message))}><FileDown className="size-4" />Receipt PDF</Button>
          {d.status === 'recorded' && can('delivery.amend_request') && !pendingAmendment &&
            <Button variant="secondary" onClick={() => setAmending(true)}><PencilLine className="size-4" />Request correction</Button>}
          {d.status === 'recorded' && can('delivery.amend_approve') &&
            <Button variant="danger" onClick={() => setVoiding(true)}><Ban className="size-4" />Void</Button>}
        </div>
      </div>
      {fileError && <div className="mb-4"><Alert>{fileError}</Alert></div>}
      {d.status === 'voided' && <div className="mb-4"><Alert>Voided {d.voided_at && fmtDateTime(d.voided_at)}: {d.void_reason}</Alert></div>}

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <h2 className="mb-3 font-semibold">Delivery</h2>
          <Rows rows={[
            ['Farmer', <Link key="f" className="text-brand-700 hover:underline" to={`/farmers/${d.farmer.id}`}>{d.farmer.full_name}</Link>],
            ['Member no.', d.farmer.membership_no], ['Crop', d.crop.name + (d.grade ? ` · ${d.grade.name}` : '')],
            ['Season', d.season.name], ['Centre', d.centre.name], ['Recorded by', d.recorder.full_name],
          ]} />
        </section>
        <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <h2 className="mb-3 font-semibold">Weights</h2>
          <Rows rows={[['Gross', formatKg(d.gross_weight)], ['Tare', formatKg(d.tare_weight)]]} />
          <div className="mt-3 flex items-baseline justify-between border-t border-slate-100 pt-3"><span className="font-medium">Net</span><span className="text-2xl font-bold">{formatKg(d.net_weight)}</span></div>
          <div className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
            <p>Captured on device: {fmtDateTime(d.captured_at)}</p>
            <p>Received by server: {fmtDateTime(d.received_at)} ({d.source === 'offline_sync' ? 'synced from offline' : 'online'})</p>
            <p className="mt-1 font-mono">Ref: {d.id}</p>
          </div>
        </section>
      </div>
      {d.notes && <p className="mt-4 rounded-lg bg-white p-4 text-sm ring-1 ring-slate-200"><b>Notes:</b> {d.notes}</p>}

      <section className="mt-6">
        <h2 className="mb-3 font-semibold">Correction history</h2>
        {review.error && <div className="mb-2"><Alert>{review.error.message}</Alert></div>}
        {d.amendments.length === 0 && <p className="text-sm text-slate-500">No corrections. The weights above are as originally recorded.</p>}
        <ul className="space-y-3">
          {d.amendments.map((a) => (
            <li key={a.id} className="rounded-lg bg-white p-4 text-sm ring-1 ring-slate-200">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>Requested by <b>{a.requester.full_name}</b> · {fmtDateTime(a.created_at)}</span>
                <Badge tone={a.status === 'approved' ? 'green' : a.status === 'rejected' ? 'red' : 'amber'}>{a.status}</Badge>
              </div>
              <p className="mt-1 text-slate-600">Reason: {a.reason}</p>
              <table className="mt-2 text-xs"><tbody>
                {(['gross_weight', 'tare_weight', 'net_weight'] as const).filter((k) => a.old_values[k] !== a.new_values[k]).map((k) => (
                  <tr key={k}><td className="pr-3 text-slate-500">{k.replace('_', ' ')}</td><td className="pr-2 line-through">{a.old_values[k]}</td><td className="font-medium">→ {a.new_values[k]}</td></tr>
                ))}
              </tbody></table>
              {a.review_note && <p className="mt-1 text-slate-500">Review note: {a.review_note}</p>}
              {a.status === 'pending' && can('delivery.amend_approve') && a.requester.id !== user?.id && (
                <div className="mt-3 flex gap-2">
                  <Button loading={review.isPending} onClick={() => review.mutate({ aid: a.id, decision: 'approve' })}>Approve</Button>
                  <Button variant="secondary" disabled={review.isPending} onClick={() => review.mutate({ aid: a.id, decision: 'reject' })}>Reject</Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      {amending && <AmendModal delivery={d} onClose={() => setAmending(false)} />}
      {voiding && <VoidModal id={d.id} onClose={() => setVoiding(false)} />}
    </div>
  )
}

function Rows({ rows }: { rows: [string, React.ReactNode][] }) {
  return <dl className="space-y-1.5 text-sm">{rows.map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt className="text-slate-500">{k}</dt><dd className="text-right">{v}</dd></div>)}</dl>
}

function AmendModal({ delivery, onClose }: { delivery: DeliveryDetail; onClose: () => void }) {
  const crops = useCrops()
  const grades = crops.data?.find((c) => c.id === delivery.crop.id)?.grades.filter((g) => g.is_active) ?? []
  const [gross, setGross] = useState(delivery.gross_weight)
  const [tare, setTare] = useState(delivery.tare_weight)
  const [grade, setGrade] = useState(delivery.grade?.id ?? '')
  const [reason, setReason] = useState('')
  const net = netWeight(gross, tare)
  const valid = isValidWeight(gross) && isValidWeight(tare) && !!net && !net.startsWith('-') && net !== '0.000' && reason.trim().length >= 5
  const save = useApiMutation(() => api(`/deliveries/${delivery.id}/amendments`, {
    method: 'POST', json: { gross_weight: gross, tare_weight: tare, grade_id: grade || null, reason },
  }), ['deliveries'])
  return (
    <Modal open onClose={onClose} title="Request a correction">
      <div className="space-y-4">
        <p className="text-sm text-slate-500">The original values are kept. A manager must approve the correction before it takes effect.</p>
        {save.error && <Alert>{save.error.message}</Alert>}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Gross (kg)" htmlFor="a-g"><Input id="a-g" inputMode="decimal" value={gross} onChange={(e) => setGross(e.target.value)} /></Field>
          <Field label="Tare (kg)" htmlFor="a-t"><Input id="a-t" inputMode="decimal" value={tare} onChange={(e) => setTare(e.target.value)} /></Field>
          <Field label="Net" htmlFor="a-n"><p id="a-n" className="py-2 font-semibold">{net && !net.startsWith('-') ? formatKg(net) : '—'}</p></Field>
        </div>
        {grades.length > 0 && <Field label="Grade" htmlFor="a-gr"><Select id="a-gr" value={grade} onChange={(e) => setGrade(e.target.value)}>
          <option value="">None</option>{grades.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</Select></Field>}
        <Field label="Reason for correction" htmlFor="a-r" hint="At least 5 characters, e.g. 'Scale was not zeroed'"><Textarea id="a-r" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Submit for approval</Button></div>
      </div>
    </Modal>
  )
}

function VoidModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const save = useApiMutation(() => api(`/deliveries/${id}/void`, { method: 'POST', json: { reason } }), ['deliveries', 'farmers'])
  return (
    <Modal open onClose={onClose} title="Void this delivery?">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">The delivery stays in the records marked VOIDED and is excluded from totals and payments. This cannot be undone.</p>
        {save.error && <Alert>{save.error.message}</Alert>}
        <Field label="Reason" htmlFor="v-r"><Textarea id="v-r" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="danger" disabled={reason.trim().length < 5} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Void delivery</Button></div>
      </div>
    </Modal>
  )
}
