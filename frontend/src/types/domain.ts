/** Types mirroring the backend response schemas. Decimal values arrive as strings. */

export interface Ref { id: string; code: string; name: string }

export interface Organization {
  id: string; name: string; code: string; registration_no: string | null; region: string | null
  district: string | null; address: string | null; phone: string | null; email: string | null
  currency: string; timezone: string; is_demo: boolean
}

export interface Centre {
  id: string; code: string; name: string; village: string | null; ward: string | null
  district: string | null; region: string | null; latitude: string | null; longitude: string | null
  status: 'active' | 'inactive'; users: { id: string; full_name: string; email: string }[]
}

export interface Grade { id: string; code: string; name: string; is_active: boolean }
export interface Crop {
  id: string; code: string; name: string; unit: string; is_active: boolean
  rules: { max_gross_kg?: string; max_tare_kg?: string; grade_required?: boolean }
  grades: Grade[]
}
export interface Season { id: string; name: string; start_date: string; end_date: string; is_active: boolean }

export interface Farmer {
  id: string; membership_no: string; full_name: string; phone: string | null; gender: string | null
  village: string | null; ward: string | null; district: string | null; region: string | null
  home_centre: Ref | null; registration_date: string; status: 'active' | 'inactive' | 'suspended'
  notes: string | null; extra_fields: Record<string, unknown>; created_at: string
  // present only for users with farmer.view_financial
  payment_method?: 'mobile_money' | 'bank' | 'cash'; mobile_money_number?: string | null
  bank_name?: string | null; bank_account_no?: string | null
}

export interface FarmerSummary {
  total_deliveries: number; total_net_weight: string; last_delivery_at: string | null
  by_crop: { crop_code: string; crop_name: string; deliveries: number; net_weight: string }[]
}

export interface Amendment {
  id: string; reason: string; status: 'pending' | 'approved' | 'rejected'
  old_values: Record<string, string | null>; new_values: Record<string, string | null>
  requester: { id: string; full_name: string }; reviewed_at: string | null; review_note: string | null
  created_at: string
}

export interface Delivery {
  id: string; receipt_no: string; provisional_receipt_no: string | null
  farmer: { id: string; membership_no: string; full_name: string; phone: string | null }
  centre: Ref; crop: Ref; grade: Ref | null; season: { id: string; name: string }
  recorder: { id: string; full_name: string }
  gross_weight: string; tare_weight: string; net_weight: string; unit: string
  captured_at: string; received_at: string; source: 'online' | 'offline_sync'
  status: 'recorded' | 'voided'; void_reason: string | null; voided_at: string | null; notes: string | null
}
export interface DeliveryDetail extends Delivery { amendments: Amendment[] }
