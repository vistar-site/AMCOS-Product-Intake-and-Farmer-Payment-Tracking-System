import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Page } from '../../types/auth'
import type { Farmer, FarmerSummary } from '../../types/domain'

export interface FarmerFilters { q?: string; village?: string; centre_id?: string; status?: string; page?: number; page_size?: number }

export function useFarmers(f: FarmerFilters, enabled = true) {
  const params = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  return useQuery({
    queryKey: ['farmers', f], enabled, placeholderData: keepPreviousData,
    queryFn: () => api<Page<Farmer>>(`/farmers?${params}`),
  })
}

export const useFarmer = (id: string) =>
  useQuery({ queryKey: ['farmers', id], queryFn: () => api<Farmer>(`/farmers/${id}`), enabled: !!id })

export const useFarmerSummary = (id: string) =>
  useQuery({ queryKey: ['farmers', id, 'summary'], queryFn: () => api<FarmerSummary>(`/farmers/${id}/summary`) })
