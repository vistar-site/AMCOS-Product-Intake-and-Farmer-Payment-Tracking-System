import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useCentres, useCrops, useSeasons } from '../features/reference/api'
import { fmtDateTime, Select } from '../components/form'
import { Alert, Badge, Button, EmptyState, Field, Modal, PageHeader, Skeleton } from '../components/ui'
import { BATCH_TONE, type Batch } from '../types/warehouse'
import { formatKg } from '../utils/weight'
import { sumKg } from '../utils/money'

export default function BatchesPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const crops = useCrops()
  const centres = useCentres()
  const [f, setF] = useState({ status: '', crop_id: '', centre_id: '' })
  const [creating, setCreating] = useState(false)
  const params = new URLSearchParams(Object.entries(f).filter(([, v]) => v))
  const batches = useQuery({ queryKey: ['batches', f], queryFn: () => api<Batch[]>(`/batches?${params}`) })

  return (
    <>
      <PageHeader title="Aggregation batches" description="Group farmer deliveries of one crop, season and centre before dispatch to the warehouse."
        actions={can('batch.manage') && <Button onClick={() => setCreating(true)}><Plus className="size-4" />New batch</Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        <Select aria-label="Status" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
          <option value="">Any status</option>{['open', 'closed', 'dispatched', 'received', 'partially_sold', 'sold'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
        </Select>
        <Select aria-label="Crop" value={f.crop_id} onChange={(e) => setF({ ...f, crop_id: e.target.value })}>
          <option value="">All crops</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select aria-label="Centre" value={f.centre_id} onChange={(e) => setF({ ...f, centre_id: e.target.value })}>
          <option value="">All centres</option>{centres.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </div>
      {batches.error && <Alert>{(batches.error as Error).message}</Alert>}
      {batches.isLoading && <Skeleton className="h-40" />}
      {batches.data?.length === 0 && <EmptyState title="No batches" description="Create a batch and add the deliveries collected at a centre." />}
      {!!batches.data?.length && (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Batch</th><th className="px-4 py-3">Crop / season</th><th className="px-4 py-3">Centre</th>
                <th className="px-4 py-3 text-right">Deliveries</th><th className="px-4 py-3 text-right">Net weight</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Created</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {batches.data.map((b) => (
                <tr key={b.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/batches/${b.id}`)}>
                  <td className="px-4 py-3 font-mono text-xs"><Link to={`/batches/${b.id}`} className="text-brand-700 hover:underline">{b.batch_no}</Link></td>
                  <td className="px-4 py-3">{b.crop.name} · {b.season.name}</td><td className="px-4 py-3">{b.centre.name}</td>
                  <td className="px-4 py-3 text-right">{b.members.length}</td>
                  <td className="px-4 py-3 text-right font-medium">{formatKg(b.total_net_weight ?? sumKg(b.members.map((m) => m.net_weight)))}</td>
                  <td className="px-4 py-3"><Badge tone={BATCH_TONE[b.status]}>{b.status.replace('_', ' ')}</Badge></td>
                  <td className="whitespace-nowrap px-4 py-3">{fmtDateTime(b.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <CreateBatchModal onClose={() => setCreating(false)} onCreated={(id) => navigate(`/batches/${id}`)} />}
    </>
  )
}

function CreateBatchModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const crops = useCrops()
  const seasons = useSeasons()
  const centres = useCentres()
  const [v, setV] = useState({ crop_id: '', season_id: seasons.data?.find((s) => s.is_active)?.id ?? '', centre_id: '' })
  const create = useApiMutation((body: typeof v) => api<Batch>('/batches', { method: 'POST', json: body }), ['batches'])
  const ok = v.crop_id && v.season_id && v.centre_id
  return (
    <Modal open onClose={onClose} title="New aggregation batch">
      <div className="space-y-4">
        {create.error && <Alert>{create.error.message}</Alert>}
        <Field label="Crop" htmlFor="b-crop"><Select id="b-crop" value={v.crop_id} onChange={(e) => setV({ ...v, crop_id: e.target.value })}>
          <option value="">Choose…</option>{crops.data?.filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
        <Field label="Season" htmlFor="b-season"><Select id="b-season" value={v.season_id} onChange={(e) => setV({ ...v, season_id: e.target.value })}>
          <option value="">Choose…</option>{seasons.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        <Field label="Collection centre" htmlFor="b-centre"><Select id="b-centre" value={v.centre_id} onChange={(e) => setV({ ...v, centre_id: e.target.value })}>
          <option value="">Choose…</option>{centres.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!ok} loading={create.isPending} onClick={() => create.mutate(v, { onSuccess: (b) => onCreated(b.id) })}>Create batch</Button></div>
      </div>
    </Modal>
  )
}
