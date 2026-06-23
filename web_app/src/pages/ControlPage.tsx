import { useState, useEffect, useCallback } from 'react'
import { Panel } from '@/components/ui/Panel'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAuthStore } from '@/store/authStore'
import {
  getAllLabs, createLab, updateLab, archiveLab,
  getLabClusters, getClusterNodes, createCluster, createNode, updateNode, deleteNode,
  getAllAdmins, createLabAdmin, updateAdminLabAccess, deleteAdminDoc,
} from '@/lib/db'
import type { Lab, Cluster, Node, AdminDoc } from '@/types/admin'

type Tab = 'labs' | 'devices' | 'admins'

// ── Shared modal ──────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg bg-[#111514] border border-white/10 rounded-xl shadow-2xl p-6 flex flex-col gap-5">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold text-[#e8ecea]">{title}</h3>
          <button onClick={onClose} className="text-[#3d4a46] hover:text-[#e8ecea] transition-colors text-xl cursor-pointer">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <label className="font-mono text-[11px] uppercase tracking-widest text-[#5a6b64]">{label}</label>
      {children}
    </div>
  )
}

const inputCls = "bg-raised border border-white/10 rounded px-4 py-2.5 text-sm text-[#e8ecea] placeholder:text-[#2d3834] outline-none focus:border-green/30 transition-colors"

// ── Labs tab ──────────────────────────────────────────────────────────────────

function LabsTab({ labs, onRefresh }: { labs: Lab[]; onRefresh: () => void }) {
  const { admin } = useAuthStore()
  const [showForm, setShowForm] = useState(false)
  const [editLab, setEditLab] = useState<Lab | null>(null)
  const [name, setName]         = useState('')
  const [code, setCode]         = useState('')
  const [location, setLocation] = useState('')
  const [timezone, setTimezone] = useState('Asia/Ho_Chi_Minh')
  const [saving, setSaving]     = useState(false)
  const [err, setErr]           = useState<string | null>(null)

  const openCreate = () => {
    setName('')
    setCode('')
    setLocation('')
    setTimezone('Asia/Ho_Chi_Minh')
    setEditLab(null)
    setErr(null)
    setShowForm(true)
  }

  const openEdit = (lab: Lab) => {
    setName(lab.name)
    setCode(lab.code)
    setLocation(lab.location ?? '')
    setTimezone(lab.timezone)
    setEditLab(lab)
    setErr(null)
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!name.trim()) return setErr('Name is required.')
    if (!timezone.trim()) return setErr('Timezone is required.')
    setSaving(true); setErr(null)
    try {
      if (editLab) {
        await updateLab(editLab.id, {
          name: name.trim(),
          code: code.trim() || undefined,
          location: location.trim() || '',
          timezone: timezone.trim(),
        })
      } else {
        await createLab({
          name: name.trim(),
          code: code.trim() || undefined,
          location: location.trim() || '',
          timezone: timezone.trim(),
        }, admin?.firebaseUid ?? 'admin')
      }
      setShowForm(false)
      onRefresh()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleArchive = async (lab: Lab) => {
    if (!confirm(`Archive "${lab.name}"? It will no longer appear in the lab selector.`)) return
    await archiveLab(lab.id)
    onRefresh()
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-between items-center">
        <p className="font-mono text-[11px] uppercase tracking-widest text-[#3d4a46]">{labs.length} lab{labs.length !== 1 ? 's' : ''}</p>
        <Button variant="primary" size="sm" onClick={openCreate}>+ New Lab</Button>
      </div>

      <Panel pad={false}>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-raised">
              {['Lab Name', 'Code / Timezone', 'Status', ''].map(h => (
                <th key={h} className="text-left px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] border-b border-white/[0.05]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labs.map(lab => (
              <tr key={lab.id} className="border-b border-white/[0.04] hover:bg-raised transition-colors last:border-0">
                <td className="px-5 py-4">
                  <p className="text-sm font-semibold text-[#e8ecea]">{lab.name}</p>
                  <p className="font-mono text-[11px] text-[#3d4a46] mt-0.5">{lab.location || '—'}</p>
                </td>
                <td className="px-5 py-4 text-sm text-[#5a6b64]">
                  {[lab.code, lab.timezone].filter(Boolean).join(' · ') || '—'}
                </td>
                <td className="px-5 py-4">
                  <Badge tone={lab.status === 'active' ? 'green' : lab.status === 'maintenance' ? 'amber' : 'neutral'}>{lab.status}</Badge>
                </td>
                <td className="px-5 py-4">
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => openEdit(lab)}
                      className="font-mono text-[11px] text-[#5a6b64] hover:text-[#e8ecea] transition-colors cursor-pointer">Edit</button>
                    {lab.status === 'active' && (
                      <button onClick={() => handleArchive(lab)}
                        className="font-mono text-[11px] text-[#5a6b64] hover:text-amber transition-colors cursor-pointer">Archive</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {labs.length === 0 && (
          <p className="py-12 text-center font-mono text-xs text-[#3d4a46]">No labs yet — create the first one.</p>
        )}
      </Panel>

      {showForm && (
        <Modal title={editLab ? 'Edit Lab' : 'New Lab'} onClose={() => setShowForm(false)}>
          <Field label="Lab Name"><input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. IoT Lab C205" className={inputCls} /></Field>
          <Field label="Lab Code"><input value={code} onChange={e => setCode(e.target.value.toUpperCase())} placeholder="e.g. ECE-A" className={inputCls} /></Field>
          <Field label="Location"><input value={location} onChange={e => setLocation(e.target.value)} placeholder="e.g. Building C, Floor 2" className={inputCls} /></Field>
          <Field label="Timezone"><input value={timezone} onChange={e => setTimezone(e.target.value)} placeholder="e.g. Asia/Ho_Chi_Minh" className={inputCls} /></Field>
          {err && <p className="text-sm text-red">{err}</p>}
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : editLab ? 'Save Changes' : 'Create Lab'}</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}

// ── Devices tab ───────────────────────────────────────────────────────────────

interface NodeWithCluster extends Node { clusterId: string; clusterName: string }

function DevicesTab({ labs }: { labs: Lab[] }) {
  const { admin } = useAuthStore()
  const [selectedLabId, setSelectedLabId]     = useState<string>(labs[0]?.id ?? '')
  const [clusters, setClusters]               = useState<Cluster[]>([])
  const [nodeMap, setNodeMap]                 = useState<Record<string, Node[]>>({})
  const [loadingDevices, setLoadingDevices]   = useState(false)
  const [showForm, setShowForm]               = useState(false)
  const [editNode, setEditNode]               = useState<NodeWithCluster | null>(null)

  const [fName, setFName]       = useState('')
  const [fDevId, setFDevId]     = useState('')
  const [fLoc, setFLoc]         = useState('')
  const [fCluster, setFCluster] = useState<string>('__new__')
  const [fClusterName, setFClusterName] = useState('')
  const [saving, setSaving]     = useState(false)
  const [err, setErr]           = useState<string | null>(null)

  const loadDevices = useCallback(async (labId: string) => {
    if (!labId) return
    setLoadingDevices(true)
    const cs = await getLabClusters(labId)
    setClusters(cs)
    const map: Record<string, Node[]> = {}
    for (const c of cs) {
      map[c.id] = await getClusterNodes(labId, c.id)
    }
    setNodeMap(map)
    setLoadingDevices(false)
  }, [])

  useEffect(() => {
    if (selectedLabId) void loadDevices(selectedLabId)
  }, [selectedLabId, loadDevices])

  useEffect(() => {
    if (selectedLabId && labs.some(l => l.id === selectedLabId)) return
    setSelectedLabId(labs[0]?.id ?? '')
  }, [labs, selectedLabId])

  const openAdd = () => {
    setFName(''); setFDevId(''); setFLoc('')
    setFCluster(clusters[0]?.id ?? '__new__')
    setFClusterName('')
    setEditNode(null); setErr(null); setShowForm(true)
  }

  const openEdit = (node: Node, clusterId: string, clusterName: string) => {
    setFName(node.name); setFDevId(node.deviceId ?? ''); setFLoc(node.location ?? '')
    setFCluster(clusterId); setFClusterName(''); setEditNode({ ...node, clusterId, clusterName })
    setErr(null); setShowForm(true)
  }

  const handleSave = async () => {
    if (!fName.trim()) return setErr('Device name is required.')
    setSaving(true); setErr(null)
    try {
      let clusterId = fCluster
      if (fCluster === '__new__') {
        if (!fClusterName.trim()) { setErr('Cluster name is required.'); setSaving(false); return }
        clusterId = await createCluster(selectedLabId, fClusterName.trim(), admin?.firebaseUid ?? 'admin')
      }
      if (editNode) {
        await updateNode(selectedLabId, clusterId, editNode.id, {
          name: fName.trim(), deviceId: fDevId.trim() || undefined, location: fLoc.trim() || undefined,
        })
      } else {
        await createNode(selectedLabId, clusterId, {
          name: fName.trim(), deviceId: fDevId.trim() || undefined, location: fLoc.trim() || undefined,
        }, admin?.firebaseUid ?? 'admin')
      }
      setShowForm(false)
      await loadDevices(selectedLabId)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (clusterId: string, nodeId: string, name: string) => {
    if (!confirm(`Delete device "${name}"? This cannot be undone.`)) return
    await deleteNode(selectedLabId, clusterId, nodeId)
    await loadDevices(selectedLabId)
  }

  const activeLabs = labs.filter(l => l.status === 'active')

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-between items-center gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] uppercase tracking-widest text-[#5a6b64]">Lab</span>
          <select value={selectedLabId} onChange={e => setSelectedLabId(e.target.value)}
            className="bg-raised border border-white/10 rounded px-3 py-2 text-sm text-[#e8ecea] outline-none focus:border-green/30 cursor-pointer">
            {activeLabs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
            {activeLabs.length === 0 && <option value="">No labs — create one first</option>}
          </select>
        </div>
        <Button variant="primary" size="sm" onClick={openAdd} disabled={!selectedLabId}>+ Add Device</Button>
      </div>

      {loadingDevices ? (
        <p className="font-mono text-[11px] text-[#3d4a46]">Loading devices…</p>
      ) : clusters.length === 0 ? (
        <Panel><p className="font-mono text-xs text-[#3d4a46]">No clusters yet — add a device to create the first cluster.</p></Panel>
      ) : (
        clusters.map(cluster => (
          <Panel key={cluster.id}>
            <div className="flex items-center gap-3 mb-4">
              <span className="font-mono text-[11px] uppercase tracking-widest text-[#3d4a46]">Cluster</span>
              <span className="text-sm font-bold text-[#e8ecea]">{cluster.name}</span>
              <span className="font-mono text-[10px] text-[#2d3834]">{cluster.id}</span>
            </div>
            {(nodeMap[cluster.id] ?? []).length === 0 ? (
              <p className="font-mono text-[11px] text-[#3d4a46]">No nodes in this cluster.</p>
            ) : (
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    {['Node Name', 'Device ID', 'Location', 'Status', ''].map(h => (
                      <th key={h} className="text-left pb-3 pr-5 font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] border-b border-white/[0.05]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(nodeMap[cluster.id] ?? []).map(node => (
                    <tr key={node.id} className="border-b border-white/[0.04] last:border-0">
                      <td className="py-3 pr-5">
                        <p className="text-sm font-semibold text-[#e8ecea]">{node.name}</p>
                        <p className="font-mono text-[11px] text-[#3d4a46]">{node.id.slice(0, 8)}</p>
                      </td>
                      <td className="py-3 pr-5 font-mono text-xs text-[#5a6b64]">{node.deviceId || '—'}</td>
                      <td className="py-3 pr-5 text-sm text-[#5a6b64]">{node.location || '—'}</td>
                      <td className="py-3 pr-5">
                        <Badge tone={node.status === 'online' ? 'green' : 'neutral'}>{node.status ?? 'offline'}</Badge>
                      </td>
                      <td className="py-3">
                        <div className="flex gap-3 justify-end">
                          <button onClick={() => openEdit(node, cluster.id, cluster.name)}
                            className="font-mono text-[11px] text-[#5a6b64] hover:text-[#e8ecea] transition-colors cursor-pointer">Edit</button>
                          <button onClick={() => handleDelete(cluster.id, node.id, node.name)}
                            className="font-mono text-[11px] text-[#5a6b64] hover:text-red transition-colors cursor-pointer">Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        ))
      )}

      {showForm && (
        <Modal title={editNode ? 'Edit Device' : 'Add Device'} onClose={() => setShowForm(false)}>
          <Field label="Device Name">
            <input value={fName} onChange={e => setFName(e.target.value)} placeholder="e.g. Pi Node Alpha" className={inputCls} />
          </Field>
          <Field label="Device ID (MAC / Serial)">
            <input value={fDevId} onChange={e => setFDevId(e.target.value)} placeholder="e.g. B8:27:EB:3A:5C:11" className={inputCls} />
          </Field>
          <Field label="Location">
            <input value={fLoc} onChange={e => setFLoc(e.target.value)} placeholder="e.g. Door A, main entrance" className={inputCls} />
          </Field>
          {!editNode && (
            <Field label="Cluster">
              <select value={fCluster} onChange={e => setFCluster(e.target.value)} className={inputCls + ' cursor-pointer'}>
                {clusters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                <option value="__new__">+ New Cluster</option>
              </select>
            </Field>
          )}
          {fCluster === '__new__' && !editNode && (
            <Field label="New Cluster Name">
              <input value={fClusterName} onChange={e => setFClusterName(e.target.value)} placeholder="e.g. Cluster A" className={inputCls} />
            </Field>
          )}
          {err && <p className="text-sm text-red">{err}</p>}
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : editNode ? 'Save Changes' : 'Add Device'}</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}

// ── Admins tab ────────────────────────────────────────────────────────────────

function AdminsTab({ labs }: { labs: Lab[] }) {
  const [admins, setAdmins]     = useState<AdminDoc[]>([])
  const [loading, setLoading]   = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editAdmin, setEditAdmin] = useState<AdminDoc | null>(null)

  const [fEmail, setFEmail]         = useState('')
  const [fPass, setFPass]           = useState('')
  const [fName, setFName]           = useState('')
  const [fLabIds, setFLabIds]       = useState<string[]>([])
  const [saving, setSaving]         = useState(false)
  const [err, setErr]               = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setAdmins(await getAllAdmins())
    setLoading(false)
  }, [])

  useEffect(() => { void load() }, [load])

  const openCreate = () => {
    setFEmail(''); setFPass(''); setFName(''); setFLabIds([])
    setEditAdmin(null); setErr(null); setShowForm(true)
  }

  const openEdit = (a: AdminDoc) => {
    setFLabIds(a.labAccessIds ?? [])
    setEditAdmin(a); setErr(null); setShowForm(true)
  }

  const toggleLab = (id: string) =>
    setFLabIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])

  const handleSave = async () => {
    setSaving(true); setErr(null)
    try {
      if (editAdmin) {
        await updateAdminLabAccess(editAdmin.id, fLabIds)
      } else {
        if (!fEmail.trim() || !fPass.trim() || !fName.trim()) {
          setErr('All fields are required.'); setSaving(false); return
        }
        await createLabAdmin({
          email: fEmail.trim(),
          password: fPass,
          displayName: fName.trim(),
          labIds: fLabIds,
        })
      }
      setShowForm(false)
      await load()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (a: AdminDoc) => {
    if (!confirm(`Remove admin "${a.displayName}"? Their auth account stays — only the admin record is deleted.`)) return
    await deleteAdminDoc(a.id)
    await load()
  }

  const activeLabs = labs.filter(l => l.status === 'active')

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-between items-center">
        <p className="font-mono text-[11px] uppercase tracking-widest text-[#3d4a46]">{admins.length} admin{admins.length !== 1 ? 's' : ''}</p>
        <Button variant="primary" size="sm" onClick={openCreate}>+ Add Lab Admin</Button>
      </div>

      <Panel pad={false}>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-raised">
              {['Admin', 'Role', 'Lab Access', ''].map(h => (
                <th key={h} className="text-left px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] border-b border-white/[0.05]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="px-5 py-8 font-mono text-xs text-[#3d4a46]">Loading…</td></tr>
            ) : admins.map(a => (
              <tr key={a.id} className="border-b border-white/[0.04] hover:bg-raised transition-colors last:border-0">
                <td className="px-5 py-4">
                  <p className="text-sm font-semibold text-[#e8ecea]">{a.displayName}</p>
                  <p className="font-mono text-[11px] text-[#3d4a46] mt-0.5">{a.email}</p>
                </td>
                <td className="px-5 py-4">
                  <Badge tone={a.role === 'super_admin' ? 'blue' : 'neutral'}>
                    {a.role === 'super_admin' ? 'Super Admin' : 'Lab Admin'}
                  </Badge>
                </td>
                <td className="px-5 py-4 font-mono text-xs text-[#5a6b64]">
                  {a.role === 'super_admin'
                    ? 'All labs'
                    : (a.labAccessIds?.length ?? 0) > 0
                      ? `${a.labAccessIds!.length} lab${a.labAccessIds!.length !== 1 ? 's' : ''}`
                      : 'None'}
                </td>
                <td className="px-5 py-4">
                  <div className="flex gap-3 justify-end">
                    {a.role !== 'super_admin' && (
                      <>
                        <button onClick={() => openEdit(a)}
                          className="font-mono text-[11px] text-[#5a6b64] hover:text-[#e8ecea] transition-colors cursor-pointer">Edit Access</button>
                        <button onClick={() => handleDelete(a)}
                          className="font-mono text-[11px] text-[#5a6b64] hover:text-red transition-colors cursor-pointer">Remove</button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && admins.length === 0 && (
          <p className="py-12 text-center font-mono text-xs text-[#3d4a46]">No admins found.</p>
        )}
      </Panel>

      {showForm && (
        <Modal title={editAdmin ? `Edit Lab Access — ${editAdmin.displayName}` : 'Add Lab Admin'} onClose={() => setShowForm(false)}>
          {!editAdmin && (
            <>
              <Field label="Email"><input type="email" value={fEmail} onChange={e => setFEmail(e.target.value)} placeholder="labadmin@university.edu" className={inputCls} /></Field>
              <Field label="Password"><input type="password" value={fPass} onChange={e => setFPass(e.target.value)} placeholder="Min 6 characters" className={inputCls} /></Field>
              <Field label="Display Name"><input value={fName} onChange={e => setFName(e.target.value)} placeholder="e.g. Lab Manager" className={inputCls} /></Field>
            </>
          )}
          <Field label="Lab Access">
            <div className="flex flex-col gap-2">
              {activeLabs.length === 0 && <p className="text-sm text-[#5a6b64]">No active labs — create labs first.</p>}
              {activeLabs.map(lab => (
                <label key={lab.id} className="flex items-center gap-3 cursor-pointer group">
                  <input type="checkbox" checked={fLabIds.includes(lab.id)} onChange={() => toggleLab(lab.id)}
                    className="w-4 h-4 accent-green rounded" />
                  <span className="text-sm text-[#a8bbb2] group-hover:text-[#e8ecea] transition-colors">{lab.name}</span>
                  {lab.location && <span className="font-mono text-[10px] text-[#3d4a46]">{lab.location}</span>}
                </label>
              ))}
            </div>
          </Field>
          {err && <p className="text-sm text-red">{err}</p>}
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : editAdmin ? 'Update Access' : 'Create Admin'}</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function ControlPage() {
  const [tab, setTab]   = useState<Tab>('labs')
  const [labs, setLabs] = useState<Lab[]>([])
  const [loadingLabs, setLoadingLabs] = useState(true)

  const fetchLabs = useCallback(async () => {
    setLoadingLabs(true)
    setLabs(await getAllLabs())
    setLoadingLabs(false)
  }, [])

  useEffect(() => { void fetchLabs() }, [fetchLabs])

  const tabCls = (t: Tab) =>
    `px-4 py-2 font-mono text-[11px] uppercase tracking-widest rounded transition-colors cursor-pointer ${
      tab === t ? 'bg-green/10 text-green border border-green/25' : 'text-[#5a6b64] hover:text-[#a8bbb2] border border-transparent'
    }`

  return (
    <div className="flex flex-col gap-7">
      <div>
        <p className="font-mono text-[11px] tracking-widest uppercase text-[#3d4a46] mb-3">Super Admin</p>
        <h1 className="text-4xl font-bold tracking-tight text-[#e8ecea]">Control Panel</h1>
        <p className="text-sm text-[#5a6b64] mt-2">Manage labs, hardware nodes, and admin accounts.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Labs',    value: labs.length,                                          color: 'text-[#e8ecea]' },
          { label: 'Active Labs',   value: labs.filter(l => l.status === 'active').length,       color: 'text-green'     },
          { label: 'Archived Labs', value: labs.filter(l => l.status === 'inactive').length,     color: 'text-[#5a6b64]' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-surface border border-white/[0.06] rounded-lg p-6">
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#3d4a46] mb-3">{label}</p>
            <p className={`text-5xl font-bold ${color}`}>{loadingLabs ? '—' : value}</p>
          </div>
        ))}
      </div>

      <Panel>
        <div className="flex gap-2 mb-6">
          <button className={tabCls('labs')}    onClick={() => setTab('labs')}>Labs</button>
          <button className={tabCls('devices')} onClick={() => setTab('devices')}>Devices</button>
          <button className={tabCls('admins')}  onClick={() => setTab('admins')}>Admins</button>
        </div>

        {loadingLabs ? (
          <p className="font-mono text-[11px] text-[#3d4a46]">Loading…</p>
        ) : tab === 'labs' ? (
          <LabsTab labs={labs} onRefresh={fetchLabs} />
        ) : tab === 'devices' ? (
          <DevicesTab labs={labs} />
        ) : (
          <AdminsTab labs={labs} />
        )}
      </Panel>
    </div>
  )
}
