import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Camera, Calendar, CalendarDays,
  Bot, Search, Building2, PanelLeftClose, PanelLeftOpen, X, Terminal, Wand2, LogOut,
} from 'lucide-react'
import { AGENTS } from '../lib/agents'
import { useAuth } from '../lib/auth'

const navBase   = 'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors'
const navActive = `bg-[var(--c-nav-active-bg)] text-[var(--c-nav-active-text)]`
const navIdle   = `text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)]`

function NavSpinner({ color = 'green' }) {
  const borderColor = color === 'blue' ? 'border-t-blue-400' : 'border-t-green-400'
  return (
    <span className={`w-3 h-3 rounded-full border-2 border-[var(--c-border)] ${borderColor} animate-spin shrink-0`} />
  )
}

export default function Sidebar({ collapsed, onToggle, onClose, appStatus, onSearch, role }) {
  const isLive      = appStatus?.is_live        ?? false
  const p1Live      = appStatus?.p1_live        ?? false
  const p2Live      = appStatus?.p2_live        ?? false
  const needsReview = appStatus?.needs_review   ?? 0
  const hasErrors   = appStatus?.has_log_errors ?? false
  const activeAgent = appStatus?.active_agent   ?? null
  const isAdmin     = role === 'admin'
  const { logout }  = useAuth()
  const navigate    = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="w-64 bg-[var(--c-sidebar)] border-r border-[var(--c-border)] flex flex-col h-full shrink-0">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--c-border)]">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 bg-[var(--c-icon-box)] rounded-lg flex items-center justify-center shrink-0">
            <span className="text-[var(--c-text-1)] font-bold text-xs">C</span>
          </div>
          <span className="text-[var(--c-text-1)] font-medium text-sm truncate">COMAP</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={onSearch} className="flex items-center gap-1.5 rounded px-1.5 py-1 text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors" title="Search  ⌘K">
            <Search size={14} />
            <span className="text-[10px] font-mono bg-[var(--c-surface-2)] px-1 py-0.5 rounded text-[9px] leading-none">⌘K</span>
          </button>
          <button
            onClick={onToggle}
            className="hidden md:flex w-6 h-6 items-center justify-center rounded text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors ml-1"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
          <button
            onClick={onClose}
            className="md:hidden w-6 h-6 flex items-center justify-center rounded text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors ml-1"
            aria-label="Close menu"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">

        {isAdmin && (
          <NavLink to="/" end className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
            <LayoutDashboard size={16} />
            <span className="flex-1">Dashboard</span>
            {isLive && <NavSpinner />}
          </NavLink>
        )}

        {isAdmin && (
          <NavLink
            to="/run"
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors mt-1 ${
                isActive
                  ? 'bg-green-600 text-white'
                  : 'bg-green-600/15 text-green-400 border border-green-500/30 hover:bg-green-600/25'
              }`
            }
          >
            <Camera size={14} />
            <span className="flex-1">New Shoot</span>
            {p1Live && <NavSpinner />}
          </NavLink>
        )}

        {isAdmin && (
          <NavLink
            to="/content-pipeline"
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors mt-1 mb-1 ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'bg-blue-600/15 text-blue-400 border border-blue-500/30 hover:bg-blue-600/25'
              }`
            }
          >
            <Wand2 size={14} />
            <span className="flex-1">New Content Planning</span>
            {p2Live && <NavSpinner color="blue" />}
          </NavLink>
        )}

        <div className="pt-4 pb-1 px-3">
          <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Workflow</span>
        </div>

        <NavLink to="/photoshoots" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
          <Camera size={15} />
          <span className="flex-1">Photoshoot</span>
          {needsReview > 0 && (
            <span
              title={`${needsReview} image${needsReview === 1 ? '' : 's'} flagged for manual review`}
              className="text-[10px] font-bold bg-orange-500 text-white px-1.5 py-0.5 rounded-full shrink-0 leading-none min-w-[18px] text-center cursor-default"
            >
              {needsReview}
            </span>
          )}
        </NavLink>

        <NavLink to="/content-planning" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
          <Calendar size={15} />
          <span className="flex-1">Content Planning</span>
        </NavLink>

        <NavLink to="/post-scheduling" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
          <CalendarDays size={15} />
          <span className="flex-1">Auto Scheduling</span>
        </NavLink>

        {isAdmin && (
          <NavLink to="/logs" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
            <Terminal size={15} />
            <span className="flex-1">Run Log</span>
            {isLive && <NavSpinner />}
            {!isLive && hasErrors && <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" title="Errors in log" />}
          </NavLink>
        )}

        {isAdmin && (
          <>
            <div className="pt-4 pb-1 px-3">
              <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Agents</span>
            </div>
            {AGENTS.map(agent => (
              <NavLink key={agent.id} to={`/agents/${agent.id}`} className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
                <Bot size={15} />
                <span className="flex-1 truncate">{agent.name}</span>
                {activeAgent === agent.id && <NavSpinner />}
              </NavLink>
            ))}

            <div className="pt-4 pb-1 px-3">
              <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Brand</span>
            </div>
            <NavLink to="/org" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
              <Building2 size={15} />
              <span>The Lunch Bags</span>
            </NavLink>
          </>
        )}

      </nav>

      <div className="border-t border-[var(--c-border)] px-4 py-3 flex items-center justify-between">
        {isAdmin && (
          <span className="text-xs text-[var(--c-text-3)] hover:text-[var(--c-text-2)] cursor-pointer transition-colors">
            Documentation
          </span>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-xs text-[var(--c-text-3)] hover:text-red-400 transition-colors ml-auto"
          title="Sign out"
        >
          <LogOut size={13} />
          <span>Sign out</span>
        </button>
      </div>

    </div>
  )
}
