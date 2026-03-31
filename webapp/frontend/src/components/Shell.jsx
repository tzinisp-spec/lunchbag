import { useState, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Menu, Sun, Moon, PanelLeftOpen, Bot, Plus } from 'lucide-react'
import Sidebar from './Sidebar'
import { useTheme } from '../lib/theme'
import { useToast } from '../lib/toast'
import { api } from '../lib/api'

// ── Run lifecycle monitor ─────────────────────────────────────────────────────
function RunMonitor({ onStatus }) {
  const { addToast } = useToast()
  const navigate     = useNavigate()
  const prevRef      = useRef(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const s = await api.status()
        if (cancelled) return
        onStatus(s)
        const prev = prevRef.current
        prevRef.current = s
        if (!prev) return  // first tick — establish baseline only

        // Run started
        if (!prev.is_live && s.is_live) {
          addToast('info', `Pipeline started · ${s.run_id ?? ''}`.replace(/· $/, '').trim())
        }
        // Run completed
        if (prev.is_live && !s.is_live && s.run_status === 'completed') {
          const sum = s.completed_summary
          addToast('success', sum
            ? `Run complete · ${sum.total_images} images · ${sum.runtime}`
            : 'Run complete')
        }
        // Run failed
        if (prev.is_live && !s.is_live && s.failed_step) {
          addToast('error', `Pipeline failed at ${s.failed_step}`)
        }
        // Sprint report ready
        if (!prev.sprint_ready && s.sprint_ready) {
          addToast('info', 'Sprint report ready', {
            action: { label: 'See the report', onClick: () => navigate('/sprint-report') },
          })
        }
        // New images need review (only fire when count increases during a live run)
        if (s.is_live && s.needs_review > (prev.needs_review ?? 0)) {
          addToast('warning', `${s.needs_review} image${s.needs_review === 1 ? '' : 's'} need manual review`)
        }
      } catch (_) { /* silent — network blip */ }
    }

    poll()
    const id = setInterval(poll, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [addToast, navigate, onStatus])

  return null
}

// ── Shell ─────────────────────────────────────────────────────────────────────
export default function Shell({ children }) {
  const [collapsed,  setCollapsed]  = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [appStatus,  setAppStatus]  = useState(null)
  const { theme, toggle } = useTheme()
  const location = useLocation()

  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  const toggleCollapsed = useCallback(() => setCollapsed(c => !c), [])

  return (
    <div className="flex h-screen bg-[var(--c-page)] text-[var(--c-text-1)] overflow-hidden">

      <RunMonitor onStatus={setAppStatus} />

      {drawerOpen && (
        <div className="fixed inset-0 bg-black/70 z-20 md:hidden" onClick={() => setDrawerOpen(false)} />
      )}

      {/* Icon Rail */}
      <div className="hidden md:flex w-16 bg-[var(--c-sidebar)] border-r border-[var(--c-border-subtle)] flex-col items-center py-4 gap-3 shrink-0">
        <div className="w-10 h-10 bg-[var(--c-icon-box)] rounded-lg flex items-center justify-center select-none" title="Lunchbag">
          <Bot size={18} className="text-[var(--c-text-1)]" />
        </div>
        <div
          className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center select-none cursor-pointer hover:bg-orange-400 transition-colors"
          style={{ boxShadow: '0 0 0 2px var(--c-sidebar), 0 0 0 4px #f97316' }}
          title="The Lunch Bags"
        >
          <span className="text-white font-bold text-sm">L</span>
        </div>
        <div className="flex-1" />
        {collapsed && (
          <button onClick={toggleCollapsed} className="w-10 h-10 flex items-center justify-center rounded-lg text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors" aria-label="Expand sidebar">
            <PanelLeftOpen size={16} />
          </button>
        )}
        <button onClick={toggle} className="w-10 h-10 flex items-center justify-center rounded-lg text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors" aria-label="Toggle theme">
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button className="w-10 h-10 flex items-center justify-center rounded-lg border-2 border-dashed border-[var(--c-border)] text-[var(--c-text-3)] hover:border-[var(--c-border-2)] hover:text-[var(--c-text-2)] transition-colors" title="Add client" aria-label="Add client">
          <Plus size={16} />
        </button>
      </div>

      {/* Sidebar */}
      <div className={[
        'fixed inset-y-0 left-0 z-30',
        'md:relative md:inset-auto md:z-auto',
        'transition-[width,transform] duration-200 ease-in-out',
        drawerOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        collapsed ? 'md:w-0' : 'md:w-64',
        'overflow-hidden w-64',
      ].join(' ')}>
        <Sidebar collapsed={collapsed} onToggle={toggleCollapsed} onClose={() => setDrawerOpen(false)} appStatus={appStatus} />
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto min-w-0">
        <div className="md:hidden sticky top-0 z-10 bg-[var(--c-sidebar)] border-b border-[var(--c-border)] px-4 py-3 flex items-center gap-3 shrink-0">
          <button onClick={() => setDrawerOpen(true)} className="w-8 h-8 flex items-center justify-center rounded text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors" aria-label="Open menu">
            <Menu size={18} />
          </button>
          <div className="flex items-center gap-2 flex-1">
            <div className="w-6 h-6 bg-[var(--c-icon-box)] rounded flex items-center justify-center">
              <span className="text-[var(--c-text-1)] font-bold text-[9px] leading-none">LB</span>
            </div>
            <span className="text-[var(--c-text-1)] font-medium text-sm">Lunchbag</span>
          </div>
          <button onClick={toggle} className="w-8 h-8 flex items-center justify-center rounded text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors" aria-label="Toggle theme">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
        {children}
      </main>

    </div>
  )
}
