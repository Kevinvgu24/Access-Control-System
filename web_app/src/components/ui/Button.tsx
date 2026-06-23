import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  children: ReactNode
}

const v = {
  primary: 'bg-green/10 border-green/25 text-green hover:bg-green/20',
  ghost:   'bg-transparent border-white/10 text-[#5a6b64] hover:text-[#a8bbb2] hover:border-white/20',
  danger:  'bg-red/10 border-red/25 text-red hover:bg-red/20',
}
const sz = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
}

export function Button({ variant = 'ghost', size = 'md', children, className = '', ...p }: BtnProps) {
  return (
    <button className={`inline-flex items-center gap-2 font-semibold border rounded cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${v[variant]} ${sz[size]} ${className}`} {...p}>
      {children}
    </button>
  )
}
