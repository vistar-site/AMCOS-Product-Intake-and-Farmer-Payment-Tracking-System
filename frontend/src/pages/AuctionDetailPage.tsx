import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, BadgeCheck, Plus, Trash2, Users } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useCrops } from '../features/reference/api'
import { fmtDate, Select } from '../components/form'
import { Alert, Badge, Button, Field, Input, Modal, Skeleton } from '../components/ui'
import type { Allocation, Auction, Lot, SellableBatch } from '../types/warehouse'
import { formatPrice, formatTZS, sumKg } from '../utils/money'
import { formatKg, isValidWeight } from '../utils/weight'

export default function AuctionDetailPage() {
  const { id = '' } = useParams()
  const { can, user } = useAuth()
  const q = useQuery({ queryKey: ['auctions', id], queryFn: () => api<Auction>(`/auctions/${id}`) })
  const [adding, setAdding] = useState(false)
  const [viewing, setViewing] = useState<Lot | null>(null)
  const [confirm, setConfirm] = useState(false)
  const remove = useApiMutation((lotId: string) => api(`/auctions/${id}/lots/${lotId}`, { method: 'DELETE' }), ['auctions'])
  const approve = useApiMutation(() => api(`/auctions/${id}/approve`, { method: 'POST' }), ['auctions', 'batches'])

  if (q.isLoading) return <Skeleton className="h-64" />
  if (q.error || !q.data) return <Alert>{(q.error as Error)?.message}</Alert>
  const a = q.data
  const draft = a.status === 'draft'
  const totalValue = a.lots.reduce((s, l) => s + Number(l.total_value), 0)
  const totalKg = sumKg(a.lots.map((l) => l.quantity_sold))
  const selfCreated = a.created_by === user?.id

  return (
    <>
      <Link to="/auctions" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="size-4" />Auctions</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3"><h1 className="text-2xl font-semibold">{a.auction_ref}</h1><Badge tone={draft ? 'amber' : 'green'}>{a.status}</Badge></div>
          <p className="mt-1 text-sm text-slate-500">{fmtDate(a.auction_date)} · {a.venue ?? '—'} · {a.crop.name} · {a.season.name}</p>
        </div>
        {draft && <div className="flex gap-2">
          {can('auction.manage') && <Button variant="secondary" onClick={() => setAdding(true)}><Plus className="size-4" />Add lot</Button>}
          {can('auction.approve') && <Button disabled={!a.lots.length || selfCreated} title={selfCreated ? 'Must be approved by a different user' : undefined}
            onClick={() => setConfirm(true)}><BadgeCheck className="size-4" />Approve results</Button>}
        </div>}
      </div>
      {draft && selfCreated && can('auction.approve') && <div className="mb-4"><Alert tone="amber">You entered these results, so a different authorized user must approve them.</Alert></div>}
      {(remove.error || approve.error) && <div className="mb-4"><Alert>{(remove.error || approve.error)!.message}</Alert></div>}

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200"><p className="text-sm text-slate-500">Lots</p><p className="text-xl font-semibold">{a.lots.length}</p></div>
        <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200"><p className="text-sm text-slate-500">Quantity sold</p><p className="text-xl font-semibold">{formatKg(totalKg)}</p></div>
        <div className="rounded-lg bg-white p-4 ring-1 ring-slate-200"><p className="text-sm text-slate-500">Total sale value</p><p className="text-xl font-semibold">{formatTZS(totalValue)}</p>
          {Number(totalKg) > 0 && <p className="text-xs text-slate-500">avg {formatPrice(String(totalValue / Number(totalKg)))}</p>}</div>
      </div>

      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-4 py-2">Lot</th><th className="px-4 py-2">Batch</th><th className="px-4 py-2">Grade</th><th className="px-4 py-2 text-right">Quantity</th>
              <th className="px-4 py-2 text-right">Price</th><th className="px-4 py-2 text-right">Value</th><th className="px-4 py-2">Buyer</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {a.lots.map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-2 font-medium">{l.lot_no}</td>
                <td className="px-4 py-2 font-mono text-xs"><Link className="text-brand-700 hover:underline" to={`/batches/${l.batch.id}`}>{l.batch.batch_no}</Link></td>
                <td className="px-4 py-2">{l.grade?.name ?? '—'}</td>
                <td className="px-4 py-2 text-right">{formatKg(l.quantity_sold)}</td><td className="px-4 py-2 text-right">{formatPrice(l.price_per_kg)}</td>
                <td className="px-4 py-2 text-right font-medium">{formatTZS(l.total_value)}</td><td className="px-4 py-2">{l.buyer ?? '—'}</td>
                <td className="px-4 py-2 text-right">
                  {!draft && <Button variant="ghost" onClick={() => setViewing(l)}><Users className="size-4" />Farmers</Button>}
                  {draft && can('auction.manage') && <button aria-label="Remove lot" className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" onClick={() => remove.mutate(l.id)}><Trash2 className="size-4" /></button>}
                </td>
              </tr>
            ))}
            {a.lots.length === 0 && <tr><td colSpan={8} className="px-4 py-6 text-center text-slate-500">No lots yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {adding && <AddLotModal auction={a} onClose={() => setAdding(false)} />}
      {viewing && <AllocationsModal auctionId={a.id} lot={viewing} onClose={() => setViewing(null)} />}
      <Modal open={confirm} onClose={() => setConfirm(false)} title="Approve auction results?">
        <p className="text-sm text-slate-600">{a.lots.length} lots · {formatKg(totalKg)} · {formatTZS(totalValue)}. Approval freezes the results and
          allocates every lot to the farmer deliveries in its batch. It cannot be undone.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button>
          <Button loading={approve.isPending} onClick={() => approve.mutate(undefined, { onSuccess: () => setConfirm(false) })}>Approve</Button></div>
      </Modal>
    </>
  )
}

function AddLotModal({ auction, onClose }: { auction: Auction; onClose: () => void }) {
  const crops = useCrops()
  const grades = crops.data?.find((c) => c.id === auction.crop.id)?.grades.filter((g) => g.is_active) ?? []
  const sellable = useQuery({ queryKey: ['auctions', 'sellable', auction.crop.id], queryFn: () => api<SellableBatch[]>(`/auctions/sellable-batches?crop_id=${auction.crop.id}`) })
  const [v, setV] = useState({ batch_id: '', lot_no: `L${auction.lots.length + 1}`, grade_id: '', quantity_sold: '', price_per_kg: '', buyer: '' })
  const save = useApiMutation(() => api(`/auctions/${auction.id}/lots`, { method: 'POST', json: { ...v, grade_id: v.grade_id || null, buyer: v.buyer || null } }), ['auctions'])
  const batch = sellable.data?.find((b) => b.id === v.batch_id)
  const priceOk = /^\d{1,8}(\.\d{1,4})?$/.test(v.price_per_kg) && Number(v.price_per_kg) > 0
  const qtyOk = isValidWeight(v.quantity_sold) && Number(v.quantity_sold) > 0 && (!batch || Number(v.quantity_sold) <= Number(batch.available_weight))
  const value = qtyOk && priceOk ? Number(v.quantity_sold) * Number(v.price_per_kg) : null
  return (
    <Modal open onClose={onClose} title="Add sale lot">
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <Field label="Batch (received at warehouse)" htmlFor="l-b"><Select id="l-b" value={v.batch_id} onChange={(e) => setV({ ...v, batch_id: e.target.value })}>
          <option value="">Choose…</option>{sellable.data?.map((b) => <option key={b.id} value={b.id}>{b.batch_no} · {b.centre_name} · {formatKg(b.available_weight)} available</option>)}</Select></Field>
        {sellable.data?.length === 0 && <p className="text-sm text-amber-700">No received {auction.crop.name} batches have unsold quantity.</p>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Lot no." htmlFor="l-no"><Input id="l-no" value={v.lot_no} onChange={(e) => setV({ ...v, lot_no: e.target.value })} /></Field>
          <Field label="Grade" htmlFor="l-g"><Select id="l-g" value={v.grade_id} onChange={(e) => setV({ ...v, grade_id: e.target.value })}>
            <option value="">—</option>{grades.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</Select></Field>
          <Field label="Quantity sold (kg)" htmlFor="l-q" error={v.quantity_sold && !qtyOk ? `Max ${batch?.available_weight ?? ''} kg` : undefined}>
            <Input id="l-q" inputMode="decimal" value={v.quantity_sold} onChange={(e) => setV({ ...v, quantity_sold: e.target.value })} /></Field>
          <Field label="Price per kg (TZS)" htmlFor="l-p"><Input id="l-p" inputMode="decimal" value={v.price_per_kg} onChange={(e) => setV({ ...v, price_per_kg: e.target.value })} /></Field>
        </div>
        <Field label="Buyer" htmlFor="l-buyer"><Input id="l-buyer" value={v.buyer} onChange={(e) => setV({ ...v, buyer: e.target.value })} /></Field>
        {value !== null && <p className="text-sm">Lot value: <b>{formatTZS(value)}</b> <span className="text-slate-500">(final figure is calculated by the server)</span></p>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!v.batch_id || !v.lot_no || !qtyOk || !priceOk} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Add lot</Button></div>
      </div>
    </Modal>
  )
}

function AllocationsModal({ auctionId, lot, onClose }: { auctionId: string; lot: Lot; onClose: () => void }) {
  const q = useQuery({ queryKey: ['auctions', auctionId, 'alloc', lot.id], queryFn: () => api<Allocation[]>(`/auctions/${auctionId}/lots/${lot.id}/allocations`) })
  return (
    <Modal open onClose={onClose} title={`Lot ${lot.lot_no}: farmer shares`}>
      <p className="mb-3 text-sm text-slate-600">{formatKg(lot.quantity_sold)} at {formatPrice(lot.price_per_kg)} from batch {lot.batch.batch_no}.
        “Loss shared” spreads warehouse losses over farmers; “AMCOS absorbs” pays farmers on delivered weight. The payout run chooses the policy.</p>
      <div className="max-h-96 overflow-y-auto rounded-md ring-1 ring-slate-200">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-3 py-2">Farmer</th><th className="px-3 py-2 text-right">Loss shared</th><th className="px-3 py-2 text-right">AMCOS absorbs</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {q.data?.map((r) => (
              <tr key={r.delivery_id}><td className="px-3 py-1.5">{r.delivery.farmer.full_name}<span className="block font-mono text-xs text-slate-500">{r.delivery.receipt_no}</span></td>
                <td className="px-3 py-1.5 text-right">{formatKg(r.weight_shared)}</td><td className="px-3 py-1.5 text-right">{formatKg(r.weight_absorbed)}</td></tr>
            ))}
          </tbody>
          {q.data && <tfoot className="border-t border-slate-200 font-medium"><tr><td className="px-3 py-2">Total</td>
            <td className="px-3 py-2 text-right">{formatKg(sumKg(q.data.map((r) => r.weight_shared)))}</td>
            <td className="px-3 py-2 text-right">{formatKg(sumKg(q.data.map((r) => r.weight_absorbed)))}</td></tr></tfoot>}
        </table>
      </div>
    </Modal>
  )
}
