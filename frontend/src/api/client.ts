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
let refreshPromise: Promise<boolean> | null = null
let onSessionExpired: () => void = () => {}

export const setAccessToken = (t: string | null) => { accessToken = t }
export const setSessionExpiredHandler = (fn: () => void) => { onSessionExpired = fn }

export async function refreshAccessToken(): Promise<boolean> {
  refreshPromise ??= fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'same-origin' })
    .then(async (r) => {
      if (!r.ok) return false
      setAccessToken((await r.json()).access_token)
      return true
    })
    .catch(() => false)
    .finally(() => { refreshPromise = null })
  return refreshPromise
}

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
    if (await refreshAccessToken()) return api<T>(path, init, false)
    setAccessToken(null)
    onSessionExpired()
  }
  if (!r.ok) throw await parseError(r)
  return (r.status === 204 ? undefined : await r.json()) as T
}
