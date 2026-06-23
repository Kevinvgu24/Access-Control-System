import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'

export function LoginPage() {
  const { signIn, loading, error } = useAuthStore()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    signIn(email, password)
  }

  return (
    <div className="min-h-screen bg-darker flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-10 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <span className="blink w-2 h-2 rounded-full bg-green shrink-0" />
            <span className="font-mono text-[11px] tracking-widest uppercase text-green">Secure Access</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-[#e8ecea]">Smart Lab</h1>
          <p className="font-mono text-[11px] text-[#3d4a46] mt-1">Access Control Dashboard</p>
        </div>

        {/* Form */}
        <form onSubmit={submit} className="bg-surface border border-white/[0.06] rounded-lg p-7 flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-[11px] uppercase tracking-widest text-[#5a6b64]">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="admin@lab.edu"
              required
              autoFocus
              className="bg-raised border border-white/10 rounded px-4 py-2.5 text-sm text-[#e8ecea] placeholder:text-[#2d3834] outline-none focus:border-green/30 transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-[11px] uppercase tracking-widest text-[#5a6b64]">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="bg-raised border border-white/10 rounded px-4 py-2.5 text-sm text-[#e8ecea] placeholder:text-[#2d3834] outline-none focus:border-green/30 transition-colors"
            />
          </div>

          {error && (
            <p className="font-mono text-[11px] text-red bg-red/5 border border-red/20 rounded px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="bg-green/10 border border-green/25 text-green hover:bg-green/20 font-semibold text-sm px-4 py-2.5 rounded cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-not-allowed mt-1"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="font-mono text-[10px] text-[#2d3834] uppercase tracking-wider text-center mt-6">
          Admin access only
        </p>
      </div>
    </div>
  )
}
