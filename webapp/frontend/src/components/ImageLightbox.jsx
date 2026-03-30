import { useEffect, useCallback } from 'react'
import { X, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'

const STATUS_BADGE = {
  needs_review: { label: 'Needs Review', cls: 'bg-orange-500 text-white' },
  regen:        { label: 'Regen',        cls: 'bg-red-600 text-white' },
  approved:     { label: 'Approved',     cls: 'bg-green-600 text-white' },
}

/**
 * props:
 *   images       array of image objects from the shoot
 *   index        current index (controlled)
 *   onNavigate   fn(newIndex)
 *   onClose      fn()
 */
export default function ImageLightbox({ images, index, onNavigate, onClose }) {
  const img   = images[index]
  const total = images.length
  const hasPrev = index > 0
  const hasNext = index < total - 1

  const prev = useCallback(() => { if (hasPrev) onNavigate(index - 1) }, [index, hasPrev, onNavigate])
  const next = useCallback(() => { if (hasNext) onNavigate(index + 1) }, [index, hasNext, onNavigate])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose])

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  if (!img) return null

  const badge = STATUS_BADGE[img.display_status]

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/95">

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

      {/* Prev arrow */}
      <button
        onClick={prev}
        disabled={!hasPrev}
        className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gray-900/70 hover:bg-gray-700 disabled:opacity-20 disabled:cursor-default flex items-center justify-center transition-colors z-10"
      >
        <ChevronLeft size={24} className="text-white" />
      </button>

      {/* Next arrow */}
      <button
        onClick={next}
        disabled={!hasNext}
        className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gray-900/70 hover:bg-gray-700 disabled:opacity-20 disabled:cursor-default flex items-center justify-center transition-colors z-10"
      >
        <ChevronRight size={24} className="text-white" />
      </button>

      {/* Image + meta */}
      <div className="flex flex-col items-center max-w-[90vw] max-h-[90vh]">
        <img
          key={img.path}
          src={api.imageUrl(img.path)}
          alt={img.filename}
          className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-2xl"
        />
        <div className="flex items-center gap-3 mt-4">
          <span className="text-gray-400 text-sm">{img.ref_code?.split('-').slice(-2).join('-')}</span>
          {badge && (
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${badge.cls}`}>
              {badge.label}
            </span>
          )}
        </div>
      </div>

      {/* Click backdrop to close */}
      <div
        className="absolute inset-0 -z-10"
        onClick={onClose}
      />
    </div>
  )
}
