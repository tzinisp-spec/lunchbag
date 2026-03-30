import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarDays, ImageIcon } from 'lucide-react'
import { api } from '../lib/api'
import StatusBadge from '../components/StatusBadge'

export default function Photoshoots() {
  const [shoots, setShoots] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.shoots()
      .then(setShoots)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading />

  return (
    <div className="p-8">

      <div className="mb-8">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Workflow</p>
        <h1 className="text-2xl text-white font-semibold">Photoshoot</h1>
      </div>

      {!shoots.length ? (
        <div className="text-gray-600 text-sm">No shoots found in asset_library.</div>
      ) : (
        <div className="space-y-3">
          {shoots.map(shoot => (
            <ShootCard
              key={shoot.id}
              shoot={shoot}
              onClick={() => navigate(`/photoshoots/${shoot.id}`)}
            />
          ))}
        </div>
      )}

    </div>
  )
}

function ShootCard({ shoot, onClick }) {
  const hasReview = shoot.needs_review > 0

  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-lg p-6 hover:bg-gray-800/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">

        {/* Left — name + meta */}
        <div>
          <div className="text-white text-lg font-medium mb-1">{shoot.name}</div>
          <div className="flex items-center gap-4 text-gray-400 text-sm">
            <span className="flex items-center gap-1.5">
              <CalendarDays size={13} />
              {shoot.date || shoot.month}
            </span>
            <span className="flex items-center gap-1.5">
              <ImageIcon size={13} />
              {shoot.total_images} images
            </span>
            {shoot.total_cost > 0 && (
              <span className="text-gray-500">${shoot.total_cost.toFixed(2)}</span>
            )}
          </div>
        </div>

        {/* Right — counts + status */}
        <div className="flex items-center gap-6">
          <div className="text-center hidden sm:block">
            <div className="text-white font-semibold">{shoot.total_images}</div>
            <div className="text-gray-500 text-xs">total</div>
          </div>
          <div className="text-center hidden sm:block">
            <div className="text-green-400 font-semibold">{shoot.approved}</div>
            <div className="text-gray-500 text-xs">approved</div>
          </div>
          <div className="text-center hidden sm:block">
            <div className={`font-semibold ${shoot.needs_review > 0 ? 'text-orange-400' : 'text-gray-600'}`}>
              {shoot.needs_review}
            </div>
            <div className="text-gray-500 text-xs">review</div>
          </div>
          <StatusBadge status={shoot.status} dot />
        </div>

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
