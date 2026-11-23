import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { changePasswordSchema, type ChangePasswordValues } from '../features/auth/schemas'
import { Alert, Button, Field, Input } from '../components/ui'

export default function ChangePasswordPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<ChangePasswordValues>({ resolver: zodResolver(changePasswordSchema) })

  const onSubmit = async (v: ChangePasswordValues) => {
    setError(null)
    try {
      await api('/auth/change-password', { method: 'POST', json: { current_password: v.current_password, new_password: v.new_password } })
      // All sessions were revoked by the server: sign in again with the new password.
      await logout()
      navigate('/login', { replace: true })
    } catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5 rounded-lg bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <div>
          <h1 className="text-xl font-semibold">Change password</h1>
          {user?.must_change_password && (
            <p className="mt-1 text-sm text-amber-700">You must set a new password before continuing.</p>
          )}
        </div>
        {error && <Alert>{error}</Alert>}
        <Field label="Current password" htmlFor="cur" error={errors.current_password?.message}>
          <Input id="cur" type="password" autoComplete="current-password" {...register('current_password')} />
        </Field>
        <Field label="New password" htmlFor="new" error={errors.new_password?.message} hint="At least 10 characters, letters and numbers">
          <Input id="new" type="password" autoComplete="new-password" {...register('new_password')} />
        </Field>
        <Field label="Confirm new password" htmlFor="confirm" error={errors.confirm?.message}>
          <Input id="confirm" type="password" autoComplete="new-password" {...register('confirm')} />
        </Field>
        <div className="flex gap-2">
          <Button type="submit" loading={isSubmitting}>Update password</Button>
          {!user?.must_change_password && <Button type="button" variant="ghost" onClick={() => navigate(-1)}>Cancel</Button>}
        </div>
      </form>
    </div>
  )
}
