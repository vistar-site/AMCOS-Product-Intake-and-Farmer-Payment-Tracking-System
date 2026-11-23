import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { getLocalFarmer, searchFarmersWithFallback } from '../../offline/cache'
import { isNetworkError } from '../../offline/network'
import type { Farmer, FarmerSummary } from '../../types/domain'

export interface FarmerFilters { q?: string; village?: string; centre_id?: string; status?: string; page?: number; page_size?: number }

/** Online: server search. Offline: searches the farmer cache on the device. */
export function useFarmers(f: FarmerFilters, enabled = true) {
  const params = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  return useQuery({
    queryKey: ['farmers', f], enabled, placeholderData: keepPreviousData,
    queryFn: () => searchFarmersWithFallback(params),
  })
}

export const useFarmer = (id: string) =>
  useQuery({
    queryKey: ['farmers', id], enabled: !!id,
    queryFn: async () => {
      try { return await api<Farmer>(`/farmers/${id}`) } catch (e) {
        const local = isNetworkError(e) ? await getLocalFarmer(id) : undefined
        if (local) return local
        throw e
      }
    },
  })

export const useFarmerSummary = (id: string) =>
  useQuery({ queryKey: ['farmers', id, 'summary'], queryFn: () => api<FarmerSummary>(`/farmers/${id}/summary`) })
