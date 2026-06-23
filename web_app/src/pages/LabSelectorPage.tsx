import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { subscribeVisibleLabs } from '@/lib/db'
import { useLabStore } from '@/store/labStore'
import { useAuthStore } from '@/store/authStore'
import type { Lab } from '@/types/admin'

export function LabSelectorPage() {
  const [labs, setLabs] = useState<Lab[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectLab } = useLabStore()
  const { admin, labAccessIds } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (!admin) {
      setLabs([])
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    return subscribeVisibleLabs({
      isSuperAdmin: admin.type === 'super_admin',
      labIds: labAccessIds,
      onData: nextLabs => {
        setLabs(nextLabs.filter(l => l.status !== 'inactive'))
        setLoading(false)
      },
      onError: err => {
        setError(err.message)
        setLoading(false)
      },
    })
  }, [admin, labAccessIds])

  const pick = (lab: Lab) => {
    selectLab(lab.id, lab.name)
    navigate('/overview')
  }

  return (
    <div className="flex flex-col gap-7">
      <div>
        <p className="font-mono text-[11px] tracking-widest uppercase text-[#3d4a46] mb-3">Select</p>
        <h1 className="text-4xl font-bold tracking-tight text-[#e8ecea]">Choose Lab</h1>
        <p className="text-sm text-[#5a6b64] mt-2">
          {admin?.type === 'super_admin' ? 'All labs — super admin view.' : `You have access to ${labs.length} lab(s).`}
        </p>
      </div>

      {loading ? (
        <p className="font-mono text-xs text-[#3d4a46]">Loading labs…</p>
      ) : error ? (
        <div className="bg-surface border border-red/20 rounded-lg p-8 text-center">
          <p className="font-mono text-xs text-red">Failed to load labs: {error}</p>
        </div>
      ) : labs.length === 0 ? (
        <div className="bg-surface border border-white/[0.06] rounded-lg p-8 text-center">
          <p className="font-mono text-xs text-[#3d4a46]">
            {admin?.type === 'super_admin'
              ? 'No labs available. Create the first lab in Control Panel.'
              : 'No active labs are assigned to this admin yet.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {labs.map(lab => (
            <button
              key={lab.id}
              onClick={() => pick(lab)}
              className="bg-surface border border-white/[0.06] rounded-lg p-6 text-left hover:border-green/25 hover:bg-green/5 transition-all cursor-pointer"
            >
              <div className="flex items-start justify-between gap-3 mb-4">
                <span className={`inline-flex px-2 py-0.5 rounded font-mono text-[11px] border ${
                  lab.status === 'active'
                    ? 'bg-green/10 text-green border-green/20'
                    : 'bg-amber/10 text-amber border-amber/20'
                }`}>{lab.status}</span>
                <span className="font-mono text-[11px] text-[#3d4a46]">{lab.code}</span>
              </div>
              <p className="text-lg font-bold text-[#e8ecea] leading-tight">{lab.name}</p>
              <p className="font-mono text-[11px] text-[#3d4a46] mt-2">{[lab.location, lab.timezone].filter(Boolean).join(' · ') || '—'}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
