import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { liveQuery } from 'dexie'
import { CloudOff, RefreshCw, RotateCcw, Wifi } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useSync } from '../context/SyncContext'
import { db, type OutboxDelivery } from '../offline/db'
import { retryRecord } from '../offline/syncEngine'
import { fmtDateTime } from '../components/form'
import { Alert, Badge, Button, EmptyState, PageHeader } from '../components/ui'
import { formatKg } from '../utils/weight'

const tone = { pending: 'amber', syncing: 'blue', synced: 'green', rejected: 'red', conflict: 'red' } as const
const label = { pending: 'Waiting to upload', syncing: 'Uploading…', synced: 'On server', rejected: 'Rejected by server', conflict: 'Conflict' }

export default function SyncPage() {
  const { user, status } = useAuth()
  const { online, syncing, counts, lastSync, lastError, syncNow } = useSync()
  const [rows, setRows] = useState<OutboxDelivery[]>([])

  useEffect(() => {
    if (!user) return
    const sub = liveQuery(() => db.outbox.where('userId').equals(user.id).reverse().sortBy('capturedAt'))
      .subscribe({ next: setRows, error: () => {} })
    return () => sub.unsubscribe()
  }, [user])

  const problems = rows.filter((r) => r.status === 'rejected' || r.status === 'conflict')

  return (
    <>
      <PageHeader title="Sync status" description="Deliveries recorded on this device and whether the server has confirmed them."
        actions={<Button onClick={syncNow} loading={syncing} disabled={!online}><RefreshCw className="size-4" />Sync now</Button>} />

      <div className="mb-6 grid gap-3 sm:grid-cols-4">
        <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
          <p className="text-sm text-slate-500">Connection</p>
          <p className="mt-1 flex items-center gap-2 font-semibold">{online ? <><Wifi className="size-4 text-brand-600" />Online</> : <><CloudOff className="size-4 text-amber-600" />Offline</>}</p>
          {status === 'offline' && <p className="mt-1 text-xs text-amber-700">Offline session — sign-in will be renewed when connected</p>}
        </div>
        <Stat title="Waiting to upload" value={counts.pending} warn={counts.pending > 0} />
        <Stat title="Need attention" value={counts.rejected + counts.conflict} warn={counts.rejected + counts.conflict > 0} />
        <Stat title="Confirmed (last 7 days)" value={counts.synced} />
      </div>
      {lastSync && <p className="mb-3 text-sm text-slate-500">Last sync {fmtDateTime(lastSync.at)}: {lastSync.summary.synced} confirmed, {lastSync.summary.rejected} rejected, {lastSync.summary.conflicts} conflicts.</p>}
      {lastError && <div className="mb-3"><Alert tone="amber">Last attempt failed: {lastError}. Retrying automatically.</Alert></div>}
      {problems.length > 0 && <div className="mb-3"><Alert>
        {problems.length} record(s) were not accepted. They stay on this device until resolved. Rejected records usually need a correction
        (e.g. the farmer was deactivated); ask a manager to record the delivery or reactivate the farmer, then press Retry.
        Conflicts mean the server already holds a <b>different</b> delivery with the same ID — report these to your manager; nothing was overwritten.
      </Alert></div>}

      {rows.length === 0 ? <EmptyState title="Nothing recorded on this device" description="Deliveries saved while offline appear here until the server confirms them." /> : (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-2">Offline receipt</th><th className="px-4 py-2">Official receipt</th><th className="px-4 py-2">Farmer</th>
                <th className="px-4 py-2 text-right">Net</th><th className="px-4 py-2">Captured</th><th className="px-4 py-2">Status</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-2 font-mono text-xs">{r.provisionalReceiptNo}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.receiptNo ? <Link className="text-brand-700 hover:underline" to={`/deliveries/${r.id}`}>{r.receiptNo}</Link> : '—'}</td>
                  <td className="px-4 py-2">{r.display.farmerName}<p className="text-xs text-slate-500">{r.display.cropName}</p></td>
                  <td className="px-4 py-2 text-right">{formatKg(r.display.net)}</td>
                  <td className="whitespace-nowrap px-4 py-2">{fmtDateTime(r.capturedAt)}</td>
                  <td className="px-4 py-2"><Badge tone={tone[r.status]}>{label[r.status]}</Badge>
                    {r.lastError && r.status !== 'synced' && <p className="mt-1 max-w-xs text-xs text-red-600">{r.lastError}</p>}
                    {r.attempts > 1 && r.status !== 'synced' && <p className="text-xs text-slate-400">{r.attempts} attempts</p>}</td>
                  <td className="px-4 py-2 text-right">{r.status === 'rejected' && <Button variant="secondary" onClick={() => retryRecord(r.id).then(syncNow)}><RotateCcw className="size-4" />Retry</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-4 text-xs text-slate-500">Confirmed records are removed from this device after 7 days; they remain permanently on the server.</p>
    </>
  )
}

function Stat({ title, value, warn }: { title: string; value: number; warn?: boolean }) {
  return (
    <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
      <p className="text-sm text-slate-500">{title}</p>
      <p className={`mt-1 text-2xl font-semibold ${warn ? 'text-amber-600' : ''}`}>{value}</p>
    </div>
  )
}
