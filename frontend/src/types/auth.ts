export interface Role { id: string; code: string; name: string }
export interface CentreRef { id: string; code: string; name: string }

export interface User {
  id: string
  organization_id: string | null
  email: string
  full_name: string
  phone: string | null
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  locked_until: string | null
  created_at: string
  roles: Role[]
  centres: CentreRef[]
}

export interface Me extends User { permissions: string[] }

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
