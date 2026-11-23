import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { CalendarRange, Plus } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useCrops, useSeasons } from '../features/reference/api'
import type { Crop } from '../types/domain'
import { fmtDate } from '../components/form'
import { Alert, Badge, Button, Field, Input, Modal, PageHeader, Skeleton } from '../components/ui'

const optionalKg = z.string().trim().regex(/^(\d+(\.\d{1,3})?)?$/, 'Enter kilograms, e.g. 500')

const cropSchema = z.object({
  code: z.string().trim().min(1).max(20).regex(/^[A-Za-z0-9_-]+$/, 'Letters and numbers only'),
  name: z.string().trim().min(2, 'Name is required'),
  max_gross_kg: optionalKg,
  max_tare_kg: optionalKg,
  grade_required: z.boolean(),
  grades: z.string().trim(), // "STD:Standard, UG:Under grade"
})
type CropValues = z.infer<typeof cropSchema>

const seasonSchema = z.object({
  name: z.string().trim().min(2, 'Name is required'),
  start_date: z.string().min(1, 'Required'),
  end_date: z.string().min(1, 'Required'),
}).refine((v) => v.end_date >= v.start_date, { path: ['end_date'], message: 'Must be after the start date' })
type SeasonValues = z.infer<typeof seasonSchema>

const rulesFrom = (v: { max_gross_kg: string; max_tare_kg: string; grade_required: boolean }) => ({
  ...(v.max_gross_kg ? { max_gross_kg: v.max_gross_kg } : {}),
  ...(v.max_tare_kg ? { max_tare_kg: v.max_tare_kg } : {}),
  grade_required: v.grade_required,
})

export default function CropsPage() {
  const { can } = useAuth()
  const crops = useCrops()
  const seasons = useSeasons()
  const [newCrop, setNewCrop] = useState(false)
  const [newSeason, setNewSeason] = useState(false)
  const [editing, setEditing] = useState<Crop | null>(null)
  const manage = can('crop.manage')
  const toggleSeason = useApiMutation((s: { id: string; is_active: boolean }) =>
    api(`/seasons/${s.id}`, { method: 'PATCH', json: { is_active: !s.is_active } }), ['seasons'])

  return (
    <>
      <PageHeader title="Crops & seasons" description="What this AMCOS buys, accepted grades, intake limits and agricultural seasons."
        actions={manage && <Button onClick={() => setNewCrop(true)}><Plus className="size-4" />New crop</Button>} />
      {crops.isLoading && <Skeleton className="h-40" />}
      <div className="grid gap-4 md:grid-cols-2">
        {crops.data?.map((c) => (
          <div key={c.id} className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
            <div className="flex items-start justify-between">
              <div><p className="text-xs font-medium text-slate-500">{c.code}</p><h3 className="font-semibold">{c.name}</h3></div>
              <Badge tone={c.is_active ? 'green' : 'slate'}>{c.is_active ? 'Accepting' : 'Disabled'}</Badge>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
              <div><dt className="text-slate-500">Unit</dt><dd>{c.unit}</dd></div>
              <div><dt className="text-slate-500">Max gross</dt><dd>{c.rules.max_gross_kg ? `${c.rules.max_gross_kg} kg` : '—'}</dd></div>
              <div><dt className="text-slate-500">Max tare</dt><dd>{c.rules.max_tare_kg ? `${c.rules.max_tare_kg} kg` : '—'}</dd></div>
            </dl>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {c.grades.map((g) => <Badge key={g.id} tone={g.is_active ? 'blue' : 'slate'}>{g.code} · {g.name}</Badge>)}
              {c.grades.length === 0 && <span className="text-sm text-slate-500">No grades</span>}
              {c.rules.grade_required && <Badge tone="amber">Grade required</Badge>}
            </div>
            {manage && <div className="mt-4 border-t border-slate-100 pt-3"><Button variant="secondary" onClick={() => setEditing(c)}>Edit</Button></div>}
          </div>
        ))}
      </div>

      <div className="mb-4 mt-10 flex items-end justify-between">
        <h2 className="text-lg font-semibold">Seasons</h2>
        {manage && <Button variant="secondary" onClick={() => setNewSeason(true)}><CalendarRange className="size-4" />New season</Button>}
      </div>
      {toggleSeason.error && <Alert>{toggleSeason.error.message}</Alert>}
      <div className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-4 py-2">Season</th><th className="px-4 py-2">From</th><th className="px-4 py-2">To</th><th className="px-4 py-2">Status</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {seasons.data?.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2 font-medium">{s.name}</td><td className="px-4 py-2">{fmtDate(s.start_date)}</td>
                <td className="px-4 py-2">{fmtDate(s.end_date)}</td>
                <td className="px-4 py-2"><Badge tone={s.is_active ? 'green' : 'slate'}>{s.is_active ? 'Active' : 'Closed'}</Badge></td>
                <td className="px-4 py-2 text-right">{manage && <Button variant="ghost" onClick={() => toggleSeason.mutate(s)}>{s.is_active ? 'Close' : 'Reopen'}</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <CropModal open={newCrop} onClose={() => setNewCrop(false)} />
      {editing && <EditCropModal crop={editing} onClose={() => setEditing(null)} />}
      <SeasonModal open={newSeason} onClose={() => setNewSeason(false)} />
    </>
  )
}

function CropModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useApiMutation((v: CropValues) => api('/crops', {
    method: 'POST',
    json: {
      code: v.code, name: v.name, rules: rulesFrom(v),
      grades: v.grades.split(',').map((s) => s.trim()).filter(Boolean).map((s) => {
        const [code, ...rest] = s.split(':')
        return { code: code.trim(), name: (rest.join(':') || code).trim() }
      }),
    },
  }), ['crops'])
  const { register, handleSubmit, reset, formState: { errors } } = useForm<CropValues>({
    resolver: zodResolver(cropSchema), defaultValues: { max_gross_kg: '', max_tare_kg: '', grade_required: false, grades: '' },
  })
  const close = () => { reset(); create.reset(); onClose() }
  return (
    <Modal open={open} onClose={close} title="New crop">
      <form noValidate onSubmit={handleSubmit((v) => create.mutate(v, { onSuccess: close }))} className="space-y-4">
        {create.error && <Alert>{create.error.message}</Alert>}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Code" htmlFor="cr-code" error={errors.code?.message}><Input id="cr-code" placeholder="MAIZE" {...register('code')} /></Field>
          <div className="col-span-2"><Field label="Name" htmlFor="cr-name" error={errors.name?.message}><Input id="cr-name" {...register('name')} /></Field></div>
        </div>
        <RuleFields register={register} errors={errors} />
        <Field label="Grades" htmlFor="cr-g" hint="Comma separated CODE:Name, e.g. STD:Standard, UG:Under grade">
          <Input id="cr-g" {...register('grades')} />
        </Field>
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Create crop</Button></div>
      </form>
    </Modal>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RuleFields({ register, errors }: { register: any; errors: any }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Max gross per delivery (kg)" htmlFor="r-g" error={errors.max_gross_kg?.message}><Input id="r-g" inputMode="decimal" {...register('max_gross_kg')} /></Field>
        <Field label="Max tare (kg)" htmlFor="r-t" error={errors.max_tare_kg?.message}><Input id="r-t" inputMode="decimal" {...register('max_tare_kg')} /></Field>
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600" {...register('grade_required')} />Quality grade is required at intake</label>
    </>
  )
}

const editSchema = cropSchema.pick({ name: true, max_gross_kg: true, max_tare_kg: true, grade_required: true })
  .extend({ is_active: z.boolean(), new_grade: z.string().trim() })
type EditValues = z.infer<typeof editSchema>

function EditCropModal({ crop, onClose }: { crop: Crop; onClose: () => void }) {
  const save = useApiMutation(async (v: EditValues) => {
    await api(`/crops/${crop.id}`, { method: 'PATCH', json: { name: v.name, is_active: v.is_active, rules: rulesFrom(v) } })
    if (v.new_grade) {
      const [code, ...rest] = v.new_grade.split(':')
      await api(`/crops/${crop.id}/grades`, { method: 'POST', json: { code: code.trim(), name: (rest.join(':') || code).trim() } })
    }
  }, ['crops'])
  const toggleGrade = useApiMutation((g: { id: string; is_active: boolean }) =>
    api(`/crops/${crop.id}/grades/${g.id}?is_active=${!g.is_active}`, { method: 'PATCH' }), ['crops'])
  const { register, handleSubmit, formState: { errors } } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { name: crop.name, is_active: crop.is_active, max_gross_kg: crop.rules.max_gross_kg ?? '',
      max_tare_kg: crop.rules.max_tare_kg ?? '', grade_required: !!crop.rules.grade_required, new_grade: '' },
  })
  return (
    <Modal open onClose={onClose} title={`Edit ${crop.name}`}>
      <form noValidate onSubmit={handleSubmit((v) => save.mutate(v, { onSuccess: onClose }))} className="space-y-4">
        {(save.error || toggleGrade.error) && <Alert>{(save.error || toggleGrade.error)!.message}</Alert>}
        <Field label="Name" htmlFor="e-name" error={errors.name?.message}><Input id="e-name" {...register('name')} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600" {...register('is_active')} />Accepting deliveries of this crop</label>
        <RuleFields register={register} errors={errors} />
        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-700">Grades (click to enable/disable)</p>
          <div className="flex flex-wrap gap-1.5">
            {crop.grades.map((g) => (
              <button type="button" key={g.id} onClick={() => toggleGrade.mutate(g)}
                className={`rounded-md px-2 py-0.5 text-xs ring-1 ${g.is_active ? 'bg-blue-50 text-blue-700 ring-blue-200' : 'bg-slate-100 text-slate-400 line-through ring-slate-200'}`}>
                {g.code} · {g.name}
              </button>
            ))}
          </div>
        </div>
        <Field label="Add grade" htmlFor="e-g" hint="CODE:Name"><Input id="e-g" {...register('new_grade')} /></Field>
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={save.isPending}>Save</Button></div>
      </form>
    </Modal>
  )
}

function SeasonModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useApiMutation((v: SeasonValues) => api('/seasons', { method: 'POST', json: v }), ['seasons'])
  const { register, handleSubmit, reset, formState: { errors } } = useForm<SeasonValues>({ resolver: zodResolver(seasonSchema) })
  const close = () => { reset(); create.reset(); onClose() }
  return (
    <Modal open={open} onClose={close} title="New season">
      <form noValidate onSubmit={handleSubmit((v) => create.mutate(v, { onSuccess: close }))} className="space-y-4">
        {create.error && <Alert>{create.error.message}</Alert>}
        <Field label="Name" htmlFor="s-name" error={errors.name?.message}><Input id="s-name" placeholder="2027/28" {...register('name')} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Start date" htmlFor="s-from" error={errors.start_date?.message}><Input id="s-from" type="date" {...register('start_date')} /></Field>
          <Field label="End date" htmlFor="s-to" error={errors.end_date?.message}><Input id="s-to" type="date" {...register('end_date')} /></Field>
        </div>
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Create season</Button></div>
      </form>
    </Modal>
  )
}
