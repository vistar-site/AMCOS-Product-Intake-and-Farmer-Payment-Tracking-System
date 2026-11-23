/**
 * Chart building blocks (Recharts), following the dataviz method:
 * - one y-axis per chart, recessive grid, thin marks, 4px rounded bar ends
 * - categorical colours assigned in FIXED order by entity name (never by rank)
 * - tooltip on every chart; a numbers table is always shown alongside (palette contrast WARN)
 */
import type { ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Validated categorical palette (light): see dataviz references/palette.md
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']
export const SINGLE = '#23703c' // brand green for single-series charts

/** Stable colour per entity name, independent of current sort order or filter. */
export function colorFor(name: string, allNames: string[]): string {
  const idx = [...allNames].sort().indexOf(name)
  return SERIES[idx % SERIES.length] ?? SERIES[0]
}

const axis = { stroke: '#94a3b8', fontSize: 11, tickLine: false, axisLine: false } as const
const compact = (n: number) => n.toLocaleString('en-GB', { notation: 'compact', maximumFractionDigits: 1 })

export function ChartCard({ title, subtitle, children, table }: { title: string; subtitle?: string; children: ReactNode; table?: ReactNode }) {
  return (
    <section className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
      <h3 className="font-semibold">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      <div className="mt-3 h-56">{children}</div>
      {table && <details className="mt-2 text-sm"><summary className="cursor-pointer text-xs text-slate-500">Show numbers</summary>{table}</details>}
    </section>
  )
}

export function TimeLine({ data, x, y, unit }: { data: Record<string, unknown>[]; x: string; y: string; unit: string }) {
  return (
    <ResponsiveContainer>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#eef2f6" vertical={false} />
        <XAxis dataKey={x} {...axis} minTickGap={24} />
        <YAxis {...axis} tickFormatter={compact} width={44} />
        <Tooltip formatter={(v: number) => [`${v.toLocaleString('en-GB')} ${unit}`, '']} separator="" cursor={{ stroke: '#cbd5e1' }} />
        <Line type="monotone" dataKey={y} stroke={SINGLE} strokeWidth={2} dot={data.length < 20 ? { r: 4 } : false} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function Bars({ data, x, y, unit, colorBy, horizontal }:
  { data: Record<string, unknown>[]; x: string; y: string; unit: string; colorBy?: string[]; horizontal?: boolean }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} barCategoryGap="25%">
        <CartesianGrid stroke="#eef2f6" vertical={!!horizontal} horizontal={!horizontal} />
        {horizontal ? <>
          <XAxis type="number" {...axis} tickFormatter={compact} />
          <YAxis type="category" dataKey={x} {...axis} width={110} />
        </> : <>
          <XAxis dataKey={x} {...axis} />
          <YAxis {...axis} tickFormatter={compact} width={44} />
        </>}
        <Tooltip formatter={(v: number) => [`${v.toLocaleString('en-GB')} ${unit}`, '']} separator="" cursor={{ fill: '#f1f5f9' }} />
        <Bar dataKey={y} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={36}>
          {data.map((d, i) => <Cell key={i} fill={colorBy ? colorFor(String(d[x]), colorBy) : SINGLE} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** A thin progress bar (paid vs outstanding) — a hero number + bar, not a pie. */
export function Progress({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full bg-slate-100">
        {parts.map((p) => p.value > 0 && <div key={p.label} title={`${p.label}: ${p.value.toLocaleString('en-GB')}`} style={{ width: `${(p.value / total) * 100}%`, background: p.color }} />)}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        {parts.map((p) => <li key={p.label} className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: p.color }} />{p.label}: <b className="text-slate-900">{((p.value / total) * 100).toFixed(1)}%</b></li>)}
      </ul>
    </div>
  )
}

export function NumbersTable({ rows, cols }: { rows: Record<string, unknown>[]; cols: [string, string][] }) {
  return (
    <table className="mt-2 w-full text-xs">
      <thead><tr className="text-left text-slate-500">{cols.map(([k, l]) => <th key={k} className="py-1">{l}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-slate-100">{cols.map(([k]) => <td key={k} className="py-1">{String(r[k] ?? '')}</td>)}</tr>)}</tbody>
    </table>
  )
}
