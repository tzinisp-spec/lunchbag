import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { AGENTS } from '../lib/agents'
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
            <div
              key={a.id}
              onClick={() => navigate(`/agents/${a.id}`)}
              className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-4 flex items-center gap-4 hover:bg-gray-800/50 transition-colors cursor-pointer group"
            >
              <div className="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center shrink-0 text-lg">
                {a.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-white text-sm font-medium">{a.name}</div>
                <div className="text-gray-500 text-xs truncate">{a.role}</div>
              </div>
              <ChevronRight size={15} className="text-gray-700 group-hover:text-gray-400 transition-colors shrink-0" />
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

