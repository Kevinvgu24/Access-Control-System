import { useState } from 'react'
import { useAdminStore } from '@/store/adminStore'
import { useLabStore }   from '@/store/labStore'
import { Panel } from '@/components/ui/Panel'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { fmtTs } from '@/lib/format'
import type { UserRole, UserStatus } from '@/types/admin'
import { useNavigate } from 'react-router-dom'

const ROLE_OPTS: UserRole[] = ['student', 'faculty', 'lab_assistant', 'guest', 'maintenance']
const ROLE_LABEL: Record<UserRole, string> = {
  student: 'Student', faculty: 'Faculty',
  lab_assistant: 'Lab Asst', guest: 'Guest', maintenance: 'Maintenance',
}
const STATUS_TONE: Record<UserStatus, 'green' | 'red'> = { active: 'green', suspended: 'red' }

export function UsersPage() {
  const { users, refreshUsers } = useAdminStore()
  const { selectedLabId }       = useLabStore()
  const navigate = useNavigate()
  const [search, setSearch]           = useState('')
  const [roleFilter, setRoleFilter]   = useState<UserRole | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<UserStatus | 'all'>('all')
  const [menuOpen, setMenuOpen]       = useState<string | null>(null)

  const filtered = users.filter(u =>
    (!search || u.fullName.toLowerCase().includes(search.toLowerCase()) || u.universityId.includes(search)) &&
    (roleFilter === 'all' || u.roles.includes(roleFilter as UserRole)) &&
    (statusFilter === 'all' || u.status === statusFilter)
  )

  const chipClass = (active: boolean) =>
    `px-3 py-1.5 rounded font-mono text-[11px] border cursor-pointer transition-colors ${
      active ? 'bg-green/10 border-green/25 text-green' : 'bg-raised border-white/10 text-[#5a6b64] hover:text-[#a8bbb2]'
    }`

  return (
    <div className="flex flex-col gap-7">
      <div className="flex justify-between items-end">
        <div>
          <p className="font-mono text-[11px] tracking-widest uppercase text-[#3d4a46] mb-3">The Roster</p>
          <h1 className="text-4xl font-bold tracking-tight text-[#e8ecea]">User Directory</h1>
          <p className="text-sm text-[#5a6b64] mt-2">Everyone authorized to access this lab.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => selectedLabId && refreshUsers(selectedLabId)}>↻ Refresh</Button>
          <Button variant="primary" onClick={() => navigate('/enrollment')}>+ Add New User</Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total',     value: users.length,                                       color: 'text-[#e8ecea]' },
          { label: 'Active',    value: users.filter(u => u.status === 'active').length,    color: 'text-green'     },
          { label: 'Suspended', value: users.filter(u => u.status === 'suspended').length, color: 'text-red'       },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-surface border border-white/[0.06] rounded-lg p-6">
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] mb-3">{label}</p>
            <p className={`text-5xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <Panel pad={false}>
        <div className="flex gap-3 items-center p-5 border-b border-white/[0.05] flex-wrap">
          <input type="text" placeholder="Search name or university ID…" value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 min-w-[160px] bg-raised border border-white/10 rounded px-3 py-2 text-sm text-[#e8ecea] placeholder:text-[#2d3834] outline-none focus:border-green/30 transition-colors"
          />
          <div className="flex gap-1.5 flex-wrap">
            <button onClick={() => setRoleFilter('all')} className={chipClass(roleFilter === 'all')}>All</button>
            {ROLE_OPTS.map(r => (
              <button key={r} onClick={() => setRoleFilter(r)} className={chipClass(roleFilter === r)}>
                {ROLE_LABEL[r]}
              </button>
            ))}
          </div>
          <div className="w-px h-5 bg-white/10" />
          <div className="flex gap-1.5">
            {(['all', 'active', 'suspended'] as const).map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} className={chipClass(statusFilter === s)}>
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-raised">
              {['User', 'Role', 'Credentials', 'Last Access', 'Status', ''].map(h => (
                <th key={h} className="text-left px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] border-b border-white/[0.05]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(u => (
              <tr key={u.id} className="border-b border-white/[0.04] hover:bg-raised transition-colors last:border-0">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-line border border-white/[0.06] flex items-center justify-center text-xs font-semibold text-[#5a6b64] shrink-0">
                      {u.fullName.split(' ').map((w: string) => w[0]).slice(-2).join('')}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[#e8ecea]">{u.fullName}</p>
                      <p className="font-mono text-[11px] text-[#3d4a46] mt-0.5">{u.universityId}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 font-mono text-xs text-[#5a6b64]">
                  {u.roles.map(r => ROLE_LABEL[r] ?? r).join(', ')}
                </td>
                <td className="px-5 py-4">
                  <div className="flex gap-1.5">
                    {u.faceStatus === 'complete' && <Badge tone="green">Face</Badge>}
                    {u.pinStatus === 'set'       && <Badge tone="blue">PIN</Badge>}
                    {u.faceStatus === 'incomplete' && <Badge tone="neutral">No Face</Badge>}
                    {u.pinStatus === 'missing'   && <Badge tone="neutral">No PIN</Badge>}
                  </div>
                </td>
                <td className="px-5 py-4 font-mono text-xs text-[#5a6b64]">{fmtTs(u.lastAccessAt)}</td>
                <td className="px-5 py-4"><Badge tone={STATUS_TONE[u.status]}>{u.status}</Badge></td>
                <td className="px-5 py-4 relative">
                  <button onClick={() => setMenuOpen(menuOpen === u.id ? null : u.id)}
                    className="w-8 h-8 flex items-center justify-center rounded text-[#3d4a46] hover:text-[#e8ecea] hover:bg-white/5 transition-colors cursor-pointer text-lg">⋯</button>
                  {menuOpen === u.id && (
                    <div className="absolute right-4 top-12 z-20 bg-[#161c19] border border-white/10 rounded shadow-2xl min-w-[150px] overflow-hidden py-1">
                      {['Edit Profile', 'Reset PIN', 'Revoke Access'].map(a => (
                        <button key={a} onClick={() => setMenuOpen(null)}
                          className={`w-full text-left px-4 py-2.5 text-sm transition-colors cursor-pointer hover:bg-white/5 ${a === 'Revoke Access' ? 'text-red' : 'text-[#a8bbb2]'}`}>
                          {a}
                        </button>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="py-12 text-center font-mono text-xs text-[#3d4a46]">No users match the current filters.</p>
        )}
      </Panel>
    </div>
  )
}
