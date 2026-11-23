import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { MapPin, Plus, Users } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useCentres } from '../features/reference/api'
import { useUsers } from '../features/users/api'
import type { Centre } from '../types/domain'
import { Alert, Badge, Button, EmptyState, Field, Input, Modal, PageHeader, Skeleton } from '../components/ui'

const centreSchema = z.object({
  code: z.string().trim().min(1, 'Code is required').max(20).regex(/^[A-Za-z0-9_-]+$/, 'Letters, numbers, - and _ only'),
  name: z.string().trim().min(2, 'Name is required'),
  village: z.string().trim().optional(),
  ward: z.string().trim().optional(),
  district: z.string().trim().optional(),
  region: z.string().trim().optional(),
})
type CentreValues = z.infer<typeof centreSchema>

export default function CentresPage() {
  const { can } = useAuth()
  const { data, isLoading, error } = useCentres()
  const [creating, setCreating] = useState(false)
  const [staffFor, setStaffFor] = useState<Centre | null>(null)
  const toggle = useApiMutation((c: Centre) => api(`/centres/${c.id}`, {
    method: 'PATCH', json: { status: c.status === 'active' ? 'inactive' : 'active' },
  }), ['centres'])

  return (
    <>
      <PageHeader title="Collection centres" description="Village collection points and the staff assigned to them."
        actions={can('centre.manage') && <Button onClick={() => setCreating(true)}><Plus className="size-4" />New centre</Button>} />
      {error && <Alert>{(error as Error).message}</Alert>}
      {toggle.error && <Alert>{toggle.error.message}</Alert>}
      {isLoading && <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-36" />)}</div>}
      {data?.length === 0 && <EmptyState title="No collection centres yet" description="Register the first collection point to start recording deliveries." />}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((c) => (
          <div key={c.id} className="flex flex-col rounded-lg bg-white p-5 ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-xs font-medium text-slate-500">{c.code}</p>
                <h3 className="font-semibold">{c.name}</h3>
              </div>
              <Badge tone={c.status === 'active' ? 'green' : 'slate'}>{c.status}</Badge>
            </div>
            <p className="mt-2 flex items-center gap-1 text-sm text-slate-600">
              <MapPin className="size-3.5" />{[c.village, c.ward, c.district, c.region].filter(Boolean).join(', ') || 'Location not set'}
            </p>
            <p className="mt-3 flex items-center gap-1 text-sm text-slate-600">
              <Users className="size-3.5" />{c.users.length ? c.users.map((u) => u.full_name).join(', ') : 'No staff assigned'}
            </p>
            {can('centre.manage') && (
              <div className="mt-4 flex gap-2 border-t border-slate-100 pt-3">
                <Button variant="secondary" onClick={() => setStaffFor(c)}>Assign staff</Button>
                <Button variant="ghost" loading={toggle.isPending && toggle.variables?.id === c.id} onClick={() => toggle.mutate(c)}>
                  {c.status === 'active' ? 'Deactivate' : 'Activate'}
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
      <CreateCentreModal open={creating} onClose={() => setCreating(false)} />
      {staffFor && <StaffModal centre={staffFor} onClose={() => setStaffFor(null)} />}
    </>
  )
}

function CreateCentreModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useApiMutation((b: CentreValues) => api('/centres', { method: 'POST', json: b }), ['centres'])
  const { register, handleSubmit, reset, formState: { errors } } = useForm<CentreValues>({ resolver: zodResolver(centreSchema) })
  const close = () => { reset(); create.reset(); onClose() }
  return (
    <Modal open={open} onClose={close} title="New collection centre">
      <form noValidate onSubmit={handleSubmit((v) => create.mutate(v, { onSuccess: close }))} className="space-y-4">
        {create.error && <Alert>{create.error.message}</Alert>}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Code" htmlFor="c-code" error={errors.code?.message}><Input id="c-code" placeholder="MTW-04" {...register('code')} /></Field>
          <div className="col-span-2"><Field label="Name" htmlFor="c-name" error={errors.name?.message}><Input id="c-name" {...register('name')} /></Field></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Village" htmlFor="c-v"><Input id="c-v" {...register('village')} /></Field>
          <Field label="Ward" htmlFor="c-w"><Input id="c-w" {...register('ward')} /></Field>
          <Field label="District" htmlFor="c-d"><Input id="c-d" {...register('district')} /></Field>
          <Field label="Region" htmlFor="c-r"><Input id="c-r" {...register('region')} /></Field>
        </div>
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Create centre</Button></div>
      </form>
    </Modal>
  )
}

function StaffModal({ centre, onClose }: { centre: Centre; onClose: () => void }) {
  const { data } = useUsers({ q: '', role: '', is_active: 'true', page: 1 })
  const [selected, setSelected] = useState<Set<string>>(new Set(centre.users.map((u) => u.id)))
  const save = useApiMutation((ids: string[]) => api(`/centres/${centre.id}/staff`, { method: 'PUT', json: { user_ids: ids } }), ['centres', 'users'])
  const staff = data?.items.filter((u) => u.roles.some((r) => ['clerk', 'manager', 'warehouse_officer'].includes(r.code))) ?? []
  return (
    <Modal open onClose={onClose} title={`Staff at ${centre.name}`}>
      <div className="space-y-3">
        {save.error && <Alert>{save.error.message}</Alert>}
        <p className="text-sm text-slate-500">Clerks can only record deliveries at centres they are assigned to.</p>
        <ul className="max-h-72 divide-y divide-slate-100 overflow-y-auto rounded-md ring-1 ring-slate-200">
          {staff.map((u) => (
            <li key={u.id}>
              <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-slate-50">
                <input type="checkbox" className="size-4 accent-brand-600" checked={selected.has(u.id)}
                  onChange={(e) => {
                    const next = new Set(selected)
                    if (e.target.checked) next.add(u.id); else next.delete(u.id)
                    setSelected(next)
                  }} />
                <span className="flex-1 text-sm"><span className="font-medium">{u.full_name}</span>
                  <span className="block text-slate-500">{u.roles.map((r) => r.name).join(', ')}</span></span>
              </label>
            </li>
          ))}
        </ul>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={save.isPending} onClick={() => save.mutate([...selected], { onSuccess: onClose })}>Save</Button></div>
      </div>
    </Modal>
  )
}
