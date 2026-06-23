import {
  collection, collectionGroup, doc, getDocs, getDoc, addDoc, setDoc, updateDoc, deleteDoc,
  onSnapshot, query, where, orderBy, limit, serverTimestamp, runTransaction, writeBatch,
  documentId, Timestamp,
  type Query, type DocumentData, type QueryConstraint,
} from 'firebase/firestore'
import { httpsCallable } from 'firebase/functions'
import { db, functions } from './firebase'
import type {
  Lab, Cluster, Node, NodeState, NodeConfig, User, AccessEvent, Incident, AdminDoc,
} from '@/types/admin'

function makeCode(input: string, fallback: string): string {
  const normalized = input
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24)

  return normalized || fallback
}

// ── Labs ─────────────────────────────────────────────────────────────────────

export function subscribeVisibleLabs(
  params: {
    isSuperAdmin: boolean
    labIds: string[]
    onData: (labs: Lab[]) => void
    onError?: (error: Error) => void
  }
) {
  const { isSuperAdmin, labIds, onData, onError } = params

  if (isSuperAdmin) {
    return onSnapshot(
      query(collection(db, 'labs'), orderBy('name')),
      snap => onData(snap.docs.map(d => ({ id: d.id, ...d.data() }) as Lab)),
      err => onError?.(err)
    )
  }

  const ids = [...new Set(labIds.filter(Boolean))]
  if (ids.length === 0) {
    onData([])
    return () => {}
  }

  const labsById = new Map<string, Lab>()
  const emit = () => {
    onData(ids.map(id => labsById.get(id)).filter(Boolean) as Lab[])
  }

  const unsubs = Array.from({ length: Math.ceil(ids.length / 30) }, (_, index) =>
    ids.slice(index * 30, index * 30 + 30)
  ).map(chunk =>
    onSnapshot(
      query(collection(db, 'labs'), where(documentId(), 'in', chunk)),
      snap => {
        snap.docChanges().forEach(change => {
          if (change.type === 'removed') {
            labsById.delete(change.doc.id)
            return
          }
          labsById.set(change.doc.id, { id: change.doc.id, ...change.doc.data() } as Lab)
        })
        emit()
      },
      err => onError?.(err)
    )
  )

  return () => {
    unsubs.forEach(unsub => unsub())
  }
}

export async function getAllLabs(): Promise<Lab[]> {
  const snap = await getDocs(query(collection(db, 'labs'), orderBy('name')))
  return snap.docs.map(d => ({ id: d.id, ...d.data() }) as Lab)
}

export async function createLab(
  data: { name: string; code?: string; location?: string; timezone: string },
  createdBy: string
): Promise<string> {
  void createdBy
  const ref = await addDoc(collection(db, 'labs'), {
    name: data.name,
    code: makeCode(data.code ?? data.name, 'LAB'),
    location: data.location ?? '',
    timezone: data.timezone,
    status: 'active',
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  })
  return ref.id
}

export async function updateLab(labId: string, patch: Partial<Lab>): Promise<void> {
  await updateDoc(doc(db, 'labs', labId), { ...patch, updatedAt: serverTimestamp() })
}

export async function archiveLab(labId: string): Promise<void> {
  await updateDoc(doc(db, 'labs', labId), { status: 'inactive', updatedAt: serverTimestamp() })
}

// ── Clusters ──────────────────────────────────────────────────────────────────

export async function getLabClusters(labId: string): Promise<Cluster[]> {
  const snap = await getDocs(collection(db, 'labs', labId, 'clusters'))
  return snap.docs.map(d => ({ id: d.id, ...d.data() }) as Cluster)
}

export async function createCluster(labId: string, name: string, createdBy: string): Promise<string> {
  void createdBy
  const ref = await addDoc(collection(db, 'labs', labId, 'clusters'), {
    name,
    code: makeCode(name, 'CLUSTER'),
    status: 'active',
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  })
  return ref.id
}

export async function createNode(
  labId: string,
  clusterId: string,
  data: { name: string; deviceId?: string; location?: string },
  createdBy: string
): Promise<string> {
  const ref = await addDoc(
    collection(db, 'labs', labId, 'clusters', clusterId, 'nodes'),
    {
      ...data,
      status: 'offline',
      onlineState: 'offline',
      code: makeCode(data.name, 'NODE'),
      currentConfigVersion: 1,
      currentManifestVersion: 0,
      lastHeartbeatAt: null,
      latestTelemetry: {},
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    }
  )
  await setDoc(
    doc(db, 'labs', labId, 'clusters', clusterId, 'nodes', ref.id, 'config', 'current'),
    {
      confidenceThreshold: 90,
      livenessThreshold: 78,
      pinFallbackEnabled: true,
      faceRequired: true,
      pinRequired: true,
      version: 1,
      updatedAt: serverTimestamp(),
      updatedBy: createdBy,
    }
  )
  return ref.id
}

export async function updateNode(
  labId: string, clusterId: string, nodeId: string, patch: Partial<Node>
): Promise<void> {
  await updateDoc(
    doc(db, 'labs', labId, 'clusters', clusterId, 'nodes', nodeId),
    { ...patch, updatedAt: serverTimestamp() }
  )
}

export async function getClusterNodes(labId: string, clusterId: string): Promise<Node[]> {
  const snap = await getDocs(collection(db, 'labs', labId, 'clusters', clusterId, 'nodes'))
  return snap.docs.map(d => ({ id: d.id, ...d.data() }) as Node)
}

export async function deleteNode(labId: string, clusterId: string, nodeId: string): Promise<void> {
  await deleteDoc(doc(db, 'labs', labId, 'clusters', clusterId, 'nodes', nodeId))
}

// ── Admins ────────────────────────────────────────────────────────────────────

export async function getAllAdmins(): Promise<AdminDoc[]> {
  const snap = await getDocs(collection(db, 'admins'))
  const admins = await Promise.all(snap.docs.map(async d => {
    const admin = { id: d.id, ...d.data() } as AdminDoc
    if (admin.type !== 'lab_admin') return admin

    const accessSnap = await getDocs(collection(db, 'admins', d.id, 'labAccess'))
    return {
      ...admin,
      labAccessIds: accessSnap.docs
        .filter(docSnap => docSnap.data().status === 'active')
        .map(docSnap => docSnap.id),
    } satisfies AdminDoc
  }))

  return admins.sort((a, b) => (a.displayName ?? a.email ?? a.id).localeCompare(b.displayName ?? b.email ?? b.id))
}

export async function createLabAdmin(
  data: { email: string; password: string; displayName: string; labIds: string[] },
): Promise<string> {
  const fn = httpsCallable<
    { email: string; password: string; displayName: string; labIds: string[] },
    { uid: string }
  >(functions, 'createAdminUser')
  const result = await fn({
    email:       data.email,
    password:    data.password,
    displayName: data.displayName,
    labIds:      data.labIds,
  })
  return result.data.uid
}

export async function updateAdminLabAccess(adminId: string, labIds: string[]): Promise<void> {
  const existing = await getDocs(collection(db, 'admins', adminId, 'labAccess'))
  const batch = writeBatch(db)
  existing.docs.forEach(d => batch.delete(d.ref))
  for (const labId of labIds) {
    batch.set(doc(db, 'admins', adminId, 'labAccess', labId), {
      labId,
      role: 'admin',
      status: 'active',
      createdAt: serverTimestamp(),
    })
  }
  await batch.commit()
}

export async function deleteAdminDoc(adminId: string): Promise<void> {
  await deleteDoc(doc(db, 'admins', adminId))
}

// ── Nodes ─────────────────────────────────────────────────────────────────────

export async function getFirstLabNode(labId: string) {
  const clustersSnap = await getDocs(collection(db, 'labs', labId, 'clusters'))
  if (clustersSnap.empty) return null
  const firstCluster = clustersSnap.docs[0]
  const nodesSnap = await getDocs(
    collection(db, 'labs', labId, 'clusters', firstCluster.id, 'nodes')
  )
  if (nodesSnap.empty) return null
  return { id: nodesSnap.docs[0].id, clusterId: firstCluster.id }
}

export async function getLabNodes(labId: string): Promise<Array<Node & { clusterId: string }>> {
  const clustersSnap = await getDocs(collection(db, 'labs', labId, 'clusters'))
  const result: Array<Node & { clusterId: string }> = []
  for (const c of clustersSnap.docs) {
    const nodesSnap = await getDocs(collection(db, 'labs', labId, 'clusters', c.id, 'nodes'))
    nodesSnap.docs.forEach(n =>
      result.push({ id: n.id, clusterId: c.id, ...n.data() } as Node & { clusterId: string })
    )
  }
  return result
}

export function subscribeNodeState(
  labId: string,
  clusterId: string,
  nodeId: string,
  cb: (state: NodeState | null) => void
) {
  return onSnapshot(
    doc(db, 'labs', labId, 'clusters', clusterId, 'nodes', nodeId, 'latest', 'state'),
    snap => cb(snap.exists() ? (snap.data() as NodeState) : null)
  )
}

// ── Node Config ───────────────────────────────────────────────────────────────

export async function getNodeConfig(
  labId: string,
  clusterId: string,
  nodeId: string
): Promise<NodeConfig | null> {
  const snap = await getDoc(
    doc(db, 'labs', labId, 'clusters', clusterId, 'nodes', nodeId, 'config', 'current')
  )
  return snap.exists() ? (snap.data() as NodeConfig) : null
}

export async function updateNodeConfig(
  labId: string,
  clusterId: string,
  nodeId: string,
  patch: Partial<NodeConfig>,
  updatedBy: string
) {
  const ref = doc(db, 'labs', labId, 'clusters', clusterId, 'nodes', nodeId, 'config', 'current')
  await runTransaction(db, async tx => {
    const current = await tx.get(ref)
    const prevVersion: number = current.exists() ? (current.data().version ?? 0) : 0

    if (current.exists()) {
      const historyRef = doc(
        db, 'labs', labId, 'clusters', clusterId, 'nodes', nodeId,
        'config', 'history', String(prevVersion)
      )
      tx.set(historyRef, {
        ...current.data(),
        changedBy: updatedBy,
        changedAt: serverTimestamp(),
        changeReason: 'dashboard update',
      })
    }

    tx.set(ref, {
      ...patch,
      version: prevVersion + 1,
      updatedAt: serverTimestamp(),
      updatedBy,
    }, { merge: true })
  })
}

// ── Access Events ─────────────────────────────────────────────────────────────

export function subscribeAccessEvents(
  labId: string,
  limitCount: number,
  cb: (events: AccessEvent[]) => void
) {
  const q: Query<DocumentData> = query(
    collection(db, 'labs', labId, 'accessEvents'),
    orderBy('occurredAt', 'desc'),
    limit(limitCount)
  )
  return onSnapshot(q, snap => {
    cb(snap.docs.map(d => ({ id: d.id, ...d.data() }) as AccessEvent))
  })
}

export async function getAccessEvents(
  labId: string,
  filters: { result?: string; dateFrom?: string; dateTo?: string; search?: string },
  limitCount = 200
): Promise<AccessEvent[]> {
  const constraints: QueryConstraint[] = [
    orderBy('occurredAt', 'desc'),
    limit(limitCount),
  ]
  if (filters.result && filters.result !== 'all') {
    constraints.push(where('result', '==', filters.result))
  }
  if (filters.dateFrom) {
    constraints.push(where('occurredAt', '>=', Timestamp.fromDate(new Date(filters.dateFrom))))
  }
  if (filters.dateTo) {
    const end = new Date(filters.dateTo)
    end.setHours(23, 59, 59, 999)
    constraints.push(where('occurredAt', '<=', Timestamp.fromDate(end)))
  }
  const q: Query<DocumentData> = query(
    collection(db, 'labs', labId, 'accessEvents'),
    ...constraints
  )
  const snap = await getDocs(q)
  return snap.docs.map(d => ({ id: d.id, ...d.data() }) as AccessEvent)
}

// ── Incidents ─────────────────────────────────────────────────────────────────

export function subscribeIncidents(labId: string, cb: (incidents: Incident[]) => void) {
  const q: Query<DocumentData> = query(
    collection(db, 'labs', labId, 'incidents'),
    where('status', '==', 'open'),
    orderBy('createdAt', 'desc'),
    limit(20)
  )
  return onSnapshot(q, snap => {
    cb(snap.docs.map(d => ({ id: d.id, ...d.data() }) as Incident))
  })
}

// ── Users ─────────────────────────────────────────────────────────────────────

export async function getLabUsers(labId: string): Promise<User[]> {
  const membershipSnap = await getDocs(
    query(collectionGroup(db, 'labMemberships'), where('labId', '==', labId))
  )
  const userIds = membershipSnap.docs.map(d => d.ref.parent.parent!.id)
  if (userIds.length === 0) return []

  // Batch into chunks of 30 (Firestore `in` query limit) — 1 read per chunk vs N individual reads
  const results: User[] = []
  for (let i = 0; i < userIds.length; i += 30) {
    const snap = await getDocs(
      query(collection(db, 'users'), where(documentId(), 'in', userIds.slice(i, i + 30)))
    )
    results.push(...snap.docs.map(d => ({ id: d.id, ...d.data() }) as User))
  }
  return results
}

// ── Enrollment ────────────────────────────────────────────────────────────────

interface EnrollmentPayload {
  universityId:  string
  fullName:      string
  email:         string
  roles:         string[]
  labId:         string
  pin:           string
  faceImageUrls: string[]
  capturedBy:    string
}

export async function enrollUser(payload: EnrollmentPayload): Promise<string> {
  const { universityId, fullName, email, roles, labId, pin, faceImageUrls, capturedBy } = payload
  const identityRef = doc(db, 'identityIndex', universityId)

  return runTransaction(db, async tx => {
    const identitySnap = await tx.get(identityRef)
    if (identitySnap.exists()) throw new Error(`ID ${universityId} is already registered`)

    const userRef = doc(collection(db, 'users'))
    const userId = userRef.id

    tx.set(userRef, {
      universityId, fullName, email,
      roles, majors: [], researchGroupIds: [],
      status: 'active',
      faceStatus: faceImageUrls.length > 0 ? 'complete' : 'incomplete',
      pinStatus: 'set',
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
      lastAccessAt: null,
    })

    tx.set(identityRef, { userId, createdAt: serverTimestamp() })

    tx.set(doc(db, 'users', userId, 'labMemberships', labId), {
      labId, status: 'active',
      accessGroupIds: [], allowedClusterIds: [], allowedNodeIds: [],
      createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
    })

    tx.set(doc(db, 'users', userId, 'private', 'security'), {
      pin,
      pinSetAt: serverTimestamp(),
      pinSetBy: capturedBy,
    })

    faceImageUrls.forEach(url => {
      const imgRef = doc(collection(db, 'users', userId, 'faceImages'))
      tx.set(imgRef, {
        labId, storagePath: url,
        source: 'upload', qualityScore: 0,
        createdAt: serverTimestamp(), capturedBy,
      })
    })

    return userId
  })
}
