import { useQuery } from '@tanstack/react-query'
import { FileDown, Printer } from 'lucide-react'
import { api, openFile } from '../../api/client'
import { fmtDate, fmtDateTime } from '../../components/form'
import { Badge, Button, Skeleton } from '../../components/ui'
import type { Statement } from '../../types/finance'
import { formatTZS } from '../../utils/money'
import { formatKg } from '../../utils/weight'
import PayoutLinesTable from './PayoutLinesTable'

/** Farmer payout statement: earnings, every deduction, net, paid and unpaid — printable. */
export default function FarmerStatement({ farmerId }: { farmerId: string }) {
  const q = useQuery({ queryKey: ['farmers', farmerId, 'statement'], queryFn: () => api<Statement>(`/farmers/${farmerId}/statement`) })
  if (q.isLoading) return <Skeleton className="h-40" />
  if (!q.data) return null
  const s = q.data
  const t = s.totals
  return (
    <section className="mt-6 rounded-lg bg-white p-5 ring-1 ring-slate-200 print:ring-0">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold">Payout statement</h2>
        <div className="flex gap-2 print:hidden">
          <Button variant="secondary" onClick={() => openFile(`/farmers/${farmerId}/statement.pdf`)}><FileDown className="size-4" />PDF</Button>
          <Button variant="secondary" onClick={() => window.print()}><Printer className="size-4" />Print</Button>
        </div>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-4">
        {([['Delivered', formatKg(t.delivered_kg)], ['Paid weight', formatKg(t.eligible_kg)], ['Gross earnings', formatTZS(t.gross)],
          ['Levies', formatTZS(t.levies)], ['Other deductions', formatTZS(t.other_deductions)], ['Loan deductions', formatTZS(t.loan_deductions)],
          ['Net payable', formatTZS(t.net_payable)], ['Paid', formatTZS(t.paid)], ['Unpaid balance', formatTZS(t.unpaid)],
          ['Held for review', formatTZS(t.held_for_review)], ['Loans outstanding', formatTZS(t.loans_outstanding)]] as const).map(([k, v]) => (
          <div key={k} className="rounded-md bg-slate-50 p-3"><dt className="text-xs text-slate-500">{k}</dt><dd className="font-semibold">{v}</dd></div>
        ))}
      </dl>
      {s.payouts.length === 0 && <p className="mt-4 text-sm text-slate-500">No approved payouts yet. Earnings appear after the produce is sold and the payout run is approved.</p>}
      {s.payouts.map((p) => (
        <div key={p.id} className="mt-5 border-t border-slate-100 pt-4">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-mono font-medium">{p.run.run_no}</span><span className="text-slate-500">{p.run.crop.name} · {p.run.season.name} ·
              {p.run.loss_policy === 'shared' ? ' loss shared' : ' loss absorbed by AMCOS'} · approved {p.run.approved_at && fmtDate(p.run.approved_at)}</span>
            <Badge tone={p.status === 'paid' ? 'green' : p.status === 'needs_review' ? 'red' : 'amber'}>{p.status.replace('_', ' ')}</Badge>
          </div>
          <div className="max-w-3xl"><PayoutLinesTable lines={p.lines} gross={p.gross_amount} deductions={p.total_deductions} net={p.net_payable} /></div>
        </div>
      ))}
      {s.payments.length > 0 && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <h3 className="mb-2 text-sm font-semibold">Payment history</h3>
          <ul className="space-y-1 text-sm">{s.payments.map((p) => (
            <li key={p.id} className="flex flex-wrap justify-between gap-2"><span>{fmtDateTime(p.paid_at ?? p.created_at)} · {p.transaction_ref ?? p.failure_reason ?? 'awaiting result'}</span>
              <span><Badge tone={p.status === 'paid' ? 'green' : p.status === 'failed' ? 'red' : 'slate'}>{p.status}</Badge> <b className="ml-2">{formatTZS(p.amount)}</b></span></li>
          ))}</ul>
        </div>
      )}
      {s.loans.length > 0 && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <h3 className="mb-2 text-sm font-semibold">Input loans</h3>
          <ul className="space-y-1 text-sm">{s.loans.map((l) => (
            <li key={l.id} className="flex flex-wrap justify-between gap-2"><span>{l.loan_ref} · {l.description} · {fmtDate(l.issue_date)}</span>
              <span>{formatTZS(l.principal)} − repaid {formatTZS(l.repaid)} = <b>{formatTZS(l.outstanding)}</b></span></li>
          ))}</ul>
        </div>
      )}
    </section>
  )
}
