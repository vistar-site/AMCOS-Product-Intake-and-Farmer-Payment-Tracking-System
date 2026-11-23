/**
 * Small per-device conveniences in localStorage (last centre/crop, recent farmers).
 * NOT business data: losing it only costs a few taps. Every access is wrapped in
 * try/catch because storage can be blocked (private mode, full disk).
 */
export function readPref<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`amcos:${key}`)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch { return fallback }
}

export function writePref(key: string, value: unknown): void {
  try { localStorage.setItem(`amcos:${key}`, JSON.stringify(value)) } catch { /* ignore */ }
}

export interface RecentFarmer { id: string; full_name: string; membership_no: string }

export function rememberFarmer(f: RecentFarmer): void {
  const list = readPref<RecentFarmer[]>('recent-farmers', []).filter((x) => x.id !== f.id)
  writePref('recent-farmers', [{ id: f.id, full_name: f.full_name, membership_no: f.membership_no }, ...list].slice(0, 8))
}
