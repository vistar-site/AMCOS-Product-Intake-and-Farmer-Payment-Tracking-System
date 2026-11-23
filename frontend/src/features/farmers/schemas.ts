import { z } from 'zod'

const phone = z.string().trim().regex(/^(\+?\d{9,15})?$/, 'Use 0712345678 or +255712345678')

export const farmerSchema = z.object({
  full_name: z.string().trim().min(3, 'Full name is required'),
  membership_no: z.string().trim().regex(/^[A-Za-z0-9/_-]*$/, 'Letters, numbers, / - _ only'),
  phone,
  gender: z.enum(['', 'female', 'male', 'other']),
  village: z.string().trim(),
  ward: z.string().trim(),
  district: z.string().trim(),
  region: z.string().trim(),
  home_centre_id: z.string(),
  payment_method: z.enum(['mobile_money', 'bank', 'cash']),
  mobile_money_number: phone,
  bank_name: z.string().trim(),
  bank_account_no: z.string().trim(),
  notes: z.string().trim().max(2000),
}).superRefine((v, ctx) => {
  if (v.payment_method === 'bank') {
    if (!v.bank_name) ctx.addIssue({ code: 'custom', path: ['bank_name'], message: 'Required for bank payments' })
    if (!v.bank_account_no) ctx.addIssue({ code: 'custom', path: ['bank_account_no'], message: 'Required for bank payments' })
  }
})
export type FarmerValues = z.infer<typeof farmerSchema>

/** Convert form strings to the API body: empty strings become null/omitted. */
export function toFarmerBody(v: FarmerValues) {
  const nul = (s: string) => (s === '' ? null : s)
  return {
    full_name: v.full_name, membership_no: nul(v.membership_no), phone: nul(v.phone), gender: nul(v.gender),
    village: nul(v.village), ward: nul(v.ward), district: nul(v.district), region: nul(v.region),
    home_centre_id: nul(v.home_centre_id), payment_method: v.payment_method,
    mobile_money_number: nul(v.mobile_money_number), bank_name: nul(v.bank_name),
    bank_account_no: nul(v.bank_account_no), notes: nul(v.notes),
  }
}
