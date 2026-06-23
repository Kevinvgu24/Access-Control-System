import type { AccessResult, NodeOnlineState, AccessMethod } from '@/types/admin'
import type { Timestamp } from 'firebase/firestore'

type Tone = 'green' | 'red' | 'amber' | 'blue' | 'neutral'

export function resultLabel(r: AccessResult): string {
  const m: Record<AccessResult, string> = {
    granted:         'Granted',
    denied:          'Denied',
    unknown_user:    'Unknown',
    liveness_failed: 'Liveness Fail',
    pin_failed:      'PIN Failed',
    system_error:    'System Error',
  }
  return m[r] ?? r
}

export function resultTone(r: AccessResult): Tone {
  const m: Record<AccessResult, Tone> = {
    granted:         'green',
    denied:          'red',
    unknown_user:    'neutral',
    liveness_failed: 'amber',
    pin_failed:      'red',
    system_error:    'neutral',
  }
  return m[r] ?? 'neutral'
}

export function onlineTone(s: NodeOnlineState): 'green' | 'amber' | 'red' {
  return s === 'online' ? 'green' : s === 'grace_period' ? 'amber' : 'red'
}

export function fmtMethod(m: AccessMethod): string {
  return m === 'face' ? 'Face ID' : 'Face + PIN'
}

export function fmtConf(v: number | null | undefined): string {
  return v == null ? 'N/A' : `${v.toFixed(1)}%`
}

export function fmtTs(ts: Timestamp | null | undefined): string {
  if (!ts) return '—'
  return ts.toDate().toLocaleString('sv-SE').replace('T', ' ').slice(0, 16)
}
