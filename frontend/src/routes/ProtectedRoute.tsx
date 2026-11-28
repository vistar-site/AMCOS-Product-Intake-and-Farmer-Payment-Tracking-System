/**
 * Route guards. They improve UX (no flashing of forbidden pages); real
 * security is the backend rejecting the API call with 401/403.
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import ForbiddenPage from '../pages/ForbiddenPage'

export function RequireAuth() {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500">
        <Loader2 className="mr-2 size-5 animate-spin" /> Loading…
      </div>
    )
  }
  if (status === 'anonymous') {
    // Visitors at the root see the public landing page; deep links go straight to sign-in.
    if (location.pathname === '/') return <Navigate to="/welcome" replace />
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (status === 'authenticated' && user?.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  return <Outlet />
}

export function RequirePermission({ permission }: { permission: string }) {
  const { can } = useAuth()
  return can(permission) ? <Outlet /> : <ForbiddenPage />
}
