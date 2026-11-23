import { Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'
import { NAVIGATION } from '../layouts/navigation'
import ChangePasswordPage from '../pages/ChangePasswordPage'
import DashboardPage from '../pages/DashboardPage'
import LoginPage from '../pages/LoginPage'
import PlaceholderPage from '../pages/PlaceholderPage'
import UsersPage from '../pages/UsersPage'
import { RequireAuth, RequirePermission } from './ProtectedRoute'

const BUILT: Record<string, React.ReactNode> = {
  '/': <DashboardPage />,
  '/users': <UsersPage />,
}
const PHASE: Record<string, number> = {
  '/batches': 6, '/warehouse': 6, '/auctions': 6, '/payouts': 7, '/payments': 7,
  '/reports': 8, '/notifications': 8, '/audit': 8, '/settings': 8,
}

export default function AppRoutes() {
  const items = NAVIGATION.flatMap((g) => g.items)
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route element={<AppLayout />}>
          {items.map((i) => (
            <Route key={i.to} element={<RequirePermission permission={i.permission} />}>
              <Route path={i.to} element={BUILT[i.to] ?? <PlaceholderPage title={i.label} phase={PHASE[i.to] ?? 5} />} />
            </Route>
          ))}
          <Route path="*" element={<PlaceholderPage title="Page not found" phase={0} />} />
        </Route>
      </Route>
    </Routes>
  )
}
