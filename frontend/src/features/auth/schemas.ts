/**
 * Zod schemas = frontend validation rules. They mirror the backend rules so the
 * user gets instant feedback; the backend still validates again (never trust the client).
 */
import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})
export type LoginValues = z.infer<typeof loginSchema>

const strongPassword = z.string()
  .min(10, 'At least 10 characters')
  .refine((v) => /[a-zA-Z]/.test(v) && /[0-9]/.test(v), 'Must contain letters and numbers')

export const changePasswordSchema = z.object({
  current_password: z.string().min(1, 'Current password is required'),
  new_password: strongPassword,
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, { message: 'Passwords do not match', path: ['confirm'] })
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>

export const createUserSchema = z.object({
  full_name: z.string().trim().min(2, 'Name is required'),
  email: z.string().trim().email('Enter a valid email address'),
  phone: z.string().trim().regex(/^\+?[0-9]{9,15}$/, 'Use format +255712345678').or(z.literal('')),
  role_code: z.string().min(1, 'Choose a role'),
  temporary_password: strongPassword,
})
export type CreateUserValues = z.infer<typeof createUserSchema>
