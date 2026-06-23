import { useAdminStore } from '@/store/adminStore'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { fmtConf, fmtMethod, fmtTs, resultLabel, resultTone } from '@/lib/format'
import { useNavigate } from 'react-router-dom'

export function OverviewPage() {
  const { systemStatus, events, incidents, todayEntries, failedAttempts, averageConfidence, loading } = useAdminStore()
  const navigate = useNavigate()

  const sysStatusColor = systemStatus.overall === 'online' ? 'text-green' : systemStatus.overall === 'grace_period' ? 'text-amber' : 'text-red'
  const sysTopColor    = systemStatus.overall === 'online' ? 'bg-green'  : systemStatus.overall === 'grace_period' ? 'bg-amber'  : 'bg-red'

  const kpis = [
    { label: 'System Status',   value: systemStatus.overall.replace('_', ' '), sub: systemStatus.nodeLabel, color: sysStatusColor, top: sysTopColor },
    { label: "Today's Entries", value: String(todayEntries),  sub: 'Granted access',          color: 'text-[#e8ecea]', top: 'bg-white/10' },
    { label: 'Failed Attempts', value: String(failedAttempts),sub: 'Denied + liveness + PIN',  color: 'text-red',       top: 'bg-red'      },
    { label: 'Avg Confidence',  value: fmtConf(averageConfidence), sub: 'Rolling face avg',   color: 'text-blue',      top: 'bg-blue'     },
  ]

  return (
    <div className="flex flex-col gap-7">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <p className="font-mono text-[11px] tracking-widest uppercase text-[#3d4a46] mb-3">Command Center</p>
          <h1 className="text-4xl font-bold tracking-tight text-[#e8ecea]">Global Dashboard</h1>
          <p className="text-sm text-[#5a6b64] mt-2">Lab health, sync status, and live door activity.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => navigate('/enrollment')}>+ Add User</Button>
          <Button variant="ghost" onClick={() => navigate('/logs')}>Export Logs</Button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {kpis.map(({ label, value, sub, color, top }) => (
          <div key={label} className="bg-surface border border-white/[0.06] rounded-lg p-6 relative overflow-hidden">
            <div className={`absolute top-0 inset-x-0 h-0.5 ${top} opacity-70`} />
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] mb-4">{label}</p>
            <p className={`text-5xl font-bold tracking-tight leading-none capitalize ${color}`}>{value}</p>
            <p className="text-xs text-[#5a6b64] mt-3">{sub}</p>
          </div>
        ))}
      </div>

      {/* Content */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 380px' }}>
        {/* Feed */}
        <Panel>
          <PanelHeader eyebrow="Real-time" title="Live Activity Feed"
            action={
              <span className="flex items-center gap-1.5 font-mono text-[11px] text-[#3d4a46]">
                <span className={`${loading ? '' : 'blink'} w-1.5 h-1.5 rounded-full bg-green`} />
                {loading ? 'Loading…' : 'AUTO'}
              </span>
            }
          />
          <div className="flex flex-col gap-1">
            {events.length === 0 && !loading && (
              <p className="py-6 text-center font-mono text-xs text-[#3d4a46]">No events yet.</p>
            )}
            {events.slice(0, 10).map(ev => (
              <div key={ev.id} className="flex items-center justify-between gap-4 px-4 py-3 rounded bg-raised hover:bg-line transition-colors">
                <div className="flex items-center gap-4 min-w-0">
                  <span className="font-mono text-[12px] text-[#3d4a46] shrink-0 w-10">
                    {fmtTs(ev.occurredAt).slice(11, 16)}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[#e8ecea] truncate">{ev.displayName ?? 'Unknown User'}</p>
                    <p className="font-mono text-[11px] text-[#3d4a46] mt-0.5 truncate">{fmtMethod(ev.method)} · {ev.reason}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {ev.confidence > 0 && <span className="font-mono text-xs text-[#5a6b64]">{fmtConf(ev.confidence)}</span>}
                  <Badge tone={resultTone(ev.result)}>{resultLabel(ev.result)}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* Right */}
        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader eyebrow="Watch" title="Incidents" />
            <div className="flex flex-col gap-2">
              {incidents.length === 0 ? (
                <div className="flex gap-3 items-start px-3 py-2.5 rounded bg-green/5 border-l-2 border-green/40 text-sm text-[#a8bbb2]">
                  System healthy. Monitoring live activity.
                </div>
              ) : incidents.map(inc => (
                <div key={inc.id} className={`flex gap-3 items-start px-3 py-2.5 rounded border-l-2 text-sm text-[#a8bbb2] ${
                  inc.severity === 'high' ? 'bg-red/5 border-red/40' : 'bg-amber/5 border-amber/40'
                }`}>{inc.summary}</div>
              ))}
            </div>
          </Panel>

          <Panel>
            <PanelHeader eyebrow="Trend" title="Confidence Band" />
            <div className="flex flex-col gap-3">
              {events.slice(0, 6).map(ev => {
                const pct = Math.max(ev.confidence ?? 50, 15)
                const barColor = ev.result === 'granted' ? 'bg-green' : ev.result === 'denied' || ev.result === 'pin_failed' ? 'bg-red' : 'bg-amber'
                return (
                  <div key={ev.id} className="flex items-center gap-3">
                    <span className="font-mono text-[11px] text-[#3d4a46] w-10 shrink-0">{fmtTs(ev.occurredAt).slice(11, 16)}</span>
                    <div className="flex-1 h-1 rounded-full bg-line overflow-hidden">
                      <div className={`h-full rounded-full opacity-75 ${barColor}`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="font-mono text-[11px] text-[#5a6b64] w-10 text-right shrink-0">{fmtConf(ev.confidence)}</span>
                  </div>
                )
              })}
              {events.length === 0 && (
                <p className="font-mono text-[11px] text-[#3d4a46]">No data yet.</p>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
