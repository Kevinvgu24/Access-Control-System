import type { Timestamp } from 'firebase/firestore'

export type AdminRole       = 'super_admin' | 'lab_admin'
export type AdminStatus     = 'active' | 'suspended'
export type UserRole        = 'student' | 'faculty' | 'lab_assistant' | 'guest' | 'maintenance'
export type UserStatus      = 'active' | 'suspended'
export type AccessMethod    = 'face' | 'face_pin_fallback'
export type AccessResult    = 'granted' | 'denied' | 'liveness_failed' | 'unknown_user' | 'pin_failed' | 'system_error'
export type NodeOnlineState = 'online' | 'grace_period' | 'offline'
export type CameraState     = 'connected' | 'disconnected' | 'unknown'
export type SyncState       = 'live' | 'delayed' | 'offline'
export type LabStatus       = 'active' | 'inactive' | 'maintenance'

export interface SystemStatus {
  overall:     NodeOnlineState
  cameraState: CameraState
  syncState:   SyncState
  lastSyncAt:  string
  nodeLabel:   string
}

export interface Lab {
  id:          string
  name:        string
  code:        string
  location?:   string
  timezone:    string
  status:      LabStatus
  createdAt:   Timestamp | null
  updatedAt:   Timestamp | null
}

export interface Cluster {
  id:          string
  name:        string
  code:        string
  status:      string
  createdAt:   Timestamp | null
  updatedAt:   Timestamp | null
}

export interface Node {
  id:          string
  name:        string
  code:        string
  clusterId?:  string
  deviceId?:   string
  location?:   string
  status:      'online' | 'offline' | 'degraded' | 'maintenance'
  onlineState?: NodeOnlineState
  lastHeartbeatAt?: Timestamp | null
  currentConfigVersion?: number
  currentManifestVersion?: number
  latestTelemetry?: Record<string, unknown>
  createdAt:   Timestamp | null
  updatedAt?:  Timestamp | null
}

export interface NodeState {
  cameraFps:         number
  cpuPercent:        number
  ramPercent:        number
  temperatureC:      number
  cameraState?:      CameraState
  onlineState:       NodeOnlineState
  modelStatus?:      'running' | 'stopped' | 'error'
  updatedAt:         Timestamp | null
  lastHeartbeatAt?:  Timestamp | null
}

export interface NodeConfig {
  confidenceThreshold: number
  livenessThreshold:   number
  pinFallbackEnabled?: boolean
  faceRequired?:       boolean
  pinRequired?:        boolean
  version?:            number
  updatedAt:           Timestamp | null
  updatedBy:           string
}

export interface AccessEvent {
  id:            string
  occurredAt:    Timestamp | null
  displayName:   string | null
  universityId:  string | null
  method:        AccessMethod
  result:        AccessResult
  confidence:    number
  reason:        string
  nodeId?:       string
  clusterId?:    string
}

export interface Incident {
  id:        string
  summary:   string
  severity:  'low' | 'medium' | 'high' | 'critical'
  status:    'open' | 'resolved'
  createdAt: Timestamp | null
}

export interface User {
  id:           string
  universityId: string
  fullName:     string
  email:        string
  roles:        UserRole[]
  status:       UserStatus
  faceStatus:   'complete' | 'incomplete'
  pinStatus:    'set' | 'missing'
  lastAccessAt: Timestamp | null
  createdAt:    Timestamp | null
}

export interface AdminDoc {
  id:            string
  firebaseUid:   string
  userId:        string
  type:          AdminRole
  role:          AdminRole
  status:        AdminStatus
  createdAt:     Timestamp | null
  createdBy:     string
  email?:        string
  displayName?:  string
  labAccessIds?: string[]
}

export interface LabMembership {
  labId:             string
  status:            'active' | 'suspended'
  accessGroupIds:    string[]
  allowedClusterIds: string[]
  allowedNodeIds:    string[]
  createdAt:         Timestamp | null
  updatedAt:         Timestamp | null
}
