import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { CloudOff, KeyRound, LogOut, Menu, RefreshCw, Sprout, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useSync } from '../context/SyncContext'
import { NAVIGATION } from './navigation'

export default function AppLayout() {
  const { user, can, logout, status } = useAuth()
  const { online, syncing, counts } = useSync()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const unsynced = counts.pending + counts.rejected + counts.conflict

  async function handleLogout() {
    if (unsynced > 0 && !window.confirm(
      `${unsynced} delivery record(s) on this device have not reached the server.\n\n` +
      'They stay on this device and will upload the next time YOU sign in here. Log out anyway?')) return
    await logout()
    navigate('/login')
  }

  // Only show groups/items the user is permitted to use.
  const groups = NAVIGATION
    .map((g) => ({ ...g, items: g.items.filter((i) => can(i.permission)) }))
    .filter((g) => g.items.length > 0)

  const sidebar = (
    <nav aria-label="Main" className="flex h-full flex-col gap-6 overflow-y-auto px-3 py-5">
      <div className="flex items-center gap-2 px-2 text-white">
        <span className="grid size-8 place-items-center rounded-md bg-brand-500"><Sprout className="size-5" /></span>
        <div className="leading-tight">
          <p className="text-sm font-semibold">AMCOS</p>
          <p className="text-xs text-brand-100/70">Produce &amp; Payments</p>
        </div>
      </div>
      {groups.map((g) => (
        <div key={g.label}>
          <p className="px-2 pb-1 text-xs font-medium uppercase tracking-wider text-brand-100/60">{g.label}</p>
          <ul className="space-y-0.5">
            {g.items.map(({ to, label, icon: Icon, ready }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/' || to === '/deliveries'}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-md px-2 py-1.5 text-sm ${
                      isActive ? 'bg-white/15 font-medium text-white' : 'text-brand-50/85 hover:bg-white/10 hover:text-white'}`}
                >
                  <Icon className="size-4 shrink-0" aria-hidden />
                  <span className="flex-1">{label}</span>
                  {!ready && <span className="text-[10px] text-brand-100/50">soon</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )

  return (
    <div className="min-h-screen lg:pl-64 print:pl-0">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 bg-brand-900 lg:block print:hidden">{sidebar}</aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-brand-900">
            <button className="absolute right-2 top-4 p-1 text-white" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <header className="print:hidden sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur">
        <button className="p-1 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="size-5" /></button>
        <div className="flex-1" />
        <NavLink to="/sync" title="Sync status"
          className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${
            !online || status === 'offline' ? 'bg-amber-50 text-amber-800 ring-amber-200'
              : unsynced ? 'bg-blue-50 text-blue-700 ring-blue-200' : 'bg-green-50 text-green-700 ring-green-200'}`}>
          {!online || status === 'offline' ? <CloudOff className="size-3.5" /> : <RefreshCw className={`size-3.5 ${syncing ? 'animate-spin' : ''}`} />}
          {!online ? 'Offline' : status === 'offline' ? 'Reconnecting' : 'Online'}
          {unsynced > 0 && <span className="rounded-full bg-white/80 px-1.5">{unsynced} unsynced</span>}
        </NavLink>
        <div className="hidden text-right leading-tight sm:block">
          <p className="text-sm font-medium">{user?.full_name}</p>
          <p className="text-xs text-slate-500">{user?.roles.map((r) => r.name).join(', ')}</p>
        </div>
        <button onClick={() => navigate('/change-password')} className="rounded-md p-2 text-slate-500 hover:bg-slate-100"
          title="Change password" aria-label="Change password"><KeyRound className="size-4" /></button>
        <button onClick={handleLogout}
          className="rounded-md p-2 text-slate-500 hover:bg-slate-100" title="Log out" aria-label="Log out">
          <LogOut className="size-4" />
        </button>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8"><Outlet /></main>
    </div>
  )
}
