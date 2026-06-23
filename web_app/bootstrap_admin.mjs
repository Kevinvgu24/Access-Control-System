import { initializeApp, cert, getApps } from 'firebase-admin/app'
import { getFirestore } from 'firebase-admin/firestore'
import { getAuth } from 'firebase-admin/auth'

// Use application default credentials
if (!getApps().length) initializeApp()

const db  = getFirestore()
const auth = getAuth()

const UID          = 'YKIVvCzwhJQ6eDrd36hbs01cmaA3'
const EMAIL        = 'dawnnkevin9@gmail.com'
const DISPLAY_NAME = 'Kevin'

async function run() {
  // Verify the Firebase Auth user exists
  try {
    const user = await auth.getUser(UID)
    console.log('✓ Auth user found:', user.email)
  } catch {
    console.error('✗ Auth user not found for UID:', UID)
    process.exit(1)
  }

  // Write admin doc (overwrites if already exists)
  await db.doc(`admins/${UID}`).set({
    firebaseUid:  UID,
    userId:       UID,
    type:         'super_admin',
    role:         'super_admin',
    status:       'active',
    email:        EMAIL,
    displayName:  DISPLAY_NAME,
    createdBy:    'bootstrap',
    createdAt:    new Date(),
  })
  console.log('✓ Admin doc created for', UID)

  // Clean up old orphaned doc if it exists
  const OLD_UID = 'L7Wd28nadsdERzzTXbrPWJqnWWf2'
  const oldDoc = await db.doc(`admins/${OLD_UID}`).get()
  if (oldDoc.exists) {
    await db.doc(`admins/${OLD_UID}`).delete()
    console.log('✓ Deleted old orphaned doc:', OLD_UID)
  }

  console.log('\nDone. Login should work now.')
}

run().catch(e => { console.error(e); process.exit(1) })
