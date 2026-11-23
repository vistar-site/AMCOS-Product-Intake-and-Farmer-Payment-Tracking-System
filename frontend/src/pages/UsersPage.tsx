import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Plus, Search } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { createUserSchema, type CreateUserValues } from '../features/auth/schemas'
import { useCreateUser, useRoles, useSetUserStatus, useUsers, type UserFilters } from '../features/users/api'
import type { User } from '../types/auth'
import { Alert, Badge, Button, EmptyState, Field, Input, Modal, PageHeader, Skeleton } from '../components/ui'

const selectCls = 'rounded-md border-0 py-2 pl-3 pr-8 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600'

function statusBadge(u: User) {
  if (!u.is_active) return <Badge tone="red">Inactive</Badge>
  if (u.locked_until && new Date(u.locked_until) > new Date()) return <Badge tone="amber">Locked</Badge>
  if (u.must_change_password) return <Badge tone="blue">Pending first login</Badge>
  return <Badge tone="green">Active</Badge>
}

export default function UsersPage() {
  const { can, user: me } = useAuth()
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState<UserFilters>({ q: '', role: '', is_active: '', page: 1 })
  const [creating, setCreating] = useState(false)
  const [toggling, setToggling] = useState<User | null>(null)
  const { data, isLoading, isError, error } = useUsers(filters)
  const { data: roles } = useRoles()

  // Debounce search typing: query the API 300 ms after the user stops typing.
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => (f.q === search ? f : { ...f, q: search, page: 1 })), 300)
    return () => clearTimeout(t)
  }, [search])

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader title="Users" description="Staff accounts, roles and collection-centre assignments."
        actions={can('user.manage') && <Button onClick={() => setCreating(true)}><Plus className="size-4" />New user</Button>} />

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
          <Input placeholder="Search name or email" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" aria-label="Search users" />
        </div>
        <select className={selectCls} value={filters.role} aria-label="Filter by role"
          onChange={(e) => setFilters({ ...filters, role: e.target.value, page: 1 })}>
          <option value="">All roles</option>
          {roles?.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
        </select>
        <select className={selectCls} value={filters.is_active} aria-label="Filter by status"
          onChange={(e) => setFilters({ ...filters, is_active: e.target.value, page: 1 })}>
          <option value="">Any status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {isError && <Alert>{(error as Error).message}</Alert>}

      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Name</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Centres</th>
              <th className="px-4 py-3">Last login</th><th className="px-4 py-3">Status</th><th className="px-4 py-3" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}><td colSpan={6} className="px-4 py-3"><Skeleton className="h-5 w-full" /></td></tr>
            ))}
            {data?.items.map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-4 py-3"><p className="font-medium">{u.full_name}</p><p className="text-slate-500">{u.email}</p></td>
                <td className="px-4 py-3">{u.roles.map((r) => r.name).join(', ')}</td>
                <td className="px-4 py-3 text-slate-600">{u.centres.map((c) => c.name).join(', ') || '—'}</td>
                <td className="px-4 py-3 text-slate-600">{u.last_login_at ? new Date(u.last_login_at).toLocaleString('en-GB', { timeZone: 'Africa/Dar_es_Salaam' }) : 'Never'}</td>
                <td className="px-4 py-3">{statusBadge(u)}</td>
                <td className="px-4 py-3 text-right">
                  {can('user.manage') && u.id !== me?.id && (
                    <Button variant={u.is_active ? 'secondary' : 'primary'} onClick={() => setToggling(u)}>
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.items.length === 0 && <div className="p-4"><EmptyState title="No users match these filters" /></div>}
      </div>

      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>{data.total} users · page {data.page} of {pages}</span>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Previous</Button>
            <Button variant="secondary" disabled={filters.page >= pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Next</Button>
          </div>
        </div>
      )}

      <CreateUserModal open={creating} onClose={() => setCreating(false)} />
      <StatusModal user={toggling} onClose={() => setToggling(null)} />
    </>
  )
}

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: roles } = useRoles()
  const create = useCreateUser()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateUserValues>({
    resolver: zodResolver(createUserSchema), defaultValues: { phone: '' },
  })
  const close = () => { reset(); create.reset(); onClose() }

  const onSubmit = (v: CreateUserValues) => create.mutate(
    { email: v.email, full_name: v.full_name, phone: v.phone || null, role_codes: [v.role_code], temporary_password: v.temporary_password },
    { onSuccess: close },
  )

  return (
    <Modal open={open} onClose={close} title="New user">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        {create.error && <Alert>{create.error.message}</Alert>}
        <Field label="Full name" htmlFor="u-name" error={errors.full_name?.message}><Input id="u-name" {...register('full_name')} /></Field>
        <Field label="Email" htmlFor="u-email" error={errors.email?.message}><Input id="u-email" type="email" {...register('email')} /></Field>
        <Field label="Phone (optional)" htmlFor="u-phone" error={errors.phone?.message}><Input id="u-phone" placeholder="+255712345678" {...register('phone')} /></Field>
        <Field label="Role" htmlFor="u-role" error={errors.role_code?.message}>
          <select id="u-role" className={`${selectCls} w-full`} {...register('role_code')}>
            <option value="">Choose…</option>
            {roles?.filter((r) => r.code !== 'system_admin').map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </select>
        </Field>
        <Field label="Temporary password" htmlFor="u-pw" error={errors.temporary_password?.message}
          hint="Share it securely. The user must change it on first login.">
          <Input id="u-pw" type="text" autoComplete="off" {...register('temporary_password')} />
        </Field>
        <p className="text-xs text-slate-500">Collection-centre assignment is added with the Centres module (Phase 5).</p>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={close}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Create user</Button>
        </div>
      </form>
    </Modal>
  )
}

/** Confirmation dialog for a sensitive action; a reason is required and audited. */
function StatusModal({ user, onClose }: { user: User | null; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const mutation = useSetUserStatus()
  const close = () => { setReason(''); mutation.reset(); onClose() }
  if (!user) return <Modal open={false} onClose={close} title="">{null}</Modal>
  const activating = !user.is_active
  return (
    <Modal open onClose={close} title={`${activating ? 'Activate' : 'Deactivate'} ${user.full_name}?`}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          {activating ? 'The user will be able to sign in again.' : 'The user will be signed out and unable to sign in. Their records are kept.'}
        </p>
        {mutation.error && <Alert>{mutation.error.message}</Alert>}
        <Field label="Reason (recorded in the audit trail)" htmlFor="reason">
          <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>Cancel</Button>
          <Button variant={activating ? 'primary' : 'danger'} disabled={reason.trim().length < 3} loading={mutation.isPending}
            onClick={() => mutation.mutate({ id: user.id, is_active: activating, reason }, { onSuccess: close })}>
            {activating ? 'Activate' : 'Deactivate'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
