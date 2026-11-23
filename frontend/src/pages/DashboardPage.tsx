import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ClipboardList, Package, Scale, Users, Warehouse, Wallet } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCentres, useCrops } from '../features/reference/api'
import { Bars, ChartCard, NumbersTable, Progress, SERIES, TimeLine } from '../features/dashboard/charts'
import { fmtDateTime, Select } from '../components/form'
import { Alert, Input, PageHeader, Skeleton } from '../components/ui'
import { formatTZS } from '../utils/money'
import { formatKg } from '../utils/weight'

interface Dash {
  farmers_total: number; farmers_active: number; centres_active: number; deliveries: number; collected_kg: string
  awaiting_dispatch_kg: string; at_warehouse_kg: string
  daily: { date: string; deliveries: number; kg: string }[]
  monthly: { month: string; deliveries: number; farmers: number; kg: string }[]
  by_crop: { name: string; kg: string; deliveries: number }[]
  by_centre: { name: string; kg: string; deliveries: number; farmers: number }[]
  recent_deliveries: { id: string; receipt_no: string; captured_at: string; net_weight: string; farmer: string; crop: string; centre: string }[]
  tasks: { label: string; count: number; link: string }[]
  finance: null | {
    sold_kg: string; auction_value: string; avg_price: string | null; payouts_calculated: string; payments_completed: string
    payments_in_process: string; outstanding: string; deductions: string
    auctions: { ref: string; date: string; kg: string; value: string; avg_price: string | null }[]
    deduction_breakdown: { type: string; name: string; amount: string }[]
  }
}

const eat = (d: string, add = 0) => { if (!d) return ''; const x = new Date(`${d}T00:00:00+03:00`); x.setUTCDate(x.getUTCDate() + add); return x.toISOString() }

export default function DashboardPage() {
  const { user } = useAuth()
  const crops = useCrops()
  const centres = useCentres()
  const [f, setF] = useState({ from: '', to: '', crop_id: '', centre_id: '' })
  const params = new URLSearchParams()
  if (f.from) params.set('date_from', eat(f.from))
  if (f.to) params.set('date_to', eat(f.to, 1))
  if (f.crop_id) params.set('crop_id', f.crop_id)
  if (f.centre_id) params.set('centre_id', f.centre_id)
  const q = useQuery({ queryKey: ['dashboard', f], queryFn: () => api<Dash>(`/dashboard?${params}`), placeholderData: (p) => p })
  const d = q.data
  const n = (s: string) => Number(s)

  return (
    <>
      <PageHeader title={`Karibu, ${user?.full_name.split(' ')[0]}`} description="Cooperative activity from recorded deliveries, warehouse, auction and payment data." />
      <div className="mb-5 grid gap-2 sm:grid-cols-4" role="group" aria-label="Dashboard filters">
        <Input type="date" aria-label="From" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} />
        <Input type="date" aria-label="To" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} />
        <Select aria-label="Crop" value={f.crop_id} onChange={(e) => setF({ ...f, crop_id: e.target.value })}>
          <option value="">All crops</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        <Select aria-label="Centre" value={f.centre_id} onChange={(e) => setF({ ...f, centre_id: e.target.value })}>
          <option value="">All centres</option>{centres.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
      </div>
      {q.error && <Alert>{(q.error as Error).message}</Alert>}
      {!d && <div className="grid gap-4 sm:grid-cols-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}</div>}
      {d && <>
        {d.tasks.length > 0 && (
          <section className="mb-5 rounded-lg bg-amber-50 p-4 ring-1 ring-amber-200">
            <h2 className="mb-2 text-sm font-semibold text-amber-900">Needs your attention</h2>
            <ul className="flex flex-wrap gap-2">{d.tasks.map((t) => (
              <li key={t.label}><Link to={t.link} className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm ring-1 ring-amber-200 hover:bg-amber-100">
                <b>{t.count}</b> {t.label}<ArrowRight className="size-3.5" /></Link></li>))}</ul>
          </section>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi icon={Users} label="Farmers" value={d.farmers_active.toLocaleString()} sub={`${d.farmers_total.toLocaleString()} registered`} />
          <Kpi icon={ClipboardList} label="Deliveries" value={d.deliveries.toLocaleString()} sub={`${d.centres_active} active centres`} />
          <Kpi icon={Scale} label="Produce collected" value={formatKg(d.collected_kg)} />
          <Kpi icon={Package} label="Awaiting dispatch" value={formatKg(d.awaiting_dispatch_kg)} sub={`${formatKg(d.at_warehouse_kg)} sent to warehouse`} />
        </div>
        {d.finance && (
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi icon={Warehouse} label="Sold at auction" value={formatKg(d.finance.sold_kg)} sub={d.finance.avg_price ? `avg ${Number(d.finance.avg_price).toLocaleString()} TZS/kg` : undefined} />
            <Kpi icon={Wallet} label="Auction value" value={formatTZS(d.finance.auction_value)} />
            <Kpi icon={Wallet} label="Net payouts approved" value={formatTZS(d.finance.payouts_calculated)} sub={`deductions ${formatTZS(d.finance.deductions)}`} />
            <Kpi icon={Wallet} label="Outstanding to farmers" value={formatTZS(d.finance.outstanding)} sub={`${formatTZS(d.finance.payments_completed)} paid`} />
          </div>
        )}

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <ChartCard title="Produce collected per day" subtitle="Net kg, Tanzania time"
            table={<NumbersTable rows={d.daily} cols={[['date', 'Date'], ['deliveries', 'Deliveries'], ['kg', 'Net kg']]} />}>
            {d.daily.length ? <TimeLine data={d.daily.map((x) => ({ ...x, kg: n(x.kg) }))} x="date" y="kg" unit="kg" /> : <Empty />}
          </ChartCard>
          <ChartCard title="Produce by crop" subtitle="Net kg" table={<NumbersTable rows={d.by_crop} cols={[['name', 'Crop'], ['deliveries', 'Deliveries'], ['kg', 'Net kg']]} />}>
            {d.by_crop.length ? <Bars data={d.by_crop.map((x) => ({ ...x, kg: n(x.kg) }))} x="name" y="kg" unit="kg" colorBy={crops.data?.map((c) => c.name) ?? []} /> : <Empty />}
          </ChartCard>
          <ChartCard title="Top collection centres" subtitle="Net kg collected"
            table={<NumbersTable rows={d.by_centre} cols={[['name', 'Centre'], ['farmers', 'Farmers'], ['deliveries', 'Deliveries'], ['kg', 'Net kg']]} />}>
            {d.by_centre.length ? <Bars horizontal data={d.by_centre.slice(0, 8).map((x) => ({ ...x, kg: n(x.kg) }))} x="name" y="kg" unit="kg" /> : <Empty />}
          </ChartCard>
          <ChartCard title="Monthly delivery trend" subtitle="Deliveries per month"
            table={<NumbersTable rows={d.monthly} cols={[['month', 'Month'], ['farmers', 'Farmers'], ['deliveries', 'Deliveries'], ['kg', 'Net kg']]} />}>
            {d.monthly.length ? <Bars data={d.monthly} x="month" y="deliveries" unit="deliveries" /> : <Empty />}
          </ChartCard>
          {d.finance && <>
            <ChartCard title="Auction prices" subtitle="Average TZS per kg by auction"
              table={<NumbersTable rows={d.finance.auctions} cols={[['ref', 'Auction'], ['date', 'Date'], ['kg', 'Sold kg'], ['value', 'Value'], ['avg_price', 'Avg/kg']]} />}>
              {d.finance.auctions.length ? <Bars data={d.finance.auctions.map((x) => ({ ...x, avg: n(x.avg_price ?? '0') }))} x="ref" y="avg" unit="TZS/kg" /> : <Empty />}
            </ChartCard>
            <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
              <h3 className="font-semibold">Payment progress</h3>
              <p className="mb-4 text-xs text-slate-500">Share of approved net payouts</p>
              <Progress parts={[
                { label: 'Paid', value: n(d.finance.payments_completed), color: SERIES[5] },
                { label: 'In process', value: n(d.finance.payments_in_process), color: SERIES[0] },
                { label: 'Not yet in a batch', value: Math.max(0, n(d.finance.outstanding) - n(d.finance.payments_in_process)), color: '#cbd5e1' },
              ]} />
              <h3 className="mt-6 font-semibold">Deductions</h3>
              <ul className="mt-2 space-y-1.5 text-sm">
                {d.finance.deduction_breakdown.map((x) => (
                  <li key={x.name} className="flex justify-between"><span>{x.name} <span className="text-xs text-slate-400">{x.type}</span></span><b>{formatTZS(x.amount)}</b></li>
                ))}
                {d.finance.deduction_breakdown.length === 0 && <li className="text-slate-500">No approved payouts yet.</li>}
              </ul>
            </section>
          </>}
        </div>

        <section className="mt-6 rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <div className="mb-3 flex items-center justify-between"><h3 className="font-semibold">Recent deliveries</h3><Link to="/deliveries" className="text-sm text-brand-700 hover:underline">All deliveries</Link></div>
          <table className="w-full text-sm"><tbody className="divide-y divide-slate-100">
            {d.recent_deliveries.map((r) => (
              <tr key={r.id}><td className="py-1.5 font-mono text-xs"><Link className="text-brand-700 hover:underline" to={`/deliveries/${r.id}`}>{r.receipt_no}</Link></td>
                <td className="py-1.5">{r.farmer}</td><td className="py-1.5 text-slate-500">{r.crop} · {r.centre}</td>
                <td className="py-1.5 text-slate-500">{fmtDateTime(r.captured_at)}</td><td className="py-1.5 text-right font-medium">{formatKg(r.net_weight)}</td></tr>
            ))}
            {d.recent_deliveries.length === 0 && <tr><td className="py-4 text-center text-slate-500">No deliveries in this period.</td></tr>}
          </tbody></table>
        </section>
      </>}
    </>
  )
}

function Kpi({ icon: Icon, label, value, sub }: { icon: typeof Users; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
      <p className="flex items-center gap-1.5 text-sm text-slate-500"><Icon className="size-4" />{label}</p>
      <p className="mt-1 text-xl font-semibold tracking-tight">{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

const Empty = () => <div className="grid h-full place-items-center text-sm text-slate-400">No data for these filters</div>
