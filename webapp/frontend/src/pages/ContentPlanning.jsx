import { useEffect, useState, useCallback, useRef } from 'react'
import { X, ChevronLeft, ChevronRight, CalendarDays, Layers, Image as ImageIcon, List, LayoutGrid, Pencil, Check, X as XIcon, MoreHorizontal, Trash2, CheckSquare, Square } from 'lucide-react'
import { api } from '../lib/api'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../lib/toast'

// ── Status config ────────────────────────────────────────────────────────────

const STATUS = {
  scheduled: { label: 'Scheduled', cls: 'bg-blue-500/15 text-blue-400 border border-blue-500/30' },
  published:  { label: 'Published', cls: 'bg-green-500/15 text-green-400 border border-green-500/30' },
  pending:    { label: 'Pending',   cls: 'bg-[var(--c-surface-3)] text-[var(--c-text-2)] border border-[var(--c-border-2)]' },
}

const STATUS_DOT = {
  scheduled: 'bg-blue-400',
  published:  'bg-green-400',
  pending:    'bg-gray-600',
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

// ── Helpers ───────────────────────────────────────────────────────────────────

function getPostMonths(posts) {
  const seen = new Set()
  for (const post of posts) {
    if (post.date) seen.add(post.date.slice(0, 7))
  }
  return Array.from(seen).sort().map(key => {
    const [y, m] = key.split('-').map(Number)
    const label  = new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    return { key, label, year: y, month: m - 1 }
  })
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ContentPlanning() {
  const { addToast } = useToast()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [active,  setActive]  = useState(null)   // open modal post
  const [activeEditing, setActiveEditing] = useState(false)  // open modal in edit mode
  const [view,    setView]    = useState('list')

  // Month filter
  const [filterMonth, setFilterMonth] = useState(null)

  // Multi-select
  const [selected,    setSelected]    = useState(new Set())  // Set of post IDs
  const [deleteConfirm, setDeleteConfirm] = useState(null)   // null | 'single' | 'multi'
  const [pendingDelete, setPendingDelete] = useState([])     // slots to delete

  // Calendar navigation
  const today = new Date()
  const [calYear,  setCalYear]  = useState(today.getFullYear())
  const [calMonth, setCalMonth] = useState(today.getMonth())

  useEffect(() => {
    api.contentPosts()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  const posts      = data?.posts ?? []
  const postMonths = getPostMonths(posts)
  const activeFilter = filterMonth ?? (postMonths[0]?.key ?? null)

  const visiblePosts = activeFilter
    ? posts.filter(p => p.date?.startsWith(activeFilter))
    : posts

  // ── Calendar helpers ──────────────────────────────────────────────────────
  const goToday   = () => { setCalYear(today.getFullYear()); setCalMonth(today.getMonth()) }
  const prevMonth = () => { if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11) } else setCalMonth(m => m - 1) }
  const nextMonth = () => { if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0) } else setCalMonth(m => m + 1) }
  const monthLabel = new Date(calYear, calMonth, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const handleFilterMonth = (key) => {
    setFilterMonth(key || null)
    setSelected(new Set())
    if (key) {
      const [y, m] = key.split('-').map(Number)
      setCalYear(y); setCalMonth(m - 1)
    } else {
      setCalYear(today.getFullYear()); setCalMonth(today.getMonth())
    }
  }

  // ── Selection helpers ─────────────────────────────────────────────────────
  const toggleSelect = (id) =>
    setSelected(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s })

  const toggleAll = () =>
    setSelected(selected.size === visiblePosts.length ? new Set() : new Set(visiblePosts.map(p => p.id)))

  const clearSelection = () => setSelected(new Set())

  // ── Delete helpers ────────────────────────────────────────────────────────
  const askDeletePosts = (slots) => {
    setPendingDelete(slots)
    setDeleteConfirm(slots.length === 1 ? 'single' : 'multi')
  }

  const confirmDelete = async () => {
    const slots = pendingDelete
    setDeleteConfirm(null)
    setPendingDelete([])
    try {
      await api.deletePosts(slots)
      setData(prev => ({
        ...prev,
        posts: prev.posts.filter(p => !slots.includes(p.slot)),
      }))
      setSelected(prev => {
        const s = new Set(prev)
        for (const post of posts) {
          if (slots.includes(post.slot)) s.delete(post.id)
        }
        return s
      })
      if (active && slots.includes(active.slot)) setActive(null)
      addToast('success', slots.length === 1 ? 'Post deleted' : `${slots.length} posts deleted`)
    } catch (e) {
      addToast('error', e.message || 'Failed to delete post(s)')
    }
  }

  // ── Post action from row menu ─────────────────────────────────────────────
  const handleRowAction = (post, action) => {
    if (action === 'edit') {
      setActive(post)
      setActiveEditing(true)
    } else if (action === 'delete') {
      askDeletePosts([post.slot])
    }
  }

  // ── Modal update callback ─────────────────────────────────────────────────
  const handleUpdate = (updated) => {
    setData(prev => ({
      ...prev,
      posts: prev.posts.map(p => p.id === updated.id ? { ...p, ...updated } : p),
    }))
    setActive(prev => ({ ...prev, ...updated }))
  }

  const openModal = (post) => { setActive(post); setActiveEditing(false) }

  return (
    <div className="p-4 sm:p-6 md:p-8">

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Workflow</p>
          <h1 className="text-2xl text-[var(--c-text-1)] font-semibold">Content Planning</h1>
          {data?.month_of && (
            <p className="text-[var(--c-text-3)] text-sm mt-1">{data.month_of} · {posts.length} posts</p>
          )}
        </div>

        {/* View toggle */}
        <div className="flex items-center gap-1 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-1">
          <ViewBtn icon={List}       label="List"     active={view === 'list'}     onClick={() => setView('list')} />
          <ViewBtn icon={LayoutGrid} label="Calendar" active={view === 'calendar'} onClick={() => setView('calendar')} />
        </div>
      </div>

      {/* Month filter dropdown + selection bar */}
      {posts.length > 0 && (
        <div className="flex items-center gap-3 mb-5 flex-wrap">
          {postMonths.length > 0 && (
            <div className="relative">
              <select
                value={activeFilter ?? ''}
                onChange={e => handleFilterMonth(e.target.value || null)}
                className="appearance-none bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg pl-3 pr-8 py-1.5 text-sm text-[var(--c-text-1)] focus:outline-none focus:border-[var(--c-border-2)] transition-colors cursor-pointer"
              >
                {postMonths.length > 1 && (
                  <option value="">All months ({posts.length})</option>
                )}
                {postMonths.map(entry => (
                  <option key={entry.key} value={entry.key}>
                    {entry.label} ({posts.filter(p => p.date?.startsWith(entry.key)).length})
                  </option>
                ))}
              </select>
              <ChevronRight size={12} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--c-text-4)] rotate-90" />
            </div>
          )}

          {/* Selection toolbar — shown when items are checked */}
          {selected.size > 0 && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-[var(--c-text-3)]">{selected.size} selected</span>
              <button
                onClick={() => {
                  const slots = posts.filter(p => selected.has(p.id)).map(p => p.slot)
                  askDeletePosts(slots)
                }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-red-400 hover:bg-red-500/10 border border-red-500/20 transition-colors"
              >
                <Trash2 size={12} /> Delete selected
              </button>
              <button onClick={clearSelection} className="text-xs text-[var(--c-text-3)] hover:text-[var(--c-text-1)] transition-colors px-2">
                Clear
              </button>
            </div>
          )}
        </div>
      )}

      {posts.length === 0 ? (
        <Empty />
      ) : view === 'list' ? (
        <div className="space-y-2">
          {/* Select-all row */}
          {visiblePosts.length > 1 && (
            <div className="flex items-center gap-3 px-4 py-1">
              <button
                onClick={toggleAll}
                className="flex items-center gap-2 text-xs text-[var(--c-text-3)] hover:text-[var(--c-text-1)] transition-colors"
              >
                {selected.size === visiblePosts.length
                  ? <CheckSquare size={14} className="text-blue-400" />
                  : <Square size={14} />
                }
                {selected.size === visiblePosts.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
          )}
          {visiblePosts.map(post => (
            <PostRow
              key={post.id}
              post={post}
              selected={selected.has(post.id)}
              anySelected={selected.size > 0}
              onToggle={() => toggleSelect(post.id)}
              onClick={() => openModal(post)}
              onAction={(action) => handleRowAction(post, action)}
            />
          ))}
          {visiblePosts.length === 0 && (
            <p className="text-[var(--c-text-4)] text-sm py-6 text-center">No posts for this month.</p>
          )}
        </div>
      ) : (
        <CalendarView
          posts={posts}
          year={calYear}
          month={calMonth}
          monthLabel={monthLabel}
          onPrev={prevMonth}
          onNext={nextMonth}
          onToday={goToday}
          onPostClick={openModal}
        />
      )}

      {active && (
        <PostModal
          post={active}
          posts={visiblePosts.length > 0 ? visiblePosts : posts}
          initialEditing={activeEditing}
          onNavigate={(p) => { setActive(p); setActiveEditing(false) }}
          onClose={() => setActive(null)}
          onUpdate={handleUpdate}
          onDelete={(post) => askDeletePosts([post.slot])}
        />
      )}

      <ConfirmDialog
        open={!!deleteConfirm}
        title={deleteConfirm === 'multi' ? `Delete ${pendingDelete.length} posts?` : 'Delete post?'}
        message={
          deleteConfirm === 'multi'
            ? `This will permanently remove ${pendingDelete.length} posts from the content plan. This cannot be undone.`
            : 'This will permanently remove the post from the content plan. This cannot be undone.'
        }
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => { setDeleteConfirm(null); setPendingDelete([]) }}
      />

    </div>
  )
}

// ── View toggle button ────────────────────────────────────────────────────────

function ViewBtn({ icon: Icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded transition-colors ${
        active ? 'bg-[var(--c-surface-3)] text-[var(--c-text-1)]' : 'text-[var(--c-text-3)] hover:text-[var(--c-text-1b)]'
      }`}
    >
      <Icon size={13} /> {label}
    </button>
  )
}

// ── Post row ──────────────────────────────────────────────────────────────────

function PostRow({ post, selected, anySelected, onToggle, onClick, onAction }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const badge = STATUS[post.status] ?? STATUS.pending

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  return (
    <div
      className={`group flex items-center gap-3 bg-[var(--c-surface)] border rounded-lg p-3 transition-colors cursor-pointer ${
        selected
          ? 'border-blue-500 ring-1 ring-blue-500/30'
          : 'border-[var(--c-border)] hover:border-[var(--c-border-2)] hover:bg-[var(--c-surface-2)]'
      }`}
    >
      {/* Checkbox */}
      <button
        onClick={e => { e.stopPropagation(); onToggle() }}
        className={`shrink-0 w-5 h-5 rounded flex items-center justify-center transition-opacity ${
          selected || anySelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        }`}
      >
        {selected
          ? <CheckSquare size={16} className="text-blue-400" />
          : <Square size={16} className="text-[var(--c-text-4)]" />
        }
      </button>

      {/* Main content — clickable area */}
      <div className="flex items-center gap-4 flex-1 min-w-0" onClick={onClick}>
        {/* Cover image */}
        <div className="shrink-0 relative w-14 h-14 rounded-md overflow-hidden bg-[var(--c-surface-2)]">
          {post.cover_path ? (
            <img src={api.imageUrl(post.cover_path)} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <ImageIcon size={18} className="text-[var(--c-text-4)]" />
            </div>
          )}
          {post.type === 'carousel' && post.images?.length > 1 && (
            <div className="absolute bottom-1 right-1 bg-black/70 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded leading-none">
              +{post.images.length - 1}
            </div>
          )}
        </div>

        {/* Caption + hashtags */}
        <div className="flex-1 min-w-0">
          <p className="text-[var(--c-text-1)] text-sm leading-snug line-clamp-2 mb-1">
            {post.caption || <span className="text-[var(--c-text-4)] italic">No caption</span>}
          </p>
          {post.hashtags?.length > 0 && (
            <p className="text-[var(--c-text-3)] text-xs truncate">
              {post.hashtags.slice(0, 5).join(' ')}
              {post.hashtags.length > 5 && <span className="text-[var(--c-text-4)]"> +{post.hashtags.length - 5} more</span>}
            </p>
          )}
        </div>

        {/* Meta */}
        <div className="shrink-0 flex flex-col items-end gap-1.5 text-right">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>
            {badge.label}
          </span>
          {post.scheduled_display && (
            <span className="text-[var(--c-text-3)] text-xs flex items-center gap-1">
              <CalendarDays size={11} />
              {post.scheduled_display}
            </span>
          )}
          <span className="text-[var(--c-text-4)] text-xs flex items-center gap-1">
            {post.type === 'carousel'
              ? <><Layers size={11} /> {post.images?.length} slides</>
              : <><ImageIcon size={11} /> Single</>
            }
          </span>
        </div>
      </div>

      {/* Three-dot menu */}
      <div className="relative shrink-0" ref={menuRef}>
        <button
          onClick={e => { e.stopPropagation(); setMenuOpen(v => !v) }}
          className={`w-7 h-7 rounded flex items-center justify-center text-[var(--c-text-4)] hover:text-[var(--c-text-1b)] hover:bg-[var(--c-surface-3)] transition-colors ${
            menuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}
        >
          <MoreHorizontal size={15} />
        </button>
        {menuOpen && (
          <PostMenu onAction={(action) => { setMenuOpen(false); onAction(action) }} />
        )}
      </div>
    </div>
  )
}

function PostMenu({ onAction }) {
  return (
    <div className="absolute right-0 top-full mt-1 w-40 bg-[var(--c-surface-2)] border border-[var(--c-border-2)] rounded-lg shadow-xl overflow-hidden z-[60] py-1">
      <MenuItem icon={Pencil} label="Edit"   onClick={() => onAction('edit')} />
      <div className="my-1 border-t border-[var(--c-border-2)]" />
      <MenuItem icon={Trash2} label="Delete" onClick={() => onAction('delete')} color="red" />
    </div>
  )
}

function MenuItem({ icon: Icon, label, onClick, color }) {
  const cls = { red: 'text-red-400' }[color] ?? 'text-[var(--c-text-1b)]'
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-[var(--c-surface-3)] transition-colors ${cls}`}
    >
      <Icon size={14} /> {label}
    </button>
  )
}

// ── Calendar view ─────────────────────────────────────────────────────────────

function CalendarView({ posts, year, month, monthLabel, onPrev, onNext, onToday, onPostClick }) {
  const today = new Date()

  const postsByDate = {}
  for (const post of posts) {
    if (post.date) {
      postsByDate[post.date] = postsByDate[post.date] || []
      postsByDate[post.date].push(post)
    }
  }

  const firstDay    = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  const isToday = (d) =>
    d && today.getFullYear() === year && today.getMonth() === month && today.getDate() === d

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button onClick={onPrev} className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors">
            <ChevronLeft size={16} />
          </button>
          <span className="text-[var(--c-text-1)] font-medium min-w-[160px] text-center">{monthLabel}</span>
          <button onClick={onNext} className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors">
            <ChevronRight size={16} />
          </button>
        </div>
        <button onClick={onToday} className="text-xs font-medium px-3 py-1.5 rounded-lg border border-[var(--c-border-2)] text-[var(--c-text-2)] hover:text-[var(--c-text-1)] transition-colors">
          Today
        </button>
      </div>

      <div className="overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0">
        <div className="min-w-[560px]">
          <div className="grid grid-cols-7 mb-1">
            {DAYS.map(d => (
              <div key={d} className="text-center text-xs text-[var(--c-text-4)] font-medium py-2">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-px bg-[var(--c-border)] border border-[var(--c-border)] rounded-xl overflow-hidden">
            {cells.map((day, i) => {
              const dateStr  = day ? `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}` : null
              const dayPosts = dateStr ? (postsByDate[dateStr] ?? []) : []
              return (
                <div key={i} className={`bg-[var(--c-page)] min-h-[110px] p-2 flex flex-col ${!day ? 'opacity-30' : ''}`}>
                  {day && (
                    <>
                      <div className={`text-xs font-medium w-6 h-6 flex items-center justify-center rounded-full mb-1 self-start ${
                        isToday(day) ? 'bg-blue-500 text-white' : 'text-[var(--c-text-3)]'
                      }`}>
                        {day}
                      </div>
                      <div className="flex flex-col gap-1 flex-1">
                        {dayPosts.map(post => (
                          <CalendarPost key={post.id} post={post} onClick={() => onPostClick(post)} />
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

function CalendarPost({ post, onClick }) {
  const dotCls = STATUS_DOT[post.status] ?? STATUS_DOT.pending
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-center gap-1.5 bg-[var(--c-surface)] hover:bg-[var(--c-surface-2)] border border-[var(--c-border)] hover:border-[var(--c-border-2)] rounded px-1.5 py-1 transition-colors group"
    >
      <div className="shrink-0 relative w-7 h-7 rounded overflow-hidden bg-[var(--c-surface-2)]">
        {post.cover_path ? (
          <img src={api.imageUrl(post.cover_path)} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ImageIcon size={10} className="text-[var(--c-text-4)]" />
          </div>
        )}
        {post.type === 'carousel' && post.images?.length > 1 && (
          <div className="absolute bottom-0 right-0 bg-black/70 text-white text-[8px] font-bold px-0.5 leading-tight">
            +{post.images.length - 1}
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1 mb-0.5">
          <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotCls}`} />
          <span className="text-[var(--c-text-2)] text-[10px] font-medium truncate">{post.time || '—'}</span>
        </div>
        <p className="text-[var(--c-text-1b)] text-[10px] leading-tight truncate">{post.caption || '…'}</p>
      </div>
    </button>
  )
}

// ── Post modal ────────────────────────────────────────────────────────────────

function PostModal({ post, posts, initialEditing, onNavigate, onClose, onUpdate, onDelete }) {
  const idx     = posts.findIndex(p => p.id === post.id)
  const hasPrev = idx > 0
  const hasNext = idx < posts.length - 1

  const [editing,      setEditing]      = useState(initialEditing ?? false)
  const [editCaption,  setEditCaption]  = useState('')
  const [editHashtags, setEditHashtags] = useState('')
  const [saving,       setSaving]       = useState(false)
  const [saveError,    setSaveError]    = useState(null)

  // Sync editing mode when initialEditing changes (e.g. opened via Edit menu)
  useEffect(() => { if (initialEditing) startEdit() }, [])   // eslint-disable-line

  const startEdit = () => {
    setEditCaption(post.caption || '')
    setEditHashtags((post.hashtags ?? []).join(' '))
    setSaveError(null)
    setEditing(true)
  }

  const cancelEdit = () => { setEditing(false); setSaveError(null) }

  const saveEdit = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      await api.updatePost(post.slot, { caption: editCaption, hashtags: editHashtags })
      const newHashtags = editHashtags.split(/\s+/).map(t => t.trim()).filter(Boolean)
      onUpdate({ id: post.id, caption: editCaption, hashtags: newHashtags })
      setEditing(false)
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const prev = useCallback(() => { if (hasPrev) { setEditing(false); onNavigate(posts[idx - 1]) } }, [idx, hasPrev, posts, onNavigate])
  const next = useCallback(() => { if (hasNext) { setEditing(false); onNavigate(posts[idx + 1]) } }, [idx, hasNext, posts, onNavigate])

  useEffect(() => {
    const handler = (e) => {
      if (editing) return
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose, editing])

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const badge = STATUS[post.status] ?? STATUS.pending

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/90">
      <div className="absolute inset-0 -z-10" onClick={onClose} />

      <button onClick={prev} disabled={!hasPrev}
        className="absolute left-4 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-gray-900/80 hover:bg-gray-700 disabled:opacity-20 disabled:cursor-default flex items-center justify-center transition-colors z-10">
        <ChevronLeft size={22} className="text-white" />
      </button>
      <button onClick={next} disabled={!hasNext}
        className="absolute right-4 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-gray-900/80 hover:bg-gray-700 disabled:opacity-20 disabled:cursor-default flex items-center justify-center transition-colors z-10">
        <ChevronRight size={22} className="text-white" />
      </button>
      <button onClick={onClose}
        className="absolute top-5 right-5 w-10 h-10 rounded-full bg-gray-900/80 hover:bg-gray-700 flex items-center justify-center transition-colors z-10">
        <X size={18} className="text-white" />
      </button>
      <div className="absolute top-5 left-5 text-[var(--c-text-3)] text-sm z-10">{idx + 1} / {posts.length}</div>

      <div className="relative w-full max-w-4xl max-h-[90vh] mx-16 flex flex-col lg:flex-row bg-[var(--c-surface)] border border-[var(--c-border)] rounded-2xl overflow-hidden shadow-2xl">

        <div className="lg:w-[45%] shrink-0 bg-[var(--c-page)]">
          <ImagePanel images={post.images} />
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">

          {/* Badges + edit/delete controls */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${badge.cls}`}>
              {badge.label}
            </span>
            {post.type === 'carousel' && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/30 flex items-center gap-1">
                <Layers size={11} /> Carousel · {post.images?.length} slides
              </span>
            )}
            <div className="ml-auto flex items-center gap-1.5">
              {editing ? (
                <>
                  <button onClick={cancelEdit} className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors">
                    <XIcon size={12} /> Cancel
                  </button>
                  <button onClick={saveEdit} disabled={saving}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors">
                    <Check size={12} /> {saving ? 'Saving…' : 'Save'}
                  </button>
                </>
              ) : (
                <>
                  <button onClick={startEdit}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] border border-[var(--c-border)] transition-colors">
                    <Pencil size={11} /> Edit
                  </button>
                  <button onClick={() => onDelete(post)}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-red-400 hover:bg-red-500/10 border border-red-500/20 transition-colors">
                    <Trash2 size={11} /> Delete
                  </button>
                </>
              )}
            </div>
          </div>

          {saveError && (
            <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{saveError}</p>
          )}

          {post.scheduled_display && (
            <div className="flex items-center gap-2 text-[var(--c-text-2)] text-sm">
              <CalendarDays size={14} />
              {post.scheduled_display}
            </div>
          )}

          {post.pillar && (
            <div>
              <Label>Content pillar</Label>
              <p className="text-[var(--c-text-1b)] text-sm">{post.pillar}</p>
            </div>
          )}

          <div>
            <Label>Caption</Label>
            {editing ? (
              <textarea
                value={editCaption}
                onChange={e => setEditCaption(e.target.value)}
                rows={6}
                className="w-full bg-[var(--c-surface-2)] border border-[var(--c-border-2)] focus:border-blue-500 rounded-lg px-3 py-2 text-sm text-[var(--c-text-1)] leading-relaxed resize-y outline-none transition-colors"
              />
            ) : (
              <p className="text-[var(--c-text-1)] text-sm leading-relaxed whitespace-pre-line">
                {post.caption || <span className="text-[var(--c-text-4)] italic">No caption yet</span>}
              </p>
            )}
          </div>

          <div>
            <Label>Hashtags {!editing && post.hashtags?.length > 0 && `(${post.hashtags.length})`}</Label>
            {editing ? (
              <input
                value={editHashtags}
                onChange={e => setEditHashtags(e.target.value)}
                placeholder="#hashtag1 #hashtag2 …"
                className="w-full bg-[var(--c-surface-2)] border border-[var(--c-border-2)] focus:border-blue-500 rounded-lg px-3 py-2 text-sm text-[var(--c-text-1)] outline-none transition-colors"
              />
            ) : post.hashtags?.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 mt-1">
                {post.hashtags.map(tag => (
                  <span key={tag} className="text-xs bg-[var(--c-surface-2)] text-[var(--c-text-2)] px-2 py-0.5 rounded">{tag}</span>
                ))}
              </div>
            ) : (
              <p className="text-[var(--c-text-4)] text-sm italic">No hashtags yet</p>
            )}
          </div>

          {post.type === 'carousel' && post.images?.some(i => i.mood || i.details) && (
            <div>
              <Label>Slide details</Label>
              <div className="space-y-3 mt-1">
                {post.images.map((img, i) =>
                  (img.mood || img.details) ? (
                    <div key={img.ref_code || i} className="text-xs bg-[var(--c-surface-2)] rounded-lg p-3 space-y-1">
                      <div className="text-[var(--c-text-3)] font-medium">Slide {i + 1} · {img.ref_code?.split('-').slice(-2).join('-')}</div>
                      {img.mood    && <div className="text-[var(--c-text-2)]"><span className="text-[var(--c-text-4)]">Mood: </span>{img.mood}</div>}
                      {img.details && <div className="text-[var(--c-text-2)] leading-relaxed">{img.details}</div>}
                    </div>
                  ) : null
                )}
              </div>
            </div>
          )}

          {post.type === 'single' && (post.mood || post.details || post.copy_angle) && (
            <div className="space-y-3">
              {post.mood      && <div><Label>Mood</Label><p className="text-[var(--c-text-1b)] text-sm">{post.mood}</p></div>}
              {post.details   && <div><Label>Scene</Label><p className="text-[var(--c-text-1b)] text-sm leading-relaxed">{post.details}</p></div>}
              {post.copy_angle && <div><Label>Copy angle</Label><p className="text-[var(--c-text-1b)] text-sm leading-relaxed">{post.copy_angle}</p></div>}
            </div>
          )}

        </div>
      </div>
    </div>
  )
}

// ── Image panel ───────────────────────────────────────────────────────────────

function ImagePanel({ images = [] }) {
  const [current, setCurrent] = useState(0)
  const img = images[current]

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 flex items-center justify-center p-4 min-h-[260px]">
        {img?.path ? (
          <img key={img.path} src={api.imageUrl(img.path)} alt={img.filename}
            className="max-w-full max-h-[55vh] object-contain rounded-lg" />
        ) : (
          <div className="flex flex-col items-center gap-2 text-[var(--c-text-4)]">
            <ImageIcon size={32} /><span className="text-xs">Image not found</span>
          </div>
        )}
      </div>
      {images.length > 1 && (
        <div className="flex gap-2 p-3 overflow-x-auto border-t border-[var(--c-border)]">
          {images.map((img, i) => (
            <button key={img.ref_code || i} onClick={() => setCurrent(i)}
              className={`shrink-0 w-12 h-12 rounded overflow-hidden border-2 transition-colors ${
                i === current ? 'border-blue-500' : 'border-transparent hover:border-[var(--c-border-2)]'
              }`}>
              {img.path
                ? <img src={api.imageUrl(img.path)} alt="" className="w-full h-full object-cover" />
                : <div className="w-full h-full bg-[var(--c-surface-2)]" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function Label({ children }) {
  return <div className="text-[var(--c-text-3)] text-xs uppercase tracking-wider mb-1">{children}</div>
}

function Empty() {
  return (
    <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-12 flex flex-col items-center justify-center text-center">
      <div className="w-12 h-12 rounded-full bg-[var(--c-surface-2)] flex items-center justify-center mb-4">
        <CalendarDays size={20} className="text-[var(--c-text-4)]" />
      </div>
      <div className="text-[var(--c-text-1)] font-medium mb-2">No content plans yet</div>
      <div className="text-[var(--c-text-3)] text-sm max-w-sm">
        Posts will appear here once the Content Planner agent runs.
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <div className="p-8 flex items-center justify-center h-64">
      <div className="text-[var(--c-text-3)] text-sm">Loading…</div>
    </div>
  )
}
