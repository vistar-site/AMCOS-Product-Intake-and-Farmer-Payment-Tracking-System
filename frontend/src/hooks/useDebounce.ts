import { useEffect, useState } from 'react'

/** Returns `value` only after it stopped changing for `ms` milliseconds (used for search boxes). */
export function useDebounce<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}
