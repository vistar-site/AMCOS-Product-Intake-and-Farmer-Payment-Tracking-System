/**
 * Public landing page for the AMCOS management portal.
 * Audience: cooperative administrators, managers, data clerks and institutional partners.
 * Every capability described here exists in the application — no invented figures.
 */
import { Link, Navigate } from 'react-router-dom'
import {
  ArrowRight, BadgeCheck, BarChart3, Building2, CloudOff, FileClock, FileSpreadsheet, Gavel, KeyRound, Landmark,
  Layers, MessageSquare, Scale, ShieldCheck, Smartphone, Sprout, Truck, UserCog, Users, Wallet, Warehouse,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import type { LucideIcon } from 'lucide-react'

const FEATURES: { icon: LucideIcon; title: string; body: string; points: string[] }[] = [
  { icon: Users, title: 'Farmer registry', body: 'One trusted register of cooperative members.',
    points: ['Automatic membership numbers', 'Search by name, member no. or phone', 'Home centre, village and ward', 'Payment details visible only to finance staff'] },
  { icon: Scale, title: 'Produce intake', body: 'Weigh, confirm and receipt every delivery at the collection point.',
    points: ['Gross, tare and net calculated exactly', 'Per-crop weight limits and grades', 'Instant receipt number and PDF receipt', 'Duplicate-entry warnings'] },
  { icon: Sprout, title: 'Crops & seasons', body: 'Configure what the cooperative buys, and when.',
    points: ['Any crop: cashew, cotton, coffee, sesame…', 'Quality grades per crop', 'Seasons with date validation', 'Intake rules without code changes'] },
  { icon: Warehouse, title: 'Warehouse & inventory', body: 'Follow produce from the village to the warehouse.',
    points: ['Aggregation batches per centre and crop', 'Dispatch with vehicle and driver', 'Warehouse receipts: received, rejected, damaged', 'Live stock position by stage'] },
  { icon: Layers, title: 'Reconciliation', body: 'Differences are recorded and explained, never hidden.',
    points: ['Delivered vs dispatched vs received vs sold', 'Automatic discrepancy flags with tolerance', 'Explanations by authorized staff', 'Farmer records never altered'] },
  { icon: Gavel, title: 'Auction results', body: 'Record sales lot by lot, at different prices and grades.',
    points: ['Lots linked to warehouse batches', 'Overselling prevented', 'Second-person approval', 'Each lot traced back to every farmer'] },
  { icon: Wallet, title: 'Payouts & deductions', body: 'Transparent, explainable farmer payments.',
    points: ['Configurable levies: %, per kg or fixed', 'Input loans recovered with caps', 'Choice of warehouse-loss policy', 'Itemized farmer statements'] },
  { icon: Landmark, title: 'Bulk payments', body: 'Prepare, approve and reconcile payment batches.',
    points: ['Mobile money, bank or cash', 'CSV / Excel export for provider portals', 'Paid only with a transaction reference', 'Duplicate payments blocked by design'] },
  { icon: MessageSquare, title: 'SMS notifications', body: 'Keep farmers informed in Kiswahili or English.',
    points: ['Delivery receipts by SMS', 'Payment confirmations', 'Editable templates', 'Automatic retries and full history'] },
]

const ROLES: { icon: LucideIcon; role: string; does: string }[] = [
  { icon: UserCog, role: 'Administrators', does: 'Manage users, roles, centres, crops, seasons and cooperative settings.' },
  { icon: Building2, role: 'AMCOS managers', does: 'Approve corrections, auctions, payouts and payment batches; monitor every centre.' },
  { icon: Smartphone, role: 'Collection clerks', does: 'Register farmers and record deliveries on a phone, online or offline.' },
  { icon: Wallet, role: 'Accountants', does: 'Configure levies and loans, calculate payouts, prepare and reconcile payments.' },
  { icon: Truck, role: 'Warehouse officers', does: 'Build batches, dispatch produce and record warehouse receipts.' },
  { icon: FileClock, role: 'Auditors & partners', does: 'Read-only access to reports, statements and the complete audit trail.' },
]

const REPORTS = ['Daily collection', 'Collection by crop', 'Centre performance', 'Seasonal produce', 'Farmer registration',
  'Warehouse dispatches & receipts', 'Discrepancies', 'Auction sales', 'Farmer earnings', 'Outstanding payments',
  'Levy & deduction collection', 'Input loans', 'Payment reconciliation']

const FLOW = [
  { icon: Scale, label: 'Delivery', sub: 'weighed & receipted' },
  { icon: Layers, label: 'Batch', sub: 'aggregated' },
  { icon: Truck, label: 'Dispatch', sub: 'to warehouse' },
  { icon: Warehouse, label: 'Receipt', sub: 'reconciled' },
  { icon: Gavel, label: 'Auction', sub: 'sold by lot' },
  { icon: Wallet, label: 'Payout', sub: 'after deductions' },
  { icon: Landmark, label: 'Payment', sub: 'confirmed' },
]

export default function LandingPage() {
  const { status } = useAuth()
  if (status === 'authenticated') return <Navigate to="/" replace />

  return (
    <div className="bg-white text-slate-900">
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
          <Link to="/welcome" className="flex items-center gap-2">
            <span className="grid size-9 place-items-center rounded-md bg-brand-600 text-white"><Sprout className="size-5" /></span>
            <span className="leading-tight"><span className="block text-sm font-semibold">AMCOS Portal</span>
              <span className="block text-xs text-slate-500">Produce &amp; Payments</span></span>
          </Link>
          <nav className="ml-auto hidden gap-6 text-sm text-slate-600 md:flex" aria-label="Sections">
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#traceability" className="hover:text-slate-900">Traceability</a>
            <a href="#reports" className="hover:text-slate-900">Reports</a>
            <a href="#roles" className="hover:text-slate-900">Who it's for</a>
            <a href="#security" className="hover:text-slate-900">Security</a>
          </nav>
          <Link to="/login" className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 md:ml-0">
            Sign in <ArrowRight className="size-4" />
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-brand-900 text-white">
        <div className="mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-28">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-brand-100">
              <BadgeCheck className="size-3.5" /> Agricultural Marketing Cooperative Societies
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              Every kilogram recorded.<br />Every shilling accounted for.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-brand-100/85">
              The management portal for AMCOS: farmer registration, produce intake, warehouse inventory, auction results and
              farmer payments in one traceable, auditable system — built to work even where the internet doesn't.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/login" className="inline-flex items-center gap-2 rounded-md bg-white px-5 py-3 text-sm font-semibold text-brand-900 hover:bg-brand-50">
                Sign in to the portal <ArrowRight className="size-4" />
              </Link>
              <a href="#features" className="inline-flex items-center rounded-md px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/30 hover:bg-white/10">
                Explore features
              </a>
            </div>
            <ul className="mt-10 grid max-w-lg grid-cols-3 gap-4 text-sm">
              {[[CloudOff, 'Works offline'], [ShieldCheck, 'Role-based access'], [FileClock, 'Full audit trail']].map(([Icon, t]) => {
                const I = Icon as LucideIcon
                return <li key={t as string} className="flex items-center gap-2 text-brand-100"><I className="size-4 shrink-0" />{t as string}</li>
              })}
            </ul>
          </div>

          {/* Product preview: an illustrative receipt, clearly labelled as an example */}
          <div className="relative mx-auto w-full max-w-md lg:mx-0 lg:ml-auto">
            <div className="rounded-xl bg-white p-6 text-slate-900 shadow-2xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Delivery receipt</p>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">Example</span>
              </div>
              <p className="mt-1 font-mono text-2xl font-bold">DEMO-2026-000042</p>
              <dl className="mt-5 space-y-2 text-sm">
                {[['Farmer', 'Fatuma Abdallah · DEMO-0002'], ['Crop', 'Cashew nuts · Standard'], ['Centre', 'Nanyamba Collection Centre'],
                  ['Gross / tare', '82.500 kg / 0.500 kg']].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3"><dt className="text-slate-500">{k}</dt><dd className="text-right">{v}</dd></div>
                ))}
              </dl>
              <div className="mt-4 flex items-baseline justify-between border-t border-slate-100 pt-4">
                <span className="font-medium">Net weight</span><span className="text-3xl font-bold">82 kg</span>
              </div>
              <div className="mt-5 rounded-md bg-brand-50 p-3 text-xs text-brand-900">
                <MessageSquare className="mr-1 inline size-3.5" /> SMS: “Tumepokea Cashew kg 82.0 … Risiti DEMO-2026-000042. Asante.”
              </div>
            </div>
            <div className="absolute -bottom-6 -left-6 hidden rounded-lg bg-white px-4 py-3 text-sm text-slate-900 shadow-xl sm:block">
              <p className="flex items-center gap-2 font-medium"><CloudOff className="size-4 text-amber-500" />Saved offline</p>
              <p className="text-xs text-slate-500">Uploads automatically when connected</p>
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="border-b border-slate-100 bg-slate-50">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3">
          {[['From paper books to a single record', 'Deliveries, warehouse records and payments live in one system instead of exercise books and scattered spreadsheets.'],
            ['From disputes to evidence', 'Every receipt, correction, sale and payment can be traced to who did it and when — ready for members, boards and auditors.'],
            ['From delays to timely payments', 'Payouts are calculated automatically from auction results, with every levy and loan deduction explained.']].map(([t, b]) => (
            <div key={t}><h2 className="font-semibold">{t}</h2><p className="mt-2 text-sm text-slate-600">{b}</p></div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-16">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
          <SectionHead eyebrow="Features" title="Everything a cooperative season needs"
            text="From the first weighed bag to the last confirmed payment, each module works with the others — no re-typing, no gaps." />
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <article key={f.title} className="rounded-xl p-6 ring-1 ring-slate-200 transition hover:shadow-md hover:ring-brand-200">
                <span className="grid size-11 place-items-center rounded-lg bg-brand-50 text-brand-700"><f.icon className="size-5" /></span>
                <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{f.body}</p>
                <ul className="mt-4 space-y-1.5 text-sm">
                  {f.points.map((p) => <li key={p} className="flex gap-2"><BadgeCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />{p}</li>)}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Traceability */}
      <section id="traceability" className="scroll-mt-16 bg-brand-900 text-white">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
          <SectionHead dark eyebrow="End-to-end traceability" title="Follow any delivery to the shilling"
            text="Open a farmer's receipt and see the batch it joined, the truck that carried it, the warehouse that received it, the auction lot it was sold in, and the payment that followed." />
          <ol className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-7">
            {FLOW.map((s, i) => (
              <li key={s.label} className="relative rounded-lg bg-white/5 p-4 text-center ring-1 ring-white/10">
                <span className="text-xs text-brand-100/60">Step {i + 1}</span>
                <s.icon className="mx-auto mt-2 size-6 text-brand-100" />
                <p className="mt-2 font-semibold">{s.label}</p>
                <p className="text-xs text-brand-100/70">{s.sub}</p>
              </li>
            ))}
          </ol>
          <p className="mt-8 max-w-3xl text-sm text-brand-100/80">
            Warehouse losses are never hidden: the cooperative chooses, per payout, whether losses are shared by farmers in proportion
            to their deliveries or absorbed by the AMCOS — and every statement says which policy was applied.
          </p>
        </div>
      </section>

      {/* Offline */}
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2">
        <div>
          <SectionHead eyebrow="Built for rural collection points" title="No signal? Keep recording."
            text="The portal installs on a clerk's phone like an app. When the network drops, deliveries are saved on the device with an offline receipt number and uploaded automatically when the connection returns." />
          <ul className="mt-6 space-y-3 text-sm">
            {['Each delivery is uploaded exactly once — retries never create duplicates', 'Server confirms every single record before it is marked synced',
              'Rejected or conflicting records stay visible for a manager to review', 'No passwords, payout amounts or bank details stored on the device']
              .map((p) => <li key={p} className="flex gap-2"><BadgeCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />{p}</li>)}
          </ul>
        </div>
        <div className="rounded-xl bg-slate-50 p-6 ring-1 ring-slate-200">
          <p className="text-sm font-semibold">Sync status</p>
          <p className="text-xs text-slate-500">Example view on a clerk's device</p>
          <ul className="mt-4 divide-y divide-slate-200 text-sm">
            {[['OFF-3F2A-0007', 'Waiting to upload', 'bg-amber-50 text-amber-800'], ['OFF-3F2A-0006', 'On server · DEMO-2026-000118', 'bg-green-50 text-green-700'],
              ['OFF-3F2A-0005', 'On server · DEMO-2026-000117', 'bg-green-50 text-green-700']].map(([r, s, c]) => (
              <li key={r} className="flex items-center justify-between gap-3 py-3"><span className="font-mono text-xs">{r}</span>
                <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${c}`}>{s}</span></li>
            ))}
          </ul>
        </div>
      </section>

      {/* Reports */}
      <section id="reports" className="scroll-mt-16 bg-slate-50">
        <div className="mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <SectionHead eyebrow="Reporting tools" title="Decisions backed by real records"
              text="A live dashboard and a full report library, generated directly from system records. Filter by date, crop, season, centre or farmer, then export." />
            <div className="mt-6 flex flex-wrap gap-2 text-sm">
              {['PDF', 'Excel', 'CSV', 'Printable statements'].map((x) => (
                <span key={x} className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 ring-1 ring-slate-200"><FileSpreadsheet className="size-3.5 text-brand-600" />{x}</span>
              ))}
            </div>
            <ul className="mt-6 space-y-2 text-sm text-slate-600">
              <li className="flex gap-2"><BarChart3 className="mt-0.5 size-4 shrink-0 text-brand-600" />Dashboard: collection trends, crop and centre totals, stock position, auction prices, payment progress</li>
              <li className="flex gap-2"><BadgeCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />“Needs attention” list of pending approvals, discrepancies and failed payments</li>
            </ul>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {REPORTS.map((r) => (
              <div key={r} className="flex items-center gap-3 rounded-lg bg-white px-4 py-3 text-sm ring-1 ring-slate-200">
                <BarChart3 className="size-4 shrink-0 text-brand-600" />{r}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Roles */}
      <section id="roles" className="scroll-mt-16 mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <SectionHead eyebrow="Who it's for" title="The right tools for every role"
          text="Each person sees only what their role allows. Permissions are enforced by the server, not just hidden in the interface." />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {ROLES.map((r) => (
            <div key={r.role} className="flex gap-4 rounded-xl p-5 ring-1 ring-slate-200">
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-700"><r.icon className="size-5" /></span>
              <div><h3 className="font-semibold">{r.role}</h3><p className="mt-1 text-sm text-slate-600">{r.does}</p></div>
            </div>
          ))}
        </div>
      </section>

      {/* Security */}
      <section id="security" className="scroll-mt-16 border-y border-slate-200 bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
          <SectionHead eyebrow="Governance & security" title="Controls that protect farmers' money"
            text="Designed around the checks cooperatives, regulators and auditors expect." />
          <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[[ShieldCheck, 'Maker-checker approvals', 'The person who enters auction results, calculates payouts or prepares payments can never approve them.'],
              [FileClock, 'Append-only audit trail', 'Every important action is logged with before-and-after values; the database refuses edits or deletions.'],
              [KeyRound, 'Secure sign-in', 'Short-lived sessions, account lockout after failed attempts, and accounts created only by administrators.'],
              [Layers, 'Original records preserved', 'Corrections need approval and keep the old values; voided deliveries remain visible with a reason.']]
              .map(([Icon, t, b]) => {
                const I = Icon as LucideIcon
                return <div key={t as string} className="rounded-xl bg-white p-6 ring-1 ring-slate-200">
                  <I className="size-6 text-brand-600" /><h3 className="mt-3 font-semibold">{t as string}</h3><p className="mt-1 text-sm text-slate-600">{b as string}</p></div>
              })}
          </div>
        </div>
      </section>

      {/* Partners */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <div className="grid gap-10 rounded-2xl bg-brand-50 p-8 ring-1 ring-brand-100 sm:p-12 lg:grid-cols-2">
          <div>
            <p className="text-sm font-semibold text-brand-700">For institutional partners</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">Reliable data for regulators, buyers and financiers</h2>
            <p className="mt-3 text-slate-600">Partners can be given read-only auditor access to verified collection volumes, warehouse reconciliation,
              auction outcomes and payment records — without spreadsheets passed between offices.</p>
          </div>
          <ul className="space-y-3 text-sm">
            {['Volumes per crop, centre and season', 'Warehouse receipts and discrepancy explanations', 'Auction sales and average prices',
              'Levy collection and payment completion', 'Exportable evidence in PDF, Excel and CSV'].map((p) => (
              <li key={p} className="flex gap-2"><BadgeCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />{p}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-brand-900 text-white">
        <div className="mx-auto flex max-w-7xl flex-col items-start gap-6 px-4 py-16 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Ready to run your season with confidence?</h2>
            <p className="mt-2 text-brand-100/80">Staff accounts are created by your AMCOS administrator.</p>
          </div>
          <Link to="/login" className="inline-flex items-center gap-2 rounded-md bg-white px-5 py-3 text-sm font-semibold text-brand-900 hover:bg-brand-50">
            Sign in <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-slate-200">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p className="flex items-center gap-2"><Sprout className="size-4 text-brand-600" />AMCOS Produce Intake &amp; Farmer Payment Tracking System</p>
          <p>Authorized cooperative staff only. All activity is audited.</p>
        </div>
      </footer>
    </div>
  )
}

function SectionHead({ eyebrow, title, text, dark }: { eyebrow: string; title: string; text: string; dark?: boolean }) {
  return (
    <div className="max-w-2xl">
      <p className={`text-sm font-semibold ${dark ? 'text-brand-100/70' : 'text-brand-700'}`}>{eyebrow}</p>
      <h2 className="mt-2 text-3xl font-semibold tracking-tight">{title}</h2>
      <p className={`mt-3 ${dark ? 'text-brand-100/80' : 'text-slate-600'}`}>{text}</p>
    </div>
  )
}
