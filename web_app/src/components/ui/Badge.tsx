import type { ReactNode } from 'react'

type Tone = 'green' | 'red' | 'amber' | 'blue' | 'neutral'

const s: Record<Tone, string> = {
  green:   'bg-green/10 text-green border-green/20',
  red:     'bg-red/10 text-red border-red/20',
  amber:   'bg-amber/10 text-amber border-amber/20',
  blue:    'bg-blue/10 text-blue border-blue/20',
  neutral: 'bg-white/5 text-[#5a6b64] border-white/10',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono text-[11px] border ${s[tone]}`}>
      {children}
    </span>
  )
}
