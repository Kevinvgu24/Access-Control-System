import { useState, useEffect, useCallback } from 'react'
import { isMockSeeded, seedMockData, clearMockData } from '@/lib/mock'
import { auth } from '@/lib/firebase'
import type { User } from 'firebase/auth'

type Status = 'idle' | 'seeding' | 'clearing' | 'done' | 'error'

export function MockPanel() {
  const [open, setOpen]       = useState(false)
  const [seeded, setSeeded]   = useState(isMockSeeded)
  const [status, setStatus]   = useState<Status>('idle')
  const [message, setMessage] = useState('')
  const [user, setUser]       = useState<User | null>(null)

  useEffect(() => auth.onAuthStateChanged(setUser), [])

  const refresh = useCallback(() => setSeeded(isMockSeeded()), [])

  async function seed() {
    setStatus('seeding')
    setMessage('')
    try {
      await seedMockData(user?.displayName ?? user?.email ?? 'dev')
      refresh()
      setStatus('done')
      setMessage('Seeded — 1 lab · 5 users · 27 events')
    } catch (e) {
      setStatus('error')
      setMessage(e instanceof Error ? e.message : 'Seed failed')
    }
  }

  async function clear() {
    setStatus('clearing')
    setMessage('')
    try {
      await clearMockData()
      refresh()
      setStatus('done')
      setMessage('Cleared')
    } catch (e) {
      setStatus('error')
      setMessage(e instanceof Error ? e.message : 'Clear failed')
    }
  }

  const busy = status === 'seeding' || status === 'clearing'

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2 font-mono text-[11px]">
      {open && (
        <div className="w-56 bg-[#0d1210] border border-[#1e2d28] rounded-lg shadow-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-[#1e2d28] flex items-center justify-between">
            <span className="text-[#3d8c6e] uppercase tracking-widest">Dev · Mock</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${seeded ? 'bg-green-500' : 'bg-[#3d4a46]'}`}
            />
          </div>

          <div className="px-3 py-2 flex flex-col gap-2">
            <p className="text-[#5a6b64]">
              {seeded ? 'Seeded — 1 lab · 5 users · 27 events' : 'No mock data'}
            </p>

            {!user && (
              <p className="text-yellow-600/80">Sign in required to write</p>
            )}

            <div className="flex gap-1.5 mt-0.5">
              <button
                type="button"
                disabled={busy || seeded || !user}
                onClick={() => { void seed() }}
                className="flex-1 py-1 rounded bg-[#1a2e25] border border-[#2a4a38] text-green-400
                           hover:bg-[#1e3a2c] disabled:opacity-40 disabled:cursor-not-allowed
                           transition-colors text-[11px] uppercase tracking-wider"
              >
                {status === 'seeding' ? 'Seeding…' : 'Seed'}
              </button>
              <button
                type="button"
                disabled={busy || !seeded || !user}
                onClick={() => { void clear() }}
                className="flex-1 py-1 rounded bg-[#2e1a1a] border border-[#4a2a2a] text-red-400
                           hover:bg-[#3a2020] disabled:opacity-40 disabled:cursor-not-allowed
                           transition-colors text-[11px] uppercase tracking-wider"
              >
                {status === 'clearing' ? 'Clearing…' : 'Clear'}
              </button>
            </div>

            {message && (
              <p className={status === 'error' ? 'text-red-400' : 'text-[#3d8c6e]'}>
                {message}
              </p>
            )}
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="px-2.5 py-1 rounded-full bg-[#0d1210] border border-[#1e2d28]
                   text-[#3d8c6e] hover:border-[#2a4a38] hover:text-green-400
                   shadow-lg transition-colors uppercase tracking-widest select-none"
      >
        {open ? 'close' : 'dev'}
      </button>
    </div>
  )
}
