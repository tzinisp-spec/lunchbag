import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, X, Check, Download, Tag, Trash2, CheckSquare, MoreHorizontal } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import StatusBadge from '../components/StatusBadge'
import ImageLightbox from '../components/ImageLightbox'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../lib/toast'

const SET_LABELS = { 1: 'Set 1', 2: 'Set 2', 3: 'Set 3', 0: 'Other' }

const STATUS_BADGE = {
  needs_review: { label: 'Needs Review', cls: 'bg-orange-500 text-white' },
  regen:        { label: 'Regen',        cls: 'bg-red-600 text-white' },
}

export default function ShootDetail() {
  const { shootId }       = useParams()
  const navigate          = useNavigate()
  const [searchParams]    = useSearchParams()
  const initialSet        = searchParams.get('set') ?? 'all'

  const [shoot,     setShoot]     = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [activeSet, setActiveSet] = useState(initialSet)

  const [lightboxIndex, setLightboxIndex] = useState(null)

  const [selectMode, setSelectMode] = useState(false)
  const [selected,   setSelected]   = useState(new Set())

  const [confirm, setConfirm] = useState(null)   // { type, filenames }
  const [working, setWorking] = useState(false)
  const { addToast } = useToast()
  const { auth } = useAuth()
  const isAdmin = auth?.role === 'admin'

  // ── Load ──────────────────────────────────────────────────
  const refresh = useCallback(() => {
    api.shoot(shootId)
      .then(data => setShoot(data))
      .catch(console.error)
  }, [shootId])

  const load = useCallback(() => {
    setLoading(true)
    api.shoot(shootId)
      .then(data => { setShoot(data); setSelected(new Set()) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [shootId])

  useEffect(() => { load() }, [load])

  // ── Poll continuously — fast during a live run, slower otherwise ──────────
  const inProgress = shoot?.status === 'in_progress'
  useEffect(() => {
    const interval = inProgress ? 3000 : 8000
    const id = setInterval(refresh, interval)
    return () => clearInterval(id)
  }, [refresh, inProgress])

  if (loading) return <Spinner />
  if (!shoot)  return <NotFound onBack={() => navigate('/photoshoots')} />

  // ── Derived ───────────────────────────────────────────────
  const totalImages = shoot.images.length
  const approved    = shoot.images.filter(i => i.display_status === 'approved').length
  const needsReview = shoot.images.filter(i => i.display_status === 'needs_review').length
  const setNums     = Object.keys(shoot.sets ?? {}).map(Number).sort()

  const visibleImages = activeSet === 'all'
    ? shoot.images
    : activeSet === 'review'
    ? shoot.images.filter(img => img.display_status === 'needs_review')
    : shoot.images.filter(img => img.set === Number(activeSet))

  // ── Selection ─────────────────────────────────────────────
  const toggleSelect = (filename) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(filename) ? next.delete(filename) : next.add(filename)
      return next
    })
  }

  const selectAll   = () => setSelected(new Set(visibleImages.map(i => i.filename)))
  const clearSelect = () => setSelected(new Set())
  const exitSelect  = () => { setSelectMode(false); clearSelect() }

  const selectedHasReviewImages = [...selected].some(f =>
    shoot.images.find(i => i.filename === f && i.display_status === 'needs_review')
  )

  // ── Click ─────────────────────────────────────────────────
  const handleImageClick = (img, visibleIdx) => {
    if (selectMode) toggleSelect(img.filename)
    else setLightboxIndex(visibleIdx)
  }

  // ── Actions (bulk) ────────────────────────────────────────
  const requestBulkAction = (type) => setConfirm({ type, filenames: [...selected] })

  // ── Actions (single image — from tile menu or lightbox) ───
  const handleSingleAction = (type, img) => {
    if (type === 'download') {
      downloadFiles([img])
    } else {
      setConfirm({ type, filenames: [img.filename] })
    }
  }

  // ── Execute confirmed action ───────────────────────────────
  const executeAction = async () => {
    if (!confirm) return
    const { type, filenames } = confirm
    setConfirm(null)
    setWorking(true)
    try {
      let updated
      if (type === 'remove_tag') updated = await api.approveImages(shootId, filenames)
      if (type === 'delete')     updated = await api.deleteImages(shootId, filenames)
      if (updated?.images) {
        setShoot(updated)
        setSelected(new Set())
        if (lightboxIndex !== null) setLightboxIndex(null)
        const count = filenames.length
        const label = count === 1 ? '1 image' : `${count} images`
        if (type === 'remove_tag') addToast('success', `${label} approved`)
        if (type === 'delete')     addToast('success', `${label} deleted`)
      }
    } catch (e) {
      console.error(e)
      addToast('error', type === 'delete' ? 'Failed to delete — try again' : 'Failed to approve — try again')
    } finally {
      setWorking(false)
    }
  }

  // ── Download helper ────────────────────────────────────────
  const downloadFiles = async (imgs) => {
    for (const img of imgs) {
      const a = document.createElement('a')
      a.href = api.imageUrl(img.path)
      a.download = img.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      await new Promise(r => setTimeout(r, 150))
    }
  }

  const handleBulkDownload = () => {
    const imgs = shoot.images.filter(i => selected.has(i.filename))
    downloadFiles(imgs)
  }

  // ── Confirm config ────────────────────────────────────────
  const confirmCount = confirm?.filenames?.length ?? 0
  const CONFIRM_CONFIG = {
    remove_tag: {
      title:        'Remove Needs Review tag?',
      message:      `This will approve ${confirmCount} image${confirmCount === 1 ? '' : 's'} and rename the file${confirmCount === 1 ? '' : 's'} on disk. This cannot be undone.`,
      confirmLabel: 'Remove tag',
      variant:      'warning',
    },
    delete: {
      title:        `Delete ${confirmCount} image${confirmCount === 1 ? '' : 's'}?`,
      message:      `This will permanently delete ${confirmCount === 1 ? 'it' : 'them'} from disk and remove ${confirmCount === 1 ? 'it' : 'them'} from the catalog. This cannot be undone.`,
      confirmLabel: 'Delete',
      variant:      'danger',
    },
  }
  const cfg = confirm ? CONFIRM_CONFIG[confirm.type] : null

  // ── Lightbox image for actions ────────────────────────────
  const lightboxImg = lightboxIndex !== null ? visibleImages[lightboxIndex] : null

  return (
    <div className={`p-4 sm:p-6 md:p-8 ${selectMode && selected.size > 0 ? 'pb-32' : ''}`}>

      {/* Back */}
      <button
        onClick={() => navigate('/photoshoots')}
        className="flex items-center gap-2 text-[var(--c-text-2)] hover:text-[var(--c-text-1)] text-sm mb-6 transition-colors"
      >
        <ArrowLeft size={15} /> Back to Photoshoots
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Photoshoot</p>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl text-[var(--c-text-1)] font-semibold">{shoot.name}</h1>
            {inProgress && (
              <span className="flex items-center gap-1 text-[10px] font-semibold text-green-400 bg-green-400/10 border border-green-400/30 px-1.5 py-0.5 rounded">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse inline-block" />
                LIVE
              </span>
            )}
          </div>
          <p className="text-[var(--c-text-3)] text-sm mt-1">{shoot.date || shoot.month} · {shoot.sprint_id}</p>
        </div>
        <StatusBadge status={shoot.status} dot />
      </div>

      {/* ── 5 metric tiles (admin only) ── */}
      {isAdmin && <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4 mb-8">

        {/* Produced Images */}
        <DetailTile
          title="Produced Images"
          main={totalImages}
          mainLabel="total images"
          items={[
            { label: 'Approved',     value: approved,    color: 'green'  },
            { label: 'Needs review', value: needsReview, color: needsReview > 0 ? 'orange' : 'muted', pulse: needsReview > 0 },
            ...(shoot.regen > 0 ? [{ label: 'Regen', value: shoot.regen, color: 'red' }] : []),
          ]}
        />

        {/* Processing Time */}
        <DetailTile
          title="Processing Time"
          main={shoot.runtime ?? '—'}
          mainLabel="total"
          items={[
            { label: 'Generation',   value: shoot.time_generation   || '—' },
            { label: 'Photo Editor', value: shoot.time_photo_editor || '—' },
            { label: 'Brief',        value: shoot.time_brief        || '—' },
          ]}
        />

        {/* API Calls */}
        <DetailTile
          title="API Calls"
          main={shoot.total_calls?.toLocaleString() ?? '—'}
          mainLabel="total calls"
          items={[
            { label: modelShortName(shoot.image_model_name), value: shoot.calls_image_model?.toLocaleString() ?? '—' },
            { label: modelShortName(shoot.text_model_name),  value: shoot.calls_text_model?.toLocaleString()  ?? '—' },
          ]}
        />

        {/* Cost */}
        <DetailTile
          title="Cost"
          main={shoot.total_cost > 0 ? `$${shoot.total_cost.toFixed(2)}` : '—'}
          mainLabel="total"
          items={[
            { label: modelShortName(shoot.image_model_name), value: shoot.cost_image_model > 0 ? `$${shoot.cost_image_model.toFixed(2)}` : '—' },
            { label: modelShortName(shoot.text_model_name),  value: shoot.cost_text_model  > 0 ? `$${shoot.cost_text_model.toFixed(2)}`  : '—' },
          ]}
        />

        {/* Errors */}
        <DetailTile
          title="Errors"
          main={shoot.errors_total > 0 ? shoot.errors_total : shoot.errors ?? '0'}
          mainLabel="total issues"
          items={[
            { label: 'Fixed by editor', value: shoot.errors_fixed   ?? '0', color: 'green'  },
            { label: 'Needs review',    value: shoot.errors_flagged ?? '0', color: shoot.errors_flagged > 0 ? 'orange' : 'muted' },
          ]}
        />

      </div>}

      {/* Per-set breakdown */}
      {setNums.length > 0 && (
        <div className="mb-8">
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-4">Sets</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {setNums.map(s => {
              const imgs   = shoot.sets[s] ?? []
              const app    = imgs.filter(i => i.display_status === 'approved').length
              const review = imgs.filter(i => i.display_status === 'needs_review').length
              const regen  = imgs.filter(i => i.display_status === 'regen').length
              return (
                <div key={s} className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-5">
                  <div className="text-[var(--c-text-1)] font-medium mb-3">{SET_LABELS[s]}</div>
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

      {/* Image grid header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 flex-wrap">
          {['all', ...setNums].map(s => (
            <button
              key={s}
              onClick={() => { setActiveSet(String(s)); clearSelect() }}
              className={`px-3 py-1 rounded text-xs transition-colors ${
                activeSet === String(s) ? 'bg-[var(--c-surface-3)] text-[var(--c-text-1)]' : 'text-[var(--c-text-3)] hover:text-[var(--c-text-1b)]'
              }`}
            >
              {s === 'all'
                ? `All (${shoot.images.length})`
                : `${SET_LABELS[s]} (${(shoot.sets[s] ?? []).length})`}
            </button>
          ))}
          {needsReview > 0 && (
            <button
              onClick={() => { setActiveSet('review'); clearSelect() }}
              className={`px-3 py-1 rounded text-xs transition-colors ${
                activeSet === 'review'
                  ? 'bg-orange-500/20 text-orange-300 ring-1 ring-orange-500/40'
                  : 'text-orange-400 hover:text-orange-300 hover:bg-orange-500/10'
              }`}
            >
              Needs Review ({needsReview})
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0 ml-4">
          {selectMode && (
            <div className="flex items-center gap-3">
              {selected.size > 0 && (
                <span className="text-xs text-[var(--c-text-2)]">
                  <span className="font-semibold text-[var(--c-text-1)]">{selected.size}</span> selected
                </span>
              )}
              <button
                onClick={selected.size === visibleImages.length ? clearSelect : selectAll}
                className="flex items-center gap-1.5 text-xs text-[var(--c-text-2)] hover:text-[var(--c-text-1)] transition-colors"
              >
                <CheckSquare size={13} />
                {selected.size === visibleImages.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
          )}

          {selectMode ? (
            <button
              onClick={exitSelect}
              className="flex items-center gap-2 text-sm text-[var(--c-text-2)] hover:text-[var(--c-text-1)] border border-[var(--c-border-2)] px-3 py-1.5 rounded-lg transition-colors"
            >
              <X size={14} /> Done
            </button>
          ) : (
            <button
              onClick={() => setSelectMode(true)}
              className="flex items-center gap-2 text-sm text-[var(--c-text-1)] bg-[var(--c-surface-2)] hover:bg-[var(--c-surface-3)] border border-[var(--c-border-2)] px-3 py-1.5 rounded-lg transition-colors"
            >
              <CheckSquare size={13} /> Select
            </button>
          )}
        </div>
      </div>

      {/* Image grid */}
      {visibleImages.length === 0 ? (
        <div className="text-[var(--c-text-4)] text-sm py-8">No images.</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {visibleImages.map((img, idx) => (
            <ImageTile
              key={img.id}
              img={img}
              selectMode={selectMode}
              isSelected={selected.has(img.filename)}
              onClick={() => handleImageClick(img, idx)}
              onAction={(type) => handleSingleAction(type, img)}
            />
          ))}
        </div>
      )}

      {/* Floating action bar (select mode + selection) */}
      {selectMode && selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-max">
          <div className="flex items-center gap-2 bg-[var(--c-page)] border border-[var(--c-border-2)] rounded-2xl shadow-2xl px-4 py-3">
            <span className="text-[var(--c-text-1)] text-sm font-medium px-1">{selected.size} selected</span>
            <div className="w-px h-5 bg-[var(--c-border-2)] mx-1" />
            <ActionButton icon={Download} label="Download"         onClick={handleBulkDownload}                        disabled={working} />
            {selectedHasReviewImages && (
              <ActionButton icon={Tag}      label="Remove Review tag" onClick={() => requestBulkAction('remove_tag')}   disabled={working} color="orange" />
            )}
            <ActionButton icon={Trash2}   label="Delete"           onClick={() => requestBulkAction('delete')}         disabled={working} color="red" />
            <div className="w-px h-5 bg-[var(--c-border-2)] mx-1" />
            <button onClick={clearSelect} className="text-[var(--c-text-2)] hover:text-[var(--c-text-1)] transition-colors p-1 rounded">
              <X size={15} />
            </button>
          </div>
        </div>
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && (
        <ImageLightbox
          images={visibleImages}
          index={lightboxIndex}
          onNavigate={setLightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onAction={(type, img) => handleSingleAction(type, img)}
        />
      )}

      {/* Confirm dialog */}
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

// ── ImageTile ─────────────────────────────────────────────────────────────────

function ImageTile({ img, selectMode, isSelected, onClick, onAction }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  const badge = STATUS_BADGE[img.display_status]

  return (
    <div
      onClick={onClick}
      className={`group relative bg-[var(--c-surface)] rounded-lg border transition-all cursor-pointer select-none ${
        isSelected
          ? 'border-blue-500 ring-2 ring-blue-500/30'
          : selectMode
          ? 'border-[var(--c-border-2)] hover:border-[var(--c-border-2)]'
          : 'border-[var(--c-border)] hover:border-[var(--c-border-2)]'
      }`}
    >
      {/* Image */}
      <div className="relative aspect-[3/4] overflow-hidden rounded-t-lg">
        <img
          src={api.imageUrl(img.path)}
          alt={img.filename}
          loading="lazy"
          className="w-full h-full object-cover"
          onError={e => { e.target.style.display = 'none' }}
        />

        {/* Selected overlay */}
        {isSelected && (
          <div className="absolute inset-0 bg-blue-500/20 flex items-start justify-end p-2">
            <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
              <Check size={13} className="text-white" strokeWidth={2.5} />
            </div>
          </div>
        )}

        {/* Unselected hint in select mode */}
        {selectMode && !isSelected && (
          <div className="absolute top-2 right-2 w-6 h-6 rounded-full border-2 border-white/40 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}

        {/* Status badge */}
        {badge && !isSelected && (
          <span className={`absolute top-2 left-2 text-xs px-2 py-0.5 rounded font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="px-2 py-1.5 flex items-center justify-between gap-1">
        <div className="text-[var(--c-text-3)] text-xs truncate">
          {(img.ref_code || img.filename)?.split('-').slice(-2).join('-').replace('.png','')}
        </div>

        {/* 3-dot menu — hidden in select mode */}
        {!selectMode && (
          <div className="relative shrink-0" ref={menuRef}>
            <button
              onClick={e => { e.stopPropagation(); setMenuOpen(v => !v) }}
              className="w-6 h-6 rounded flex items-center justify-center text-[var(--c-text-4)] hover:text-[var(--c-text-1b)] hover:bg-[var(--c-surface-3)] transition-colors"
            >
              <MoreHorizontal size={14} />
            </button>

            {menuOpen && (
              <TileMenu
                img={img}
                onAction={(type) => { setMenuOpen(false); onAction(type) }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TileMenu({ img, onAction }) {
  const isReview = img.display_status === 'needs_review'
  return (
    <div className="absolute bottom-full right-0 mb-1 w-48 bg-[var(--c-surface-2)] border border-[var(--c-border-2)] rounded-lg shadow-xl overflow-hidden z-[60] py-1">
      <MenuItem icon={Download} label="Download"          onClick={() => onAction('download')} />
      {isReview && (
        <MenuItem icon={Tag}    label="Remove Review tag" onClick={() => onAction('remove_tag')} color="orange" />
      )}
      <div className="my-1 border-t border-[var(--c-border-2)]" />
      <MenuItem icon={Trash2}  label="Delete image"      onClick={() => onAction('delete')} color="red" />
    </div>
  )
}

function MenuItem({ icon: Icon, label, onClick, color }) {
  const cls = { orange: 'text-orange-400', red: 'text-red-400' }[color] ?? 'text-[var(--c-text-1b)]'
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-[var(--c-surface-3)] transition-colors ${cls}`}
    >
      <Icon size={14} />
      {label}
    </button>
  )
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function ActionButton({ icon: Icon, label, onClick, disabled, color }) {
  const cls = {
    orange: 'hover:bg-orange-600/20 hover:text-orange-300 text-orange-400',
    red:    'hover:bg-red-600/20 hover:text-red-300 text-red-400',
  }[color] ?? 'hover:bg-[var(--c-surface-3)] text-[var(--c-text-1b)]'
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 text-sm font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40 ${cls}`}
    >
      <Icon size={14} /> {label}
    </button>
  )
}

// ── Detail tile ───────────────────────────────────────────────────────────────

const VALUE_COLOR = {
  green:  'text-green-400',
  orange: 'text-orange-400',
  red:    'text-red-400',
  muted:  'text-[var(--c-text-4)]',
}

function DetailTile({ title, main, mainLabel, items = [] }) {
  return (
    <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-5 flex flex-col">
      <div className="text-[var(--c-text-3)] text-xs uppercase tracking-wider mb-3">{title}</div>
      <div className="text-2xl text-[var(--c-text-1)] font-semibold leading-none">{main}</div>
      {mainLabel && <div className="text-[var(--c-text-4)] text-xs mt-1">{mainLabel}</div>}
      {items.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--c-border)] space-y-1.5 flex-1">
          {items.map((item, i) => (
            <div key={i} className="flex items-center justify-between gap-2">
              <span className="text-[var(--c-text-3)] text-xs truncate">{item.label}</span>
              <span className={`text-xs font-medium shrink-0 ${VALUE_COLOR[item.color] ?? 'text-[var(--c-text-1b)]'} ${item.pulse ? 'animate-pulse' : ''}`}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function modelShortName(name) {
  if (!name) return 'Unknown'
  // gemini-3-pro-image-preview → Gemini Image
  if (/image/i.test(name))  return 'Gemini Image'
  // gemini-2.5-pro → Gemini 2.5 Pro
  const m = name.match(/gemini[- ]?([\d.]+[^\s]*)/i)
  return m ? `Gemini ${m[1]}` : name
}

function Stat({ value, label, color }) {
  const cls = { green: 'text-green-400', orange: 'text-orange-400', red: 'text-red-400' }[color] ?? 'text-[var(--c-text-4)]'
  return (
    <div>
      <div className={`font-semibold ${cls}`}>{value}</div>
      <div className="text-[var(--c-text-4)] text-xs">{label}</div>
    </div>
  )
}

function Spinner() {
  return <div className="p-8 flex items-center justify-center h-64"><div className="text-[var(--c-text-3)] text-sm">Loading…</div></div>
}

function NotFound({ onBack }) {
  return (
    <div className="p-8">
      <button onClick={onBack} className="flex items-center gap-2 text-[var(--c-text-2)] hover:text-[var(--c-text-1)] text-sm mb-6"><ArrowLeft size={15} /> Back</button>
      <p className="text-[var(--c-text-3)]">Shoot not found.</p>
    </div>
  )
}
