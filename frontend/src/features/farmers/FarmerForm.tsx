import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useAuth } from '../../context/AuthContext'
import { useCentres } from '../reference/api'
import { Select, Textarea } from '../../components/form'
import { Alert, Button, Field, Input } from '../../components/ui'
import type { Farmer } from '../../types/domain'
import { farmerSchema, type FarmerValues } from './schemas'

const emptyValues: FarmerValues = {
  full_name: '', membership_no: '', phone: '', gender: '', village: '', ward: '', district: '', region: '',
  home_centre_id: '', payment_method: 'mobile_money', mobile_money_number: '', bank_name: '', bank_account_no: '', notes: '',
}

export function farmerToValues(f: Farmer): FarmerValues {
  return {
    full_name: f.full_name, membership_no: f.membership_no, phone: f.phone ?? '', gender: (f.gender ?? '') as FarmerValues['gender'],
    village: f.village ?? '', ward: f.ward ?? '', district: f.district ?? '', region: f.region ?? '',
    home_centre_id: f.home_centre?.id ?? '', payment_method: f.payment_method ?? 'mobile_money',
    mobile_money_number: f.mobile_money_number ?? '', bank_name: f.bank_name ?? '', bank_account_no: f.bank_account_no ?? '',
    notes: f.notes ?? '',
  }
}

export default function FarmerForm({ initial, editing, onSubmit, onCancel, submitting, error }: {
  initial?: FarmerValues; editing?: boolean; onSubmit: (v: FarmerValues) => void; onCancel: () => void
  submitting: boolean; error?: string
}) {
  const { can } = useAuth()
  const { data: centres } = useCentres()
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FarmerValues>({
    resolver: zodResolver(farmerSchema), defaultValues: initial ?? emptyValues,
  })
  const method = watch('payment_method')
  const financial = can('farmer.view_financial')

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <Field label="Full name" htmlFor="f-name" error={errors.full_name?.message}><Input id="f-name" autoFocus {...register('full_name')} /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Membership no." htmlFor="f-mem" error={errors.membership_no?.message} hint={editing ? undefined : 'Leave blank to assign automatically'}>
          <Input id="f-mem" disabled={editing} {...register('membership_no')} />
        </Field>
        <Field label="Phone" htmlFor="f-phone" error={errors.phone?.message}><Input id="f-phone" inputMode="tel" placeholder="0712345678" {...register('phone')} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Gender (optional)" htmlFor="f-g">
          <Select id="f-g" {...register('gender')}><option value="">Not recorded</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></Select>
        </Field>
        <Field label="Home collection centre" htmlFor="f-c">
          <Select id="f-c" {...register('home_centre_id')}><option value="">—</option>{centres?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Village" htmlFor="f-v"><Input id="f-v" {...register('village')} /></Field>
        <Field label="Ward" htmlFor="f-w"><Input id="f-w" {...register('ward')} /></Field>
        <Field label="District" htmlFor="f-d"><Input id="f-d" {...register('district')} /></Field>
        <Field label="Region" htmlFor="f-r"><Input id="f-r" {...register('region')} /></Field>
      </div>
      {(financial || !editing) && (
        <fieldset className="space-y-3 rounded-md border border-slate-200 p-3">
          <legend className="px-1 text-sm font-medium text-slate-700">Payment details</legend>
          <Field label="Payment method" htmlFor="f-pm">
            <Select id="f-pm" {...register('payment_method')}>
              <option value="mobile_money">Mobile money</option>
              {financial && <option value="bank">Bank account</option>}
              <option value="cash">Cash</option>
            </Select>
          </Field>
          {method === 'mobile_money' && (
            <Field label="Mobile money number" htmlFor="f-mm" error={errors.mobile_money_number?.message} hint="Defaults to the phone number">
              <Input id="f-mm" inputMode="tel" {...register('mobile_money_number')} />
            </Field>
          )}
          {method === 'bank' && financial && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Bank" htmlFor="f-bn" error={errors.bank_name?.message}><Input id="f-bn" {...register('bank_name')} /></Field>
              <Field label="Account no." htmlFor="f-ba" error={errors.bank_account_no?.message}><Input id="f-ba" {...register('bank_account_no')} /></Field>
            </div>
          )}
        </fieldset>
      )}
      <Field label="Notes" htmlFor="f-n"><Textarea id="f-n" {...register('notes')} /></Field>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={submitting}>{editing ? 'Save changes' : 'Register farmer'}</Button>
      </div>
    </form>
  )
}
