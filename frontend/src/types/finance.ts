export interface NameRef { id: string; name: string }
export interface FarmerMini { id: string; full_name: string; membership_no: string }

export interface DeductionType {
  id: string; code: string; name: string; category: 'levy' | 'other'
  calc_method: 'percent_of_gross' | 'per_kg' | 'fixed'; rate: string; applies_per: 'farmer' | 'delivery'
  priority: number; crop: NameRef | null; season: NameRef | null; effective_from: string; effective_to: string | null
  is_active: boolean; description: string | null
}

export interface Loan {
  id: string; loan_ref: string; farmer: FarmerMini; issue_date: string; description: string; principal: string
  max_deduction_percent: string | null; terms: string | null; status: 'active' | 'repaid' | 'written_off'
  repaid: string; outstanding: string
  repayments: { id: string; amount: string; source: 'payout' | 'cash'; repayment_date: string; reference: string | null; reversed: boolean }[]
}

export interface PayoutLine { sort_order: number; line_type: 'earning' | 'levy' | 'loan' | 'other'; description: string; quantity: string | null; rate: string | null; amount: string }
export interface FarmerPayout {
  id: string; farmer: FarmerMini; eligible_weight: string; gross_amount: string; total_deductions: string
  net_payable: string; shortfall: string; status: 'calculated' | 'approved' | 'needs_review' | 'paid' | 'cancelled'
  flags: string[]; lines: PayoutLine[]
}
export interface RunSummary {
  id: string; run_no: string; crop: NameRef; season: NameRef; loss_policy: 'shared' | 'absorbed'
  status: 'calculated' | 'approved' | 'cancelled'; calculated_by: string; calculated_at: string; approved_at: string | null
  cancelled_reason: string | null; total_gross: string; total_deductions: string; total_net: string; notes: string | null
}
export interface Run extends RunSummary { payouts: FarmerPayout[] }

export interface EligiblePayout { payout_id: string; run_no: string; farmer: FarmerMini; net_payable: string; problem: string | null }
export interface Payment {
  id: string; farmer: FarmerMini; farmer_payout_id: string; amount: string; destination: string | null
  destination_bank: string | null; status: 'pending' | 'exported' | 'paid' | 'failed' | 'reversed'
  transaction_ref: string | null; paid_at: string | null; failure_reason: string | null
}
export interface PaymentBatch {
  id: string; batch_no: string; method: 'mobile_money' | 'bank' | 'cash'
  status: 'draft' | 'awaiting_approval' | 'approved' | 'exported' | 'partially_completed' | 'paid' | 'failed' | 'cancelled'
  preparer: { id: string; full_name: string }; prepared_by: string; approved_by: string | null
  submitted_at: string | null; approved_at: string | null; exported_at: string | null; export_count: number
  notes: string | null; created_at: string; payments: Payment[]
}

export interface Statement {
  farmer: FarmerMini
  deliveries: { id: string; receipt_no: string; captured_at: string; crop: NameRef; centre: NameRef; net_weight: string; status: string }[]
  payouts: (Omit<FarmerPayout, 'farmer'> & { run: RunSummary })[]
  payments: { id: string; amount: string; status: string; transaction_ref: string | null; paid_at: string | null; failure_reason: string | null; created_at: string }[]
  loans: Loan[]
  totals: Record<'delivered_kg' | 'eligible_kg' | 'gross' | 'levies' | 'other_deductions' | 'loan_deductions' | 'net_payable' | 'paid' | 'unpaid' | 'held_for_review' | 'loans_outstanding', string>
}

export const PAY_TONE = { pending: 'slate', exported: 'blue', paid: 'green', failed: 'red', reversed: 'amber' } as const
export const BATCH_PAY_TONE = { draft: 'slate', awaiting_approval: 'amber', approved: 'blue', exported: 'blue', partially_completed: 'amber', paid: 'green', failed: 'red', cancelled: 'slate' } as const
export const METHOD_LABEL = { mobile_money: 'Mobile money', bank: 'Bank', cash: 'Cash' } as const
