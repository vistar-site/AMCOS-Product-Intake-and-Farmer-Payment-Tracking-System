import { Construction } from 'lucide-react'
import { PageHeader } from '../components/ui'

/** Shown for modules scheduled in later phases, so navigation is complete but honest. */
export default function PlaceholderPage({ title, phase }: { title: string; phase: number }) {
  return (
    <>
      <PageHeader title={title} />
      <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
        <Construction className="mx-auto size-8 text-slate-400" />
        <p className="mt-3 font-medium">Not built yet</p>
        <p className="mt-1 text-sm text-slate-500">This module is scheduled for Phase {phase} of the roadmap.</p>
      </div>
    </>
  )
}
