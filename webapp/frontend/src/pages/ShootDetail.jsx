import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Pencil, X, Check, Download, Tag, Trash2, CheckSquare } from 'lucide-react'
import { api } from '../lib/api'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import ImageLightbox from '../components/ImageLightbox'
import ConfirmDialog from '../components/ConfirmDialog'

const SET_LABELS = { 1: 'Set 1', 2: 'Set 2', 3: 'Set 3', 0: 'Other' }

const STATUS_BADGE = {
  needs_review: { label: 'Needs Review', cls: 'bg-orange-500 text-white' },
  regen:        { label: 'Regen',        cls: 'bg-red-600 text-white' },
  pending:      { label: 'Pending',      cls: 'bg-gray-700 text-gray-300' },
}

export default function ShootDetail() {
  const { shootId } = useParams()
  const navigate    = useNavigate()

  const [shoot,     setShoot]     = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [activeSet, setActiveSet] = useState('all')

  // ── Lightbox ──────────────────────────────────────────────
  const [lightboxIndex, setLightboxIndex] = useState(null)

  // ── Edit mode ─────────────────────────────────────────────
  const [editMode,  setEditMode]  = useState(false)
  const [selected,  setSelected]  = useState(new Set())

  // ── Confirm dialogs ───────────────────────────────────────
  const [confirm, setConfirm] = useState(null)   // { type, filenames }
  const [working, setWorking] = useState(false)

  // ── Data loading ──────────────────────────────────────────
  const load = useCallback(() => {
    setLoading(true)
    api.shoot(shootId)
      .then(data => { setShoot(data); setSelected(new Set()) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [shootId])

  useEffect(() => { load() }, [load])

  if (loading) return <Spinner />
  if (!shoot)  return <NotFound onBack={() => navigate('/photoshoots')} />

  // ── Derived ───────────────────────────────────────────────
  const totalImages = shoot.total_images
  const approved    = shoot.images.filter(i => i.display_status === 'approved').length
  const needsReview = shoot.images.filter(i => i.display_status === 'needs_review').length
  const setNums     = Object.keys(shoot.sets ?? {}).map(Number).sort()

  const visibleImages = activeSet === 'all'
    ? shoot.images
    : shoot.images.filter(img => img.set === Number(activeSet))

  // ── Selection helpers ─────────────────────────────────────
  const toggleSelect = (filename) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(filename) ? next.delete(filename) : next.add(filename)
      return next
    })
  }

  const selectAll  = () => setSelected(new Set(visibleImages.map(i => i.filename)))
  const clearSelect = () => setSelected(new Set())

  const exitEditMode = () => { setEditMode(false); clearSelect() }

  const selectedHasReviewImages = [...selected].some(f =>
    shoot.images.find(i => i.filename === f && i.display_status === 'needs_review')
  )

  // ── Click handler ─────────────────────────────────────────
  const handleImageClick = (img, visibleIdx) => {
    if (editMode) {
      toggleSelect(img.filename)
    } else {
      setLightboxIndex(visibleIdx)
    }
  }

  // ── Actions ───────────────────────────────────────────────
  const requestAction = (type) => {
    const filenames = type === 'remove_tag' || type === 'delete'
      ? [...selected]
      : [...selected]
    setConfirm({ type, filenames })
  }

  const executeAction = async () => {
    if (!confirm) return
    const { type, filenames } = confirm
    setConfirm(null)
    setWorking(true)
    try {
      let updated
      if (type === 'remove_tag') updated = await api.approveImages(shootId, filenames)
      if (type === 'delete')     updated = await api.deleteImages(shootId, filenames)
      if (updated?.images) { setShoot(updated); setSelected(new Set()) }
    } catch (e) {
      console.error(e)
    } finally {
      setWorking(false)
    }
  }

  const handleDownload = async () => {
    const toDownload = shoot.images.filter(i => selected.has(i.filename))
    for (const img of toDownload) {
      const a = document.createElement('a')
      a.href = api.imageUrl(img.path)
      a.download = img.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      await new Promise(r => setTimeout(r, 150))
    }
  }

  // ── Confirm dialog config ─────────────────────────────────
  const CONFIRM_CONFIG = {
    remove_tag: {
      title:        'Remove Needs Review tag?',
      message:      `This will approve ${confirm?.filenames?.length ?? 0} image${confirm?.filenames?.length === 1 ? '' : 's'} and rename the file${confirm?.filenames?.length === 1 ? '' : 's'} on disk. This cannot be undone.`,
      confirmLabel: 'Remove tag',
      variant:      'warning',
    },
    delete: {
      title:        'Delete images?',
      message:      `This will permanently delete ${confirm?.filenames?.length ?? 0} image${confirm?.filenames?.length === 1 ? '' : 's'} from disk and remove ${confirm?.filenames?.length === 1 ? 'it' : 'them'} from the catalog. This cannot be undone.`,
      confirmLabel: 'Delete',
      variant:      'danger',
    },
  }

  const cfg = confirm ? CONFIRM_CONFIG[confirm.type] : null

  return (
    <div className={`p-8 ${editMode && selected.size > 0 ? 'pb-32' : ''}`}>

      {/* Back */}
      <button
        onClick={() => navigate('/photoshoots')}
        className="flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-6 transition-colors"
      >
        <ArrowLeft size={15} /> Back to Photoshoots
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Photoshoot</p>
          <h1 className="text-2xl text-white font-semibold">{shoot.name}</h1>
          <p className="text-gray-500 text-sm mt-1">{shoot.date || shoot.month} · {shoot.sprint_id}</p>
        </div>
        <StatusBadge status={shoot.status} dot />
      </div>

      {/* Always-visible image counts */}
      <div className="grid grid-cols-3 gap-3 mb-8">
        <CountCard value={totalImages} label="Total images" />
        <CountCard value={approved}    label="Approved"     color="green"  />
        <CountCard value={needsReview} label="Needs review" color={needsReview > 0 ? 'orange' : undefined} />
      </div>

      {/* Sprint stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <StatCard label="Runtime"   value={shoot.runtime ?? '—'} />
        <StatCard label="API Calls" value={shoot.total_calls?.toLocaleString() ?? '—'} />
        <StatCard label="Cost"      value={shoot.total_cost > 0 ? `$${shoot.total_cost.toFixed(2)}` : '—'} />
        <StatCard label="Errors"    value={shoot.errors ?? '0'} />
      </div>

      {/* Per-set breakdown */}
      {setNums.length > 0 && (
        <div className="mb-8">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Sets</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {setNums.map(s => {
              const imgs   = shoot.sets[s] ?? []
              const app    = imgs.filter(i => i.display_status === 'approved').length
              const review = imgs.filter(i => i.display_status === 'needs_review').length
              const regen  = imgs.filter(i => i.display_status === 'regen').length
              return (
                <div key={s} className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                  <div className="text-white font-medium mb-3">{SET_LABELS[s]}</div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <Stat value={app}    label="approved" color="green"  />
                    <Stat value={review} label="review"   color={review > 0 ? 'orange' : undefined} />
                    <Stat value={regen}  label="regen"    color={regen  > 0 ? 'red'    : undefined} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Image grid header ── */}
      <div className="flex items-center justify-between mb-4">
        {/* Set filter tabs */}
        <div className="flex gap-1 flex-wrap">
          {['all', ...setNums].map(s => (
            <button
              key={s}
              onClick={() => { setActiveSet(String(s)); clearSelect() }}
              className={`px-3 py-1 rounded text-xs transition-colors ${
                activeSet === String(s) ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {s === 'all'
                ? `All (${shoot.images.length})`
                : `${SET_LABELS[s]} (${(shoot.sets[s] ?? []).length})`}
            </button>
          ))}
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-3 shrink-0 ml-4">
          {editMode && (
            <button
              onClick={selected.size === visibleImages.length ? clearSelect : selectAll}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
            >
              <CheckSquare size={13} />
              {selected.size === visibleImages.length ? 'Deselect all' : 'Select all'}
            </button>
          )}

          {editMode ? (
            <button
              onClick={exitEditMode}
              className="flex items-center gap-2 text-sm text-gray-400 hover:text-white border border-gray-700 px-3 py-1.5 rounded-lg transition-colors"
            >
              <X size={14} /> Done
            </button>
          ) : (
            <button
              onClick={() => setEditMode(true)}
              className="flex items-center gap-2 text-sm text-white bg-gray-800 hover:bg-gray-700 border border-gray-700 px-3 py-1.5 rounded-lg transition-colors"
            >
              <Pencil size={13} /> Edit images
            </button>
          )}
        </div>
      </div>

      {/* Image grid */}
      {visibleImages.length === 0 ? (
        <div className="text-gray-600 text-sm py-8">No images.</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {visibleImages.map((img, idx) => (
            <ImageTile
              key={img.id}
              img={img}
              editMode={editMode}
              isSelected={selected.has(img.filename)}
              onClick={() => handleImageClick(img, idx)}
            />
          ))}
        </div>
      )}

      {/* ── Floating action bar (edit mode + selection) ── */}
      {editMode && selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-max">
          <div className="flex items-center gap-2 bg-gray-950 border border-gray-700 rounded-2xl shadow-2xl px-4 py-3">
            <span className="text-white text-sm font-medium px-1">{selected.size} selected</span>
            <div className="w-px h-5 bg-gray-700 mx-1" />

            {/* Download */}
            <ActionButton icon={Download} label="Download" onClick={handleDownload} disabled={working} />

            {/* Remove tag — only when needs_review images in selection */}
            {selectedHasReviewImages && (
              <ActionButton
                icon={Tag}
                label="Remove Review tag"
                onClick={() => requestAction('remove_tag')}
                disabled={working}
                color="orange"
              />
            )}

            {/* Delete */}
            <ActionButton
              icon={Trash2}
              label="Delete"
              onClick={() => requestAction('delete')}
              disabled={working}
              color="red"
            />

            <div className="w-px h-5 bg-gray-700 mx-1" />
            <button onClick={clearSelect} className="text-gray-400 hover:text-white transition-colors p-1 rounded">
              <X size={15} />
            </button>
          </div>
        </div>
      )}

      {/* ── Lightbox ── */}
      {lightboxIndex !== null && (
        <ImageLightbox
          images={visibleImages}
          index={lightboxIndex}
          onNavigate={setLightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}

      {/* ── Confirmation dialogs ── */}
      {confirm && cfg && (
        <ConfirmDialog
          open
          title={cfg.title}
          message={cfg.message}
          confirmLabel={cfg.confirmLabel}
          variant={cfg.variant}
          onConfirm={executeAction}
          onCancel={() => setConfirm(null)}
        />
      )}

    </div>
  )
}

// ── Image tile ────────────────────────────────────────────────────────────────

function ImageTile({ img, editMode, isSelected, onClick }) {
  const badge = STATUS_BADGE[img.display_status]
  const src   = api.imageUrl(img.path)

  return (
    <div
      onClick={onClick}
      className={`group relative bg-gray-900 rounded-lg overflow-hidden border transition-all cursor-pointer select-none ${
        isSelected
          ? 'border-blue-500 ring-2 ring-blue-500/30'
          : editMode
          ? 'border-gray-700 hover:border-gray-500'
          : 'border-gray-800 hover:border-gray-600'
      }`}
    >
      <div className="relative aspect-[3/4]">
        <img
          src={src}
          alt={img.filename}
          loading="lazy"
          className="w-full h-full object-cover"
          onError={e => { e.target.style.display = 'none' }}
        />

        {/* Selected overlay */}
        {isSelected && (
          <div className="absolute inset-0 bg-blue-500/20 flex items-start justify-end p-2">
            <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center shadow-lg">
              <Check size={13} className="text-white" strokeWidth={2.5} />
            </div>
          </div>
        )}

        {/* Unselected checkbox hint in edit mode */}
        {editMode && !isSelected && (
          <div className="absolute top-2 right-2 w-6 h-6 rounded-full border-2 border-white/40 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}

        {/* Status badge — only when not selected */}
        {badge && !isSelected && (
          <span className={`absolute top-2 left-2 text-xs px-2 py-0.5 rounded font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        )}
      </div>

      <div className="px-2 py-1.5">
        <div className="text-gray-500 text-xs truncate">
          {img.ref_code?.split('-').slice(-2).join('-')}
        </div>
      </div>
    </div>
  )
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function ActionButton({ icon: Icon, label, onClick, disabled, color }) {
  const cls = {
    orange: 'hover:bg-orange-600/20 hover:text-orange-300 text-orange-400',
    red:    'hover:bg-red-600/20 hover:text-red-300 text-red-400',
  }[color] ?? 'hover:bg-gray-700 text-gray-200'

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 text-sm font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40 ${cls}`}
    >
      <Icon size={14} />
      {label}
    </button>
  )
}

function CountCard({ value, label, color }) {
  const valueColor = {
    green:  'text-green-400',
    orange: 'text-orange-400',
    red:    'text-red-400',
  }[color] ?? 'text-white'

  const borderColor = {
    green:  'border-green-900/40',
    orange: 'border-orange-900/50',
  }[color] ?? 'border-gray-800'

  return (
    <div className={`bg-gray-900 border ${borderColor} rounded-lg px-5 py-4 text-center`}>
      <div className={`text-2xl font-semibold ${valueColor}`}>{value}</div>
      <div className="text-gray-500 text-xs mt-1">{label}</div>
    </div>
  )
}

function Stat({ value, label, color }) {
  const cls = { green: 'text-green-400', orange: 'text-orange-400', red: 'text-red-400' }[color] ?? 'text-gray-600'
  return (
    <div>
      <div className={`font-semibold ${cls}`}>{value}</div>
      <div className="text-gray-600 text-xs">{label}</div>
    </div>
  )
}

function Spinner() {
  return (
    <div className="p-8 flex items-center justify-center h-64">
      <div className="text-gray-500 text-sm">Loading…</div>
    </div>
  )
}

function NotFound({ onBack }) {
  return (
    <div className="p-8">
      <button onClick={onBack} className="flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-6">
        <ArrowLeft size={15} /> Back
      </button>
      <p className="text-gray-500">Shoot not found.</p>
    </div>
  )
}
