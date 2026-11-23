import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileDown, FileSpreadsheet, FileText, Printer } from 'lucide-react'
import { api, downloadFile } from '../api/client'
import { useCentres, useCrops, useSeasons } from '../features/reference/api'
import { fmtDateTime, Select } from '../components/form'
import { Alert, Button, EmptyState, Input, PageHeader, Skeleton } from '../components/ui'

interface ReportDef { code: string; title: string; category: 'operational' | 'financial'; filters: string[] }
interface Col { key: string; label: string; kind: string }
interface Result { code: string; title: string; filters_text: string; generated_at: string; columns: Col[]; rows: Record<string, unknown>[]; row_count: number; truncated: boolean; totals: Record<string, unknown> }

const RIGHT = new Set(['kg', 'money', 'price', 'int'])
function fmt(v: unknown, kind: string): string {
  if (v === null || v === undefined || v === '') return ''
  if (kind === 'money') return Number(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (kind === 'kg') return Number(v).toLocaleString('en-GB', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
  if (kind === 'price') return Number(v).toLocaleString('en-GB', { maximumFractionDigits: 4 })
  if (kind === 'int') return Number(v).toLocaleString('en-GB')
  if (kind === 'datetime') return fmtDateTime(String(v))
  return String(v)
}

export default function ReportsPage() {
  const cat = useQuery({ queryKey: ['reports'], queryFn: () => api<ReportDef[]>('/reports') })
  const crops = useCrops(); const centres = useCentres(); const seasons = useSeasons()
  const [code, setCode] = useState('')
  const [f, setF] = useState({ date_from: '', date_to: '', crop_id: '', centre_id: '', season_id: '' })
  const def = cat.data?.find((r) => r.code === code)
  const params = new URLSearchParams()
  if (def) Object.entries(f).forEach(([k, v]) => {
    const group = k.startsWith('date') ? 'date' : k.replace('_id', '')
    if (v && def.filters.includes(group)) params.set(k, v)
  })
  const result = useQuery({ queryKey: ['report', code, params.toString()], enabled: !!code, queryFn: () => api<Result>(`/reports/${code}?${params}`) })
  const [dlError, setDlError] = useState<string | null>(null)
  const dl = (format: string) => { setDlError(null); downloadFile(`/reports/${code}/export?format=${format}&${params}`).catch((e) => setDlError(e.message)) }
  const r = result.data

  return (
    <>
      <PageHeader title="Reports" description="Operational and financial reports generated from current records." />
      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <nav aria-label="Reports" className="space-y-4 print:hidden">
          {cat.isLoading && <Skeleton className="h-60" />}
          {(['operational', 'financial'] as const).map((group) => {
            const items = cat.data?.filter((x) => x.category === group) ?? []
            return items.length > 0 && (
              <div key={group}>
                <p className="mb-1 text-xs font-medium uppercase tracking-wider text-slate-500">{group}</p>
                <ul className="space-y-0.5">{items.map((x) => (
                  <li key={x.code}><button onClick={() => setCode(x.code)} className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${code === x.code ? 'bg-brand-50 font-medium text-brand-700' : 'hover:bg-slate-100'}`}>{x.title}</button></li>
                ))}</ul>
              </div>
            )
          })}
        </nav>

        <div className="min-w-0">
          {!def && <EmptyState title="Choose a report" description="Pick a report on the left, adjust filters, then preview or export it." />}
          {def && <>
            <div className="mb-4 flex flex-wrap items-end gap-2 print:hidden">
              {def.filters.includes('date') && <>
                <Input type="date" className="w-40" aria-label="From date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} />
                <Input type="date" className="w-40" aria-label="To date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} /></>}
              {def.filters.includes('crop') && <Select className="w-40" aria-label="Crop" value={f.crop_id} onChange={(e) => setF({ ...f, crop_id: e.target.value })}>
                <option value="">All crops</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}
              {def.filters.includes('centre') && <Select className="w-48" aria-label="Centre" value={f.centre_id} onChange={(e) => setF({ ...f, centre_id: e.target.value })}>
                <option value="">All centres</option>{centres.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}
              {def.filters.includes('season') && <Select className="w-36" aria-label="Season" value={f.season_id} onChange={(e) => setF({ ...f, season_id: e.target.value })}>
                <option value="">All seasons</option>{seasons.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>}
              <div className="ml-auto flex gap-2">
                <Button variant="secondary" onClick={() => dl('pdf')}><FileDown className="size-4" />PDF</Button>
                <Button variant="secondary" onClick={() => dl('xlsx')}><FileSpreadsheet className="size-4" />Excel</Button>
                <Button variant="secondary" onClick={() => dl('csv')}><FileText className="size-4" />CSV</Button>
                <Button variant="ghost" onClick={() => window.print()}><Printer className="size-4" /></Button>
              </div>
            </div>
            {(result.error || dlError) && <Alert>{(result.error as Error)?.message ?? dlError}</Alert>}
            {result.isLoading && <Skeleton className="h-48" />}
            {r && <>
              <h2 className="text-lg font-semibold">{r.title}</h2>
              <p className="mb-3 text-xs text-slate-500">{r.filters_text} · {r.row_count.toLocaleString()} rows · generated {fmtDateTime(r.generated_at)}</p>
              {r.truncated && <div className="mb-2"><Alert tone="amber">Showing the first 1,000 rows. Exports contain all {r.row_count.toLocaleString()} rows.</Alert></div>}
              <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>{r.columns.map((c) => <th key={c.key} className={`whitespace-nowrap px-3 py-2 ${RIGHT.has(c.kind) ? 'text-right' : 'text-left'}`}>{c.label}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {r.rows.map((row, i) => <tr key={i}>{r.columns.map((c) => <td key={c.key} className={`whitespace-nowrap px-3 py-1.5 ${RIGHT.has(c.kind) ? 'text-right tabular-nums' : ''}`}>{fmt(row[c.key], c.kind)}</td>)}</tr>)}
                    {r.rows.length === 0 && <tr><td colSpan={r.columns.length} className="px-3 py-6 text-center text-slate-500">No records match these filters.</td></tr>}
                  </tbody>
                  <tfoot className="border-t-2 border-slate-300 bg-slate-50 font-semibold">
                    <tr>{r.columns.map((c, i) => <td key={c.key} className={`whitespace-nowrap px-3 py-2 ${RIGHT.has(c.kind) ? 'text-right tabular-nums' : ''}`}>{i === 0 ? 'Total' : fmt(r.totals[c.key], c.kind)}</td>)}</tr>
                  </tfoot>
                </table>
              </div>
            </>}
          </>}
        </div>
      </div>
    </>
  )
}
