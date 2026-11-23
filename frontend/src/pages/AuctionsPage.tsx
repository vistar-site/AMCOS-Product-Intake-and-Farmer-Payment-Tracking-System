import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useCrops, useSeasons } from '../features/reference/api'
import { fmtDate, Select } from '../components/form'
import { Alert, Badge, Button, EmptyState, Field, Input, Modal, PageHeader, Skeleton } from '../components/ui'
import type { Auction } from '../types/warehouse'
import { formatTZS, sumKg } from '../utils/money'
import { formatKg } from '../utils/weight'

export default function AuctionsPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const list = useQuery({ queryKey: ['auctions'], queryFn: () => api<Auction[]>('/auctions') })
  const [creating, setCreating] = useState(false)
  return (
    <>
      <PageHeader title="Auctions" description="Sale results per lot. Each lot links to a warehouse-received batch and its farmers."
        actions={can('auction.manage') && <Button onClick={() => setCreating(true)}><Plus className="size-4" />New auction</Button>} />
      {list.isLoading && <Skeleton className="h-32" />}
      {list.data?.length === 0 && <EmptyState title="No auctions recorded" description="Record an auction once produce has been received at the warehouse." />}
      {!!list.data?.length && (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Crop</th><th className="px-4 py-3 text-right">Lots</th>
                <th className="px-4 py-3 text-right">Sold</th><th className="px-4 py-3 text-right">Value</th><th className="px-4 py-3">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.data.map((a) => (
                <tr key={a.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/auctions/${a.id}`)}>
                  <td className="px-4 py-3"><Link to={`/auctions/${a.id}`} className="font-medium text-brand-700 hover:underline">{a.auction_ref}</Link><p className="text-xs text-slate-500">{a.venue}</p></td>
                  <td className="px-4 py-3">{fmtDate(a.auction_date)}</td><td className="px-4 py-3">{a.crop.name} · {a.season.name}</td>
                  <td className="px-4 py-3 text-right">{a.lots.length}</td>
                  <td className="px-4 py-3 text-right">{formatKg(sumKg(a.lots.map((l) => l.quantity_sold)))}</td>
                  <td className="px-4 py-3 text-right font-medium">{formatTZS(a.lots.reduce((s, l) => s + Number(l.total_value), 0))}</td>
                  <td className="px-4 py-3"><Badge tone={a.status === 'approved' ? 'green' : 'amber'}>{a.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <CreateAuctionModal onClose={() => setCreating(false)} onCreated={(id) => navigate(`/auctions/${id}`)} />}
    </>
  )
}

function CreateAuctionModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const crops = useCrops()
  const seasons = useSeasons()
  const [v, setV] = useState({ auction_ref: '', auction_date: new Date().toLocaleDateString('en-CA'), venue: '', crop_id: '', season_id: seasons.data?.find((s) => s.is_active)?.id ?? '' })
  const save = useApiMutation(() => api<Auction>('/auctions', { method: 'POST', json: { ...v, venue: v.venue || null } }), ['auctions'])
  return (
    <Modal open onClose={onClose} title="New auction">
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <Field label="Auction / sale reference" htmlFor="a-ref" hint="As printed on the official sale document"><Input id="a-ref" value={v.auction_ref} onChange={(e) => setV({ ...v, auction_ref: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date" htmlFor="a-date"><Input id="a-date" type="date" value={v.auction_date} onChange={(e) => setV({ ...v, auction_date: e.target.value })} /></Field>
          <Field label="Venue" htmlFor="a-venue"><Input id="a-venue" value={v.venue} onChange={(e) => setV({ ...v, venue: e.target.value })} /></Field>
          <Field label="Crop" htmlFor="a-crop"><Select id="a-crop" value={v.crop_id} onChange={(e) => setV({ ...v, crop_id: e.target.value })}>
            <option value="">Choose…</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="Season" htmlFor="a-season"><Select id="a-season" value={v.season_id} onChange={(e) => setV({ ...v, season_id: e.target.value })}>
            <option value="">Choose…</option>{seasons.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        </div>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!v.auction_ref || !v.crop_id || !v.season_id} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: (a) => onCreated(a.id) })}>Create</Button></div>
      </div>
    </Modal>
  )
}
