##V2.1


<aside>
📌

This document defines the Firestore + Firebase Storage schema, security model, and required Cloud Functions for the Lab Access Control System. It is the source of truth for humans and AI coding agents. If implementation and this document disagree, update this document first, then change code.

</aside>

## 1. System overview

The product is a multi-lab access control system. Each lab contains one or more clusters of edge nodes (e.g. Raspberry Pi devices) that authenticate people using **face recognition as the primary method and PIN as a fallback**. Nodes must keep working when offline and reconcile with Firebase on reconnect.

The domain hierarchy is:

```
Lab → Cluster → Node
```

Key rules:

- Labs are the top-level domain. Every operational resource (nodes, access events, access groups, audit logs, stats, incidents) is scoped to a lab.
- **Super Admins** are global; they create labs and admins.
- **Lab Admins** are scoped to specific labs via an explicit lab-access subcollection.
- Every user must have **both face and PIN** enrolled. Face is primary; PIN is fallback.
- Nodes are offline-capable. Access decisions are made on-device using an encrypted manifest. Events are queued locally and synced when online.
- Configuration changes are versioned and audited.

## 2. Top-level collections

| Path | Purpose |
| --- | --- |
| `/labs/{labId}` | Lab metadata and all lab-scoped subcollections |
| `/users/{userId}` | Global user directory (a person may belong to multiple labs) |
| `/identityIndex/{universityId}` | Uniqueness lookup for student/staff IDs |
| `/admins/{adminUid}` | Admin authority (separate from person type) |
| `/globalAuditLogs/{auditLogId}` | Audit records for Super Admin / non-lab actions |

## 3. Labs, clusters, nodes

### 3.1 `/labs/{labId}`

```
name: string
code: string                     // short human code, e.g. "ECE-A"
location: string
timezone: string                 // IANA, e.g. "Asia/Saigon"
status: "active" | "inactive" | "maintenance"
createdAt: timestamp
updatedAt: timestamp
```

### 3.2 `/labs/{labId}/clusters/{clusterId}`

```
name: string
code: string
status: string
createdAt: timestamp
updatedAt: timestamp
```

Even if only one cluster exists today, the `clusters` layer is kept so `Lab → Cluster → Node` scales without migration.

### 3.3 `/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}`

```
name: string
code: string
status: "online" | "offline" | "degraded" | "maintenance"
lastHeartbeatAt: timestamp
onlineState: "online" | "grace_period" | "offline"
currentConfigVersion: number
currentManifestVersion: number
latestTelemetry: map         // denormalized last snapshot
createdAt: timestamp
updatedAt: timestamp
```

## 4. Users and memberships

### 4.1 `/users/{userId}`

```
universityId: string             // student/staff ID, globally unique
fullName: string
email: string
roles: string[]                  // ["student", "faculty", "lab_assistant", "guest", "maintenance"]
majors: string[]                 // e.g. ["ECE", "CSE"]
researchGroupIds: string[]
status: "active" | "suspended"
faceStatus: "incomplete" | "complete"
pinStatus: "missing" | "set" | "reset_required"
createdAt: timestamp
updatedAt: timestamp
lastAccessAt: timestamp
```

`roles` is a **person type**, not admin authority. Admin authority lives in `/admins`.

### 4.2 `/users/{userId}/labMemberships/{labId}`

```
labId: string
status: "active" | "suspended"
accessGroupIds: string[]
allowedClusterIds: string[]
allowedNodeIds: string[]
createdAt: timestamp
updatedAt: timestamp
```

A user must have a membership document in a lab to be allowed in any of its nodes. `allowedNodeIds` is the effective allow-list used to generate that node's manifest.

### 4.3 `/identityIndex/{universityId}`

```
userId: string
createdAt: timestamp
```

Written inside the same transaction that creates the user. If a document at this path already exists, the user creation fails. This enforces global uniqueness of `universityId`.

## 5. Admin authority

### 5.1 `/admins/{adminUid}`

```
firebaseUid: string
userId: string                   // points to /users/{userId}
type: "super_admin" | "lab_admin"
status: "active" | "suspended"
createdAt: timestamp
createdBy: string                // adminUid of creator
```

### 5.2 `/admins/{adminUid}/labAccess/{labId}`

```
labId: string
role: "admin"
status: "active" | "suspended"
createdAt: timestamp
```

A `lab_admin` may only act inside labs listed under their `labAccess` subcollection. A `super_admin` is implicitly authorized everywhere and does not need `labAccess` documents.

## 6. Enrollment, credentials, and storage

### 6.1 `/users/{userId}/faceImages/{imageId}`

```
labId: string
storagePath: string              // path in Firebase Storage
source: "camera_capture" | "upload"
qualityScore: number
createdAt: timestamp
capturedBy: string               // adminUid or device id
```

### 6.2 `/users/{userId}/credentials/{credentialId}`

```
type: "face" | "pin"
labId: string                    // null if global credential
status: "active" | "revoked" | "reset_required"
createdAt: timestamp
updatedAt: timestamp
metadata: map                    // versioning, hash references, etc.
```

### 6.3 Firebase Storage layout

```
/labs/{labId}/users/{userId}/faceImages/{imageId}.jpg
/labs/{labId}/manifests/{nodeId}/{manifestVersion}.enc
```

**Never** store raw PINs in Firestore. PIN verification material is distributed only inside the encrypted node manifest. The dashboard must never expose raw PINs.

## 7. Access groups

### `/labs/{labId}/accessGroups/{accessGroupId}`

```
name: string
description: string
allowedClusterIds: string[]
allowedNodeIds: string[]
createdAt: timestamp
updatedAt: timestamp
createdBy: string
```

A membership references `accessGroupIds`. The effective `allowedNodeIds` for a user in a lab is the union of every group's `allowedNodeIds` plus any direct `allowedNodeIds` on the membership.

## 8. Access events

### `/labs/{labId}/accessEvents/{eventId}`

```
labId: string
clusterId: string
nodeId: string

localEventId: string             // unique on the node
localSequence: number
occurredAt: timestamp            // node time
receivedAt: timestamp            // Firebase server time
syncedFromOffline: boolean

userId: string | null            // null if unknown
universityId: string | null      // denormalized if known
displayName: string | null       // denormalized if known

method: "face" | "face_pin_fallback"
result: "granted" | "denied" | "unknown_user" | "liveness_failed" | "pin_failed" | "system_error"
reason: string                   // "low_confidence" | "bad_pin" | "no_match" | "inactive_user" | "suspended_user" | ...

confidence: number
livenessScore: number
pinFallbackUsed: boolean

reviewed: boolean
reviewedBy: string | null
reviewedAt: timestamp | null
notes: string | null
```

### 8.1 Decision flow

```
face match with high confidence            -> granted (method = face)
face match uncertain or below threshold    -> request PIN
    face + correct PIN                     -> granted (method = face_pin_fallback)
    face + wrong PIN                       -> denied  (result = pin_failed)
no face match                              -> denied  (result = unknown_user)
liveness check failed                      -> denied  (result = liveness_failed)
```

Unknown-user face snapshots are **not** stored. Only structured event metadata is kept.

### 8.2 Offline sync deduplication

`/labs/{labId}/syncReceipts/{nodeId}_{localEventId}`

```
nodeId: string
localEventId: string
eventId: string                  // points to /labs/{labId}/accessEvents/{eventId}
receivedAt: timestamp
```

Before writing an access event, the backend checks for an existing receipt at `{nodeId}_{localEventId}`. If present, the upload is a retry and is ignored.

## 9. Node manifests

### `/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}/accessManifests/{manifestId}`

```
version: number
generatedAt: timestamp
generatedBy: string
userCount: number
storagePath: string              // points to /labs/{labId}/manifests/{nodeId}/{version}.enc
checksum: string
status: "active" | "retired"
```

The manifest file in Storage is **encrypted** and contains:

- Only users authorized for that specific node (not the entire lab).
- Face-recognition embeddings/templates.
- PIN verification material (hashed, salted).
- User IDs, university IDs, access group mappings needed for offline decisions.

Nodes must not read `/users` directly. They only consume their own manifest.

## 10. Telemetry and online state

### 10.1 Latest snapshot

`/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}/latest/state`

```
heartbeatAt: timestamp
onlineState: "online" | "grace_period" | "offline"
cpuPercent: number
ramPercent: number
cameraFps: number
temperatureC: number
networkStatus: string
doorState: string
modelStatus: string
currentConfigVersion: number
currentManifestVersion: number
updatedAt: timestamp
```

### 10.2 Optional rolling history

`/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}/telemetry/{telemetryId}` with TTL deletion, same fields as above plus `recordedAt` and `receivedAt`. Only enable if hardware history is needed.

### 10.3 Grace period rules

```
Telemetry interval: every 60 seconds

online:        lastHeartbeatAt ≤ 90s ago
grace_period:  90s < lastHeartbeatAt ≤ 180s ago
offline:       lastHeartbeatAt > 180s ago
```

A node is only marked truly offline after roughly two missed updates. This prevents false alerts from one delayed heartbeat.

## 11. Node configuration

### 11.1 Current config

`/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}/config/current`

```
version: number
confidenceThreshold: number
livenessThreshold: number
pinFallbackEnabled: boolean      // true
faceRequired: boolean            // true
pinRequired: boolean             // true, used only as fallback
updatedAt: timestamp
updatedBy: string
```

### 11.2 Config history

`/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}/config/history/{configVersion}`

Same fields as `current` plus:

```
changedBy: string
changedAt: timestamp
changeReason: string
```

Every write to `current` must also append a `history` document with the previous version's snapshot, written in the same transaction.

### 11.3 Commands (push pattern)

`/labs/{labId}/clusters/{clusterId}/nodes/{nodeId}/commands/{commandId}`

```
type: "apply_config" | "refresh_manifest" | "reboot"
payload: map
status: "pending" | "acknowledged" | "failed"
createdAt: timestamp
createdBy: string
acknowledgedAt: timestamp | null
error: string | null
```

Nodes subscribe to their own `commands` collection. Pending commands are applied immediately when online, or on next reconnect.

## 12. Audit logs

### 12.1 Lab-scoped: `/labs/{labId}/auditLogs/{auditLogId}`

```
actorUid: string
actorUserId: string
actorType: "super_admin" | "lab_admin"
action: string                   // create_user, enroll_face, reset_pin, update_config,
                                 // export_logs, suspend_user, ...
targetType: "user" | "node" | "config" | "access_group" | "access_event"
targetId: string
before: map | null
after: map | null
createdAt: timestamp
```

### 12.2 Global: `/globalAuditLogs/{auditLogId}`

For actions that are not lab-specific (Super Admin only):

```
actorUid: string
action: string                   // create_lab, create_admin, assign_admin_to_lab
targetType: string
targetId: string
before: map | null
after: map | null
createdAt: timestamp
```

## 13. Incidents

`/labs/{labId}/incidents/{incidentId}`

```
labId: string
clusterId: string
nodeId: string
eventId: string | null           // null for hardware-only incidents
type: "failed_attempt" | "repeated_failure" | "liveness_failure"
    | "offline_node" | "high_temp" | "low_fps"
severity: "low" | "medium" | "high"
status: "open" | "acknowledged" | "resolved"
summary: string
createdAt: timestamp
resolvedAt: timestamp | null
resolvedBy: string | null
```

Incidents are produced automatically by Cloud Functions reacting to access events and telemetry.

## 14. Dashboard aggregates

Precomputed counters keep dashboard queries cheap. Cloud Functions update these documents as events arrive, so they remain effectively live.

```
/labs/{labId}/stats/dailyNodeStats/{nodeId}_{yyyyMMdd}
/labs/{labId}/stats/hourlyNodeStats/{nodeId}_{yyyyMMddHH}
/labs/{labId}/stats/weeklyNodeStats/{nodeId}_{yyyyWeek}
```

Each document contains:

```
labId: string
clusterId: string
nodeId: string
date: string                     // or year/week/hour fields
grantedCount: number
failedCount: number
pinFallbackCount: number
unknownUserCount: number         // daily only
livenessFailedCount: number      // daily only
updatedAt: timestamp
```

Cluster- and lab-level dashboard views are computed by summing the relevant node documents at read time.

## 15. Security model

### Super Admin

- Create labs.
- Create admins.
- Assign admins to labs.
- Read/write all lab data.

### Lab Admin

- Read/write only labs listed in `/admins/{adminUid}/labAccess/{labId}`.
- Enroll users into assigned labs.
- Update memberships, access groups, node configs inside assigned labs.
- Read and export logs inside assigned labs.

### Regular user

- No access to admin dashboard data.
- Future: may read own profile. Cannot reset PIN directly.

### Node device

- Read only its own `config/current`, `accessManifests/*` metadata, and `commands/*`.
- Write only its own `latest/state`, `telemetry/*`, and `accessEvents` for its `nodeId`.
- Must **not** be allowed to read `/users` or other nodes' data.
- Each physical node authenticates as a distinct device identity (custom token or service-account-mediated). Broad Firebase credentials must not live on edge devices. (Final device-auth choice is tracked as an open question — see section 18.)

## 16. Required Cloud Functions

```
createUserWithUniversityId
  - Transaction: create /identityIndex/{universityId} then /users/{userId}.
  - Fails if /identityIndex/{universityId} already exists.

enrollUser
  - Stores face image metadata, updates faceStatus and pinStatus.
  - Regenerates affected node manifests (any node whose allow-list includes this user).

onAccessEventCreated  (Firestore trigger)
  - Updates hourly/daily/weekly stats.
  - Updates /users/{userId}.lastAccessAt.
  - Creates an incident when result indicates a problem.

onNodeStateUpdated  (Firestore trigger)
  - Detects high temp, low FPS, degraded state.
  - Creates incidents as needed.

scheduledNodeHealthCheck  (every 60s)
  - Applies the 90s / 180s grace period rules.
  - Updates onlineState on each node and emits offline_node incidents.

onConfigUpdated  (Firestore trigger on config/current writes)
  - Writes the previous version into config/history/{configVersion}.
  - Creates an apply_config command for the node.
  - Optionally pushes via FCM.

createAdmin                (Super Admin only)
assignAdminToLab           (Super Admin only)

syncOfflineAccessEvents    (callable from node)
  - Checks /syncReceipts for duplicates.
  - Writes accessEvent + syncReceipt in one transaction.
```

## 17. Indexing notes (composite indexes likely required)

- `accessEvents`: `(labId, occurredAt desc)`, `(nodeId, occurredAt desc)`, `(userId, occurredAt desc)`, `(result, occurredAt desc)`.
- `incidents`: `(labId, status, createdAt desc)`, `(nodeId, status, createdAt desc)`.
- `auditLogs`: `(labId, createdAt desc)`, `(actorUid, createdAt desc)`.
- `users` (collection group queries on `labMemberships`): `(labId, status)`.

## 18. Open questions

- **Device identity for nodes.** Decide between (a) per-node Firebase Auth user with custom token minted by backend, or (b) backend-mediated API where nodes hold no Firebase credentials. Implementation should not give edge devices broad Firebase access.
- **PIN verification material distribution.** Confirm hashing scheme (e.g. Argon2id parameters) and rotation policy inside the encrypted manifest.
- **Manifest re-issue cadence.** Define triggers (membership change, access group change, PIN reset, face re-enrollment, periodic rotation).
- **Retention policies.** Confirm TTLs for `telemetry`, `commands`, `syncReceipts`, and `accessEvents`.

## 19. Change control

- Any change to this schema must update this document in the same pull request as the code change.
- Schema migrations must include a migration plan section in the PR description and corresponding admin scripts under `tools/migrations/`.