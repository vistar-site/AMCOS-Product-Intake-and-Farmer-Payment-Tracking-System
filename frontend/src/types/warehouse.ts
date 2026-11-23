import type { Ref } from './domain'

export type BatchStatus = 'open' | 'closed' | 'dispatched' | 'received' | 'partially_sold' | 'sold'
export interface FarmerMini { id: string; full_name: string; membership_no: string }
export interface BatchMini { id: string; batch_no: string; status: BatchStatus; total_net_weight: string | null }

export interface Batch extends BatchMini {
  crop: Ref; season: { id: string; name: string }; centre: Ref; created_at: string; closed_at: string | null
  notes: string | null
  members: { delivery_id: string; net_weight: string; delivery: { id: string; receipt_no: string; captured_at: string; farmer: FarmerMini } }[]
}
export interface EligibleDelivery { id: string; receipt_no: string; captured_at: string; net_weight: string; farmer: FarmerMini }

export interface Warehouse { id: string; code: string; name: string; operator_name: string | null; licence_no: string | null; location: string | null; is_active: boolean }

export interface ReceiptLine { batch_id: string; received_weight: string; rejected_weight: string; damaged_weight: string; accepted_weight: string }
export interface Dispatch {
  id: string; dispatch_no: string; warehouse: { id: string; code: string; name: string }; dispatch_date: string
  vehicle_reg: string | null; driver_name: string | null; status: 'in_transit' | 'received'; notes: string | null
  lines: { batch_id: string; dispatched_weight: string; batch: BatchMini }[]
  receipt: { id: string; receipt_no: string; receipt_date: string; notes: string | null; lines: ReceiptLine[] } | null
}

export interface Discrepancy {
  id: string; batch: BatchMini; stage: 'batch_to_dispatch' | 'dispatch_to_warehouse' | 'warehouse_rejections'
  expected_weight: string; actual_weight: string; difference: string; status: 'open' | 'explained' | 'accepted'
  explanation: string | null; resolved_at: string | null; created_at: string
}

export interface Reconciliation {
  batch: BatchMini; farmer_deliveries: number; delivered_weight: string; batch_weight: string | null
  dispatched_weight: string | null; received_weight: string | null; rejected_weight: string | null
  damaged_weight: string | null; accepted_weight: string | null; warehouse_receipt_no: string | null
  sold_weight: string; sold_value: string; unsold_weight: string | null; discrepancies: Discrepancy[]
}

export interface Lot {
  id: string; lot_no: string; batch: BatchMini; grade: { id: string; code: string; name: string } | null
  quantity_sold: string; price_per_kg: string; total_value: string; buyer: string | null
}
export interface Auction {
  id: string; auction_ref: string; auction_date: string; venue: string | null; crop: Ref; season: { id: string; name: string }
  status: 'draft' | 'approved'; created_by: string; approved_at: string | null; notes: string | null; lots: Lot[]
}
export interface SellableBatch { id: string; batch_no: string; centre_name: string; available_weight: string }
export interface Allocation {
  delivery_id: string; farmer_id: string; weight_shared: string; weight_absorbed: string; price_per_kg: string
  delivery: { id: string; receipt_no: string; captured_at: string; farmer: FarmerMini }
}

export interface DeliveryTrace {
  delivery_id: string; receipt_no: string; net_weight: string
  batch: { id: string; batch_no: string; status: string; total_net_weight: string | null } | null
  dispatch: { id: string; dispatch_no: string; dispatch_date: string; dispatched_weight: string } | null
  warehouse_receipt: { receipt_no: string; receipt_date: string; received_weight: string; accepted_weight: string } | null
  allocations: { auction_ref: string; auction_date: string; lot_no: string; price_per_kg: string; weight_shared: string; weight_absorbed: string }[]
}

export const BATCH_TONE: Record<BatchStatus, 'blue' | 'slate' | 'amber' | 'green'> = {
  open: 'blue', closed: 'slate', dispatched: 'amber', received: 'amber', partially_sold: 'green', sold: 'green',
}
export const STAGE_LABEL: Record<Discrepancy['stage'], string> = {
  batch_to_dispatch: 'Batch → dispatch', dispatch_to_warehouse: 'Dispatch → warehouse', warehouse_rejections: 'Rejected / damaged',
}
