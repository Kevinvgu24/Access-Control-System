import { initializeApp, getApps } from 'firebase-admin/app'
import { getFirestore } from 'firebase-admin/firestore'

if (!getApps().length) initializeApp()

const db = getFirestore()

const UID          = 'YKIVvCzwhJQ6eDrd36hbs01cmaA3'
const EMAIL        = 'dawnnkevin9@gmail.com'
const DISPLAY_NAME = 'Kevin'

async function run() {
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

  const OLD_UID = 'L7Wd28nadsdERzzTXbrPWJqnWWf2'
  const oldDoc = await db.doc(`admins/${OLD_UID}`).get()
  if (oldDoc.exists) {
    await db.doc(`admins/${OLD_UID}`).delete()
    console.log('✓ Deleted old orphaned doc:', OLD_UID)
  }

  console.log('Done. Login should work now.')
}

run().catch(e => { console.error(e); process.exit(1) })
