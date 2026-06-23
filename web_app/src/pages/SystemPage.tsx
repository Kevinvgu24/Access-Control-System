import { useState } from 'react'
import { useAdminStore } from '@/store/adminStore'
import { useLabStore }   from '@/store/labStore'
import { useAuthStore }  from '@/store/authStore'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { Button } from '@/components/ui/Button'
import { updateNodeConfig, getFirstLabNode } from '@/lib/db'
import { fmtTs } from '@/lib/format'

function Slider({ label, value, hint, onChange, warn }: {
  label: string; value: number; hint: string; onChange: (v: number) => void; warn?: boolean
}) {
  const color    = warn ? 'text-amber' : 'text-green'
  const barColor = warn ? 'bg-amber'   : 'bg-green'
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-between items-start gap-4">
        <div>
          <p className="text-[15px] font-semibold text-[#e8ecea]">{label}</p>
          <p className="text-sm text-[#5a6b64] mt-1">{hint}</p>
        </div>
        <strong className={`font-mono text-3xl font-semibold leading-none shrink-0 ${color}`}>
          {value}<span className="text-base opacity-50">%</span>
        </strong>
      </div>
      <div className="relative h-1.5 rounded-full bg-line">
        <div className={`absolute left-0 top-0 h-full rounded-full opacity-75 transition-all ${barColor}`} style={{ width: `${value}%` }} />
        <input type="range" min={0} max={100} value={value} onChange={e => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
      </div>
      <div className="flex justify-between font-mono text-[10px] text-[#3d4a46]"><span>0%</span><span>100%</span></div>
    </div>
  )
}

type MT = 'green' | 'amber' | 'red'
function Stat({ label, value, unit, tone }: { label: string; value: string | number; unit: string; tone: MT }) {
  const c: Record<MT, string> = { green: 'text-green', amber: 'text-amber', red: 'text-red' }
  return (
    <div className="bg-raised border border-white/[0.06] rounded-lg px-5 py-4 flex flex-col gap-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-[#3d4a46]">{label}</span>
      <strong className={`font-mono text-3xl font-semibold leading-none ${c[tone]}`}>
        {value}<span className="text-sm opacity-50 ml-0.5">{unit}</span>
      </strong>
    </div>
  )
}

export function SystemPage() {
  const { nodeConfig, nodeState, refreshNodeConfig } = useAdminStore()
  const { selectedLabId } = useLabStore()
  const { admin }         = useAuthStore()

  const [localConf, setLocalConf] = useState<number>(nodeConfig?.confidenceThreshold ?? 90)
  const [localLiv,  setLocalLiv]  = useState<number>(nodeConfig?.livenessThreshold  ?? 78)
  const [saving, setSaving]       = useState(false)
  const [saved,  setSaved]        = useState(false)

  const save = async () => {
    if (!selectedLabId) return
    setSaving(true)
    try {
      const node = await getFirstLabNode(selectedLabId)
      if (node) {
        await updateNodeConfig(
          selectedLabId, node.clusterId, node.id,
          { confidenceThreshold: localConf, livenessThreshold: localLiv },
          admin?.firebaseUid ?? 'unknown'
        )
        await refreshNodeConfig(selectedLabId, node.clusterId, node.id)
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      }
    } finally {
      setSaving(false)
    }
  }

  const conf = localConf
  const fps  = nodeState?.cameraFps    ?? 0
  const cpu  = nodeState?.cpuPercent   ?? 0
  const ram  = nodeState?.ramPercent   ?? 0
  const temp = nodeState?.temperatureC ?? 0

  return (
    <div className="flex flex-col gap-7">
      <div>
        <p className="font-mono text-[11px] tracking-widest uppercase text-[#3d4a46] mb-3">The Engine Room</p>
        <h1 className="text-4xl font-bold tracking-tight text-[#e8ecea]">System Config</h1>
        <p className="text-sm text-[#5a6b64] mt-2">Tune model thresholds and monitor hardware in real time.</p>
      </div>

      <div className="grid gap-5" style={{ gridTemplateColumns: '1fr 360px' }}>
        <Panel>
          <PanelHeader eyebrow="Model Tuning" title="Recognition Thresholds"
            action={
              <Button variant="primary" size="sm" onClick={save} disabled={saving}>
                {saved ? '✓ Saved' : saving ? 'Saving…' : 'Apply Changes'}
              </Button>
            }
          />
          <div className="flex flex-col gap-8">
            <Slider label="Match Confidence Threshold" hint="Minimum confidence score to grant face access."
              value={localConf} onChange={v => setLocalConf(v)} warn={localConf < 80} />
            <Slider label="Liveness Threshold" hint="How aggressively the system rejects spoofing attempts."
              value={localLiv} onChange={v => setLocalLiv(v)} />
          </div>
          {conf < 80 && (
            <div className="flex items-start gap-3 px-4 py-3.5 bg-amber/5 border border-amber/20 rounded text-sm text-amber mt-7">
              <span className="shrink-0">⚠</span> Low threshold increases false positives. Recommended minimum: 80%.
            </div>
          )}
          {nodeConfig && (
            <p className="font-mono text-[11px] text-[#3d4a46] mt-7 pt-5 border-t border-white/[0.05]">
              Updated {fmtTs(nodeConfig.updatedAt)} · {nodeConfig.updatedBy}
            </p>
          )}
          {!nodeConfig && (
            <p className="font-mono text-[11px] text-[#3d4a46] mt-7 pt-5 border-t border-white/[0.05]">
              No config found — defaults shown. Apply to create initial config.
            </p>
          )}
        </Panel>

        <div className="flex flex-col gap-5">
          <Panel>
            <PanelHeader eyebrow="Hardware" title="Live Metrics" />
            {nodeState ? (
              <div className="grid grid-cols-2 gap-3">
                <Stat label="FPS"  value={fps.toFixed(1)} unit="fps" tone={fps < 15 ? 'red' : fps < 20 ? 'amber' : 'green'} />
                <Stat label="CPU"  value={cpu}            unit="%"   tone={cpu > 80 ? 'red' : cpu > 60 ? 'amber' : 'green'} />
                <Stat label="RAM"  value={ram}            unit="%"   tone={ram > 80 ? 'red' : ram > 60 ? 'amber' : 'green'} />
                <Stat label="Temp" value={temp}           unit="°C"  tone={temp > 70 ? 'red' : temp > 55 ? 'amber' : 'green'} />
              </div>
            ) : (
              <p className="font-mono text-[11px] text-[#3d4a46]">No telemetry — node offline or no node found.</p>
            )}
          </Panel>
          <Panel>
            <PanelHeader eyebrow="Notes" title="Testing Tips" />
            <ul className="flex flex-col gap-3">
              {[
                'Start at 90% confidence, lower if good users are rejected.',
                'High liveness + poor lighting = false rejections.',
                'CPU above 80% consistently? Check model thread count.',
                'FPS below 15? Camera buffer overflow suspected.',
              ].map(note => (
                <li key={note} className="flex items-start gap-3 text-sm text-[#5a6b64] leading-snug">
                  <span className="w-1 h-1 rounded-full bg-[#3d4a46] shrink-0 mt-1.5" />{note}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  )
}
