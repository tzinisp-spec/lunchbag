import { useEffect, useCallback } from 'react'
import { X, ChevronLeft, ChevronRight, Download, Tag, Trash2 } from 'lucide-react'
import { api } from '../lib/api'

const STATUS_BADGE = {
  needs_review: { label: 'Needs Review', cls: 'bg-orange-500 text-white' },
  regen:        { label: 'Regen',        cls: 'bg-red-600 text-white' },
  approved:     { label: 'Approved',     cls: 'bg-green-600/80 text-white' },
}

/**
 * props:
 *   images      array of image objects
 *   index       current index (controlled)
 *   onNavigate  fn(newIndex)
 *   onClose     fn()
 *   onAction    fn(type, img)  — 'download' | 'remove_tag' | 'delete'
 */
export default function ImageLightbox({ images, index, onNavigate, onClose, onAction }) {
  const img   = images[index]
  const total = images.length
  const hasPrev = index > 0
  const hasNext = index < total - 1

  const prev = useCallback(() => { if (hasPrev) onNavigate(index - 1) }, [index, hasPrev, onNavigate])
  const next = useCallback(() => { if (hasNext) onNavigate(index + 1) }, [index, hasNext, onNavigate])

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose])

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  if (!img) return null

  const badge      = STATUS_BADGE[img.display_status]
  const isReview   = img.display_status === 'needs_review'

  return (
    <div className="fixed inset-0 z-[90] flex flex-col items-center justify-center bg-black/95">

      {/* Close */}
      <button
        onClick={onClose}
        className="absolute top-5 right-5 w-10 h-10 rounded-full bg-gray-900/80 hover:bg-gray-700 flex items-center justify-center transition-colors z-10"
      >
        <X size={18} className="text-white" />
      </button>

      {/* Counter */}
      <div className="absolute top-5 left-5 text-gray-400 text-sm font-medium z-10">
        {index + 1} / {total}
      </div>

      {/* Prev */}
      <button
        onClick={prev}
        disabled={!hasPrev}
        className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gray-900/70 hover:bg-gray-700 disabled:opacity-20 disabled:cursor-default flex items-center justify-center transition-colors z-10"
      >
        <ChevronLeft size={24} className="text-white" />
      </button>

      {/* Next */}
      <button
        onClick={next}
        disabled={!hasNext}
        className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gray-900/70 hover:bg-gray-700 disabled:opacity-20 disabled:cursor-default flex items-center justify-center transition-colors z-10"
      >
        <ChevronRight size={24} className="text-white" />
      </button>

      {/* Image */}
      <img
        key={img.path}
        src={api.imageUrl(img.path)}
        alt={img.filename}
        className="max-w-[88vw] max-h-[76vh] object-contain rounded-lg shadow-2xl"
      />

      {/* Meta + actions */}
      <div className="flex flex-col items-center gap-3 mt-5">
        {/* Filename + badge */}
        <div className="flex items-center gap-3">
          <span className="text-gray-400 text-sm">
            {img.ref_code?.split('-').slice(-2).join('-')}
          </span>
          {badge && (
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${badge.cls}`}>
              {badge.label}
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1">
          <LightboxAction
            icon={Download}
            label="Download"
            onClick={() => onAction('download', img)}
          />
          {isReview && (
            <LightboxAction
              icon={Tag}
              label="Remove Review tag"
              onClick={() => onAction('remove_tag', img)}
              color="orange"
            />
          )}
          <LightboxAction
            icon={Trash2}
            label="Delete"
            onClick={() => onAction('delete', img)}
            color="red"
          />
        </div>
      </div>

      {/* Backdrop click to close */}
      <div className="absolute inset-0 -z-10" onClick={onClose} />
    </div>
  )
}

function LightboxAction({ icon: Icon, label, onClick, color }) {
  const cls = {
    orange: 'text-orange-400 hover:bg-orange-500/15 hover:text-orange-300',
    red:    'text-red-400   hover:bg-red-500/15    hover:text-red-300',
  }[color] ?? 'text-gray-300 hover:bg-gray-700/60 hover:text-white'

  return (
    <button
      onClick={e => { e.stopPropagation(); onClick() }}
      className={`flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg transition-colors ${cls}`}
    >
      <Icon size={14} />
      {label}
    </button>
  )
}
