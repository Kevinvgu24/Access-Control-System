import {
  collection, doc, addDoc, setDoc, deleteDoc, getDocs,
  writeBatch, serverTimestamp, Timestamp,
} from 'firebase/firestore'
import { db } from './firebase'

const STORAGE_KEY = '__ece_mock__'

interface MockIds {
  labId:        string
  clusterId:    string
  nodeIds:      string[]
  userIds:      string[]
  universityIds: string[]
}

function stored(): MockIds | null {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') } catch { return null }
}

export function isMockSeeded(): boolean { return stored() !== null }

// ── Mock users ────────────────────────────────────────────────────────────────

const MOCK_USERS = [
  { universityId: '104240001', fullName: 'Nguyen Van An',   email: 'an.nguyen@hcmut.edu.vn',    roles: ['student']       },
  { universityId: '104240002', fullName: 'Tran Thi Bich',   email: 'bich.tran@hcmut.edu.vn',    roles: ['faculty']       },
  { universityId: '104240003', fullName: 'Le Van Cuong',    email: 'cuong.le@hcmut.edu.vn',     roles: ['lab_assistant'] },
  { universityId: '104240004', fullName: 'Pham Thi Dung',   email: 'dung.pham@hcmut.edu.vn',    roles: ['student']       },
  { universityId: '104240005', fullName: 'Hoang Van Em',    email: 'em.hoang@hcmut.edu.vn',     roles: ['guest']         },
]

// ── Event generator ───────────────────────────────────────────────────────────

type EventResult = 'granted' | 'denied' | 'unknown_user' | 'liveness_failed'

const EVENT_TEMPLATES: Array<{ result: EventResult; reason: string; confMin: number; confMax: number }> = [
  { result: 'granted',        reason: 'Face match above threshold',    confMin: 85, confMax: 99 },
  { result: 'granted',        reason: 'Face match above threshold',    confMin: 88, confMax: 97 },
  { result: 'granted',        reason: 'Face match above threshold',    confMin: 90, confMax: 99 },
  { result: 'denied',         reason: 'Confidence below threshold',    confMin: 35, confMax: 60 },
  { result: 'liveness_failed',reason: 'Liveness check failed',         confMin: 70, confMax: 85 },
  { result: 'unknown_user',   reason: 'No matching profile in database', confMin: 20, confMax: 45 },
  { result: 'granted',        reason: 'Face match above threshold',    confMin: 87, confMax: 96 },
  { result: 'denied',         reason: 'Confidence below threshold',    confMin: 40, confMax: 58 },
]

function makeEvents(_labId: string, daysAgo: number, count: number) {
  const base = new Date()
  base.setDate(base.getDate() - daysAgo)
  base.setHours(7, 30, 0, 0)

  return Array.from({ length: count }, (_, i) => {
    const tmpl  = EVENT_TEMPLATES[i % EVENT_TEMPLATES.length]
    const user  = tmpl.result === 'unknown_user' ? null : MOCK_USERS[i % (MOCK_USERS.length - 1)]
    const t     = new Date(base.getTime() + i * 28 * 60_000) // ~28 min apart
    const conf  = tmpl.confMin + Math.random() * (tmpl.confMax - tmpl.confMin)
    return {
      occurredAt:    Timestamp.fromDate(t),
      displayName:   user?.fullName ?? null,
      universityId:  user?.universityId ?? null,
      method:        'face' as const,
      result:        tmpl.result,
      confidence:    Math.round(conf * 10) / 10,
      reason:        tmpl.reason,
      _mock:         true,
    }
  })
}

// ── Seed ──────────────────────────────────────────────────────────────────────

export async function seedMockData(capturedBy: string): Promise<void> {
  if (isMockSeeded()) throw new Error('Already seeded — clear first.')

  // Lab
  const labRef = await addDoc(collection(db, 'labs'), {
    name: 'ECE Demo Lab', code: 'ECE-DEMO',
    location: 'Building C, Room 205', timezone: 'Asia/Ho_Chi_Minh',
    status: 'active', _mock: true,
    createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
  })
  const labId = labRef.id

  // Cluster
  const clusterRef = await addDoc(collection(db, 'labs', labId, 'clusters'), {
    name: 'Main Cluster', code: 'MAIN', status: 'active', _mock: true,
    createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
  })
  const clusterId = clusterRef.id

  // Nodes
  const nodeAlpha = await addDoc(collection(db, 'labs', labId, 'clusters', clusterId, 'nodes'), {
    name: 'Door A — Main Entrance', code: 'DOOR-A',
    deviceId: 'B8:27:EB:3A:5C:11', location: 'Main Entrance',
    status: 'online', onlineState: 'online',
    currentConfigVersion: 1, currentManifestVersion: 1,
    lastHeartbeatAt: serverTimestamp(), latestTelemetry: {},
    _mock: true, createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
  })
  const nodeBeta = await addDoc(collection(db, 'labs', labId, 'clusters', clusterId, 'nodes'), {
    name: 'Door B — Side Entrance', code: 'DOOR-B',
    deviceId: 'B8:27:EB:4B:6D:22', location: 'Side Entrance',
    status: 'offline', onlineState: 'offline',
    currentConfigVersion: 1, currentManifestVersion: 0,
    lastHeartbeatAt: null, latestTelemetry: {},
    _mock: true, createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
  })

  // Node state + config for alpha
  const alphaPath = `labs/${labId}/clusters/${clusterId}/nodes/${nodeAlpha.id}`
  await setDoc(doc(db, alphaPath, 'latest', 'state'), {
    cameraFps: 28.5, cpuPercent: 45.2, ramPercent: 62.1, temperatureC: 58.3,
    onlineState: 'online', modelStatus: 'running',
    updatedAt: serverTimestamp(), _mock: true,
  })
  await setDoc(doc(db, alphaPath, 'config', 'current'), {
    confidenceThreshold: 90, livenessThreshold: 78,
    pinFallbackEnabled: true, faceRequired: true, pinRequired: true,
    version: 1, updatedAt: serverTimestamp(), updatedBy: capturedBy, _mock: true,
  })

  // Users + memberships + identityIndex
  const userBatch = writeBatch(db)
  const userIds:      string[] = []
  const universityIds: string[] = []

  for (const u of MOCK_USERS) {
    const uRef = doc(collection(db, 'users'))
    userBatch.set(uRef, {
      ...u, majors: [], researchGroupIds: [],
      status: 'active', faceStatus: 'complete', pinStatus: 'set',
      _mock: true, lastAccessAt: null,
      createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
    })
    userBatch.set(doc(db, 'identityIndex', u.universityId), {
      userId: uRef.id, _mock: true, createdAt: serverTimestamp(),
    })
    userBatch.set(doc(db, 'users', uRef.id, 'labMemberships', labId), {
      labId, status: 'active',
      accessGroupIds: [], allowedClusterIds: [], allowedNodeIds: [],
      _mock: true, createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
    })
    userIds.push(uRef.id)
    universityIds.push(u.universityId)
  }
  await userBatch.commit()

  // Access events across 3 days
  const allEvents = [
    ...makeEvents(labId, 0, 12),
    ...makeEvents(labId, 1, 9),
    ...makeEvents(labId, 2, 6),
  ]
  // Firestore batch max 500 writes
  for (let i = 0; i < allEvents.length; i += 490) {
    const b = writeBatch(db)
    allEvents.slice(i, i + 490).forEach(ev =>
      b.set(doc(collection(db, 'labs', labId, 'accessEvents')), ev)
    )
    await b.commit()
  }

  // Incident
  await addDoc(collection(db, 'labs', labId, 'incidents'), {
    summary: 'Multiple failed access attempts at Door A — possible unauthorized entry',
    severity: 'medium', status: 'open', _mock: true,
    createdAt: serverTimestamp(),
  })

  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    labId, clusterId,
    nodeIds: [nodeAlpha.id, nodeBeta.id],
    userIds, universityIds,
  } satisfies MockIds))
}

// ── Clear ─────────────────────────────────────────────────────────────────────

export async function clearMockData(): Promise<void> {
  const ids = stored()
  if (!ids) throw new Error('No mock data found in this browser.')

  const { labId, clusterId, nodeIds, userIds, universityIds } = ids

  // Delete access events + incidents (batch up to 500)
  for (const colName of ['accessEvents', 'incidents'] as const) {
    const snap = await getDocs(collection(db, 'labs', labId, colName))
    for (let i = 0; i < snap.docs.length; i += 490) {
      const b = writeBatch(db)
      snap.docs.slice(i, i + 490).forEach(d => b.delete(d.ref))
      await b.commit()
    }
  }

  // Delete node sub-docs + nodes
  const nodeBatch = writeBatch(db)
  for (const nodeId of nodeIds) {
    const base = `labs/${labId}/clusters/${clusterId}/nodes/${nodeId}`
    nodeBatch.delete(doc(db, base, 'latest', 'state'))
    nodeBatch.delete(doc(db, base, 'config', 'current'))
    nodeBatch.delete(doc(db, base))
  }
  await nodeBatch.commit()

  // Delete cluster + lab
  await deleteDoc(doc(db, 'labs', labId, 'clusters', clusterId))
  await deleteDoc(doc(db, 'labs', labId))

  // Delete users + subcollections + identityIndex
  const userBatch = writeBatch(db)
  for (const userId of userIds) {
    userBatch.delete(doc(db, 'users', userId, 'labMemberships', labId))
    userBatch.delete(doc(db, 'users', userId))
  }
  for (const uniId of universityIds) {
    userBatch.delete(doc(db, 'identityIndex', uniId))
  }
  await userBatch.commit()

  localStorage.removeItem(STORAGE_KEY)
}
