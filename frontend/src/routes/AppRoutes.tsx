import { Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'
import { NAVIGATION } from '../layouts/navigation'
import AuditPage from '../pages/AuditPage'
import NotificationsPage from '../pages/NotificationsPage'
import ReportsPage from '../pages/ReportsPage'
import SettingsPage from '../pages/SettingsPage'
import SyncReviewPage from '../pages/SyncReviewPage'
import AuctionDetailPage from '../pages/AuctionDetailPage'
import AuctionsPage from '../pages/AuctionsPage'
import BatchDetailPage from '../pages/BatchDetailPage'
import BatchesPage from '../pages/BatchesPage'
import CentresPage from '../pages/CentresPage'
import ChangePasswordPage from '../pages/ChangePasswordPage'
import CropsPage from '../pages/CropsPage'
import DashboardPage from '../pages/DashboardPage'
import DeliveriesPage from '../pages/DeliveriesPage'
import DeliveryDetailPage from '../pages/DeliveryDetailPage'
import FarmerProfilePage from '../pages/FarmerProfilePage'
import FarmersPage from '../pages/FarmersPage'
import LoginPage from '../pages/LoginPage'
import PaymentBatchPage from '../pages/PaymentBatchPage'
import PaymentsPage from '../pages/PaymentsPage'
import PayoutRunPage from '../pages/PayoutRunPage'
import PayoutsPage from '../pages/PayoutsPage'
import PlaceholderPage from '../pages/PlaceholderPage'
import RecordDeliveryPage from '../pages/RecordDeliveryPage'
import SyncPage from '../pages/SyncPage'
import UsersPage from '../pages/UsersPage'
import WarehousePage from '../pages/WarehousePage'
import { RequireAuth, RequirePermission } from './ProtectedRoute'

const BUILT: Record<string, React.ReactNode> = {
  '/': <DashboardPage />,
  '/users': <UsersPage />,
  '/centres': <CentresPage />,
  '/crops': <CropsPage />,
  '/farmers': <FarmersPage />,
  '/deliveries': <DeliveriesPage />,
  '/deliveries/new': <RecordDeliveryPage />,
  '/sync': <SyncPage />,
  '/batches': <BatchesPage />,
  '/warehouse': <WarehousePage />,
  '/auctions': <AuctionsPage />,
  '/payouts': <PayoutsPage />,
  '/payments': <PaymentsPage />,
  '/reports': <ReportsPage />,
  '/notifications': <NotificationsPage />,
  '/audit': <AuditPage />,
  '/settings': <SettingsPage />,
  '/sync-review': <SyncReviewPage />,
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
          <Route element={<RequirePermission permission="farmer.view" />}>
            <Route path="/farmers/:id" element={<FarmerProfilePage />} />
          </Route>
          <Route element={<RequirePermission permission="delivery.view" />}>
            <Route path="/deliveries/:id" element={<DeliveryDetailPage />} />
          </Route>
          <Route element={<RequirePermission permission="auction.view" />}>
            <Route path="/batches/:id" element={<BatchDetailPage />} />
            <Route path="/auctions/:id" element={<AuctionDetailPage />} />
          </Route>
          <Route element={<RequirePermission permission="payout.view" />}>
            <Route path="/payouts/:id" element={<PayoutRunPage />} />
            <Route path="/payments/:id" element={<PaymentBatchPage />} />
          </Route>
          <Route path="*" element={<PlaceholderPage title="Page not found" phase={0} />} />
        </Route>
      </Route>
    </Routes>
  )
}
