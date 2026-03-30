import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Check, X, CheckSquare } from 'lucide-react'
import { api } from '../lib/api'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'

const SET_LABELS = { 1: 'Set 1', 2: 'Set 2', 3: 'Set 3', 0: 'Other' }

export default function ShootDetail() {
  const { shootId } = useParams()
  const navigate    = useNavigate()

  const [shoot, setShoot]       = useState(null)
  const [loading, setLoading]   = useState(true)
  const [activeSet, setActiveSet] = useState('all')
  const [selected, setSelected] = useState(new Set())
  const [working, setWorking]   = useState(false)

  const load = useCallback(() => {
    api.shoot(shootId)
      .then(data => { setShoot(data); setSelected(new Set()) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [shootId])

  useEffect(() => { load() }, [load])

  if (loading) return <Spinner />
  if (!shoot)  return <NotFound onBack={() => navigate('/photoshoots')} />

  // ── Derived counts ──────────────────────────────────────
  const totalImages  = shoot.total_images
  const approved     = shoot.images.filter(i => i.display_status === 'approved').length
  const needsReview  = shoot.images.filter(i => i.display_status === 'needs_review').length

  const setNums = Object.keys(shoot.sets ?? {}).map(Number).sort()

  const visibleImages = activeSet === 'all'
    ? shoot.images
    : shoot.images.filter(img => img.set === Number(activeSet))

  // ── Selection helpers ────────────────────────────────────
  const toggle = (filename) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(filename) ? next.delete(filename) : next.add(filename)
      return next
    })
  }

  const selectAllVisible = () => {
    setSelected(prev => {
      const next = new Set(prev)
      visibleImages.forEach(img => next.add(img.filename))
      return next
    })
  }

  const clearSelection = () => setSelected(new Set())

  // ── Actions ──────────────────────────────────────────────
  async function handleApprove() {
    const filenames = [...selected]
    if (!filenames.length) return
    setWorking(true)
    try {
      const updated = await api.approveImages(shootId, filenames)
      setShoot(updated)
      setSelected(new Set())
    } catch (e) {
      console.error(e)
    } finally {
      setWorking(false)
    }
  }

  async function handleDelete(filenames) {
    if (!filenames.length) return
    setWorking(true)
    try {
      const updated = await api.deleteImages(shootId, filenames)
      setShoot(updated)
      setSelected(new Set())
    } catch (e) {
      console.error(e)
    } finally {
      setWorking(false)
    }
  }

  const selectedCanApprove = [...selected].some(f =>
    shoot.images.find(i => i.filename === f && i.display_status === 'needs_review')
  )

  return (
    <div className="p-8 pb-32">

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

      {/* ── Always-visible image counts ── */}
      <div className="grid grid-cols-3 gap-3 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-4 text-center">
          <div className="text-2xl font-semibold text-white">{totalImages}</div>
          <div className="text-gray-500 text-xs mt-1">Total images</div>
        </div>
        <div className="bg-gray-900 border border-green-900/40 rounded-lg px-5 py-4 text-center">
          <div className="text-2xl font-semibold text-green-400">{approved}</div>
          <div className="text-gray-500 text-xs mt-1">Approved</div>
        </div>
        <div className={`bg-gray-900 rounded-lg px-5 py-4 text-center border ${needsReview > 0 ? 'border-orange-900/50' : 'border-gray-800'}`}>
          <div className={`text-2xl font-semibold ${needsReview > 0 ? 'text-orange-400' : 'text-gray-600'}`}>{needsReview}</div>
          <div className="text-gray-500 text-xs mt-1">Needs review</div>
        </div>
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
              const imgs    = shoot.sets[s] ?? []
              const app     = imgs.filter(i => i.display_status === 'approved').length
              const review  = imgs.filter(i => i.display_status === 'needs_review').length
              const regen   = imgs.filter(i => i.display_status === 'regen').length
              return (
                <div key={s} className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                  <div className="text-white font-medium mb-3">{SET_LABELS[s]}</div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <div className="text-green-400 font-semibold">{app}</div>
                      <div className="text-gray-600 text-xs">approved</div>
                    </div>
                    <div>
                      <div className={`font-semibold ${review > 0 ? 'text-orange-400' : 'text-gray-600'}`}>{review}</div>
                      <div className="text-gray-600 text-xs">review</div>
                    </div>
                    <div>
                      <div className={`font-semibold ${regen > 0 ? 'text-red-400' : 'text-gray-600'}`}>{regen}</div>
                      <div className="text-gray-600 text-xs">regen</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Image grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          {/* Set filter */}
          <div className="flex gap-1">
            {['all', ...setNums].map(s => (
              <button
                key={s}
                onClick={() => { setActiveSet(String(s)); clearSelection() }}
                className={`px-3 py-1 rounded text-xs transition-colors ${
                  activeSet === String(s) ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {s === 'all' ? `All (${shoot.images.length})` : `${SET_LABELS[s]} (${(shoot.sets[s] ?? []).length})`}
              </button>
            ))}
          </div>

          {/* Select all visible */}
          {visibleImages.length > 0 && (
            <button
              onClick={selected.size > 0 ? clearSelection : selectAllVisible}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <CheckSquare size={13} />
              {selected.size > 0 ? 'Clear selection' : 'Select all'}
            </button>
          )}
        </div>

        {visibleImages.length === 0 ? (
          <div className="text-gray-600 text-sm py-8">No images.</div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {visibleImages.map(img => (
              <ImageTile
                key={img.id}
                img={img}
                isSelected={selected.has(img.filename)}
                onToggle={() => toggle(img.filename)}
                onDelete={() => handleDelete([img.filename])}
                working={working}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Floating action bar ── */}
      {selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
          <div className="flex items-center gap-3 bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl px-5 py-3">
            <span className="text-white text-sm font-medium">{selected.size} selected</span>
            <div className="w-px h-5 bg-gray-700" />

            {selectedCanApprove && (
              <button
                onClick={handleApprove}
                disabled={working}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
              >
                <Check size={14} /> Approve
              </button>
            )}

            <button
              onClick={() => handleDelete([...selected])}
              disabled={working}
              className="flex items-center gap-2 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              <Trash2 size={14} /> Delete
            </button>

            <button
              onClick={clearSelection}
              className="text-gray-400 hover:text-white transition-colors p-1"
            >
              <X size={15} />
            </button>
          </div>
        </div>
      )}

    </div>
  )
}

// ── Image tile ───────────────────────────────────────────────────────────────

const STATUS_BADGE = {
  needs_review: { label: 'Needs Review', cls: 'bg-orange-500 text-white' },
  regen:        { label: 'Regen',        cls: 'bg-red-600 text-white' },
  pending:      { label: 'Pending',      cls: 'bg-gray-700 text-gray-300' },
}

function ImageTile({ img, isSelected, onToggle, onDelete, working }) {
  const badge = STATUS_BADGE[img.display_status]
  const src   = api.imageUrl(img.path)

  return (
    <div
      onClick={onToggle}
      className={`group relative bg-gray-900 rounded-lg overflow-hidden border transition-all cursor-pointer ${
        isSelected
          ? 'border-blue-500 ring-2 ring-blue-500/30'
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

        {/* Selection overlay */}
        {isSelected && (
          <div className="absolute inset-0 bg-blue-500/15 flex items-center justify-center">
            <div className="w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center shadow-lg">
              <Check size={14} className="text-white" strokeWidth={2.5} />
            </div>
          </div>
        )}

        {/* Status badge */}
        {badge && !isSelected && (
          <span className={`absolute top-2 left-2 text-xs px-2 py-0.5 rounded font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        )}

        {/* Delete button — top-right, visible on hover */}
        <button
          onClick={e => { e.stopPropagation(); onDelete() }}
          disabled={working}
          className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-red-600 transition-all"
        >
          <Trash2 size={12} className="text-white" />
        </button>
      </div>

      <div className="px-2 py-1.5">
        <div className="text-gray-500 text-xs truncate">
          {img.ref_code?.split('-').slice(-2).join('-')}
        </div>
      </div>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

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
