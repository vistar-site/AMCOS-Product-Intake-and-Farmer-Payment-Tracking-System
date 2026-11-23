import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, Scale } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import FarmerForm, { farmerToValues } from '../features/farmers/FarmerForm'
import { useFarmer, useFarmerSummary } from '../features/farmers/api'
import { toFarmerBody, type FarmerValues } from '../features/farmers/schemas'
import { useDeliveries } from '../features/deliveries/api'
import { useApiMutation } from '../features/reference/api'
import { fmtDate, fmtDateTime, Pagination, Select } from '../components/form'
import { Alert, Badge, Button, Field, Input, Modal, Skeleton } from '../components/ui'
import { formatKg } from '../utils/weight'
import { farmerStatusTone } from './FarmersPage'
import FarmerStatement from '../features/finance/FarmerStatement'

export default function FarmerProfilePage() {
  const { id = '' } = useParams()
  const { can } = useAuth()
  const farmer = useFarmer(id)
  const summary = useFarmerSummary(id)
  const [page, setPage] = useState(1)
  const deliveries = useDeliveries({ farmer_id: id, page })
  const [editing, setEditing] = useState(false)
  const [statusOpen, setStatusOpen] = useState(false)
  const update = useApiMutation((v: FarmerValues) => {
    const { membership_no: _ignored, ...body } = toFarmerBody(v)
    return api(`/farmers/${id}`, { method: 'PATCH', json: body })
  }, ['farmers'])

  if (farmer.isLoading) return <Skeleton className="h-64" />
  if (farmer.error) return <Alert>{(farmer.error as Error).message}</Alert>
  const f = farmer.data!

  return (
    <>
      <Link to="/farmers" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="size-4" />Farmers</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3"><h1 className="text-2xl font-semibold">{f.full_name}</h1><Badge tone={farmerStatusTone[f.status]}>{f.status}</Badge></div>
          <p className="mt-1 text-sm text-slate-500">Member {f.membership_no} · registered {fmtDate(f.registration_date)}</p>
        </div>
        <div className="flex gap-2">
          {can('delivery.create') && f.status === 'active' &&
            <Link to={`/deliveries/new?farmer=${f.id}`}><Button><Scale className="size-4" />Record delivery</Button></Link>}
          {can('farmer.update') && <>
            <Button variant="secondary" onClick={() => setEditing(true)}><Pencil className="size-4" />Edit</Button>
            <Button variant="secondary" onClick={() => setStatusOpen(true)}>Change status</Button>
          </>}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <h2 className="mb-3 font-semibold">Member details</h2>
          <dl className="space-y-2 text-sm">
            {[['Phone', f.phone], ['Gender', f.gender], ['Village', f.village], ['Ward', f.ward], ['District', f.district],
              ['Region', f.region], ['Home centre', f.home_centre?.name]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4"><dt className="text-slate-500">{k}</dt><dd className="text-right capitalize-first">{v || '—'}</dd></div>
            ))}
            {f.payment_method && <>
              <div className="flex justify-between gap-4 border-t border-slate-100 pt-2"><dt className="text-slate-500">Payment</dt><dd>{f.payment_method.replace('_', ' ')}</dd></div>
              {f.payment_method === 'mobile_money' && <div className="flex justify-between"><dt className="text-slate-500">Mobile money</dt><dd>{f.mobile_money_number || <span className="text-amber-600">Missing</span>}</dd></div>}
              {f.payment_method === 'bank' && <div className="flex justify-between"><dt className="text-slate-500">Bank</dt><dd>{f.bank_name} · {f.bank_account_no}</dd></div>}
            </>}
          </dl>
          {f.notes && <p className="mt-3 rounded bg-slate-50 p-2 text-sm text-slate-600">{f.notes}</p>}
        </section>

        <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200 lg:col-span-2">
          <h2 className="mb-3 font-semibold">Produce delivered</h2>
          {summary.data && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Deliveries" value={String(summary.data.total_deliveries)} />
                <Stat label="Total net weight" value={formatKg(summary.data.total_net_weight)} />
                <Stat label="Last delivery" value={summary.data.last_delivery_at ? fmtDate(summary.data.last_delivery_at) : '—'} />
              </div>
              {summary.data.by_crop.length > 0 && (
                <ul className="mt-4 divide-y divide-slate-100 text-sm">
                  {summary.data.by_crop.map((c) => (
                    <li key={c.crop_code} className="flex justify-between py-2"><span>{c.crop_name}</span>
                      <span className="text-slate-600">{c.deliveries} deliveries · <b>{formatKg(c.net_weight)}</b></span></li>
                  ))}
                </ul>
              )}
            </>
          )}
          <p className="mt-4 rounded-md bg-slate-50 p-3 text-xs text-slate-500">
            Auction results, earnings, deductions, loans and payments appear here once Phases 6–7 are built.
          </p>
        </section>
      </div>

      {can('farmer.view_financial') && <FarmerStatement farmerId={f.id} />}

      <section className="mt-6 print:hidden">
        <h2 className="mb-3 font-semibold">Delivery history</h2>
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-2">Receipt</th><th className="px-4 py-2">Date</th><th className="px-4 py-2">Crop</th><th className="px-4 py-2">Centre</th><th className="px-4 py-2 text-right">Net weight</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {deliveries.data?.items.map((d) => (
                <tr key={d.id} className={d.status === 'voided' ? 'text-slate-400 line-through' : ''}>
                  <td className="px-4 py-2"><Link className="text-brand-700 hover:underline" to={`/deliveries/${d.id}`}>{d.receipt_no}</Link></td>
                  <td className="px-4 py-2">{fmtDateTime(d.captured_at)}</td><td className="px-4 py-2">{d.crop.name}</td>
                  <td className="px-4 py-2">{d.centre.name}</td><td className="px-4 py-2 text-right font-medium">{formatKg(d.net_weight)}</td>
                </tr>
              ))}
              {deliveries.data?.items.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No deliveries yet</td></tr>}
            </tbody>
          </table>
        </div>
        {deliveries.data && <Pagination page={page} pageSize={deliveries.data.page_size} total={deliveries.data.total} onPage={setPage} />}
      </section>

      <Modal open={editing} onClose={() => { setEditing(false); update.reset() }} title="Edit farmer">
        {editing && <FarmerForm editing initial={farmerToValues(f)} submitting={update.isPending} error={update.error?.message}
          onCancel={() => setEditing(false)} onSubmit={(v) => update.mutate(v, { onSuccess: () => setEditing(false) })} />}
      </Modal>
      {statusOpen && <StatusModal farmerId={f.id} current={f.status} onClose={() => setStatusOpen(false)} />}
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-0.5 font-semibold">{value}</p></div>
}

function StatusModal({ farmerId, current, onClose }: { farmerId: string; current: string; onClose: () => void }) {
  const [status, setStatus] = useState(current === 'active' ? 'inactive' : 'active')
  const [reason, setReason] = useState('')
  const save = useApiMutation(() => api(`/farmers/${farmerId}/status`, { method: 'POST', json: { status, reason } }), ['farmers'])
  return (
    <Modal open onClose={onClose} title="Change farmer status">
      <div className="space-y-4">
        {save.error && <Alert>{save.error.message}</Alert>}
        <Field label="New status" htmlFor="fs"><Select id="fs" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="active">Active</option><option value="inactive">Inactive</option><option value="suspended">Suspended</option></Select></Field>
        <Field label="Reason (recorded in the audit trail)" htmlFor="fr"><Input id="fr" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <p className="text-xs text-slate-500">Inactive or suspended farmers cannot deliver produce. Their history is kept.</p>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={reason.trim().length < 3 || status === current} loading={save.isPending}
            onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Save</Button></div>
      </div>
    </Modal>
  )
}
