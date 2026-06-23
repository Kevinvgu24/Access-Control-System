import { create } from 'zustand'
import { auth, db } from '@/lib/firebase'
import {
  onAuthStateChanged, signInWithEmailAndPassword,
  signOut as firebaseSignOut, type User,
} from 'firebase/auth'
import { doc, getDocFromServer, getDocs, collection } from 'firebase/firestore'
import type { AdminDoc } from '@/types/admin'
import { useLabStore } from '@/store/labStore'

interface AuthState {
  user: User | null
  admin: AdminDoc | null
  labAccessIds: string[]
  initialized: boolean
  loading: boolean
  error: string | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  init: () => () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  admin: null,
  labAccessIds: [],
  initialized: false,
  loading: false,
  error: null,

  signIn: async (email, password) => {
    set({ loading: true, error: null })
    try {
      await signInWithEmailAndPassword(auth, email, password)
    } catch (err: unknown) {
      set({
        error: err instanceof Error ? err.message : 'Login failed',
        loading: false,
      })
    }
  },

  signOut: async () => {
    await firebaseSignOut(auth)
    useLabStore.getState().clearLab()
    set({ user: null, admin: null, labAccessIds: [] })
  },

  init: () =>
    onAuthStateChanged(auth, async (user) => {
      if (!user) {
        set({ user: null, admin: null, labAccessIds: [], initialized: true, loading: false })
        return
      }
      try {
        console.log('[auth] uid:', user.uid)
        const adminSnap = await getDocFromServer(doc(db, 'admins', user.uid))
        console.log('[auth] exists:', adminSnap.exists(), 'data:', adminSnap.data())
        const admin = adminSnap.exists()
          ? ({ id: adminSnap.id, ...adminSnap.data() } as AdminDoc)
          : null

        if (!admin) {
          set({
            user,
            admin: null,
            labAccessIds: [],
            initialized: true,
            loading: false,
            error: 'This account is authenticated but has no admin profile.',
          })
          return
        }

        if (admin.status !== 'active') {
          set({
            user,
            admin: null,
            labAccessIds: [],
            initialized: true,
            loading: false,
            error: 'This admin account is suspended.',
          })
          return
        }

        let labAccessIds: string[] = []
        if (admin?.type === 'lab_admin') {
          const labAccessSnap = await getDocs(
            collection(db, 'admins', user.uid, 'labAccess')
          )
          labAccessIds = labAccessSnap.docs
            .filter(d => d.data().status === 'active')
            .map(d => d.id)
        }

        set({ user, admin, labAccessIds, initialized: true, loading: false, error: null })
      } catch (err: unknown) {
        set({
          user,
          admin: null,
          labAccessIds: [],
          initialized: true,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load admin profile',
        })
      }
    }),
}))
