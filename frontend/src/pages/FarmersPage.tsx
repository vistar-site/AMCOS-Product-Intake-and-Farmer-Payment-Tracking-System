import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import FarmerForm from '../features/farmers/FarmerForm'
import { useFarmers } from '../features/farmers/api'
import { toFarmerBody, type FarmerValues } from '../features/farmers/schemas'
import { useApiMutation, useCentres } from '../features/reference/api'
import { useDebounce } from '../hooks/useDebounce'
import type { Farmer } from '../types/domain'
import { Pagination, Select } from '../components/form'
import { Alert, Badge, Button, EmptyState, Input, Modal, PageHeader, Skeleton } from '../components/ui'

export const farmerStatusTone = { active: 'green', inactive: 'slate', suspended: 'red' } as const

export default function FarmersPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const { data: centres } = useCentres()
  const [search, setSearch] = useState('')
  const [village, setVillage] = useState('')
  const [centre, setCentre] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const q = useDebounce(search)
  const v = useDebounce(village)
  const { data, isLoading, error } = useFarmers({ q, village: v, centre_id: centre, status, page })
  const create = useApiMutation((b: FarmerValues) => api<Farmer>('/farmers', { method: 'POST', json: toFarmerBody(b) }), ['farmers'])

  return (
    <>
      <PageHeader title="Farmers" description="Registered cooperative members."
        actions={can('farmer.create') && <Button onClick={() => setCreating(true)}><Plus className="size-4" />Register farmer</Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative sm:col-span-2 lg:col-span-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
          <Input className="pl-9" placeholder="Name, member no. or phone" aria-label="Search farmers"
            value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        </div>
        <Input placeholder="Village" aria-label="Filter by village" value={village} onChange={(e) => { setVillage(e.target.value); setPage(1) }} />
        <Select aria-label="Filter by centre" value={centre} onChange={(e) => { setCentre(e.target.value); setPage(1) }}>
          <option value="">All centres</option>{centres?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">Any status</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="suspended">Suspended</option>
        </Select>
      </div>
      {error && <Alert>{(error as Error).message}</Alert>}
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Farmer</th><th className="px-4 py-3">Phone</th><th className="px-4 py-3">Village</th><th className="px-4 py-3">Centre</th><th className="px-4 py-3">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && [1, 2, 3, 4].map((i) => <tr key={i}><td colSpan={5} className="px-4 py-3"><Skeleton className="h-5" /></td></tr>)}
            {data?.items.map((f) => (
              <tr key={f.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/farmers/${f.id}`)}>
                <td className="px-4 py-3"><Link to={`/farmers/${f.id}`} className="font-medium text-brand-700 hover:underline">{f.full_name}</Link>
                  <p className="text-slate-500">{f.membership_no}</p></td>
                <td className="px-4 py-3">{f.phone ?? '—'}</td>
                <td className="px-4 py-3">{f.village ?? '—'}</td>
                <td className="px-4 py-3">{f.home_centre?.name ?? '—'}</td>
                <td className="px-4 py-3"><Badge tone={farmerStatusTone[f.status]}>{f.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.items.length === 0 && <div className="p-4"><EmptyState title="No farmers found" description="Try a different search, or register a new farmer." /></div>}
      </div>
      {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}

      <Modal open={creating} onClose={() => { setCreating(false); create.reset() }} title="Register farmer">
        {creating && (
          <FarmerForm submitting={create.isPending} error={create.error?.message}
            onCancel={() => { setCreating(false); create.reset() }}
            onSubmit={(vals) => create.mutate(vals, { onSuccess: (f) => { setCreating(false); navigate(`/farmers/${f.id}`) } })} />
        )}
      </Modal>
    </>
  )
}
