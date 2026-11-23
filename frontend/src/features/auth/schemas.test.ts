import { describe, expect, it } from 'vitest'
import { changePasswordSchema, createUserSchema, loginSchema } from './schemas'

describe('loginSchema', () => {
  it('accepts a valid email and password', () => {
    expect(loginSchema.safeParse({ email: 'clerk@demo.amcos.test', password: 'x' }).success).toBe(true)
  })
  it('rejects an invalid email', () => {
    const r = loginSchema.safeParse({ email: 'not-an-email', password: 'x' })
    expect(r.success).toBe(false)
  })
  it('rejects an empty password', () => {
    expect(loginSchema.safeParse({ email: 'a@b.co', password: '' }).success).toBe(false)
  })
})

describe('changePasswordSchema', () => {
  it('requires matching confirmation', () => {
    const r = changePasswordSchema.safeParse({ current_password: 'a', new_password: 'Abcdefgh12', confirm: 'Abcdefgh13' })
    expect(r.success).toBe(false)
  })
  it('rejects letters-only passwords', () => {
    const r = changePasswordSchema.safeParse({ current_password: 'a', new_password: 'abcdefghijkl', confirm: 'abcdefghijkl' })
    expect(r.success).toBe(false)
  })
})

describe('createUserSchema', () => {
  const base = { full_name: 'Juma', email: 'j@x.co', phone: '', role_code: 'clerk', temporary_password: 'Passw0rd123' }
  it('allows empty phone', () => expect(createUserSchema.safeParse(base).success).toBe(true))
  it('rejects malformed phone', () => expect(createUserSchema.safeParse({ ...base, phone: '0712-abc' }).success).toBe(false))
})
