import { forwardRef, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

const base = 'block w-full rounded-md border-0 px-3 py-2 text-sm ring-1 ring-inset focus:ring-2 focus:ring-inset focus:outline-none'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }>(
  ({ className = '', invalid, ...rest }, ref) => (
    <select ref={ref} aria-invalid={invalid || undefined} {...rest}
      className={`${base} pr-8 ${invalid ? 'ring-red-400' : 'ring-slate-300 focus:ring-brand-600'} ${className}`} />
  ),
)

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className = '', ...rest }, ref) => (
    <textarea ref={ref} rows={3} {...rest} className={`${base} ring-slate-300 focus:ring-brand-600 ${className}`} />
  ),
)

export function Pagination({ page, pageSize, total, onPage }:
  { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) return null
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
      <span>{total.toLocaleString()} records · page {page} of {pages}</span>
      <div className="flex gap-2">
        <button className="rounded-md px-3 py-1.5 ring-1 ring-slate-300 disabled:opacity-50" disabled={page <= 1}
          onClick={() => onPage(page - 1)}>Previous</button>
        <button className="rounded-md px-3 py-1.5 ring-1 ring-slate-300 disabled:opacity-50" disabled={page >= pages}
          onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  )
}

export const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { timeZone: 'Africa/Dar_es_Salaam', dateStyle: 'medium', timeStyle: 'short' })
export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-GB', { timeZone: 'Africa/Dar_es_Salaam', dateStyle: 'medium' })
