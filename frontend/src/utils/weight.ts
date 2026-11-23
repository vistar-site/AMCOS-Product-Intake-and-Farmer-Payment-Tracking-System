/**
 * Exact weight arithmetic without floating point.
 *
 * JavaScript numbers are binary floats: 82.5 - 0.1 = 82.4 is fine, but
 * 0.1 + 0.2 = 0.30000000000000004. For weights that become money we convert
 * the decimal STRING to integer grams, do integer maths, and convert back.
 * The backend recomputes everything with Decimal anyway; this is for display.
 */

const WEIGHT_RE = /^\d{1,9}(\.\d{0,3})?$/

export function isValidWeight(s: string): boolean {
  return WEIGHT_RE.test(s.trim())
}

/** "82.5" -> 82500 (grams). Returns null for invalid input. */
export function toGrams(s: string): number | null {
  const t = s.trim()
  if (!isValidWeight(t)) return null
  const [whole, frac = ''] = t.split('.')
  return Number(whole) * 1000 + Number(frac.padEnd(3, '0'))
}

/** 82000 -> "82.000" */
export function fromGrams(g: number): string {
  const sign = g < 0 ? '-' : ''
  const abs = Math.abs(g)
  return `${sign}${Math.floor(abs / 1000)}.${String(abs % 1000).padStart(3, '0')}`
}

/** Net weight as a decimal string, or null if inputs are invalid. */
export function netWeight(gross: string, tare: string): string | null {
  const g = toGrams(gross)
  const t = toGrams(tare || '0')
  if (g === null || t === null) return null
  return fromGrams(g - t)
}

/** "1234.500" -> "1,234.5 kg" for display */
export function formatKg(value: string | number, unit = 'kg'): string {
  const n = typeof value === 'number' ? value : Number(value)
  return `${n.toLocaleString('en-GB', { maximumFractionDigits: 3 })} ${unit}`
}
