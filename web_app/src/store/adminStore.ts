import { create } from 'zustand'
import {
  subscribeAccessEvents, subscribeIncidents, subscribeNodeState,
  getFirstLabNode, getLabUsers, getNodeConfig,
} from '@/lib/db'
import type { AccessEvent, User, Incident, SystemStatus, NodeState, NodeConfig } from '@/types/admin'
import { fmtTs } from '@/lib/format'
import { useLabStore } from '@/store/labStore'

// ── Helpers ─────────────────────────────────────────────────────────────────

function isToday(ts: import('firebase/firestore').Timestamp | null | undefined): boolean {
  if (!ts) return false
  const d = ts.toDate()
  const now = new Date()
  return d.getFullYear() === now.getFullYear() &&
         d.getMonth() === now.getMonth() &&
         d.getDate() === now.getDate()
}

function computeStats(events: AccessEvent[]) {
  const today = events.filter(e => isToday(e.occurredAt))
  const todayEntries  = today.filter(e => e.result === 'granted').length
  const failedAttempts = today.filter(e => e.result === 'denied' || e.result === 'liveness_failed' || e.result === 'pin_failed').length
  const withConf = events.filter(e => e.confidence != null).slice(0, 30)
  const averageConfidence = withConf.length
    ? withConf.reduce((s, e) => s + e.confidence, 0) / withConf.length
    : null
  return { todayEntries, failedAttempts, averageConfidence }
}

function deriveSystemStatus(state: NodeState | null, nodeLabel: string): SystemStatus {
  if (!state) return { overall: 'offline', cameraState: 'unknown', syncState: 'offline', lastSyncAt: '—', nodeLabel }
  const syncState = state.onlineState === 'online' ? 'live'
    : state.onlineState === 'grace_period' ? 'delayed'
    : 'offline'
  return {
    overall:     state.onlineState,
    cameraState: state.modelStatus === 'running' ? 'connected' : 'disconnected',
    syncState,
    lastSyncAt:  fmtTs(state.updatedAt),
    nodeLabel,
  }
}

// ── Store ────────────────────────────────────────────────────────────────────

interface AdminStore {
  systemStatus: SystemStatus
  events: AccessEvent[]
  users: User[]
  nodeState: NodeState | null
  nodeConfig: NodeConfig | null
  incidents: Incident[]
  todayEntries: number
  failedAttempts: number
  averageConfidence: number | null
  loading: boolean

  subscribe: (labId: string, labName: string) => () => void
  refreshUsers: (labId: string) => Promise<void>
  refreshNodeConfig: (labId: string, clusterId: string, nodeId: string) => Promise<void>
}

const defaultStatus: SystemStatus = {
  overall: 'offline', cameraState: 'disconnected',
  syncState: 'offline', lastSyncAt: '—', nodeLabel: '—',
}

// Monotonically-increasing counter — guards stale async results after lab switch
let _subscribeVersion = 0

export const useAdminStore = create<AdminStore>((set) => ({
  systemStatus: defaultStatus,
  events: [],
  users: [],
  nodeState: null,
  nodeConfig: null,
  incidents: [],
  todayEntries: 0,
  failedAttempts: 0,
  averageConfidence: null,
  loading: false,

  subscribe: (labId, labName) => {
    set({ loading: true })
    const v = ++_subscribeVersion

    const unsubEvents    = subscribeAccessEvents(labId, 60, events => {
      set({ events, ...computeStats(events), loading: false })
    })
    const unsubIncidents = subscribeIncidents(labId, incidents => set({ incidents }))

    let unsubNode: (() => void) | undefined

    const setupNode = (clusterId: string, nodeId: string) => {
      const nodeLabel = `${labName} / Node ${nodeId.slice(0, 4).toUpperCase()}`
      unsubNode = subscribeNodeState(labId, clusterId, nodeId, state => {
        set({ nodeState: state, systemStatus: deriveSystemStatus(state, nodeLabel) })
      })
      void getNodeConfig(labId, clusterId, nodeId).then(cfg => {
        if (_subscribeVersion === v) set({ nodeConfig: cfg })
      })
    }

    const { selectedClusterId, selectedNodeId, cacheNode } = useLabStore.getState()

    const nodeTask = selectedClusterId && selectedNodeId
      ? Promise.resolve(setupNode(selectedClusterId, selectedNodeId))
      : getFirstLabNode(labId).then(node => {
          if (!node || _subscribeVersion !== v) return
          cacheNode(node.clusterId, node.id)
          setupNode(node.clusterId, node.id)
        })

    void Promise.all([
      getLabUsers(labId).then(users => {
        if (_subscribeVersion === v) set({ users })
      }),
      nodeTask,
    ])

    return () => {
      unsubEvents()
      unsubIncidents()
      unsubNode?.()
    }
  },

  refreshUsers: async (labId) => {
    const users = await getLabUsers(labId)
    set({ users })
  },

  refreshNodeConfig: async (labId, clusterId, nodeId) => {
    const cfg = await getNodeConfig(labId, clusterId, nodeId)
    set({ nodeConfig: cfg })
  },
}))
