import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface LabState {
  selectedLabId: string | null
  selectedLabName: string | null
  selectedClusterId: string | null
  selectedNodeId: string | null
  selectLab: (id: string, name: string) => void
  selectNode: (clusterId: string, nodeId: string) => void
  clearLab: () => void
  cacheNode: (clusterId: string, nodeId: string) => void
}

export const useLabStore = create<LabState>()(
  persist(
    (set) => ({
      selectedLabId: null,
      selectedLabName: null,
      selectedClusterId: null,
      selectedNodeId: null,

      selectLab: (id, name) =>
        set({ selectedLabId: id, selectedLabName: name, selectedClusterId: null, selectedNodeId: null }),

      selectNode: (clusterId, nodeId) =>
        set({ selectedClusterId: clusterId, selectedNodeId: nodeId }),

      cacheNode: (clusterId, nodeId) =>
        set({ selectedClusterId: clusterId, selectedNodeId: nodeId }),

      clearLab: () =>
        set({ selectedLabId: null, selectedLabName: null, selectedClusterId: null, selectedNodeId: null }),
    }),
    { name: 'lab-selection' }
  )
)
