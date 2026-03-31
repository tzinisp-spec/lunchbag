import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Camera, Calendar, CalendarDays,
  Bot, Search, Building2, PanelLeftClose, PanelLeftOpen, X, Terminal,
} from 'lucide-react'
import { AGENTS } from '../lib/agents'

const navBase   = 'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors'
const navActive = `bg-[var(--c-nav-active-bg)] text-[var(--c-nav-active-text)]`
const navIdle   = `text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)]`

export default function Sidebar({ collapsed, onToggle, onClose, appStatus }) {
  const isLive      = appStatus?.is_live        ?? false
  const needsReview = appStatus?.needs_review   ?? 0
  const hasErrors   = appStatus?.has_log_errors ?? false

  return (
    <div className="w-64 bg-[var(--c-sidebar)] border-r border-[var(--c-border)] flex flex-col h-full shrink-0">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--c-border)]">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 bg-[var(--c-icon-box)] rounded-lg flex items-center justify-center shrink-0">
            <span className="text-[var(--c-text-1)] font-bold text-xs">LB</span>
          </div>
          <span className="text-[var(--c-text-1)] font-medium text-sm truncate">Lunchbag</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Search size={15} className="text-[var(--c-text-3)] cursor-pointer hover:text-[var(--c-text-1)]" />
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

        <NavLink to="/" end className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
          <LayoutDashboard size={16} />
          <span className="flex-1">Dashboard</span>
          {isLive && <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse shrink-0" title="Pipeline running" />}
        </NavLink>

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

        <NavLink to="/logs" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
          <Terminal size={15} />
          <span className="flex-1">Run Log</span>
          {hasErrors && <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" title="Errors in log" />}
        </NavLink>

        <div className="pt-4 pb-1 px-3">
          <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Agents</span>
        </div>

        {AGENTS.map(agent => (
          <NavLink key={agent.id} to={`/agents/${agent.id}`} className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
            <Bot size={15} />
            <span className="flex-1 truncate">{agent.name}</span>
          </NavLink>
        ))}

        <div className="pt-4 pb-1 px-3">
          <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Brand</span>
        </div>

        <NavLink to="/org" className={({ isActive }) => `${navBase} ${isActive ? navActive : navIdle}`}>
          <Building2 size={15} />
          <span>The Lunch Bags</span>
        </NavLink>

      </nav>

      <div className="border-t border-[var(--c-border)] px-4 py-3">
        <span className="text-xs text-[var(--c-text-3)] hover:text-[var(--c-text-2)] cursor-pointer transition-colors">
          Documentation
        </span>
      </div>

    </div>
  )
}
