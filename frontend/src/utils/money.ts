/** Display helpers for money/prices that arrive as decimal strings from the API. */
export function formatTZS(value: string | number, currency = 'TZS'): string {
  const n = typeof value === 'number' ? value : Number(value)
  return `${currency} ${n.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatPrice(value: string): string {
  return `${Number(value).toLocaleString('en-GB', { maximumFractionDigits: 4 })} /kg`
}

/** Exact sum of decimal strings with up to 3 decimals (via integer grams). */
export function sumKg(values: string[]): string {
  const g = values.reduce((acc, v) => acc + Math.round(Number(v) * 1000), 0)
  return (g / 1000).toFixed(3)
}
