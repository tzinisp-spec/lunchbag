import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'

const SET_LABELS = { 1: 'Set 1', 2: 'Set 2', 3: 'Set 3', 0: 'Unassigned' }

const IMAGE_STATUS_BADGE = {
  approved:     null,
  needs_review: { label: 'Needs Review', cls: 'bg-orange-500 text-white' },
  regen:        { label: 'Regen',        cls: 'bg-red-600 text-white' },
  pending:      { label: 'Pending',      cls: 'bg-gray-700 text-gray-300' },
}

export default function ShootDetail() {
  const { shootId } = useParams()
  const navigate    = useNavigate()
  const [shoot, setShoot]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeSet, setActiveSet] = useState('all')

  useEffect(() => {
    api.shoot(shootId)
      .then(setShoot)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [shootId])

  if (loading) return <Loading />
  if (!shoot)  return <NotFound onBack={() => navigate('/photoshoots')} />

  const setNums = Object.keys(shoot.sets ?? {})
    .map(Number)
    .sort()

  const visibleImages = activeSet === 'all'
    ? shoot.images
    : shoot.images.filter(img => img.set === Number(activeSet))

  return (
    <div className="p-8">

      {/* Back */}
      <button
        onClick={() => navigate('/photoshoots')}
        className="flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-6 transition-colors"
      >
        <ArrowLeft size={15} />
        Back to Photoshoots
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Photoshoot</p>
          <h1 className="text-2xl text-white font-semibold">{shoot.name}</h1>
          <p className="text-gray-500 text-sm mt-1">{shoot.date || shoot.month} · {shoot.sprint_id}</p>
        </div>
        <StatusBadge status={shoot.status} dot />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-10">
        <StatCard label="Runtime"      value={shoot.runtime ?? '—'} />
        <StatCard label="API Calls"    value={shoot.total_calls?.toLocaleString() ?? '—'} />
        <StatCard label="Cost"         value={shoot.total_cost > 0 ? `$${shoot.total_cost.toFixed(2)}` : '—'} />
        <StatCard label="Errors"       value={shoot.errors ?? '0'} />
        <StatCard label="Final Images" value={shoot.approved} sub={`of ${shoot.total_images} generated`} />
      </div>

      {/* Per-set breakdown */}
      {setNums.length > 0 && (
        <div className="mb-8">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Sets</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {setNums.map(s => {
              const imgs = shoot.sets[s] ?? []
              const approved = imgs.filter(i => i.display_status === 'approved').length
              const review   = imgs.filter(i => i.display_status === 'needs_review').length
              const regen    = imgs.filter(i => i.display_status === 'regen').length
              return (
                <div key={s} className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                  <div className="text-white font-medium mb-3">{SET_LABELS[s]}</div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <div className="text-green-500 font-semibold">{approved}</div>
                      <div className="text-gray-600 text-xs">approved</div>
                    </div>
                    <div>
                      <div className="text-orange-400 font-semibold">{review}</div>
                      <div className="text-gray-600 text-xs">review</div>
                    </div>
                    <div>
                      <div className="text-red-400 font-semibold">{regen}</div>
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
          <p className="text-xs text-gray-500 uppercase tracking-wider">Images</p>
          {/* Set filter tabs */}
          <div className="flex gap-1">
            {['all', ...setNums].map(s => (
              <button
                key={s}
                onClick={() => setActiveSet(String(s))}
                className={`px-3 py-1 rounded text-xs transition-colors ${
                  activeSet === String(s)
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {s === 'all' ? 'All' : SET_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        {visibleImages.length === 0 ? (
          <div className="text-gray-600 text-sm py-8">No images.</div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {visibleImages.map(img => (
              <ImageTile key={img.id} img={img} />
            ))}
          </div>
        )}
      </div>

    </div>
  )
}

function ImageTile({ img }) {
  const badge = IMAGE_STATUS_BADGE[img.display_status]
  const src   = api.imageUrl(img.path)

  return (
    <div className="group bg-gray-900 rounded-lg overflow-hidden border border-gray-800 hover:border-gray-600 transition-colors">
      <div className="relative aspect-[3/4]">
        <img
          src={src}
          alt={img.filename}
          loading="lazy"
          className="w-full h-full object-cover"
          onError={e => { e.target.style.display = 'none' }}
        />
        {badge && (
          <span className={`absolute top-2 right-2 text-xs px-2 py-0.5 rounded font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        )}
      </div>
      <div className="px-2 py-1.5">
        <div className="text-gray-500 text-xs truncate">{img.ref_code?.split('-').slice(-2).join('-')}</div>
      </div>
    </div>
  )
}

function Loading() {
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
