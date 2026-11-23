import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, RotateCcw, Send } from 'lucide-react'
import { api } from '../api/client'
import { useApiMutation } from '../features/reference/api'
import { fmtDateTime, Pagination, Select, Textarea } from '../components/form'
import { Alert, Badge, Button, PageHeader, Skeleton } from '../components/ui'

interface Msg { id: string; created_at: string; phone: string; template_code: string | null; body: string; status: string; provider: string | null
  attempts: number; last_error: string | null; sent_at: string | null; next_attempt_at: string | null }
interface Tpl { code: string; language: string; body: string; is_default: boolean; placeholders: string[] }
const TONE: Record<string, 'green' | 'amber' | 'red' | 'blue' | 'slate'> = { queued: 'amber', sent: 'blue', delivered: 'green', simulated: 'slate', failed: 'red', cancelled: 'slate' }

export default function NotificationsPage() {
  const [tab, setTab] = useState<'messages' | 'templates'>('messages')
  return (
    <>
      <PageHeader title="SMS & notifications" description="Farmer SMS history, the retry queue and message templates." />
      <div className="mb-4"><Alert tone="amber">The SMS gateway is in <b>mock mode</b>: messages are recorded as “simulated” and are <b>not</b> sent to phones.
        A real provider is connected by adding an adapter with its credentials (see README).</Alert></div>
      <div className="mb-5 flex gap-1 border-b border-slate-200" role="tablist">
        {(['messages', 'templates'] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
          className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${tab === t ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500'}`}>{t}</button>)}
      </div>
      {tab === 'messages' ? <Messages /> : <Templates />}
    </>
  )
}

function Messages() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), page_size: '50' })
  if (status) params.set('status', status)
  const list = useQuery({ queryKey: ['sms', params.toString()], placeholderData: (p) => p,
    queryFn: () => api<{ total: number; page_size: number; items: Msg[] }>(`/notifications/messages?${params}`) })
  const retry = useApiMutation((id: string) => api(`/notifications/messages/${id}/retry`, { method: 'POST' }), ['sms'])
  const process = useApiMutation(() => api<Record<string, number>>('/notifications/process', { method: 'POST' }), ['sms'])
  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="w-48"><Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">All</option>{Object.keys(TONE).map((s) => <option key={s} value={s}>{s}</option>)}</Select></div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => list.refetch()}><RefreshCw className="size-4" /></Button>
          <Button loading={process.isPending} onClick={() => process.mutate(undefined)}><Send className="size-4" />Send queued now</Button>
        </div>
      </div>
      {process.data && <div className="mb-3"><Alert tone="green">Processed: {Object.entries(process.data).map(([k, v]) => `${v} ${k}`).join(', ')}</Alert></div>}
      {(retry.error || process.error) && <Alert>{(retry.error || process.error)!.message}</Alert>}
      {list.isLoading && <Skeleton className="h-40" />}
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-3 py-2">When</th><th className="px-3 py-2">Phone</th><th className="px-3 py-2">Message</th><th className="px-3 py-2">Status</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.data?.items.map((m) => (
              <tr key={m.id} className="align-top">
                <td className="whitespace-nowrap px-3 py-2">{fmtDateTime(m.created_at)}</td>
                <td className="px-3 py-2 font-mono text-xs">{m.phone}</td>
                <td className="max-w-md px-3 py-2"><p>{m.body}</p><p className="text-xs text-slate-400">{m.template_code}{m.provider && ` · via ${m.provider}`}</p></td>
                <td className="px-3 py-2"><Badge tone={TONE[m.status]}>{m.status}</Badge>
                  <p className="text-xs text-slate-500">{m.attempts} attempt(s)</p>
                  {m.last_error && <p className="max-w-[14rem] text-xs text-red-600">{m.last_error}</p>}
                  {m.status === 'queued' && m.next_attempt_at && <p className="text-xs text-slate-400">next {fmtDateTime(m.next_attempt_at)}</p>}</td>
                <td className="px-3 py-2 text-right">{m.status === 'failed' && <Button variant="ghost" onClick={() => retry.mutate(m.id)}><RotateCcw className="size-4" />Retry</Button>}</td>
              </tr>
            ))}
            {list.data?.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">No messages.</td></tr>}
          </tbody>
        </table>
      </div>
      {list.data && <Pagination page={page} pageSize={list.data.page_size} total={list.data.total} onPage={setPage} />}
    </>
  )
}

function Templates() {
  const list = useQuery({ queryKey: ['sms-templates'], queryFn: () => api<Tpl[]>('/notifications/templates') })
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {list.data?.map((t) => <TemplateCard key={`${t.code}:${t.language}`} t={t} />)}
    </div>
  )
}

function TemplateCard({ t }: { t: Tpl }) {
  const [body, setBody] = useState(t.body)
  const save = useApiMutation(() => api(`/notifications/templates/${t.code}/${t.language}`, { method: 'PUT', json: { body } }), ['sms-templates'])
  return (
    <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
      <div className="mb-2 flex items-center justify-between"><p className="font-medium">{t.code.replace('_', ' ').toLowerCase()} · {t.language === 'sw' ? 'Kiswahili' : 'English'}</p>
        {t.is_default && <Badge>default</Badge>}</div>
      {save.error && <div className="mb-2"><Alert>{save.error.message}</Alert></div>}
      <Textarea aria-label={`${t.code} ${t.language}`} rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
      <p className="mt-1 text-xs text-slate-500">Placeholders: {t.placeholders.map((p) => `{${p}}`).join(' ')} · {body.length}/480 characters ({Math.ceil(body.length / 160)} SMS)</p>
      <div className="mt-2 flex justify-end"><Button variant="secondary" disabled={body === t.body || body.length < 10} loading={save.isPending} onClick={() => save.mutate(undefined)}>Save</Button></div>
    </div>
  )
}
