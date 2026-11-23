import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Centre, Crop, Organization, Season } from '../../types/domain'

export const useOrganization = () =>
  useQuery({ queryKey: ['organization'], queryFn: () => api<Organization>('/organization'), staleTime: 300_000 })

export const useCentres = () =>
  useQuery({ queryKey: ['centres'], queryFn: () => api<Centre[]>('/centres'), staleTime: 60_000 })

export const useCrops = () =>
  useQuery({ queryKey: ['crops'], queryFn: () => api<Crop[]>('/crops'), staleTime: 60_000 })

export const useSeasons = () =>
  useQuery({ queryKey: ['seasons'], queryFn: () => api<Season[]>('/seasons'), staleTime: 60_000 })

/** Generic mutation that refreshes the given query keys afterwards. */
export function useApiMutation<TBody, TResult = unknown>(
  request: (body: TBody) => Promise<TResult>, invalidate: string[],
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: () => Promise.all(invalidate.map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  })
}
