import { initializeApp } from 'firebase-admin/app'
import { getAuth } from 'firebase-admin/auth'
import { getFirestore, FieldValue } from 'firebase-admin/firestore'
import { onCall, HttpsError } from 'firebase-functions/v2/https'

initializeApp()
const db   = getFirestore()
const auth = getAuth()

interface CreateAdminUserData {
  email:       string
  password:    string
  displayName: string
  labIds:      string[]
}

export const createAdminUser = onCall(async (request) => {
  if (!request.auth) {
    throw new HttpsError('unauthenticated', 'Must be authenticated.')
  }

  const callerSnap = await db.doc(`admins/${request.auth.uid}`).get()
  const caller = callerSnap.data()
  if (!callerSnap.exists || caller?.type !== 'super_admin' || caller?.status !== 'active') {
    throw new HttpsError('permission-denied', 'Only active super_admins can create admin accounts.')
  }

  const { email, password, displayName, labIds } = request.data as CreateAdminUserData

  if (!email?.trim() || !password || !displayName?.trim()) {
    throw new HttpsError('invalid-argument', 'email, password, and displayName are required.')
  }

  const userRecord = await auth.createUser({ email, password, displayName })
  const uid = userRecord.uid

  const batch = db.batch()
  batch.set(db.doc(`admins/${uid}`), {
    firebaseUid: uid,
    userId:      uid,
    type:        'lab_admin',
    role:        'lab_admin',
    status:      'active',
    createdAt:   FieldValue.serverTimestamp(),
    createdBy:   request.auth.uid,
    email,
    displayName,
  })
  for (const labId of (labIds ?? [])) {
    batch.set(db.doc(`admins/${uid}/labAccess/${labId}`), {
      labId,
      role:      'admin',
      status:    'active',
      createdAt: FieldValue.serverTimestamp(),
    })
  }
  await batch.commit()

  return { uid }
})
