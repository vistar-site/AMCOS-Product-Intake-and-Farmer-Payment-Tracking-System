import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useApiMutation, useOrganization } from '../features/reference/api'
import { Select } from '../components/form'
import { Alert, Button, Field, Input, PageHeader, Skeleton } from '../components/ui'

interface SettingRow { key: string; label: string; type: 'bool' | 'decimal' | 'int' | 'str' | 'choice'; group: string; help: string; choices: string[]; min: number | null; max: number | null; value: unknown }

export default function SettingsPage() {
  const { can } = useAuth()
  const editable = can('settings.manage')
  return (
    <>
      <PageHeader title="Settings" description="AMCOS profile and operational settings. Changes are recorded in the audit trail." />
      <div className="grid gap-6 lg:grid-cols-2">
        <OrgProfile editable={editable} />
        <OperationalSettings editable={editable} />
      </div>
      <p className="mt-6 text-sm text-slate-500">Crops, seasons, collection centres, levies, loans and user roles are managed on their own pages.</p>
    </>
  )
}

function OrgProfile({ editable }: { editable: boolean }) {
  const org = useOrganization()
  const [v, setV] = useState<Record<string, string>>({})
  useEffect(() => {
    if (org.data) setV({ name: org.data.name, registration_no: org.data.registration_no ?? '', region: org.data.region ?? '', district: org.data.district ?? '',
      address: org.data.address ?? '', phone: org.data.phone ?? '', email: org.data.email ?? '' })
  }, [org.data])
  const save = useApiMutation(() => api('/organization', { method: 'PATCH', json: Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x || null])) }), ['organization'])
  if (!org.data) return <Skeleton className="h-64" />
  return (
    <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
      <h2 className="mb-3 font-semibold">Cooperative profile</h2>
      {save.error && <div className="mb-2"><Alert>{save.error.message}</Alert></div>}
      {save.isSuccess && <div className="mb-2"><Alert tone="green">Saved.</Alert></div>}
      <div className="space-y-3">
        {([['name', 'Name'], ['registration_no', 'Registration no.'], ['region', 'Region'], ['district', 'District'], ['address', 'Address'], ['phone', 'Phone'], ['email', 'Email']] as const).map(([k, label]) => (
          <Field key={k} label={label} htmlFor={`o-${k}`}><Input id={`o-${k}`} disabled={!editable} value={v[k] ?? ''} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></Field>
        ))}
        <p className="text-xs text-slate-500">Code {org.data.code} · currency {org.data.currency} · timezone {org.data.timezone}{org.data.is_demo && ' · DEMONSTRATION DATA'}</p>
        {editable && <div className="flex justify-end"><Button loading={save.isPending} onClick={() => save.mutate(undefined)}>Save profile</Button></div>}
      </div>
    </section>
  )
}

function OperationalSettings({ editable }: { editable: boolean }) {
  const q = useQuery({ queryKey: ['settings'], queryFn: () => api<SettingRow[]>('/settings') })
  const [vals, setVals] = useState<Record<string, unknown>>({})
  useEffect(() => { if (q.data) setVals(Object.fromEntries(q.data.map((s) => [s.key, s.value]))) }, [q.data])
  const save = useApiMutation(() => {
    const changed = Object.fromEntries(Object.entries(vals).filter(([k, v]) => q.data?.find((s) => s.key === k)?.value !== v))
    return api('/settings', { method: 'PUT', json: { values: changed } })
  }, ['settings'])
  if (!q.data) return <Skeleton className="h-64" />
  const groups = [...new Set(q.data.map((s) => s.group))]
  return (
    <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
      <h2 className="mb-3 font-semibold">Operational settings</h2>
      {save.error && <div className="mb-2"><Alert>{save.error.message}</Alert></div>}
      {save.isSuccess && <div className="mb-2"><Alert tone="green">Saved.</Alert></div>}
      {groups.map((g) => (
        <fieldset key={g} className="mb-4"><legend className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">{g}</legend>
          <div className="space-y-3">{q.data.filter((s) => s.group === g).map((s) => (
            <div key={s.key}>
              {s.type === 'bool' ? (
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-brand-600" disabled={!editable}
                  checked={!!vals[s.key]} onChange={(e) => setVals({ ...vals, [s.key]: e.target.checked })} />{s.label}</label>
              ) : (
                <Field label={s.label} htmlFor={s.key} hint={s.help || (s.min !== null ? `Between ${s.min} and ${s.max}` : undefined)}>
                  {s.type === 'choice'
                    ? <Select id={s.key} disabled={!editable} value={String(vals[s.key] ?? '')} onChange={(e) => setVals({ ...vals, [s.key]: e.target.value })}>
                        {s.choices.map((c) => <option key={c} value={c}>{c === 'sw' ? 'Kiswahili' : c === 'en' ? 'English' : c}</option>)}</Select>
                    : <Input id={s.key} disabled={!editable} inputMode={s.type === 'str' ? 'text' : 'decimal'} value={String(vals[s.key] ?? '')}
                        onChange={(e) => setVals({ ...vals, [s.key]: s.type === 'int' ? Number(e.target.value) : e.target.value })} />}
                </Field>
              )}
              {s.type === 'bool' && s.help && <p className="ml-6 text-xs text-slate-500">{s.help}</p>}
            </div>
          ))}</div>
        </fieldset>
      ))}
      {editable && <div className="flex justify-end"><Button loading={save.isPending} onClick={() => save.mutate(undefined)}>Save settings</Button></div>}
    </section>
  )
}
