import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../context/AuthContext'
import { cachedFetch } from '../../offline/cache'
import type { Centre, Crop, Organization, Season } from '../../types/domain'

/** Reference data: fetched from the API, kept in IndexedDB so the intake screen works offline. */
function useCachedQuery<T>(key: string, path: string) {
  const { user } = useAuth()
  const org = user?.organization_id ?? 'none'
  return useQuery({
    queryKey: [key, org], staleTime: 60_000, enabled: !!user,
    queryFn: () => cachedFetch<T>(`${key}:${org}`, org, path),
  })
}

export const useOrganization = () => useCachedQuery<Organization>('organization', '/organization')
export const useCentres = () => useCachedQuery<Centre[]>('centres', '/centres')
export const useCrops = () => useCachedQuery<Crop[]>('crops', '/crops')
export const useSeasons = () => useCachedQuery<Season[]>('seasons', '/seasons')

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
