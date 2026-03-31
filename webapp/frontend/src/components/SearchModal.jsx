import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, X, LayoutDashboard, Camera, Calendar, CalendarDays,
  Bot, Building2, Terminal, Wand2, Image, FolderOpen, FileText,
  ArrowRight,
} from 'lucide-react'
import { AGENTS } from '../lib/agents'
import { api } from '../lib/api'

// ── Static data ───────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { label: 'Dashboard',          url: '/',                  icon: LayoutDashboard, category: 'Pages' },
  { label: 'Photoshoots',        url: '/photoshoots',       icon: Camera,          category: 'Pages' },
  { label: 'Content Planning',   url: '/content-planning',  icon: Calendar,        category: 'Pages' },
  { label: 'Auto Scheduling',    url: '/post-scheduling',   icon: CalendarDays,    category: 'Pages' },
  { label: 'Run Log',            url: '/logs',              icon: Terminal,        category: 'Pages' },
  { label: 'New Shoot',          url: '/run',               icon: Camera,          category: 'Pages' },
  { label: 'New Content Plan',   url: '/content-pipeline',  icon: Wand2,           category: 'Pages' },
  { label: 'Organisation',       url: '/org',               icon: Building2,       category: 'Pages' },
]

function buildAgentItems(q) {
  const lq = q.toLowerCase()
  const results = []
  for (const a of AGENTS) {
    const searchable = [
      a.name, a.role, a.tagline, a.goal,
      ...(a.skills ?? []),
      ...(a.tasks ?? []).map(t => `${t.name} ${t.description}`),
      ...(a.what_they_do ?? []).map(w => `${w.title} ${w.text}`),
    ].join(' ').toLowerCase()

    if (searchable.includes(lq)) {
      // Find matching context snippet
      let sub = a.role
      const matchTask = (a.tasks ?? []).find(t =>
        t.name.toLowerCase().includes(lq) || t.description.toLowerCase().includes(lq)
      )
      const matchSkill = (a.skills ?? []).find(s => s.toLowerCase().includes(lq))
      if (matchTask) sub = matchTask.name
      else if (matchSkill) sub = matchSkill

      results.push({
        id:       a.id,
        label:    a.name,
        sub,
        url:      `/agents/${a.id}`,
        category: 'Agents',
        icon:     Bot,
        color:    a.color,
      })
    }
  }
  return results
}

// ── Result item ───────────────────────────────────────────────────────────────

function ResultItem({ item, active, onClick }) {
  const ref = useRef(null)
  useEffect(() => { if (active) ref.current?.scrollIntoView({ block: 'nearest' }) }, [active])

  const Icon = item.icon ?? ArrowRight

  return (
    <button
      ref={ref}
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
        active
          ? 'bg-[var(--c-nav-active-bg)] text-[var(--c-nav-active-text)]'
          : 'hover:bg-[var(--c-surface-2)] text-[var(--c-text-2)]'
      }`}
    >
      <div className="w-7 h-7 rounded-md bg-[var(--c-surface-3)] flex items-center justify-center shrink-0">
        <Icon size={14} className={active ? '' : 'text-[var(--c-text-3)]'} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm truncate ${active ? '' : 'text-[var(--c-text-1)]'}`}>{item.label}</p>
        {item.sub && (
          <p className={`text-xs truncate mt-0.5 ${active ? 'opacity-70' : 'text-[var(--c-text-3)]'}`}>
            {item.sub}
          </p>
        )}
      </div>
      {item.badge && (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--c-surface-3)] text-[var(--c-text-3)] shrink-0">
          {item.badge}
        </span>
      )}
    </button>
  )
}

// ── Group header ──────────────────────────────────────────────────────────────

function GroupHeader({ label }) {
  return (
    <div className="px-4 py-1.5 mt-1">
      <span className="text-[10px] uppercase tracking-wider text-[var(--c-text-3)] font-medium">{label}</span>
    </div>
  )
}

// ── SearchModal ───────────────────────────────────────────────────────────────

export default function SearchModal({ open, onClose }) {
  const [query,     setQuery]     = useState('')
  const [apiResult, setApiResult] = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [cursor,    setCursor]    = useState(0)
  const inputRef  = useRef(null)
  const debounceRef = useRef(null)
  const navigate  = useNavigate()

  // Reset on open
  useEffect(() => {
    if (open) {
      setQuery('')
      setApiResult(null)
      setCursor(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Debounced API search
  useEffect(() => {
    clearTimeout(debounceRef.current)
    if (query.length < 2) { setApiResult(null); return }
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const r = await api.search(query)
        setApiResult(r)
      } catch (_) {}
      setLoading(false)
    }, 250)
    return () => clearTimeout(debounceRef.current)
  }, [query])

  // Build flat result list for keyboard nav
  const items = buildResultList(query, apiResult)

  useEffect(() => { setCursor(0) }, [query])

  const go = useCallback((item) => {
    navigate(item.url)
    onClose()
  }, [navigate, onClose])

  // Keyboard nav
  useEffect(() => {
    if (!open) return
    function onKey(e) {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, items.length - 1)) }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)) }
      if (e.key === 'Enter' && items[cursor]) go(items[cursor])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, items, cursor, go, onClose])

  if (!open) return null

  const grouped = buildGrouped(query, apiResult)
  let flatIdx = 0

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-xl bg-[var(--c-sidebar)] border border-[var(--c-border)] rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[70vh]">

        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--c-border)]">
          <Search size={16} className="text-[var(--c-text-3)] shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search shoots, images, posts, agents…"
            className="flex-1 bg-transparent text-[var(--c-text-1)] text-sm placeholder:text-[var(--c-text-3)] outline-none"
          />
          {loading && (
            <div className="w-4 h-4 border-2 border-[var(--c-border)] border-t-[var(--c-text-3)] rounded-full animate-spin shrink-0" />
          )}
          {query && !loading && (
            <button onClick={() => setQuery('')} className="text-[var(--c-text-3)] hover:text-[var(--c-text-1)] transition-colors">
              <X size={15} />
            </button>
          )}
        </div>

        {/* Results */}
        <div className="overflow-y-auto flex-1">
          {query.length < 2 ? (
            <EmptyState />
          ) : grouped.length === 0 && !loading ? (
            <p className="text-center text-[var(--c-text-3)] text-sm py-10">No results for "{query}"</p>
          ) : (
            grouped.map(group => (
              <div key={group.category}>
                <GroupHeader label={group.category} />
                {group.items.map(item => {
                  const idx = flatIdx++
                  return (
                    <ResultItem
                      key={item.id ?? item.url + item.label}
                      item={item}
                      active={cursor === idx}
                      onClick={() => go(item)}
                    />
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-[var(--c-border)] flex items-center gap-4 text-[10px] text-[var(--c-text-3)]">
          <span><kbd className="font-mono bg-[var(--c-surface-2)] px-1 py-0.5 rounded text-[10px]">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono bg-[var(--c-surface-2)] px-1 py-0.5 rounded text-[10px]">↵</kbd> open</span>
          <span><kbd className="font-mono bg-[var(--c-surface-2)] px-1 py-0.5 rounded text-[10px]">esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}

// ── Empty / hint state ────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="px-4 py-6">
      <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-3">Jump to</p>
      <div className="grid grid-cols-2 gap-1">
        {NAV_ITEMS.slice(0, 6).map(item => {
          const Icon = item.icon
          return (
            <div key={item.url} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-[var(--c-text-2)]">
              <Icon size={13} className="text-[var(--c-text-3)]" />
              <span className="truncate">{item.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildGrouped(query, apiResult) {
  if (query.length < 2) return []
  const lq = query.toLowerCase()
  const groups = []

  // Pages
  const pages = NAV_ITEMS.filter(n => n.label.toLowerCase().includes(lq))
  if (pages.length) groups.push({ category: 'Pages', items: pages.map(n => ({ ...n, id: n.url })) })

  // Agents
  const agents = buildAgentItems(query)
  if (agents.length) groups.push({ category: 'Agents', items: agents })

  // Shoots
  const shoots = (apiResult?.shoots ?? []).map(s => ({
    id:       s.id,
    label:    s.name,
    sub:      s.month,
    url:      s.url,
    icon:     FolderOpen,
    category: 'Photoshoots',
  }))
  if (shoots.length) groups.push({ category: 'Photoshoots', items: shoots })

  // Images
  const images = (apiResult?.images ?? []).map(img => ({
    id:       img.filename,
    label:    img.filename,
    sub:      `${img.shoot} · ${img.status}`,
    url:      img.url,
    icon:     Image,
    badge:    img.status,
    category: 'Images',
  }))
  if (images.length) groups.push({ category: 'Images', items: images })

  // Posts
  const posts = (apiResult?.posts ?? []).map(p => ({
    id:       String(p.slot),
    label:    p.caption || `Post ${p.slot}`,
    sub:      `${p.date}  ·  ${p.type}`,
    url:      p.url,
    icon:     FileText,
    category: 'Posts',
  }))
  if (posts.length) groups.push({ category: 'Posts', items: posts })

  return groups
}

function buildResultList(query, apiResult) {
  return buildGrouped(query, apiResult).flatMap(g => g.items)
}
