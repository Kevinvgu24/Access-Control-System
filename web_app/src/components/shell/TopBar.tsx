import { useAdminStore } from '@/store/adminStore'

export function TopBar() {
  const { systemStatus } = useAdminStore()
  const sys  = systemStatus.overall
  const cam  = systemStatus.cameraState
  const sync = systemStatus.syncState

  const sysColor  = sys === 'online' ? 'text-green' : sys === 'grace_period' ? 'text-amber' : 'text-red'
  const camColor  = cam === 'connected' ? 'text-green' : 'text-red'
  const syncColor = sync === 'live' ? 'text-green' : sync === 'delayed' ? 'text-amber' : 'text-red'

  return (
    <div className="h-11 flex items-center px-8 gap-6 bg-darker border-b border-white/[0.05] shrink-0">
      <Item label="Node"   value={systemStatus.nodeLabel} />
      <div className="w-px h-4 bg-white/10" />
      <Item label="System" value={sys.replace('_', ' ')} color={sysColor} />
      <Item label="Camera" value={cam}                   color={camColor} />
      <Item label="Sync"   value={sync}                  color={syncColor} />
      <div className="ml-auto font-mono text-[11px] text-[#3d4a46]">{systemStatus.lastSyncAt}</div>
    </div>
  )
}

function Item({ label, value, color = 'text-[#a8bbb2]' }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-[10px] text-[#3d4a46] uppercase tracking-widest">{label}</span>
      <span className={`font-mono text-[12px] font-medium capitalize ${color}`}>{value}</span>
    </div>
  )
}
