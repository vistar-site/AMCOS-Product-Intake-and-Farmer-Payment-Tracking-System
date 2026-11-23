import type { PayoutLine } from '../../types/finance'
import { formatPrice, formatTZS } from '../../utils/money'
import { formatKg } from '../../utils/weight'

/** The itemized, explainable breakdown of one farmer payout. */
export default function PayoutLinesTable({ lines, gross, deductions, net, shortfall }:
  { lines: PayoutLine[]; gross: string; deductions: string; net: string; shortfall?: string }) {
  const earnings = lines.filter((l) => l.line_type === 'earning')
  const minus = lines.filter((l) => l.line_type !== 'earning')
  return (
    <table className="w-full text-sm">
      <tbody>
        {earnings.map((l) => (
          <tr key={l.sort_order}><td className="py-1 pr-2">{l.description}</td>
            <td className="py-1 text-right text-slate-500">{l.quantity && formatKg(l.quantity)} × {l.rate && formatPrice(l.rate)}</td>
            <td className="py-1 text-right">{formatTZS(l.amount)}</td></tr>
        ))}
        <tr className="border-t border-slate-200 font-medium"><td className="py-1.5" colSpan={2}>Gross earnings</td><td className="py-1.5 text-right">{formatTZS(gross)}</td></tr>
        {minus.map((l) => (
          <tr key={l.sort_order}><td className="py-1 pr-2" colSpan={2}>
            <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-600">{l.line_type}</span>{l.description}</td>
            <td className="py-1 text-right text-red-700">− {formatTZS(l.amount)}</td></tr>
        ))}
        <tr className="border-t border-slate-200"><td className="py-1.5" colSpan={2}>Total deductions</td><td className="py-1.5 text-right text-red-700">− {formatTZS(deductions)}</td></tr>
        {shortfall && Number(shortfall) > 0 && <tr><td className="py-1 text-amber-700" colSpan={2}>Shortfall (deductions exceed gross — held for review)</td><td className="py-1 text-right text-amber-700">+ {formatTZS(shortfall)}</td></tr>}
        <tr className="border-t-2 border-slate-300 text-base font-bold"><td className="py-2" colSpan={2}>Net payable</td><td className="py-2 text-right">{formatTZS(net)}</td></tr>
      </tbody>
    </table>
  )
}
