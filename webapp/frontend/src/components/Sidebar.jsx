import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Camera, Calendar, CalendarDays,
  Users, Search, Building2,
} from 'lucide-react'

const AGENTS = [
  { id: 'orchestrator', name: 'Content Orchestrator' },
  { id: 'trend_scout',  name: 'Trend Scout' },
  { id: 'strategist',   name: 'Content Strategist' },
  { id: 'director',     name: 'Visual Director' },
  { id: 'photographer', name: 'Photographer' },
  { id: 'photo_editor', name: 'Photo Editor' },
]

const navBase   = 'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors'
const navActive = 'bg-gray-900 text-white'
const navIdle   = 'text-gray-400 hover:text-white hover:bg-gray-900'

export default function Sidebar() {
  return (
    <div className="w-64 bg-black border-r border-gray-800 flex flex-col h-full shrink-0">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gray-900 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-xs">LB</span>
          </div>
          <span className="text-white font-medium text-sm">Lunchbag</span>
        </div>
        <Search size={15} className="text-gray-500 cursor-pointer hover:text-gray-300" />
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">

        {/* Dashboard */}
        <NavLink
          to="/"
          end
          className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}
        >
          <LayoutDashboard size={16} />
          <span className="flex-1">Dashboard</span>
        </NavLink>

        {/* ── Workflow ── */}
        <div className="pt-4 pb-1 px-3">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Workflow</span>
        </div>

        <NavLink
          to="/photoshoots"
          className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}
        >
          <span className="w-2 h-2 rounded-full bg-pink-500 shrink-0" />
          <Camera size={15} />
          <span className="flex-1">Photoshoot</span>
        </NavLink>

        <NavLink
          to="/content-planning"
          className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}
        >
          <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
          <Calendar size={15} />
          <span className="flex-1">Content Planning</span>
        </NavLink>

        <NavLink
          to="/post-scheduling"
          className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}
        >
          <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
          <CalendarDays size={15} />
          <span className="flex-1">Post Scheduling</span>
        </NavLink>

        {/* ── Agents ── */}
        <div className="pt-4 pb-1 px-3 flex items-center justify-between">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Agents</span>
        </div>

        {AGENTS.map(agent => (
          <NavLink
            key={agent.id}
            to={`/agents/${agent.id}`}
            className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}
          >
            <Users size={15} />
            <span className="flex-1 truncate">{agent.name}</span>
          </NavLink>
        ))}

        {/* ── Company ── */}
        <div className="pt-4 pb-1 px-3">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Company</span>
        </div>

        <div className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-900 transition-colors cursor-default">
          <Building2 size={15} />
          <span>Org</span>
        </div>

      </nav>

      {/* Footer */}
      <div className="border-t border-gray-800 px-4 py-3">
        <span className="text-xs text-gray-500 hover:text-gray-400 cursor-pointer transition-colors">
          Documentation
        </span>
      </div>

    </div>
  )
}
