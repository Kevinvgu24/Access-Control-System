import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useLabStore }  from '@/store/labStore'
import { useAdminStore } from '@/store/adminStore'

const NAV = [
  { href: '/overview',   icon: '▣', label: 'Dashboard'  },
  { href: '/users',      icon: '◈', label: 'Users'      },
  { href: '/enrollment', icon: '⊕', label: 'Enrollment' },
  { href: '/logs',       icon: '≡', label: 'Logs'       },
  { href: '/system',     icon: '◎', label: 'System'     },
]

export function Sidebar() {
  const { admin, signOut }          = useAuthStore()
  const { selectedLabName, clearLab } = useLabStore()
  const systemStatus                  = useAdminStore(s => s.systemStatus)
  const navigate                      = useNavigate()

  const handleSignOut = async () => {
    clearLab()
    await signOut()
  }

  const statusDot = systemStatus.overall === 'online'
    ? 'bg-green' : systemStatus.overall === 'grace_period'
    ? 'bg-amber' : 'bg-red'

  return (
    <aside className="w-[200px] shrink-0 flex flex-col h-screen sticky top-0 bg-darker border-r border-white/[0.05]">
      <div className="px-6 py-7 border-b border-white/[0.05]">
        <div className="flex items-center gap-2 mb-1">
          <span className={`blink w-2 h-2 rounded-full shrink-0 ${statusDot}`} />
          <span className={`font-mono text-[10px] tracking-widest uppercase ${systemStatus.overall === 'online' ? 'text-green' : 'text-amber'}`}>
            {systemStatus.overall === 'online' ? 'Live' : systemStatus.overall}
          </span>
        </div>
        <p className="text-[17px] font-bold tracking-tight text-[#e8ecea] leading-tight mt-2">Smart Lab</p>
        <p className="font-mono text-[11px] text-[#3d4a46] mt-1 truncate">
          {selectedLabName ?? 'No lab selected'}
        </p>
      </div>

      <nav className="flex flex-col p-3 gap-0.5 flex-1">
        {NAV.map(({ href, icon, label }) => (
          <NavLink key={href} to={href}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-all
               ${isActive ? 'bg-green/10 text-green' : 'text-[#5a6b64] hover:text-[#a8bbb2] hover:bg-white/5'}`
            }
          >
            <span className="text-base leading-none">{icon}</span>
            {label}
          </NavLink>
        ))}

        {/* Control Panel — super_admin only */}
        {admin?.role === 'super_admin' && (
          <NavLink to="/control"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-all mt-3
               ${isActive ? 'bg-green/10 text-green' : 'text-[#5a6b64] hover:text-[#a8bbb2] hover:bg-white/5'}`
            }
          >
            <span className="text-base leading-none">⚙</span>
            Control Panel
          </NavLink>
        )}

        {/* Switch lab */}
        <button
          onClick={() => { clearLab(); navigate('/labs') }}
          className="flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-all text-[#5a6b64] hover:text-[#a8bbb2] hover:bg-white/5 mt-1 cursor-pointer"
        >
          <span className="text-base leading-none">⊞</span>
          Switch Lab
        </button>
      </nav>

      <div className="px-5 py-4 border-t border-white/[0.05] flex flex-col gap-2">
        <p className="font-mono text-[10px] text-[#3d4a46] uppercase tracking-wider truncate">
          {admin?.type === 'super_admin' ? 'Super Admin' : 'Lab Admin'}
        </p>
        <button
          onClick={handleSignOut}
          className="font-mono text-[11px] text-[#5a6b64] hover:text-red transition-colors cursor-pointer text-left"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
