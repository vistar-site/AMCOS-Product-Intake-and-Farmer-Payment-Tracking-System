/** TanStack Query hooks for users: caching, loading states and refetch after changes. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Page, Role, User } from '../../types/auth'

export interface UserFilters { q: string; role: string; is_active: string; page: number }

export function useUsers(f: UserFilters) {
  const params = new URLSearchParams({ page: String(f.page), page_size: '20' })
  if (f.q) params.set('q', f.q)
  if (f.role) params.set('role', f.role)
  if (f.is_active) params.set('is_active', f.is_active)
  return useQuery({
    queryKey: ['users', f],
    queryFn: () => api<Page<User>>(`/users?${params}`),
    placeholderData: keepPreviousData, // keep showing the old page while the next loads
  })
}

export const useRoles = () => useQuery({ queryKey: ['roles'], queryFn: () => api<Role[]>('/roles'), staleTime: Infinity })

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: object) => api<User>('/users', { method: 'POST', json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useSetUserStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_active, reason }: { id: string; is_active: boolean; reason: string }) =>
      api<User>(`/users/${id}/status`, { method: 'POST', json: { is_active, reason } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}
