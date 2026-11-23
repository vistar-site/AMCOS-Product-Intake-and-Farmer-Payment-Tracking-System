/**
 * The single place where the frontend talks to the backend.
 *
 * - The access token lives in a module variable (memory only). A page reload
 *   loses it, and we get a new one from /auth/refresh using the httpOnly cookie.
 * - On a 401, we try ONE refresh, then repeat the request. Concurrent 401s share
 *   one refresh call (refreshPromise) so we never rotate the token twice at once.
 */

export class ApiError extends Error {
  status: number
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

let accessToken: string | null = null
let refreshPromise: Promise<RefreshResult> | null = null
let onSessionExpired: () => void = () => {}

export const setAccessToken = (t: string | null) => { accessToken = t }
export const hasAccessToken = () => accessToken !== null
export const setSessionExpiredHandler = (fn: () => void) => { onSessionExpired = fn }

/** 'ok' = new token; 'invalid' = server says log in again; 'network' = server unreachable. */
export type RefreshResult = 'ok' | 'invalid' | 'network'

export async function refreshSession(): Promise<RefreshResult> {
  refreshPromise ??= fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'same-origin' })
    .then(async (r): Promise<RefreshResult> => {
      // A dev proxy with the backend down answers 5xx: treat as unreachable, not as logged out.
      if (r.status >= 500) return 'network'
      if (!r.ok) return 'invalid'
      setAccessToken((await r.json()).access_token)
      return 'ok'
    })
    .catch((): RefreshResult => 'network')
    .finally(() => { refreshPromise = null })
  return refreshPromise
}

export const refreshAccessToken = async () => (await refreshSession()) === 'ok'

async function parseError(r: Response): Promise<ApiError> {
  try {
    const body = await r.json()
    // FastAPI validation errors: detail is a list of {loc, msg}
    const msg = Array.isArray(body.detail)
      ? body.detail.map((d: { msg: string }) => d.msg).join('; ')
      : body.detail ?? r.statusText
    return new ApiError(r.status, msg, body.code)
  } catch {
    return new ApiError(r.status, r.statusText || 'Request failed')
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  let body = init.body
  if (init.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(init.json)
  }

  let r: Response
  try {
    r = await fetch(`/api/v1${path}`, { ...init, headers, body, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection.')
  }

  if (r.status === 401 && retry && !path.startsWith('/auth/login')) {
    const result = await refreshSession()
    if (result === 'ok') return api<T>(path, init, false)
    if (result === 'network') throw new ApiError(0, 'Cannot reach the server. Check your connection.')
    setAccessToken(null)
    onSessionExpired()
  }
  // The Vite dev proxy returns 502/503/504 when the backend is down: same as offline.
  if ([502, 503, 504].includes(r.status)) throw new ApiError(0, 'Cannot reach the server. Check your connection.')
  if (!r.ok) throw await parseError(r)
  return (r.status === 204 ? undefined : await r.json()) as T
}

/** POST/GET a file endpoint and save the response as a download (e.g. payment CSV/Excel). */
export async function downloadFile(path: string, method: 'GET' | 'POST' = 'GET'): Promise<void> {
  const doFetch = () => fetch(`/api/v1${path}`, {
    method, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {}, credentials: 'same-origin',
  })
  let r = await doFetch()
  if (r.status === 401 && await refreshAccessToken()) r = await doFetch()
  if (!r.ok) throw await parseError(r)
  const name = /filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') ?? '')?.[1] ?? 'download'
  const url = URL.createObjectURL(await r.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Download a file (e.g. a PDF) with the auth header and open it in a new tab. */
export async function openFile(path: string): Promise<void> {
  const tab = window.open('', '_blank') // open synchronously so pop-up blockers allow it
  const doFetch = () => fetch(`/api/v1${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {}, credentials: 'same-origin',
  })
  let r = await doFetch()
  if (r.status === 401 && await refreshAccessToken()) r = await doFetch()
  if (!r.ok) { tab?.close(); throw await parseError(r) }
  const url = URL.createObjectURL(await r.blob())
  if (tab) tab.location.href = url
  else window.location.href = url
}
