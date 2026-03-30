import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Image, Bot, Phone, DollarSign } from 'lucide-react'
import { api } from '../lib/api'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'

function fmt(n) {
  return n?.toLocaleString() ?? '—'
}

export default function Dashboard() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.dashboard()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading />

  const d = data ?? {}

  return (
    <div className="p-8">

      {/* Header */}
      <div className="mb-8">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Dashboard</p>
        <h1 className="text-2xl text-white font-semibold">Lunchbag</h1>
      </div>

      {/* Overview stats */}
      <Section label="Overview">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <StatCard label="Agents"        value={fmt(d.agents)}        />
          <StatCard label="Shoots"        value={fmt(d.shoots)}        />
          <StatCard label="Total Images"  value={fmt(d.total_images)}  />
          <StatCard label="API Calls"     value={fmt(d.total_calls)}   />
          <StatCard label="Total Cost"    value={d.total_cost != null ? `$${d.total_cost.toFixed(2)}` : '—'} />
        </div>
      </Section>

      {/* Recent shoots */}
      <Section label="Recent Shoots">
        {!d.recent_shoots?.length ? (
          <Empty text="No shoots found." />
        ) : (
          <div className="space-y-3">
            {d.recent_shoots.map(shoot => (
              <ShootRow
                key={shoot.id}
                shoot={shoot}
                onClick={() => navigate(`/photoshoots/${shoot.id}`)}
              />
            ))}
          </div>
        )}
      </Section>

      {/* Agents */}
      <Section label="Agents">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {AGENTS.map(a => (
            <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-4 flex items-center gap-4">
              <div className="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center shrink-0">
                <Bot size={16} className="text-gray-400" />
              </div>
              <div>
                <div className="text-white text-sm font-medium">{a.name}</div>
                <div className="text-gray-500 text-xs">{a.role}</div>
              </div>
            </div>
          ))}
        </div>
      </Section>

    </div>
  )
}

function ShootRow({ shoot, onClick }) {
  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-lg px-6 py-4 flex items-center justify-between hover:bg-gray-800/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div>
        <div className="text-white font-medium">{shoot.name}</div>
        <div className="text-gray-500 text-sm mt-0.5">{shoot.date || shoot.month}</div>
      </div>
      <div className="flex items-center gap-8">
        <div className="text-center hidden sm:block">
          <div className="text-white font-semibold">{shoot.approved}</div>
          <div className="text-gray-500 text-xs">approved</div>
        </div>
        <div className="text-center hidden sm:block">
          <div className="text-white font-semibold">{shoot.total_images}</div>
          <div className="text-gray-500 text-xs">total</div>
        </div>
        {shoot.total_cost > 0 && (
          <div className="text-center hidden md:block">
            <div className="text-white font-semibold">${shoot.total_cost.toFixed(2)}</div>
            <div className="text-gray-500 text-xs">cost</div>
          </div>
        )}
        <StatusBadge status={shoot.status} dot />
      </div>
    </div>
  )
}

function Section({ label, children }) {
  return (
    <div className="mb-10">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">{label}</p>
      {children}
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

function Empty({ text }) {
  return <div className="text-gray-600 text-sm py-4">{text}</div>
}

const AGENTS = [
  { id: 'orchestrator', name: 'Content Orchestrator', role: 'Coordinates the full sprint' },
  { id: 'trend_scout',  name: 'Trend Scout',          role: 'Instagram trend research' },
  { id: 'strategist',   name: 'Content Strategist',   role: 'Creative brief & references' },
  { id: 'director',     name: 'Visual Director',      role: 'Style Bible & Shot List' },
  { id: 'photographer', name: 'Photographer',         role: 'Image generation' },
  { id: 'qc',           name: 'QC Inspector',         role: 'Photo editing & quality control' },
]
