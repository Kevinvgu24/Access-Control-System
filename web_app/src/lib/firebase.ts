import { initializeApp, getApps } from 'firebase/app'
import {
  initializeFirestore, getFirestore,
  persistentLocalCache, persistentMultipleTabManager,
} from 'firebase/firestore'
import { getAuth } from 'firebase/auth'
import { getFunctions } from 'firebase/functions'

const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             import.meta.env.VITE_FIREBASE_APP_ID,
}

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0]

// Enable IndexedDB persistence so repeat visits are served from local cache first,
// then updated in background. Falls back to memory cache on re-init (HMR).
function buildDb() {
  try {
    return initializeFirestore(app, {
      localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() }),
    })
  } catch {
    return getFirestore(app)
  }
}

export const db        = buildDb()
export const auth      = getAuth(app)
export const functions = getFunctions(app)
export default app
