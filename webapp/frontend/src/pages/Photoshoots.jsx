import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarDays, ImageIcon, MoreHorizontal, Pencil, Trash2, Check, X, Square, CheckSquare } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useToast } from '../lib/toast'
import StatusBadge from '../components/StatusBadge'
import ConfirmDialog from '../components/ConfirmDialog'

export default function Photoshoots() {
  const [shoots,   setShoots]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [selected, setSelected] = useState(new Set())   // shoot ids
  const [confirm,  setConfirm]  = useState(null)        // { ids }
  const { auth } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const isAdmin  = auth?.role === 'admin'

  const load = useCallback(() => {
    api.shoots()
      .then(setShoots)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  // ── Selection ─────────────────────────────────────────────
  const toggleSelect = (id) =>
    setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  const allSelected  = shoots.length > 0 && selected.size === shoots.length
  const toggleAll    = () => setSelected(allSelected ? new Set() : new Set(shoots.map(s => s.id)))

  // ── Rename ────────────────────────────────────────────────
  const handleRename = async (shoot, newName) => {
    try {
      const updated = await api.renameShoot(shoot.id, newName)
      setShoots(prev => prev.map(s =>
        s.id === shoot.id ? { ...s, id: updated.id, name: updated.name } : s
      ))
      // If this shoot was selected, update the selected id too
      if (selected.has(shoot.id)) {
        setSelected(prev => { const n = new Set(prev); n.delete(shoot.id); n.add(updated.id); return n })
      }
      addToast('success', `Renamed to "${updated.name}"`)
    } catch (e) {
      const msg = await e?.response?.json?.().then(r => r.error).catch(() => null)
      addToast('error', msg || 'Rename failed')
      throw e  // re-throw so the card can reset its input
    }
  }

  // ── Delete ────────────────────────────────────────────────
  const handleDelete = async (ids) => {
    try {
      const res = await api.deleteShoots(ids)
      setShoots(prev => prev.filter(s => !res.deleted.includes(s.id)))
      setSelected(prev => { const n = new Set(prev); res.deleted.forEach(id => n.delete(id)); return n })
      if (res.deleted.length) addToast('success', `Deleted ${res.deleted.length} shoot${res.deleted.length > 1 ? 's' : ''}`)
      if (res.errors?.length)  addToast('error',   `${res.errors.length} shoot${res.errors.length > 1 ? 's' : ''} could not be deleted`)
    } catch {
      addToast('error', 'Delete failed')
    }
    setConfirm(null)
  }

  if (loading) return <Loading />

  const selectedArr = [...selected]

  return (
    <div className="p-4 sm:p-6 md:p-8">

      {/* Header */}
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Workflow</p>
          <h1 className="text-2xl text-[var(--c-text-1)] font-semibold">Photoshoot</h1>
        </div>
      </div>

      {/* Bulk action bar */}
      {isAdmin && selected.size > 0 && (
        <div className="mb-4 flex items-center gap-3 px-4 py-2.5 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg">
          <span className="text-sm text-[var(--c-text-2)] flex-1">{selected.size} selected</span>
          <button
            onClick={() => setConfirm({ ids: selectedArr })}
            className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 transition-colors"
          >
            <Trash2 size={14} /> Delete selected
          </button>
          <button onClick={() => setSelected(new Set())} className="text-[var(--c-text-3)] hover:text-[var(--c-text-1)] transition-colors ml-1">
            <X size={15} />
          </button>
        </div>
      )}

      {!shoots.length ? (
        <div className="text-[var(--c-text-4)] text-sm">No shoots found in asset_library.</div>
      ) : (
        <div className="space-y-3">
          {/* Select-all row */}
          {isAdmin && shoots.length > 1 && (
            <div className="flex items-center gap-2 px-1 pb-1">
              <button onClick={toggleAll} className="flex items-center gap-2 text-xs text-[var(--c-text-3)] hover:text-[var(--c-text-2)] transition-colors">
                {allSelected ? <CheckSquare size={14} /> : <Square size={14} />}
                {allSelected ? 'Deselect all' : 'Select all'}
              </button>
            </div>
          )}

          {shoots.map(shoot => (
            <ShootCard
              key={shoot.id}
              shoot={shoot}
              isAdmin={isAdmin}
              selected={selected.has(shoot.id)}
              onSelect={() => toggleSelect(shoot.id)}
              onClick={() => navigate(`/photoshoots/${shoot.id}`)}
              onRename={(newName) => handleRename(shoot, newName)}
              onDelete={() => setConfirm({ ids: [shoot.id] })}
            />
          ))}
        </div>
      )}

      {/* Delete confirmation */}
      {confirm && (
        <ConfirmDialog
          variant="danger"
          title={`Delete ${confirm.ids.length > 1 ? `${confirm.ids.length} shoots` : 'shoot'}?`}
          message={`This will permanently delete the folder${confirm.ids.length > 1 ? 's' : ''} and all images inside. This cannot be undone.`}
          confirmLabel="Delete"
          onConfirm={() => handleDelete(confirm.ids)}
          onCancel={() => setConfirm(null)}
        />
      )}

    </div>
  )
}

// ── Shoot card ─────────────────────────────────────────────────────────────────

function ShootCard({ shoot, isAdmin, selected, onSelect, onClick, onRename, onDelete }) {
  const [menuOpen,  setMenuOpen]  = useState(false)
  const [renaming,  setRenaming]  = useState(false)
  const [nameVal,   setNameVal]   = useState(shoot.name)
  const [saving,    setSaving]    = useState(false)
  const menuRef  = useRef(null)
  const inputRef = useRef(null)

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return
    const handler = (e) => { if (!menuRef.current?.contains(e.target)) setMenuOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  // Focus input when rename mode opens
  useEffect(() => {
    if (renaming) { setNameVal(shoot.name); inputRef.current?.focus(); inputRef.current?.select() }
  }, [renaming, shoot.name])

  const cancelRename = () => { setRenaming(false); setNameVal(shoot.name) }

  const commitRename = async () => {
    const trimmed = nameVal.trim()
    if (!trimmed || trimmed === shoot.name) { cancelRename(); return }
    setSaving(true)
    try {
      await onRename(trimmed)
      setRenaming(false)
    } catch {
      // toast shown by parent; reset input
      setNameVal(shoot.name)
      setRenaming(false)
    } finally {
      setSaving(false)
    }
  }

  const hasReview = shoot.needs_review > 0

  return (
    <div className={`relative bg-[var(--c-surface)] border rounded-lg p-6 transition-colors ${
      selected ? 'border-blue-500/50 bg-blue-500/5' : 'border-[var(--c-border)]'
    }`}>

      <div className="flex items-center gap-3">

        {/* Checkbox (admin only) */}
        {isAdmin && (
          <button
            onClick={(e) => { e.stopPropagation(); onSelect() }}
            className="shrink-0 text-[var(--c-text-3)] hover:text-[var(--c-text-1)] transition-colors"
          >
            {selected ? <CheckSquare size={16} className="text-blue-400" /> : <Square size={16} />}
          </button>
        )}

        {/* Main clickable area */}
        <div className="flex-1 flex items-center justify-between cursor-pointer min-w-0" onClick={!renaming ? onClick : undefined}>

          {/* Left — name + meta */}
          <div className="min-w-0">
            {renaming ? (
              <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                <input
                  ref={inputRef}
                  value={nameVal}
                  onChange={e => setNameVal(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') cancelRename() }}
                  disabled={saving}
                  className="bg-[var(--c-surface-2)] border border-blue-500 rounded px-2 py-1 text-[var(--c-text-1)] text-lg font-medium outline-none w-48"
                />
                <button onClick={commitRename} disabled={saving} className="text-green-400 hover:text-green-300 transition-colors">
                  <Check size={16} />
                </button>
                <button onClick={cancelRename} className="text-[var(--c-text-3)] hover:text-[var(--c-text-1)] transition-colors">
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="text-[var(--c-text-1)] text-lg font-medium mb-1 truncate">{shoot.name}</div>
            )}
            <div className="flex items-center gap-4 text-[var(--c-text-2)] text-sm mt-1">
              <span className="flex items-center gap-1.5"><CalendarDays size={13} />{shoot.date || shoot.month}</span>
              <span className="flex items-center gap-1.5"><ImageIcon size={13} />{shoot.total_images} images</span>
              {shoot.total_cost > 0 && <span className="text-[var(--c-text-3)]">${shoot.total_cost.toFixed(2)}</span>}
            </div>
          </div>

          {/* Right — counts + status */}
          <div className="flex items-center gap-6 shrink-0 ml-4">
            <div className="text-center hidden sm:block">
              <div className="text-[var(--c-text-1)] font-semibold">{shoot.total_images}</div>
              <div className="text-[var(--c-text-3)] text-xs">total</div>
            </div>
            <div className="text-center hidden sm:block">
              <div className="text-green-400 font-semibold">{shoot.approved}</div>
              <div className="text-[var(--c-text-3)] text-xs">approved</div>
            </div>
            <div className="text-center hidden sm:block">
              <div className={`font-semibold ${hasReview ? 'text-orange-400' : 'text-[var(--c-text-4)]'}`}>{shoot.needs_review}</div>
              <div className="text-[var(--c-text-3)] text-xs">review</div>
            </div>
            <StatusBadge status={shoot.status} dot />
          </div>

        </div>

        {/* Three-dot menu (admin only) */}
        {isAdmin && (
          <div className="relative shrink-0 ml-2" ref={menuRef}>
            <button
              onClick={(e) => { e.stopPropagation(); setMenuOpen(o => !o) }}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors"
            >
              <MoreHorizontal size={16} />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-9 z-20 bg-[var(--c-sidebar)] border border-[var(--c-border)] rounded-lg shadow-lg py-1 w-36">
                <button
                  onClick={(e) => { e.stopPropagation(); setMenuOpen(false); setRenaming(true) }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors"
                >
                  <Pencil size={13} /> Rename
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onDelete() }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-[var(--c-surface-2)] transition-colors"
                >
                  <Trash2 size={13} /> Delete
                </button>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}

function Loading() {
  return (
    <div className="p-8 flex items-center justify-center h-64">
      <div className="text-[var(--c-text-3)] text-sm">Loading…</div>
    </div>
  )
}
