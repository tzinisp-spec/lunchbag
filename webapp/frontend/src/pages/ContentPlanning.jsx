import { useEffect, useState, useCallback } from 'react'
import { X, ChevronLeft, ChevronRight, CalendarDays, Layers, Image as ImageIcon, List, LayoutGrid } from 'lucide-react'
import { api } from '../lib/api'

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

// ── Main page ────────────────────────────────────────────────────────────────

export default function ContentPlanning() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [active,  setActive]  = useState(null)
  const [view,    setView]    = useState('list')   // 'list' | 'calendar'

  // calendar navigation — start on today's month
  const today = new Date()
  const [calYear,  setCalYear]  = useState(today.getFullYear())
  const [calMonth, setCalMonth] = useState(today.getMonth())   // 0-based

  useEffect(() => {
    api.contentPosts()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  const posts = data?.posts ?? []

  const goToday = () => { setCalYear(today.getFullYear()); setCalMonth(today.getMonth()) }

  const prevMonth = () => {
    if (calMonth === 0) { setCalYear(y => y - 1); setCalMonth(11) }
    else setCalMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (calMonth === 11) { setCalYear(y => y + 1); setCalMonth(0) }
    else setCalMonth(m => m + 1)
  }

  const monthLabel = new Date(calYear, calMonth, 1)
    .toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

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

      {posts.length === 0 ? (
        <Empty />
      ) : view === 'list' ? (
        <div className="space-y-2">
          {posts.map(post => (
            <PostRow key={post.id} post={post} onClick={() => setActive(post)} />
          ))}
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
          onPostClick={setActive}
        />
      )}

      {active && (
        <PostModal
          post={active}
          posts={posts}
          onNavigate={setActive}
          onClose={() => setActive(null)}
        />
      )}

    </div>
  )
}

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

// ── Calendar view ─────────────────────────────────────────────────────────────

function CalendarView({ posts, year, month, monthLabel, onPrev, onNext, onToday, onPostClick }) {
  const today = new Date()

  // Build day → posts map
  const postsByDate = {}
  for (const post of posts) {
    if (post.date) {
      postsByDate[post.date] = postsByDate[post.date] || []
      postsByDate[post.date].push(post)
    }
  }

  // Build grid: pad start with nulls, then day numbers
  const firstDay = new Date(year, month, 1).getDay()   // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
  // pad end to complete last row
  while (cells.length % 7 !== 0) cells.push(null)

  const isToday = (d) =>
    d && today.getFullYear() === year && today.getMonth() === month && today.getDate() === d

  return (
    <div>
      {/* Calendar toolbar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={onPrev}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-[var(--c-text-1)] font-medium min-w-[160px] text-center">{monthLabel}</span>
          <button
            onClick={onNext}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)] transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <button
          onClick={onToday}
          className="text-xs font-medium px-3 py-1.5 rounded-lg border border-[var(--c-border-2)] text-[var(--c-text-2)] hover:text-[var(--c-text-1)] hover:border-[var(--c-border-2)] transition-colors"
        >
          Today
        </button>
      </div>

      {/* Day-of-week headers + grid — horizontal scroll on mobile */}
      <div className="overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0">
        <div className="min-w-[560px]">
        <div className="grid grid-cols-7 mb-1">
          {DAYS.map(d => (
            <div key={d} className="text-center text-xs text-[var(--c-text-4)] font-medium py-2">{d}</div>
          ))}
        </div>

      {/* Grid */}
      <div className="grid grid-cols-7 gap-px bg-[var(--c-border)] border border-[var(--c-border)] rounded-xl overflow-hidden">
        {cells.map((day, i) => {
          const dateStr = day ? `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}` : null
          const dayPosts = dateStr ? (postsByDate[dateStr] ?? []) : []

          return (
            <div
              key={i}
              className={`bg-[var(--c-page)] min-h-[110px] p-2 flex flex-col ${!day ? 'opacity-30' : ''}`}
            >
              {day && (
                <>
                  {/* Date number */}
                  <div className={`text-xs font-medium w-6 h-6 flex items-center justify-center rounded-full mb-1 self-start ${
                    isToday(day)
                      ? 'bg-blue-500 text-white'
                      : 'text-[var(--c-text-3)]'
                  }`}>
                    {day}
                  </div>

                  {/* Posts */}
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
      </div>{/* min-w wrapper */}
      </div>{/* overflow-x-auto */}
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
      {/* Thumbnail */}
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

      {/* Time + status dot */}
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

// ── Post row ─────────────────────────────────────────────────────────────────

function PostRow({ post, onClick }) {
  const badge = STATUS[post.status] ?? STATUS.pending

  return (
    <div
      onClick={onClick}
      className="flex items-center gap-4 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-4 hover:bg-[var(--c-surface-2)] hover:border-[var(--c-border-2)] transition-colors cursor-pointer"
    >
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
  )
}

// ── Post modal ────────────────────────────────────────────────────────────────

function PostModal({ post, posts, onNavigate, onClose }) {
  const idx     = posts.findIndex(p => p.id === post.id)
  const hasPrev = idx > 0
  const hasNext = idx < posts.length - 1

  const prev = useCallback(() => { if (hasPrev) onNavigate(posts[idx - 1]) }, [idx, hasPrev, posts, onNavigate])
  const next = useCallback(() => { if (hasNext) onNavigate(posts[idx + 1]) }, [idx, hasNext, posts, onNavigate])

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowLeft')  prev()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'Escape')     onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose])

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

          <div className="flex items-center gap-3 flex-wrap">
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${badge.cls}`}>
              {badge.label}
            </span>
            {post.type === 'carousel' && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/30 flex items-center gap-1">
                <Layers size={11} /> Carousel · {post.images?.length} slides
              </span>
            )}
          </div>

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
            <p className="text-[var(--c-text-1)] text-sm leading-relaxed whitespace-pre-line">
              {post.caption || <span className="text-[var(--c-text-4)] italic">No caption yet</span>}
            </p>
          </div>

          {post.hashtags?.length > 0 && (
            <div>
              <Label>Hashtags ({post.hashtags.length})</Label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {post.hashtags.map(tag => (
                  <span key={tag} className="text-xs bg-[var(--c-surface-2)] text-[var(--c-text-2)] px-2 py-0.5 rounded">{tag}</span>
                ))}
              </div>
            </div>
          )}

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
              {post.mood && (
                <div><Label>Mood</Label><p className="text-[var(--c-text-1b)] text-sm">{post.mood}</p></div>
              )}
              {post.details && (
                <div><Label>Scene</Label><p className="text-[var(--c-text-1b)] text-sm leading-relaxed">{post.details}</p></div>
              )}
              {post.copy_angle && (
                <div><Label>Copy angle</Label><p className="text-[var(--c-text-1b)] text-sm leading-relaxed">{post.copy_angle}</p></div>
              )}
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

// ── Helpers ───────────────────────────────────────────────────────────────────

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
