import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Sidebar }         from '@/components/shell/Sidebar'
import { TopBar }          from '@/components/shell/TopBar'
import { LoginPage }       from '@/pages/LoginPage'
import { LabSelectorPage } from '@/pages/LabSelectorPage'
import { OverviewPage }    from '@/pages/OverviewPage'
import { UsersPage }       from '@/pages/UsersPage'
import { EnrollmentPage }  from '@/pages/EnrollmentPage'
import { LogsPage }        from '@/pages/LogsPage'
import { SystemPage }      from '@/pages/SystemPage'
import { ControlPage }     from '@/pages/ControlPage'
import { useAuthStore }    from '@/store/authStore'
import { useLabStore }     from '@/store/labStore'
import { useAdminStore }   from '@/store/adminStore'
import { MockPanel }       from '@/components/dev/MockPanel'

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-darker flex items-center justify-center">
      <div className="flex items-center gap-3">
        <span className="blink w-2 h-2 rounded-full bg-green" />
        <span className="font-mono text-xs text-[#3d4a46] uppercase tracking-widest">Initializing…</span>
      </div>
    </div>
  )
}

function AuthenticatedApp() {
  const { selectedLabId, selectedLabName } = useLabStore()
  const { admin, error, signOut } = useAuthStore()
  const subscribe = useAdminStore(s => s.subscribe)

  useEffect(() => {
    if (selectedLabId && selectedLabName) {
      return subscribe(selectedLabId, selectedLabName)
    }
  }, [selectedLabId, selectedLabName, subscribe])

  if (!admin) {
    return (
      <div className="min-h-screen bg-darker flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-surface border border-red/20 rounded-lg p-7 flex flex-col gap-4">
          <div>
            <p className="font-mono text-[11px] tracking-widest uppercase text-red mb-2">Access</p>
            <h1 className="text-2xl font-bold tracking-tight text-[#e8ecea]">Admin Profile Required</h1>
            <p className="text-sm text-[#5a6b64] mt-2">
              {error ?? 'This authenticated account is not mapped to an active admin profile.'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => { void signOut() }}
            className="bg-red/10 border border-red/25 text-red hover:bg-red/20 font-semibold text-sm px-4 py-2.5 rounded cursor-pointer transition-colors self-start"
          >
            Sign out
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-8 pb-16">
          <Routes>
            <Route path="/control" element={admin.role === 'super_admin' ? <ControlPage /> : <Navigate to="/labs" replace />} />
            <Route path="/labs"    element={<LabSelectorPage />} />
            {selectedLabId ? (
              <>
                <Route path="/"           element={<Navigate to="/overview" replace />} />
                <Route path="/overview"   element={<OverviewPage />} />
                <Route path="/users"      element={<UsersPage />} />
                <Route path="/enrollment" element={<EnrollmentPage />} />
                <Route path="/logs"       element={<LogsPage />} />
                <Route path="/system"     element={<SystemPage />} />
              </>
            ) : (
              <Route path="*" element={<LabSelectorPage />} />
            )}
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const { user, initialized, init } = useAuthStore()

  useEffect(() => {
    return init()
  }, [init])

  if (!initialized) return <LoadingScreen />

  return (
    <BrowserRouter>
      {user ? <AuthenticatedApp /> : <LoginPage />}
      <MockPanel />
    </BrowserRouter>
  )
}
