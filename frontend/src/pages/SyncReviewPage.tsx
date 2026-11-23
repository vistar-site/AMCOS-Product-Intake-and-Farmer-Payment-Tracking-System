import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { fmtDateTime } from '../components/form'
import { Alert, Badge, EmptyState, PageHeader, Skeleton } from '../components/ui'

interface Problem { id: string; created_at: string; user_name: string; device_id: string | null; received: number; created: number; duplicates: number
  conflicts: number; rejected: number; details: { id: string; status: string; message: string | null }[] }

/** Manager view of offline uploads the server did not accept. Nothing here was saved or overwritten. */
export default function SyncReviewPage() {
  const q = useQuery({ queryKey: ['sync-problems'], queryFn: () => api<Problem[]>('/sync/problems') })
  return (
    <>
      <PageHeader title="Offline sync review" description="Offline deliveries that the server rejected or that conflicted with an existing record." />
      <div className="mb-4"><Alert tone="amber">
        <b>Rejected</b> records failed validation (e.g. inactive farmer, wrong centre). Fix the cause, then the clerk presses Retry on the device, or record the delivery again.
        {' '}<b>Conflicts</b> mean a different delivery already exists with the same ID — the server kept its record and did not overwrite it. Compare the device copy with the server record
        (open the ID on the Deliveries page) and record a correction if the device copy is right.
      </Alert></div>
      {q.isLoading && <Skeleton className="h-40" />}
      {q.data?.length === 0 && <EmptyState title="No sync problems" description="Every offline upload so far was accepted." />}
      <div className="space-y-3">
        {q.data?.map((p) => (
          <div key={p.id} className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span><b>{p.user_name}</b> · device <span className="font-mono">{p.device_id}</span> · {fmtDateTime(p.created_at)}</span>
              <span className="text-slate-500">{p.received} received · {p.created} saved · {p.duplicates} duplicates · {p.conflicts} conflicts · {p.rejected} rejected</span>
            </div>
            <ul className="mt-2 space-y-1">
              {p.details.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-2 text-sm">
                  <Badge tone={d.status === 'conflict' ? 'red' : 'amber'}>{d.status}</Badge>
                  <span className="font-mono text-xs">{d.id}</span><span className="text-slate-600">{d.message}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  )
}
