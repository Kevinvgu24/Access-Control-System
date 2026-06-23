import { useState, useMemo } from 'react'
import { useAdminStore } from '@/store/adminStore'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { fmtConf, fmtMethod, fmtTs, resultLabel, resultTone } from '@/lib/format'
import type { AccessResult } from '@/types/admin'

const OPTS: { value: AccessResult | 'all'; label: string }[] = [
  { value: 'all',             label: 'All Events'    },
  { value: 'granted',         label: 'Granted'       },
  { value: 'denied',          label: 'Denied'        },
  { value: 'unknown_user',    label: 'Unknown'       },
  { value: 'liveness_failed', label: 'Liveness Fail' },
  { value: 'pin_failed',      label: 'PIN Failed'    },
]

export function LogsPage() {
  const { events } = useAdminStore()
  const [search, setSearch]             = useState('')
  const [resultFilter, setResultFilter] = useState<AccessResult | 'all'>('all')
  const [dateFrom, setDateFrom]         = useState('')
  const [dateTo, setDateTo]             = useState('')

  const filtered = useMemo(() => events.filter(ev => {
    const ts = fmtTs(ev.occurredAt)
    const name = (ev.displayName ?? '').toLowerCase()
    const uid  = ev.universityId ?? ''
    return (
      (!search || name.includes(search.toLowerCase()) || uid.includes(search)) &&
      (resultFilter === 'all' || ev.result === resultFilter) &&
      (!dateFrom || ts >= dateFrom) &&
      (!dateTo   || ts <= dateTo + ' 23:59')
    )
  }), [events, search, resultFilter, dateFrom, dateTo])

  function exportCSV() {
    const rows = [
      'Timestamp,University ID,Name,Method,Confidence,Result,Reason',
      ...filtered.map(ev => [
        fmtTs(ev.occurredAt), ev.universityId ?? '', ev.displayName ?? 'Unknown',
        ev.method, ev.confidence, ev.result, ev.reason,
      ].join(','))
    ].join('\n')
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([rows], { type: 'text/csv' })),
      download: 'access-log.csv',
    })
    a.click()
  }

  const chipClass = (active: boolean) =>
    `px-3 py-1.5 rounded font-mono text-[11px] border cursor-pointer transition-colors ${
      active ? 'bg-green/10 border-green/25 text-green' : 'bg-raised border-white/10 text-[#5a6b64] hover:text-[#a8bbb2]'
    }`

  return (
    <div className="flex flex-col gap-7">
      <div className="flex justify-between items-end">
        <div>
          <p className="font-mono text-[11px] tracking-widest uppercase text-[#3d4a46] mb-3">The Ledger</p>
          <h1 className="text-4xl font-bold tracking-tight text-[#e8ecea]">Access Log</h1>
          <p className="text-sm text-[#5a6b64] mt-2">{filtered.length} of {events.length} events shown.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="primary" onClick={exportCSV}>Export CSV</Button>
          <Button variant="ghost">Export JSON</Button>
        </div>
      </div>

      <Panel>
        <PanelHeader eyebrow="Filter" title="Search & Filter" />
        <div className="flex flex-col gap-3">
          <div className="flex gap-3 items-center">
            <input type="text" placeholder="Search by name or university ID…" value={search}
              onChange={e => setSearch(e.target.value)}
              className="flex-1 bg-raised border border-white/10 rounded px-3 py-2 text-sm text-[#e8ecea] placeholder:text-[#2d3834] outline-none focus:border-green/30 transition-colors"
            />
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="bg-raised border border-white/10 rounded px-3 py-2 text-sm text-[#5a6b64] outline-none focus:border-green/30 [color-scheme:dark]"
            />
            <span className="font-mono text-xs text-[#3d4a46]">to</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="bg-raised border border-white/10 rounded px-3 py-2 text-sm text-[#5a6b64] outline-none focus:border-green/30 [color-scheme:dark]"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {OPTS.map(({ value, label }) => (
              <button key={value} onClick={() => setResultFilter(value)} className={chipClass(resultFilter === value)}>{label}</button>
            ))}
          </div>
        </div>
      </Panel>

      <Panel pad={false}>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-raised">
              {['Timestamp', 'User', 'Method', 'Confidence', 'Result', 'Reason'].map(h => (
                <th key={h} className="text-left px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] border-b border-white/[0.05]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(ev => (
              <tr key={ev.id} className="border-b border-white/[0.04] hover:bg-raised transition-colors last:border-0">
                <td className="px-5 py-3.5 font-mono text-xs text-[#5a6b64]">{fmtTs(ev.occurredAt)}</td>
                <td className="px-5 py-3.5">
                  <p className="text-sm font-semibold text-[#e8ecea]">{ev.displayName ?? 'Unknown User'}</p>
                  <p className="font-mono text-[11px] text-[#3d4a46] mt-0.5">{ev.universityId ?? '—'}</p>
                </td>
                <td className="px-5 py-3.5 font-mono text-xs text-[#5a6b64]">{fmtMethod(ev.method)}</td>
                <td className="px-5 py-3.5 font-mono text-sm font-semibold text-[#e8ecea]">{fmtConf(ev.confidence)}</td>
                <td className="px-5 py-3.5"><Badge tone={resultTone(ev.result)}>{resultLabel(ev.result)}</Badge></td>
                <td className="px-5 py-3.5 font-mono text-xs text-[#5a6b64] max-w-[200px] truncate">{ev.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="py-12 text-center font-mono text-xs text-[#3d4a46]">No events match current filters.</p>
        )}
      </Panel>
    </div>
  )
}
