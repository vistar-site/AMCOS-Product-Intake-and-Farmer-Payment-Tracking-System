/** Sidebar definition. Each item lists the permission needed to see it. */
import {
  Banknote, BarChart3, RefreshCw, Building2, ClipboardList, FileClock, Gavel, LayoutDashboard, MessageSquare,
  Scale, Settings, Sprout, Truck, Users, UserCog, Warehouse, Wallet, type LucideIcon,
} from 'lucide-react'

export interface NavItem { to: string; label: string; icon: LucideIcon; permission: string; ready?: boolean }
export interface NavGroup { label: string; items: NavItem[] }

export const NAVIGATION: NavGroup[] = [
  { label: 'Overview', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard, permission: 'delivery.view', ready: true },
  ] },
  { label: 'Collection', items: [
    { to: '/deliveries/new', label: 'Record delivery', icon: Scale, permission: 'delivery.create', ready: true },
    { to: '/deliveries', label: 'Deliveries', icon: ClipboardList, permission: 'delivery.view', ready: true },
    { to: '/farmers', label: 'Farmers', icon: Users, permission: 'farmer.view', ready: true },
    { to: '/centres', label: 'Collection centres', icon: Building2, permission: 'centre.view', ready: true },
    { to: '/crops', label: 'Crops & seasons', icon: Sprout, permission: 'crop.view', ready: true },
    { to: '/sync', label: 'Sync status', icon: RefreshCw, permission: 'delivery.create', ready: true },
  ] },
  { label: 'Warehouse & sales', items: [
    { to: '/batches', label: 'Aggregation', icon: Truck, permission: 'auction.view', ready: true },
    { to: '/warehouse', label: 'Warehouse', icon: Warehouse, permission: 'auction.view', ready: true },
    { to: '/auctions', label: 'Auctions', icon: Gavel, permission: 'auction.view', ready: true },
  ] },
  { label: 'Finance', items: [
    { to: '/payouts', label: 'Payouts', icon: Wallet, permission: 'payout.view', ready: true },
    { to: '/payments', label: 'Payments', icon: Banknote, permission: 'payout.view', ready: true },
  ] },
  { label: 'Administration', items: [
    { to: '/reports', label: 'Reports', icon: BarChart3, permission: 'report.operational', ready: true },
    { to: '/sync-review', label: 'Sync review', icon: RefreshCw, permission: 'delivery.amend_approve', ready: true },
    { to: '/notifications', label: 'SMS & notifications', icon: MessageSquare, permission: 'notification.manage', ready: true },
    { to: '/users', label: 'Users', icon: UserCog, permission: 'user.view', ready: true },
    { to: '/audit', label: 'Audit trail', icon: FileClock, permission: 'audit.view', ready: true },
    { to: '/settings', label: 'Settings', icon: Settings, permission: 'centre.view', ready: true },
  ] },
]
