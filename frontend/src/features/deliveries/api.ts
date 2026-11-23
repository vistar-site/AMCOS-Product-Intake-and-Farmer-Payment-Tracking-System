import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Page } from '../../types/auth'
import type { Amendment, Delivery, DeliveryDetail } from '../../types/domain'

export interface DeliveryFilters {
  q?: string; farmer_id?: string; centre_id?: string; crop_id?: string; season_id?: string
  status?: string; date_from?: string; date_to?: string; mine?: boolean; page?: number; page_size?: number
}
export interface DeliveryPage extends Page<Delivery> { total_net_weight: string }

export function useDeliveries(f: DeliveryFilters) {
  const params = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== '' && v !== false) params.set(k, String(v)) })
  return useQuery({
    queryKey: ['deliveries', f], placeholderData: keepPreviousData,
    queryFn: () => api<DeliveryPage>(`/deliveries?${params}`),
  })
}

export const useDelivery = (id: string) =>
  useQuery({ queryKey: ['deliveries', id], queryFn: () => api<DeliveryDetail>(`/deliveries/${id}`) })

export const usePendingAmendments = (enabled: boolean) =>
  useQuery({ queryKey: ['deliveries', 'pending-amendments'], enabled,
    queryFn: () => api<(Amendment & { delivery: Delivery })[]>('/deliveries/amendments/pending') })

export interface DeliveryCreateResult { delivery: Delivery; created: boolean; warnings: string[] }
