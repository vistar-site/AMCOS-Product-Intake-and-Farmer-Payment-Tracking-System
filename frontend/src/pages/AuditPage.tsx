import { Fragment, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Lock } from 'lucide-react'
import { api } from '../api/client'
import { useDebounce } from '../hooks/useDebounce'
import { fmtDateTime, Pagination, Select } from '../components/form'
import { Alert, Input, PageHeader, Skeleton } from '../components/ui'

interface Entry { id: number; created_at: string; user_name: string | null; action: string; entity_type: string | null; entity_id: string | null
  before: Record<string, unknown> | null; after: Record<string, unknown> | null; reason: string | null; ip_address: string | null }

export default function AuditPage() {
  const actions = useQuery({ queryKey: ['audit-actions'], queryFn: () => api<string[]>('/audit-logs/actions') })
  const [f, setF] = useState({ action: '', from: '', to: '', q: '', entity_id: '' })
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState<number | null>(null)
  const q = useDebounce(f.q); const entity = useDebounce(f.entity_id)
  const params = new URLSearchParams({ page: String(page), page_size: '50' })
  if (f.action) params.set('action', f.action)
  if (f.from) params.set('date_from', new Date(`${f.from}T00:00:00+03:00`).toISOString())
  if (f.to) { const d = new Date(`${f.to}T00:00:00+03:00`); d.setUTCDate(d.getUTCDate() + 1); params.set('date_to', d.toISOString()) }
  if (q) params.set('q', q)
  if (entity) params.set('entity_id', entity)
  const list = useQuery({ queryKey: ['audit', params.toString()], placeholderData: (p) => p,
    queryFn: () => api<{ total: number; page: number; page_size: number; items: Entry[] }>(`/audit-logs?${params}`) })
  const upd = (p: Partial<typeof f>) => { setF({ ...f, ...p }); setPage(1) }

  return (
    <>
      <PageHeader title="Audit trail" description="Every important operation: who did what, when, and the values before and after." />
      <p className="mb-4 flex items-center gap-1.5 text-xs text-slate-500"><Lock className="size-3.5" />Audit records are append-only: the database rejects any attempt to edit or delete them.</p>
      <div className="mb-4 grid gap-2 sm:grid-cols-5">
        <Select aria-label="Action" value={f.action} onChange={(e) => upd({ action: e.target.value })}>
          <option value="">All actions</option>{actions.data?.map((a) => <option key={a} value={a}>{a}</option>)}</Select>
        <Input type="date" aria-label="From" value={f.from} onChange={(e) => upd({ from: e.target.value })} />
        <Input type="date" aria-label="To" value={f.to} onChange={(e) => upd({ to: e.target.value })} />
        <Input placeholder="Search user, reason" aria-label="Search" value={f.q} onChange={(e) => upd({ q: e.target.value })} />
        <Input placeholder="Record ID" aria-label="Record ID" value={f.entity_id} onChange={(e) => upd({ entity_id: e.target.value })} />
      </div>
      {list.error && <Alert>{(list.error as Error).message}</Alert>}
      {list.isLoading && <Skeleton className="h-60" />}
      {list.data && (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="w-8" /><th className="px-3 py-2">When</th><th className="px-3 py-2">User</th><th className="px-3 py-2">Action</th><th className="px-3 py-2">Record</th><th className="px-3 py-2">Reason</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.data.items.map((e) => (
                <Fragment key={e.id}>
                  <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === e.id ? null : e.id)}>
                    <td className="pl-3 text-slate-400">{(e.before || e.after) && (open === e.id ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{fmtDateTime(e.created_at)}</td>
                    <td className="px-3 py-2">{e.user_name ?? <span className="text-slate-400">system / anonymous</span>}</td>
                    <td className="px-3 py-2 font-mono text-xs">{e.action}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{e.entity_type}{e.entity_id && <span className="block font-mono">{e.entity_id}</span>}</td>
                    <td className="max-w-xs px-3 py-2 text-slate-600">{e.reason}</td>
                  </tr>
                  {open === e.id && (e.before || e.after) && (
                    <tr className="bg-slate-50"><td /><td colSpan={5} className="px-3 py-3"><div className="grid gap-3 md:grid-cols-2">
                      {e.before && <Json label="Before" value={e.before} />}{e.after && <Json label="After" value={e.after} />}
                    </div>{e.ip_address && <p className="mt-2 text-xs text-slate-400">IP {e.ip_address}</p>}</td></tr>
                  )}
                </Fragment>
              ))}
              {list.data.items.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-500">No audit records match.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {list.data && <Pagination page={page} pageSize={list.data.page_size} total={list.data.total} onPage={setPage} />}
    </>
  )
}

function Json({ label, value }: { label: string; value: Record<string, unknown> }) {
  return <div><p className="mb-1 text-xs font-medium text-slate-500">{label}</p>
    <pre className="max-h-64 overflow-auto rounded bg-white p-2 text-xs ring-1 ring-slate-200">{JSON.stringify(value, null, 2)}</pre></div>
}
