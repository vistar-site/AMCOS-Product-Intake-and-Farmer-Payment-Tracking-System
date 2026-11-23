/**
 * Produce intake screen, designed for a phone held by a clerk at the scale.
 * Flow: enter -> review -> saved (receipt). The delivery UUID is created when the
 * form is opened, so pressing "Save" twice (or a network retry) can never create
 * two deliveries — the server treats the second request as the same delivery.
 */
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, FileDown, Plus } from 'lucide-react'
import { api, openFile } from '../api/client'
import { useAuth } from '../context/AuthContext'
import FarmerPicker, { type PickedFarmer } from '../features/deliveries/FarmerPicker'
import type { DeliveryCreateResult } from '../features/deliveries/api'
import { useFarmer } from '../features/farmers/api'
import { useApiMutation, useCentres, useCrops } from '../features/reference/api'
import { fmtDateTime, Select, Textarea } from '../components/form'
import { Alert, Button, Field, Input, PageHeader } from '../components/ui'
import { formatKg, isValidWeight, netWeight, toGrams } from '../utils/weight'
import { readPref, rememberFarmer, writePref } from '../utils/prefs'

interface Draft { farmer: PickedFarmer | null; centreId: string; cropId: string; gradeId: string; gross: string; tare: string; notes: string }

export default function RecordDeliveryPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const centres = useCentres()
  const crops = useCrops()
  const preselected = useFarmer(params.get('farmer') ?? '')
  const activeCentres = useMemo(() => centres.data?.filter((c) => c.status === 'active') ?? [], [centres.data])
  const activeCrops = useMemo(() => crops.data?.filter((c) => c.is_active) ?? [], [crops.data])

  const blank = (): Draft => ({ farmer: null, centreId: readPref('last-centre', ''), cropId: readPref('last-crop', ''),
    gradeId: '', gross: '', tare: '', notes: '' })
  const [draft, setDraft] = useState<Draft>(blank)
  const [deliveryId, setDeliveryId] = useState(() => crypto.randomUUID())
  const [step, setStep] = useState<'enter' | 'review' | 'done'>('enter')
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({})
  const [result, setResult] = useState<DeliveryCreateResult | null>(null)
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }))

  // Sensible defaults: the only centre / the remembered one; remembered crop.
  useEffect(() => {
    if (activeCentres.length && !activeCentres.some((c) => c.id === draft.centreId)) set({ centreId: activeCentres.length === 1 ? activeCentres[0].id : '' })
  }, [activeCentres, draft.centreId])
  useEffect(() => {
    if (activeCrops.length && !activeCrops.some((c) => c.id === draft.cropId)) set({ cropId: activeCrops.length === 1 ? activeCrops[0].id : '' })
  }, [activeCrops, draft.cropId])
  useEffect(() => {
    if (preselected.data && preselected.data.status === 'active' && !draft.farmer) set({ farmer: preselected.data })
  }, [preselected.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const crop = activeCrops.find((c) => c.id === draft.cropId)
  const grades = crop?.grades.filter((g) => g.is_active) ?? []
  const net = netWeight(draft.gross, draft.tare)

  const save = useApiMutation(() => api<DeliveryCreateResult>('/deliveries', {
    method: 'POST',
    json: {
      id: deliveryId, farmer_id: draft.farmer!.id, centre_id: draft.centreId, crop_id: draft.cropId,
      grade_id: draft.gradeId || null, gross_weight: draft.gross, tare_weight: draft.tare || '0',
      captured_at: new Date().toISOString(), notes: draft.notes || null,
    },
  }), ['deliveries', 'farmers'])

  function validate(): boolean {
    const e: typeof errors = {}
    if (!draft.farmer) e.farmer = 'Choose the farmer'
    if (!draft.centreId) e.centreId = 'Choose the collection centre'
    if (!draft.cropId) e.cropId = 'Choose the crop'
    if (!isValidWeight(draft.gross) || toGrams(draft.gross) === 0) e.gross = 'Enter the gross weight in kg (max 3 decimals)'
    if (draft.tare && !isValidWeight(draft.tare)) e.tare = 'Enter the tare in kg'
    if (net?.startsWith('-')) e.tare = 'Tare cannot exceed gross weight'
    else if (net === '0.000') e.tare = 'Net weight must be more than zero'
    if (crop?.rules.max_gross_kg && toGrams(draft.gross)! > toGrams(String(crop.rules.max_gross_kg))!) e.gross = `Over the ${crop.rules.max_gross_kg} kg limit for ${crop.name}`
    if (crop?.rules.max_tare_kg && draft.tare && toGrams(draft.tare)! > toGrams(String(crop.rules.max_tare_kg))!) e.tare = `Over the ${crop.rules.max_tare_kg} kg tare limit`
    if (crop?.rules.grade_required && !draft.gradeId) e.gradeId = 'Grade is required for this crop'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function submit() {
    save.mutate(undefined, {
      onSuccess: (r) => {
        setResult(r)
        setStep('done')
        rememberFarmer(r.delivery.farmer)
        writePref('last-centre', draft.centreId)
        writePref('last-crop', draft.cropId)
      },
    })
  }

  function next() {
    setDraft((d) => ({ ...blank(), centreId: d.centreId, cropId: d.cropId }))
    setDeliveryId(crypto.randomUUID()) // new delivery = new idempotency key
    setResult(null); save.reset(); setStep('enter')
  }

  if (step === 'done' && result) {
    const d = result.delivery
    return (
      <div className="mx-auto max-w-md">
        <div className="rounded-xl bg-white p-6 text-center ring-1 ring-slate-200">
          <CheckCircle2 className="mx-auto size-12 text-brand-600" />
          <h1 className="mt-2 text-xl font-semibold">{result.created ? 'Delivery recorded' : 'Already recorded'}</h1>
          <p className="mt-1 text-sm text-slate-500">Receipt number</p>
          <p className="font-mono text-2xl font-bold tracking-wide">{d.receipt_no}</p>
          <dl className="mt-5 space-y-1.5 text-left text-sm">
            {[['Farmer', `${d.farmer.full_name} (${d.farmer.membership_no})`], ['Crop', d.crop.name + (d.grade ? ` · ${d.grade.code}` : '')],
              ['Gross / tare', `${formatKg(d.gross_weight)} / ${formatKg(d.tare_weight)}`], ['Centre', d.centre.name], ['Time', fmtDateTime(d.captured_at)]]
              .map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt className="text-slate-500">{k}</dt><dd className="text-right">{v}</dd></div>)}
            <div className="flex justify-between border-t border-slate-100 pt-2 text-base"><dt className="font-medium">Net weight</dt><dd className="font-bold">{formatKg(d.net_weight)}</dd></div>
          </dl>
          {result.warnings.map((w) => <div key={w} className="mt-3"><Alert tone="amber">{w}</Alert></div>)}
          <div className="mt-6 grid gap-2">
            <Button className="h-12 text-base" onClick={next}><Plus className="size-5" />Next delivery</Button>
            <Button variant="secondary" onClick={() => openFile(`/deliveries/${d.id}/receipt.pdf`)}><FileDown className="size-4" />Receipt PDF</Button>
          </div>
          <p className="mt-4 text-xs text-slate-400">SMS receipts are sent once the SMS module (Phase 8) is configured.</p>
        </div>
      </div>
    )
  }

  if (step === 'review') {
    const centre = activeCentres.find((c) => c.id === draft.centreId)
    const grade = grades.find((g) => g.id === draft.gradeId)
    return (
      <div className="mx-auto max-w-md">
        <PageHeader title="Confirm delivery" description="Check the details with the farmer before saving." />
        <div className="space-y-2 rounded-xl bg-white p-5 text-sm ring-1 ring-slate-200">
          {[['Farmer', `${draft.farmer!.full_name} · ${draft.farmer!.membership_no}`], ['Centre', centre?.name], ['Crop', crop?.name + (grade ? ` · ${grade.name}` : '')],
            ['Gross weight', formatKg(draft.gross)], ['Tare weight', formatKg(draft.tare || '0')]]
            .map(([k, v]) => <div key={k} className="flex justify-between gap-3"><span className="text-slate-500">{k}</span><span className="text-right font-medium">{v}</span></div>)}
          <div className="flex items-baseline justify-between border-t border-slate-100 pt-3"><span className="font-medium">Net weight</span><span className="text-2xl font-bold">{formatKg(net!)}</span></div>
          {draft.notes && <p className="rounded bg-slate-50 p-2 text-slate-600">{draft.notes}</p>}
        </div>
        {save.error && <div className="mt-3"><Alert>{save.error.message}</Alert></div>}
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button variant="secondary" className="h-12" onClick={() => setStep('enter')} disabled={save.isPending}>Back</Button>
          <Button className="h-12 text-base" loading={save.isPending} onClick={submit}>Save delivery</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Record delivery" description={user?.full_name} />
      {activeCentres.length === 0 && !centres.isLoading && <Alert tone="amber">You are not assigned to an active collection centre. Ask your manager.</Alert>}
      <form noValidate className="space-y-5" onSubmit={(e) => { e.preventDefault(); if (validate()) setStep('review') }}>
        <Field label="Farmer" htmlFor="farmer"><FarmerPicker value={draft.farmer} onChange={(f) => set({ farmer: f })} error={errors.farmer} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Centre" htmlFor="centre" error={errors.centreId}>
            <Select id="centre" className="h-11" value={draft.centreId} invalid={!!errors.centreId} onChange={(e) => set({ centreId: e.target.value })}>
              <option value="">Choose…</option>{activeCentres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <Field label="Crop" htmlFor="crop" error={errors.cropId}>
            <Select id="crop" className="h-11" value={draft.cropId} invalid={!!errors.cropId} onChange={(e) => set({ cropId: e.target.value, gradeId: '' })}>
              <option value="">Choose…</option>{activeCrops.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
        </div>
        {grades.length > 0 && (
          <Field label={`Grade${crop?.rules.grade_required ? '' : ' (optional)'}`} htmlFor="grade" error={errors.gradeId}>
            <div className="flex flex-wrap gap-2" role="radiogroup" id="grade">
              {grades.map((g) => (
                <button type="button" role="radio" aria-checked={draft.gradeId === g.id} key={g.id}
                  onClick={() => set({ gradeId: draft.gradeId === g.id ? '' : g.id })}
                  className={`rounded-md px-3 py-2 text-sm ring-1 ${draft.gradeId === g.id ? 'bg-brand-600 text-white ring-brand-600' : 'bg-white ring-slate-300'}`}>
                  {g.name}
                </button>
              ))}
            </div>
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Gross weight (kg)" htmlFor="gross" error={errors.gross}>
            <Input id="gross" inputMode="decimal" autoComplete="off" className="h-12 text-lg" invalid={!!errors.gross}
              value={draft.gross} onChange={(e) => set({ gross: e.target.value.replace(',', '.') })} />
          </Field>
          <Field label="Tare (kg)" htmlFor="tare" error={errors.tare}>
            <Input id="tare" inputMode="decimal" autoComplete="off" className="h-12 text-lg" placeholder="0" invalid={!!errors.tare}
              value={draft.tare} onChange={(e) => set({ tare: e.target.value.replace(',', '.') })} />
          </Field>
        </div>
        <div className="flex items-baseline justify-between rounded-lg bg-slate-100 px-4 py-3">
          <span className="text-sm text-slate-600">Net weight</span>
          <span className={`text-2xl font-bold ${net?.startsWith('-') ? 'text-red-600' : ''}`}>{net ? formatKg(net) : '—'}</span>
        </div>
        <Field label="Notes (optional)" htmlFor="notes"><Textarea id="notes" rows={2} value={draft.notes} onChange={(e) => set({ notes: e.target.value })} /></Field>
        {Object.keys(errors).length > 0 && <p className="flex items-center gap-1 text-sm text-red-600"><AlertTriangle className="size-4" />Please fix the highlighted fields.</p>}
        <Button type="submit" className="h-12 w-full text-base">Review delivery</Button>
      </form>
    </div>
  )
}
