import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useDeliveries, usePendingAmendments } from '../features/deliveries/api'
import { useCentres, useCrops, useSeasons } from '../features/reference/api'
import { useDebounce } from '../hooks/useDebounce'
import { fmtDateTime, Pagination, Select } from '../components/form'
import { Alert, Badge, Button, EmptyState, Input, PageHeader, Skeleton } from '../components/ui'
import { formatKg } from '../utils/weight'

/** Convert a yyyy-mm-dd date in Tanzania time to an ISO instant (start of that day, EAT = UTC+3). */
const eatDay = (d: string, addDays = 0) => {
  if (!d) return undefined
  const dt = new Date(`${d}T00:00:00+03:00`)
  dt.setUTCDate(dt.getUTCDate() + addDays)
  return dt.toISOString()
}

export default function DeliveriesPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const centres = useCentres()
  const crops = useCrops()
  const seasons = useSeasons()
  const pending = usePendingAmendments(can('delivery.amend_approve'))
  const [search, setSearch] = useState('')
  const [f, setF] = useState({ centre_id: '', crop_id: '', season_id: '', status: '', from: '', to: '', mine: false })
  const [page, setPage] = useState(1)
  const q = useDebounce(search)
  const { data, isLoading, error } = useDeliveries({
    q, centre_id: f.centre_id, crop_id: f.crop_id, season_id: f.season_id, status: f.status, mine: f.mine,
    date_from: eatDay(f.from), date_to: eatDay(f.to, 1), page,
  })
  const upd = (patch: Partial<typeof f>) => { setF({ ...f, ...patch }); setPage(1) }

  return (
    <>
      <PageHeader title="Deliveries" description="All produce received at collection centres."
        actions={can('delivery.create') && <Link to="/deliveries/new"><Button><Plus className="size-4" />Record delivery</Button></Link>} />

      {pending.data && pending.data.length > 0 && (
        <div className="mb-4"><Alert tone="amber">
          {pending.data.length} correction request{pending.data.length > 1 ? 's' : ''} awaiting approval:{' '}
          {pending.data.slice(0, 5).map((a) => <Link key={a.id} className="mr-2 font-medium underline" to={`/deliveries/${a.delivery.id}`}>{a.delivery.receipt_no}</Link>)}
        </Alert></div>
      )}

      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
          <Input className="pl-9" placeholder="Receipt, farmer or member no." aria-label="Search deliveries" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        </div>
        <Select aria-label="Centre" value={f.centre_id} onChange={(e) => upd({ centre_id: e.target.value })}>
          <option value="">All centres</option>{centres.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        <Select aria-label="Crop" value={f.crop_id} onChange={(e) => upd({ crop_id: e.target.value })}>
          <option value="">All crops</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        <Select aria-label="Season" value={f.season_id} onChange={(e) => upd({ season_id: e.target.value })}>
          <option value="">All seasons</option>{seasons.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
        <Input type="date" aria-label="From date" value={f.from} onChange={(e) => upd({ from: e.target.value })} />
        <Input type="date" aria-label="To date" value={f.to} onChange={(e) => upd({ to: e.target.value })} />
        <Select aria-label="Status" value={f.status} onChange={(e) => upd({ status: e.target.value })}>
          <option value="">Any status</option><option value="recorded">Recorded</option><option value="voided">Voided</option></Select>
        <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" className="size-4 accent-brand-600" checked={f.mine} onChange={(e) => upd({ mine: e.target.checked })} />Only recorded by me</label>
      </div>

      {data && (
        <div className="mb-3 flex gap-6 text-sm text-slate-600">
          <span><b className="text-slate-900">{data.total.toLocaleString()}</b> deliveries</span>
          <span><b className="text-slate-900">{formatKg(data.total_net_weight)}</b> net (excluding voided)</span>
        </div>
      )}
      {error && <Alert>{(error as Error).message}</Alert>}
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Receipt</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Farmer</th><th className="px-4 py-3">Crop</th>
              <th className="px-4 py-3">Centre</th><th className="px-4 py-3 text-right">Net</th><th className="px-4 py-3">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && [1, 2, 3, 4, 5].map((i) => <tr key={i}><td colSpan={7} className="px-4 py-3"><Skeleton className="h-5" /></td></tr>)}
            {data?.items.map((d) => (
              <tr key={d.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/deliveries/${d.id}`)}>
                <td className="px-4 py-3 font-mono text-xs">{d.receipt_no}{d.source === 'offline_sync' && <span className="ml-1 text-slate-400" title="Captured offline">⇅</span>}</td>
                <td className="whitespace-nowrap px-4 py-3">{fmtDateTime(d.captured_at)}</td>
                <td className="px-4 py-3">{d.farmer.full_name}<p className="text-xs text-slate-500">{d.farmer.membership_no}</p></td>
                <td className="px-4 py-3">{d.crop.name}{d.grade && <span className="text-slate-500"> · {d.grade.code}</span>}</td>
                <td className="px-4 py-3">{d.centre.name}</td>
                <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{formatKg(d.net_weight)}</td>
                <td className="px-4 py-3"><Badge tone={d.status === 'voided' ? 'red' : 'green'}>{d.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.items.length === 0 && <div className="p-4"><EmptyState title="No deliveries match these filters" /></div>}
      </div>
      {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
    </>
  )
}
