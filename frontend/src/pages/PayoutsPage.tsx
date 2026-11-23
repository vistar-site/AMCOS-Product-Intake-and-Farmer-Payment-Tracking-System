import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Calculator, Plus } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useCrops, useSeasons } from '../features/reference/api'
import { useFarmers } from '../features/farmers/api'
import { useDebounce } from '../hooks/useDebounce'
import { fmtDate, fmtDateTime, Select, Textarea } from '../components/form'
import { Alert, Badge, Button, EmptyState, Field, Input, Modal, PageHeader, Skeleton } from '../components/ui'
import type { DeductionType, Loan, RunSummary } from '../types/finance'
import { formatTZS } from '../utils/money'

type Tab = 'runs' | 'deductions' | 'loans'
const RUN_TONE = { calculated: 'amber', approved: 'green', cancelled: 'slate' } as const
const today = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Africa/Dar_es_Salaam' })

export default function PayoutsPage() {
  const [tab, setTab] = useState<Tab>('runs')
  return (
    <>
      <PageHeader title="Farmer payouts" description="Levies, input loans and payout calculations from auction results." />
      <div className="mb-5 flex gap-1 border-b border-slate-200" role="tablist">
        {([['runs', 'Payout runs'], ['deductions', 'Levies & deductions'], ['loans', 'Input loans']] as [Tab, string][]).map(([t, label]) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${tab === t ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>{label}</button>
        ))}
      </div>
      {tab === 'runs' && <RunsTab />}
      {tab === 'deductions' && <DeductionsTab />}
      {tab === 'loans' && <LoansTab />}
    </>
  )
}

function RunsTab() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const runs = useQuery({ queryKey: ['payout-runs'], queryFn: () => api<RunSummary[]>('/payout-runs') })
  const [open, setOpen] = useState(false)
  return (
    <>
      {can('payout.calculate') && <div className="mb-4 flex justify-end"><Button onClick={() => setOpen(true)}><Calculator className="size-4" />Calculate payouts</Button></div>}
      {runs.isLoading && <Skeleton className="h-32" />}
      {runs.data?.length === 0 && <EmptyState title="No payout runs yet" description="Once auction results are approved, calculate what each farmer is owed." />}
      {!!runs.data?.length && (
        <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Run</th><th className="px-4 py-3">Crop / season</th><th className="px-4 py-3">Loss policy</th>
                <th className="px-4 py-3 text-right">Gross</th><th className="px-4 py-3 text-right">Deductions</th><th className="px-4 py-3 text-right">Net</th><th className="px-4 py-3">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.data.map((r) => (
                <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => navigate(`/payouts/${r.id}`)}>
                  <td className="px-4 py-3"><Link to={`/payouts/${r.id}`} className="font-mono text-xs text-brand-700 hover:underline">{r.run_no}</Link><p className="text-xs text-slate-500">{fmtDateTime(r.calculated_at)}</p></td>
                  <td className="px-4 py-3">{r.crop.name} · {r.season.name}</td>
                  <td className="px-4 py-3">{r.loss_policy === 'shared' ? 'Loss shared by farmers' : 'AMCOS absorbs loss'}</td>
                  <td className="px-4 py-3 text-right">{formatTZS(r.total_gross)}</td><td className="px-4 py-3 text-right">{formatTZS(r.total_deductions)}</td>
                  <td className="px-4 py-3 text-right font-medium">{formatTZS(r.total_net)}</td>
                  <td className="px-4 py-3"><Badge tone={RUN_TONE[r.status]}>{r.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && <CalculateModal onClose={() => setOpen(false)} onDone={(id) => navigate(`/payouts/${id}`)} />}
    </>
  )
}

function CalculateModal({ onClose, onDone }: { onClose: () => void; onDone: (id: string) => void }) {
  const crops = useCrops()
  const seasons = useSeasons()
  const [v, setV] = useState({ crop_id: '', season_id: seasons.data?.find((s) => s.is_active)?.id ?? '', loss_policy: '' as '' | 'shared' | 'absorbed', notes: '' })
  const run = useApiMutation(() => api<{ id: string }>('/payout-runs', { method: 'POST', json: { ...v, notes: v.notes || null } }), ['payout-runs'])
  return (
    <Modal open onClose={onClose} title="Calculate farmer payouts">
      <div className="space-y-4">
        {run.error && <Alert>{run.error.message}</Alert>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Crop" htmlFor="c-crop"><Select id="c-crop" value={v.crop_id} onChange={(e) => setV({ ...v, crop_id: e.target.value })}>
            <option value="">Choose…</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="Season" htmlFor="c-season"><Select id="c-season" value={v.season_id} onChange={(e) => setV({ ...v, season_id: e.target.value })}>
            <option value="">Choose…</option>{seasons.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-slate-700">Warehouse loss policy</legend>
          {([['shared', 'Loss shared by farmers', 'Farmers are paid on the kilograms actually sold. A 2% warehouse loss reduces every farmer’s paid weight by 2%.'],
            ['absorbed', 'AMCOS absorbs the loss', 'Farmers are paid on their full delivered kilograms (once the batch is sold). The AMCOS bears the cost of warehouse losses.']] as const)
            .map(([val, title, desc]) => (
              <label key={val} className={`mb-2 flex cursor-pointer gap-3 rounded-md p-3 ring-1 ${v.loss_policy === val ? 'bg-brand-50 ring-brand-600' : 'ring-slate-200'}`}>
                <input type="radio" name="policy" className="mt-1 accent-brand-600" checked={v.loss_policy === val} onChange={() => setV({ ...v, loss_policy: val })} />
                <span><span className="font-medium">{title}</span><span className="block text-sm text-slate-600">{desc}</span></span>
              </label>
            ))}
        </fieldset>
        <Field label="Notes" htmlFor="c-notes"><Textarea id="c-notes" rows={2} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} /></Field>
        <p className="text-xs text-slate-500">Includes all sold produce from approved auctions not yet in a payout run. Results must be approved by a different user before payment.</p>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!v.crop_id || !v.season_id || !v.loss_policy} loading={run.isPending} onClick={() => run.mutate(undefined, { onSuccess: (r) => onDone(r.id) })}>Calculate</Button></div>
      </div>
    </Modal>
  )
}

const METHOD = { percent_of_gross: '% of gross', per_kg: 'per kg', fixed: 'fixed' }

function DeductionsTab() {
  const { can } = useAuth()
  const list = useQuery({ queryKey: ['deductions'], queryFn: () => api<DeductionType[]>('/deductions') })
  const toggle = useApiMutation((d: DeductionType) => api(`/deductions/${d.id}`, { method: 'PATCH', json: { is_active: !d.is_active } }), ['deductions'])
  const [open, setOpen] = useState(false)
  return (
    <>
      {can('deduction.manage') && <div className="mb-4 flex justify-end"><Button onClick={() => setOpen(true)}><Plus className="size-4" />New deduction</Button></div>}
      <Alert tone="amber">Rates are configured by the AMCOS. Changing a rate only affects future calculations; approved payouts keep the rate they used.</Alert>
      {toggle.error && <div className="mt-2"><Alert>{toggle.error.message}</Alert></div>}
      <div className="mt-4 overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-4 py-2">Order</th><th className="px-4 py-2">Deduction</th><th className="px-4 py-2">Type</th><th className="px-4 py-2 text-right">Rate</th>
              <th className="px-4 py-2">Applies to</th><th className="px-4 py-2">Effective</th><th className="px-4 py-2">Status</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.data?.map((d) => (
              <tr key={d.id}>
                <td className="px-4 py-2 text-slate-500">{d.priority}</td>
                <td className="px-4 py-2"><span className="font-medium">{d.name}</span><span className="block text-xs text-slate-500">{d.code}</span></td>
                <td className="px-4 py-2 capitalize">{d.category}</td>
                <td className="px-4 py-2 text-right">{Number(d.rate).toLocaleString()} {METHOD[d.calc_method]}{d.calc_method === 'fixed' && d.applies_per === 'delivery' ? ' / delivery' : ''}</td>
                <td className="px-4 py-2">{d.crop?.name ?? 'All crops'} · {d.season?.name ?? 'All seasons'}</td>
                <td className="px-4 py-2">{fmtDate(d.effective_from)}{d.effective_to ? ` – ${fmtDate(d.effective_to)}` : ' onward'}</td>
                <td className="px-4 py-2"><Badge tone={d.is_active ? 'green' : 'slate'}>{d.is_active ? 'Active' : 'Inactive'}</Badge></td>
                <td className="px-4 py-2 text-right">{can('deduction.manage') && <Button variant="ghost" onClick={() => toggle.mutate(d)}>{d.is_active ? 'Deactivate' : 'Activate'}</Button>}</td>
              </tr>
            ))}
            {list.data?.length === 0 && <tr><td colSpan={8} className="px-4 py-6 text-center text-slate-500">No deductions configured.</td></tr>}
          </tbody>
        </table>
      </div>
      {open && <DeductionModal onClose={() => setOpen(false)} />}
    </>
  )
}

function DeductionModal({ onClose }: { onClose: () => void }) {
  const crops = useCrops()
  const seasons = useSeasons()
  const [v, setV] = useState({ code: '', name: '', category: 'levy', calc_method: 'percent_of_gross', rate: '', applies_per: 'farmer', priority: '100', crop_id: '', season_id: '', effective_from: today(), effective_to: '' })
  const save = useApiMutation(() => api('/deductions', { method: 'POST', json: {
    ...v, priority: Number(v.priority), crop_id: v.crop_id || null, season_id: v.season_id || null, effective_to: v.effective_to || null } }), ['deductions'])
  const rateOk = /^\d+(\.\d{1,4})?$/.test(v.rate) && (v.calc_method !== 'percent_of_gross' || Number(v.rate) <= 100)
  return (
    <Modal open onClose={onClose} title="New levy or deduction">
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Code" htmlFor="d-code"><Input id="d-code" value={v.code} onChange={(e) => setV({ ...v, code: e.target.value })} /></Field>
          <div className="col-span-2"><Field label="Name" htmlFor="d-name"><Input id="d-name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} /></Field></div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Category" htmlFor="d-cat"><Select id="d-cat" value={v.category} onChange={(e) => setV({ ...v, category: e.target.value })}><option value="levy">Levy</option><option value="other">Other</option></Select></Field>
          <Field label="Calculated as" htmlFor="d-m"><Select id="d-m" value={v.calc_method} onChange={(e) => setV({ ...v, calc_method: e.target.value })}>
            <option value="percent_of_gross">% of gross</option><option value="per_kg">Amount per kg</option><option value="fixed">Fixed amount</option></Select></Field>
          <Field label={v.calc_method === 'percent_of_gross' ? 'Rate (%)' : 'Amount (TZS)'} htmlFor="d-r" error={v.rate && !rateOk ? 'Invalid rate' : undefined}>
            <Input id="d-r" inputMode="decimal" value={v.rate} onChange={(e) => setV({ ...v, rate: e.target.value })} /></Field>
        </div>
        {v.calc_method === 'fixed' && <Field label="Fixed amount applies" htmlFor="d-ap"><Select id="d-ap" value={v.applies_per} onChange={(e) => setV({ ...v, applies_per: e.target.value })}>
          <option value="farmer">Once per farmer per payout</option><option value="delivery">Once per delivery</option></Select></Field>}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Order" htmlFor="d-p" hint="Lower runs first"><Input id="d-p" inputMode="numeric" value={v.priority} onChange={(e) => setV({ ...v, priority: e.target.value })} /></Field>
          <Field label="Crop" htmlFor="d-crop"><Select id="d-crop" value={v.crop_id} onChange={(e) => setV({ ...v, crop_id: e.target.value })}><option value="">All crops</option>{crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="Season" htmlFor="d-s"><Select id="d-s" value={v.season_id} onChange={(e) => setV({ ...v, season_id: e.target.value })}><option value="">All seasons</option>{seasons.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Effective from" htmlFor="d-f"><Input id="d-f" type="date" value={v.effective_from} onChange={(e) => setV({ ...v, effective_from: e.target.value })} /></Field>
          <Field label="Effective to (optional)" htmlFor="d-t"><Input id="d-t" type="date" value={v.effective_to} onChange={(e) => setV({ ...v, effective_to: e.target.value })} /></Field>
        </div>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!v.code || v.name.length < 2 || !rateOk} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Save</Button></div>
      </div>
    </Modal>
  )
}

function LoansTab() {
  const { can } = useAuth()
  const [status, setStatus] = useState('active')
  const list = useQuery({ queryKey: ['loans', status], queryFn: () => api<Loan[]>(`/loans${status ? `?status=${status}` : ''}`) })
  const [open, setOpen] = useState(false)
  const [repaying, setRepaying] = useState<Loan | null>(null)
  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="w-48"><Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="active">Active</option><option value="repaid">Repaid</option><option value="">All</option></Select></div>
        {can('loan.manage') && <Button onClick={() => setOpen(true)}><Plus className="size-4" />Record input loan</Button>}
      </div>
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-4 py-2">Loan</th><th className="px-4 py-2">Farmer</th><th className="px-4 py-2">Inputs</th><th className="px-4 py-2 text-right">Principal</th>
              <th className="px-4 py-2 text-right">Repaid</th><th className="px-4 py-2 text-right">Outstanding</th><th className="px-4 py-2">Cap</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.data?.map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-2"><span className="font-mono text-xs">{l.loan_ref}</span><p className="text-xs text-slate-500">{fmtDate(l.issue_date)}</p></td>
                <td className="px-4 py-2"><Link className="text-brand-700 hover:underline" to={`/farmers/${l.farmer.id}`}>{l.farmer.full_name}</Link></td>
                <td className="px-4 py-2">{l.description}</td>
                <td className="px-4 py-2 text-right">{formatTZS(l.principal)}</td><td className="px-4 py-2 text-right">{formatTZS(l.repaid)}</td>
                <td className="px-4 py-2 text-right font-medium">{formatTZS(l.outstanding)}</td>
                <td className="px-4 py-2">{l.max_deduction_percent ? `${Number(l.max_deduction_percent)}% per payout` : 'None'}</td>
                <td className="px-4 py-2 text-right">{l.status === 'active' && can('loan.manage') && <Button variant="ghost" onClick={() => setRepaying(l)}>Cash repayment</Button>}</td>
              </tr>
            ))}
            {list.data?.length === 0 && <tr><td colSpan={8} className="px-4 py-6 text-center text-slate-500">No loans.</td></tr>}
          </tbody>
        </table>
      </div>
      {open && <LoanModal onClose={() => setOpen(false)} />}
      {repaying && <RepayModal loan={repaying} onClose={() => setRepaying(null)} />}
    </>
  )
}

function LoanModal({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState('')
  const term = useDebounce(q)
  const farmers = useFarmers({ q: term, page_size: 6 }, term.length >= 2)
  const [farmer, setFarmer] = useState<{ id: string; full_name: string } | null>(null)
  const [v, setV] = useState({ issue_date: today(), description: '', principal: '', max_deduction_percent: '50', terms: '' })
  const save = useApiMutation(() => api('/loans', { method: 'POST', json: {
    farmer_id: farmer!.id, ...v, max_deduction_percent: v.max_deduction_percent || null, terms: v.terms || null } }), ['loans'])
  const ok = farmer && v.description.length >= 3 && /^\d+(\.\d{1,2})?$/.test(v.principal) && Number(v.principal) > 0
  return (
    <Modal open onClose={onClose} title="Record input loan">
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        {farmer ? <div className="flex items-center justify-between rounded-md bg-brand-50 px-3 py-2"><span className="font-medium">{farmer.full_name}</span><Button variant="ghost" onClick={() => setFarmer(null)}>Change</Button></div> : (
          <Field label="Farmer" htmlFor="ln-f"><Input id="ln-f" placeholder="Search name or member no." value={q} onChange={(e) => setQ(e.target.value)} />
            <ul className="mt-1 divide-y divide-slate-100 rounded-md ring-1 ring-slate-200 empty:hidden">
              {farmers.data?.items.map((f) => <li key={f.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => setFarmer(f)}>{f.full_name} · {f.membership_no}</button></li>)}
            </ul></Field>
        )}
        <Field label="Inputs supplied" htmlFor="ln-d"><Input id="ln-d" placeholder="e.g. Sulphur dust, 6 bags" value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} /></Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Issue date" htmlFor="ln-dt"><Input id="ln-dt" type="date" value={v.issue_date} onChange={(e) => setV({ ...v, issue_date: e.target.value })} /></Field>
          <Field label="Amount (TZS)" htmlFor="ln-p"><Input id="ln-p" inputMode="decimal" value={v.principal} onChange={(e) => setV({ ...v, principal: e.target.value })} /></Field>
          <Field label="Max % per payout" htmlFor="ln-c" hint="Blank = no cap"><Input id="ln-c" inputMode="decimal" value={v.max_deduction_percent} onChange={(e) => setV({ ...v, max_deduction_percent: e.target.value })} /></Field>
        </div>
        <Field label="Approved terms" htmlFor="ln-t"><Textarea id="ln-t" rows={2} value={v.terms} onChange={(e) => setV({ ...v, terms: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!ok} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Save loan</Button></div>
      </div>
    </Modal>
  )
}

function RepayModal({ loan, onClose }: { loan: Loan; onClose: () => void }) {
  const [v, setV] = useState({ amount: '', repayment_date: today(), reference: '' })
  const save = useApiMutation(() => api(`/loans/${loan.id}/repayments`, { method: 'POST', json: { ...v, reference: v.reference || null } }), ['loans'])
  const ok = /^\d+(\.\d{1,2})?$/.test(v.amount) && Number(v.amount) > 0 && Number(v.amount) <= Number(loan.outstanding)
  return (
    <Modal open onClose={onClose} title={`Cash repayment · ${loan.loan_ref}`}>
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <p className="text-sm text-slate-600">{loan.farmer.full_name} · outstanding <b>{formatTZS(loan.outstanding)}</b></p>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Amount" htmlFor="rp-a"><Input id="rp-a" inputMode="decimal" value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} /></Field>
          <Field label="Date" htmlFor="rp-d"><Input id="rp-d" type="date" value={v.repayment_date} onChange={(e) => setV({ ...v, repayment_date: e.target.value })} /></Field>
          <Field label="Receipt ref." htmlFor="rp-r"><Input id="rp-r" value={v.reference} onChange={(e) => setV({ ...v, reference: e.target.value })} /></Field>
        </div>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!ok} loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>Record</Button></div>
      </div>
    </Modal>
  )
}
