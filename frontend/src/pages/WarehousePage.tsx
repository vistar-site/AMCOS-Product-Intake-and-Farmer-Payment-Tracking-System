import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PackageCheck, Plus, Truck } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation } from '../features/reference/api'
import { fmtDate, Select, Textarea } from '../components/form'
import { Alert, Badge, Button, EmptyState, Field, Input, Modal, PageHeader, Skeleton } from '../components/ui'
import { STAGE_LABEL, type Batch, type Discrepancy, type Dispatch, type Warehouse } from '../types/warehouse'
import { formatKg, isValidWeight, netWeight } from '../utils/weight'

type Tab = 'dispatches' | 'discrepancies' | 'warehouses'
const today = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Africa/Dar_es_Salaam' })

export default function WarehousePage() {
  const [tab, setTab] = useState<Tab>('dispatches')
  const openDisc = useQuery({ queryKey: ['discrepancies', 'open'], queryFn: () => api<Discrepancy[]>('/discrepancies?status=open') })
  return (
    <>
      <PageHeader title="Warehouse" description="Dispatch batches, record warehouse receipts and reconcile quantities." />
      <div className="mb-5 flex gap-1 border-b border-slate-200" role="tablist">
        {(['dispatches', 'discrepancies', 'warehouses'] as Tab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${tab === t ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
            {t}{t === 'discrepancies' && !!openDisc.data?.length && <span className="ml-1.5 rounded-full bg-red-100 px-1.5 text-xs text-red-700">{openDisc.data.length}</span>}
          </button>
        ))}
      </div>
      {tab === 'dispatches' && <DispatchesTab />}
      {tab === 'discrepancies' && <DiscrepanciesTab />}
      {tab === 'warehouses' && <WarehousesTab />}
    </>
  )
}

function DispatchesTab() {
  const { can } = useAuth()
  const dispatches = useQuery({ queryKey: ['dispatches'], queryFn: () => api<Dispatch[]>('/dispatches') })
  const [creating, setCreating] = useState(false)
  const [receiving, setReceiving] = useState<Dispatch | null>(null)
  return (
    <>
      {can('dispatch.manage') && <div className="mb-4 flex justify-end"><Button onClick={() => setCreating(true)}><Truck className="size-4" />New dispatch</Button></div>}
      {dispatches.isLoading && <Skeleton className="h-32" />}
      {dispatches.data?.length === 0 && <EmptyState title="No dispatches yet" description="Close an aggregation batch, then dispatch it to a warehouse." />}
      <div className="space-y-3">
        {dispatches.data?.map((d) => (
          <div key={d.id} className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-sm font-semibold">{d.dispatch_no}</p>
                <p className="text-sm text-slate-600">{fmtDate(d.dispatch_date)} → {d.warehouse.name}{d.vehicle_reg && ` · ${d.vehicle_reg}`}{d.driver_name && ` · ${d.driver_name}`}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={d.status === 'received' ? 'green' : 'amber'}>{d.status.replace('_', ' ')}</Badge>
                {d.status === 'in_transit' && can('warehouse_receipt.manage') &&
                  <Button variant="secondary" onClick={() => setReceiving(d)}><PackageCheck className="size-4" />Record receipt</Button>}
              </div>
            </div>
            <table className="mt-3 w-full text-sm">
              <thead className="text-left text-xs text-slate-500"><tr><th className="py-1">Batch</th><th className="py-1 text-right">Batch total</th><th className="py-1 text-right">Dispatched</th>
                <th className="py-1 text-right">Received</th><th className="py-1 text-right">Accepted</th></tr></thead>
              <tbody>
                {d.lines.map((l) => {
                  const rl = d.receipt?.lines.find((x) => x.batch_id === l.batch_id)
                  return (
                    <tr key={l.batch_id} className="border-t border-slate-100">
                      <td className="py-1.5 font-mono text-xs"><Link className="text-brand-700 hover:underline" to={`/batches/${l.batch_id}`}>{l.batch.batch_no}</Link></td>
                      <td className="py-1.5 text-right">{l.batch.total_net_weight ? formatKg(l.batch.total_net_weight) : '—'}</td>
                      <td className="py-1.5 text-right">{formatKg(l.dispatched_weight)}</td>
                      <td className="py-1.5 text-right">{rl ? formatKg(rl.received_weight) : '—'}</td>
                      <td className="py-1.5 text-right font-medium">{rl ? formatKg(rl.accepted_weight) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {d.receipt && <p className="mt-2 text-xs text-slate-500">Warehouse receipt {d.receipt.receipt_no} · {fmtDate(d.receipt.receipt_date)}</p>}
          </div>
        ))}
      </div>
      {creating && <CreateDispatchModal onClose={() => setCreating(false)} />}
      {receiving && <ReceiptModal dispatch={receiving} onClose={() => setReceiving(null)} />}
    </>
  )
}

function CreateDispatchModal({ onClose }: { onClose: () => void }) {
  const warehouses = useQuery({ queryKey: ['warehouses'], queryFn: () => api<Warehouse[]>('/warehouses') })
  const closed = useQuery({ queryKey: ['batches', { status: 'closed' }], queryFn: () => api<Batch[]>('/batches?status=closed') })
  const [v, setV] = useState({ warehouse_id: '', dispatch_date: today(), vehicle_reg: '', driver_name: '', notes: '' })
  const [weights, setWeights] = useState<Record<string, string>>({})
  const save = useApiMutation((body: object) => api('/dispatches', { method: 'POST', json: body }), ['dispatches', 'batches', 'discrepancies'])
  const lines = Object.entries(weights).filter(([, w]) => w !== '')
  const valid = v.warehouse_id && lines.length > 0 && lines.every(([, w]) => isValidWeight(w) && Number(w) > 0)
  return (
    <Modal open onClose={onClose} title="Dispatch batches to a warehouse">
      <div className="space-y-4">
        {save.error && <Alert>{save.error.message}</Alert>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Warehouse" htmlFor="d-wh"><Select id="d-wh" value={v.warehouse_id} onChange={(e) => setV({ ...v, warehouse_id: e.target.value })}>
            <option value="">Choose…</option>{warehouses.data?.filter((w) => w.is_active).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</Select></Field>
          <Field label="Dispatch date" htmlFor="d-date"><Input id="d-date" type="date" value={v.dispatch_date} onChange={(e) => setV({ ...v, dispatch_date: e.target.value })} /></Field>
          <Field label="Vehicle reg." htmlFor="d-veh"><Input id="d-veh" value={v.vehicle_reg} onChange={(e) => setV({ ...v, vehicle_reg: e.target.value })} /></Field>
          <Field label="Driver" htmlFor="d-drv"><Input id="d-drv" value={v.driver_name} onChange={(e) => setV({ ...v, driver_name: e.target.value })} /></Field>
        </div>
        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-700">Closed batches — tick and enter the weight measured at loading</p>
          {closed.data?.length === 0 && <p className="text-sm text-slate-500">No closed batches waiting for dispatch.</p>}
          <ul className="divide-y divide-slate-100 rounded-md ring-1 ring-slate-200">
            {closed.data?.map((b) => (
              <li key={b.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                <input type="checkbox" className="size-4 accent-brand-600" checked={b.id in weights} aria-label={`Include ${b.batch_no}`}
                  onChange={(e) => { const n = { ...weights }; if (e.target.checked) n[b.id] = b.total_net_weight ?? ''; else delete n[b.id]; setWeights(n) }} />
                <span className="flex-1"><span className="font-mono text-xs">{b.batch_no}</span><span className="block text-slate-500">{b.crop.name} · {b.centre.name} · {formatKg(b.total_net_weight ?? '0')}</span></span>
                {b.id in weights && <Input aria-label="Dispatched kg" inputMode="decimal" className="w-28" value={weights[b.id]} onChange={(e) => setWeights({ ...weights, [b.id]: e.target.value })} />}
              </li>
            ))}
          </ul>
        </div>
        <Field label="Notes" htmlFor="d-notes"><Textarea id="d-notes" rows={2} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate({
            ...v, vehicle_reg: v.vehicle_reg || null, driver_name: v.driver_name || null, notes: v.notes || null,
            lines: lines.map(([batch_id, w]) => ({ batch_id, dispatched_weight: w })),
          }, { onSuccess: onClose })}>Create dispatch</Button></div>
      </div>
    </Modal>
  )
}

function ReceiptModal({ dispatch, onClose }: { dispatch: Dispatch; onClose: () => void }) {
  const [head, setHead] = useState({ receipt_no: '', receipt_date: today(), notes: '' })
  const [lines, setLines] = useState(() => Object.fromEntries(dispatch.lines.map((l) => [l.batch_id, { received: l.dispatched_weight, rejected: '0', damaged: '0' }])))
  const save = useApiMutation((body: object) => api(`/dispatches/${dispatch.id}/receipt`, { method: 'POST', json: body }), ['dispatches', 'batches', 'discrepancies'])
  const accepted = (l: { received: string; rejected: string; damaged: string }) => {
    const a = netWeight(l.received, l.rejected || '0')
    return a ? netWeight(a, l.damaged || '0') : null
  }
  const valid = head.receipt_no.trim() && Object.values(lines).every((l) => [l.received, l.rejected, l.damaged].every((x) => isValidWeight(x || '0')) && !accepted(l)?.startsWith('-'))
  return (
    <Modal open onClose={onClose} title={`Warehouse receipt for ${dispatch.dispatch_no}`}>
      <div className="space-y-4">
        {save.error && <Alert>{save.error.message}</Alert>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Warehouse receipt no." htmlFor="r-no"><Input id="r-no" value={head.receipt_no} onChange={(e) => setHead({ ...head, receipt_no: e.target.value })} /></Field>
          <Field label="Receipt date" htmlFor="r-date"><Input id="r-date" type="date" value={head.receipt_date} onChange={(e) => setHead({ ...head, receipt_date: e.target.value })} /></Field>
        </div>
        {dispatch.lines.map((l) => {
          const v = lines[l.batch_id]
          const set = (k: 'received' | 'rejected' | 'damaged', x: string) => setLines({ ...lines, [l.batch_id]: { ...v, [k]: x } })
          const acc = accepted(v)
          return (
            <fieldset key={l.batch_id} className="rounded-md border border-slate-200 p-3">
              <legend className="px-1 font-mono text-xs">{l.batch.batch_no} · dispatched {formatKg(l.dispatched_weight)}</legend>
              <div className="grid grid-cols-4 gap-2">
                <Field label="Received" htmlFor={`rc-${l.batch_id}`}><Input id={`rc-${l.batch_id}`} inputMode="decimal" value={v.received} onChange={(e) => set('received', e.target.value)} /></Field>
                <Field label="Rejected" htmlFor={`rj-${l.batch_id}`}><Input id={`rj-${l.batch_id}`} inputMode="decimal" value={v.rejected} onChange={(e) => set('rejected', e.target.value)} /></Field>
                <Field label="Damaged" htmlFor={`dm-${l.batch_id}`}><Input id={`dm-${l.batch_id}`} inputMode="decimal" value={v.damaged} onChange={(e) => set('damaged', e.target.value)} /></Field>
                <Field label="Accepted" htmlFor={`ac-${l.batch_id}`}><p id={`ac-${l.batch_id}`} className={`py-2 font-semibold ${acc?.startsWith('-') ? 'text-red-600' : ''}`}>{acc ? formatKg(acc) : '—'}</p></Field>
              </div>
            </fieldset>
          )
        })}
        <Field label="Notes" htmlFor="r-notes"><Textarea id="r-notes" rows={2} value={head.notes} onChange={(e) => setHead({ ...head, notes: e.target.value })} /></Field>
        <p className="text-xs text-slate-500">Document upload (scanned receipt) is added with file handling in Phase 8.</p>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate({
            receipt_no: head.receipt_no.trim(), receipt_date: head.receipt_date, notes: head.notes || null,
            lines: Object.entries(lines).map(([batch_id, l]) => ({ batch_id, received_weight: l.received, rejected_weight: l.rejected || '0', damaged_weight: l.damaged || '0' })),
          }, { onSuccess: onClose })}>Save receipt</Button></div>
      </div>
    </Modal>
  )
}

function DiscrepanciesTab() {
  const { can } = useAuth()
  const [status, setStatus] = useState('open')
  const list = useQuery({ queryKey: ['discrepancies', status], queryFn: () => api<Discrepancy[]>(`/discrepancies${status ? `?status=${status}` : ''}`) })
  const [resolving, setResolving] = useState<Discrepancy | null>(null)
  return (
    <>
      <div className="mb-4 w-48"><Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="open">Open</option><option value="explained">Explained</option><option value="accepted">Auto-accepted</option><option value="">All</option></Select></div>
      {list.data?.length === 0 && <EmptyState title="No discrepancies in this view" />}
      {!!list.data?.length && (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-2">Batch</th><th className="px-4 py-2">Stage</th><th className="px-4 py-2 text-right">Expected</th><th className="px-4 py-2 text-right">Actual</th>
                <th className="px-4 py-2 text-right">Difference</th><th className="px-4 py-2">Status</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.data.map((d) => (
                <tr key={d.id}>
                  <td className="px-4 py-2 font-mono text-xs"><Link className="text-brand-700 hover:underline" to={`/batches/${d.batch.id}`}>{d.batch.batch_no}</Link></td>
                  <td className="px-4 py-2">{STAGE_LABEL[d.stage]}</td>
                  <td className="px-4 py-2 text-right">{formatKg(d.expected_weight)}</td><td className="px-4 py-2 text-right">{formatKg(d.actual_weight)}</td>
                  <td className={`px-4 py-2 text-right font-medium ${Number(d.difference) < 0 ? 'text-red-600' : 'text-blue-700'}`}>
                    {formatKg(d.difference)} ({((Number(d.difference) / Number(d.expected_weight)) * 100).toFixed(2)}%)</td>
                  <td className="px-4 py-2"><Badge tone={d.status === 'open' ? 'red' : 'green'}>{d.status}</Badge>
                    {d.explanation && <p className="mt-1 max-w-xs text-xs text-slate-500">{d.explanation}</p>}</td>
                  <td className="px-4 py-2 text-right">{d.status === 'open' && can('reconciliation.approve') && <Button variant="secondary" onClick={() => setResolving(d)}>Explain</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {resolving && <ResolveModal d={resolving} onClose={() => setResolving(null)} />}
    </>
  )
}

function ResolveModal({ d, onClose }: { d: Discrepancy; onClose: () => void }) {
  const [text, setText] = useState('')
  const save = useApiMutation(() => api(`/discrepancies/${d.id}/resolve`, { method: 'POST', json: { explanation: text } }), ['discrepancies', 'batches'])
  return (
    <Modal open onClose={onClose} title={`Explain ${STAGE_LABEL[d.stage].toLowerCase()} difference`}>
      <div className="space-y-4">
        {save.error && <Alert>{save.error.message}</Alert>}
        <p className="text-sm text-slate-600">Batch {d.batch.batch_no}: {formatKg(d.difference)}. Your explanation is recorded in the audit trail.
          Farmer delivery records are not changed; how the loss affects payments is decided by the payout policy.</p>
        <Field label="Explanation (min. 10 characters)" htmlFor="x"><Textarea id="x" value={text} onChange={(e) => setText(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={text.trim().length < 10} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Save explanation</Button></div>
      </div>
    </Modal>
  )
}

function WarehousesTab() {
  const { can } = useAuth()
  const list = useQuery({ queryKey: ['warehouses'], queryFn: () => api<Warehouse[]>('/warehouses') })
  const [open, setOpen] = useState(false)
  const [v, setV] = useState({ code: '', name: '', operator_name: '', licence_no: '', location: '' })
  const save = useApiMutation(() => api('/warehouses', { method: 'POST', json: Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x || null])) }), ['warehouses'])
  return (
    <>
      {can('warehouse.manage') && <div className="mb-4 flex justify-end"><Button onClick={() => setOpen(true)}><Plus className="size-4" />Register warehouse</Button></div>}
      <div className="grid gap-3 md:grid-cols-2">
        {list.data?.map((w) => (
          <div key={w.id} className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
            <p className="text-xs text-slate-500">{w.code}</p><p className="font-semibold">{w.name}</p>
            <p className="mt-1 text-sm text-slate-600">{[w.operator_name, w.location, w.licence_no && `Licence ${w.licence_no}`].filter(Boolean).join(' · ') || '—'}</p>
          </div>
        ))}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Register warehouse">
        <div className="space-y-3">
          {save.error && <Alert>{save.error.message}</Alert>}
          {([['code', 'Code'], ['name', 'Name'], ['operator_name', 'Operator'], ['licence_no', 'Licence no.'], ['location', 'Location']] as const).map(([k, label]) => (
            <Field key={k} label={label} htmlFor={`w-${k}`}><Input id={`w-${k}`} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></Field>
          ))}
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button disabled={!v.code || v.name.length < 2} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: () => setOpen(false) })}>Save</Button></div>
        </div>
      </Modal>
    </>
  )
}
