import type { ReactNode } from 'react'

interface PanelProps { children: ReactNode; className?: string; pad?: boolean }

export function Panel({ children, className = '', pad = true }: PanelProps) {
  return (
    <div className={`bg-surface border border-white/[0.06] rounded-lg ${pad ? 'p-6' : ''} ${className}`}>
      {children}
    </div>
  )
}

export function PanelHeader({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return (
    <div className="flex justify-between items-start mb-5">
      <div>
        {eyebrow && <p className="font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] mb-1">{eyebrow}</p>}
        <h2 className="text-[15px] font-semibold text-[#e8ecea]">{title}</h2>
      </div>
      {action}
    </div>
  )
}
