import { useAuth } from '../context/AuthContext'
import { PageHeader } from '../components/ui'

export default function DashboardPage() {
  const { user } = useAuth()
  return (
    <>
      <PageHeader title={`Karibu, ${user?.full_name.split(' ')[0]}`}
        description="Operational dashboard. Metrics appear here as deliveries, auctions and payments are recorded." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <p className="text-sm text-slate-500">Your role</p>
          <p className="mt-1 font-medium">{user?.roles.map((r) => r.name).join(', ')}</p>
        </div>
        <div className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <p className="text-sm text-slate-500">Assigned collection centres</p>
          <p className="mt-1 font-medium">{user?.centres.length ? user.centres.map((c) => c.name).join(', ') : 'All centres'}</p>
        </div>
        <div className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
          <p className="text-sm text-slate-500">Permissions</p>
          <p className="mt-1 font-medium">{user?.permissions.length}</p>
        </div>
      </div>
    </>
  )
}
