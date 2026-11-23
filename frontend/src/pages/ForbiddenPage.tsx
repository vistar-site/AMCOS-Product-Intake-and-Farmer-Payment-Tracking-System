import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

export default function ForbiddenPage() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <ShieldAlert className="mx-auto size-10 text-amber-500" />
      <h1 className="mt-3 text-xl font-semibold">Access denied</h1>
      <p className="mt-1 text-sm text-slate-500">Your role does not include permission to open this page.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">Back to dashboard</Link>
    </div>
  )
}
