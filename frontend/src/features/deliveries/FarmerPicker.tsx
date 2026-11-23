import { useState } from 'react'
import { Search, UserRound, X } from 'lucide-react'
import { useFarmers } from '../farmers/api'
import { useDebounce } from '../../hooks/useDebounce'
import { readPref, type RecentFarmer } from '../../utils/prefs'
import { Input } from '../../components/ui'

export interface PickedFarmer { id: string; full_name: string; membership_no: string; village?: string | null }

/** Fast farmer lookup: recent farmers one tap away, search by name / member no. / phone. */
export default function FarmerPicker({ value, onChange, error }:
  { value: PickedFarmer | null; onChange: (f: PickedFarmer | null) => void; error?: string }) {
  const [q, setQ] = useState('')
  const term = useDebounce(q.trim(), 250)
  const results = useFarmers({ q: term, status: 'active', page_size: 8 }, term.length >= 2)
  const recent = readPref<RecentFarmer[]>('recent-farmers', [])

  if (value) {
    return (
      <div className="flex items-center gap-3 rounded-lg bg-brand-50 p-3 ring-1 ring-brand-100">
        <UserRound className="size-8 rounded-full bg-white p-1.5 text-brand-600" />
        <div className="flex-1"><p className="font-semibold">{value.full_name}</p><p className="text-sm text-slate-600">{value.membership_no}{value.village ? ` · ${value.village}` : ''}</p></div>
        <button type="button" onClick={() => onChange(null)} className="rounded-md p-2 text-slate-500 hover:bg-white" aria-label="Change farmer"><X className="size-5" /></button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-3.5 size-5 text-slate-400" />
        <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} invalid={!!error}
          placeholder="Search name, member no. or phone" aria-label="Search farmer" className="h-12 pl-10 text-base" />
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {term.length >= 2 ? (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
          {results.isFetching && !results.data && <li className="p-3 text-sm text-slate-500">Searching…</li>}
          {results.data?.items.map((f) => (
            <li key={f.id}><button type="button" onClick={() => onChange(f)} className="w-full px-3 py-3 text-left hover:bg-slate-50">
              <span className="font-medium">{f.full_name}</span>
              <span className="block text-sm text-slate-500">{f.membership_no} · {f.village ?? '—'} · {f.phone ?? 'no phone'}</span>
            </button></li>
          ))}
          {results.data?.items.length === 0 && <li className="p-3 text-sm text-slate-500">No active farmer matches “{term}”.</li>}
        </ul>
      ) : recent.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Recent</p>
          <div className="flex flex-wrap gap-2">
            {recent.map((f) => (
              <button type="button" key={f.id} onClick={() => onChange(f)}
                className="rounded-full bg-white px-3 py-1.5 text-sm ring-1 ring-slate-300 hover:bg-slate-50">{f.full_name}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
