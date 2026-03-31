import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api'

const LEVELS = ['ALL', 'SUCCESS', 'ERROR', 'WARN', 'INFO']

const LEVEL_CLS = {
  SUCCESS: 'text-green-400',
  ERROR:   'text-red-400',
  WARN:    'text-yellow-400',
  INFO:    'text-[#8b8fa8]',
}

const SRC_CLS = {
  monitor:      'text-blue-400',
  pipeline:     'text-purple-400',
  crew:         'text-cyan-400',
  image_gen:    'text-pink-400',
  photo_editor: 'text-orange-400',
}

function fmtTs(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    return `${hh}:${mm}:${ss}`
  } catch {
    return ts.slice(11, 19) || ''
  }
}

export default function Logs() {
  const [entries, setEntries]     = useState([])
  const [isLive, setIsLive]       = useState(false)
  const [filter, setFilter]       = useState('ALL')
  const [autoScroll, setAutoScroll] = useState(true)
  const [loading, setLoading]     = useState(true)
  const bottomRef = useRef(null)
  const containerRef = useRef(null)

  // Load log entries
  const load = async () => {
    try {
      const data = await api.logs(1000)
      setEntries(data.entries || [])
      setIsLive(data.is_live || false)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // Poll every 3s when live
  useEffect(() => {
    if (!isLive) return
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [isLive])

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [entries, autoScroll])

  // Detect if user scrolled away from bottom
  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    setAutoScroll(atBottom)
  }

  const visible = filter === 'ALL'
    ? entries
    : entries.filter(e => e.level === filter)

  return (
    <div className="flex flex-col h-full relative">

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--c-border)] shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[var(--c-text-1)] font-semibold text-sm">Run Log</h1>
          {isLive && (
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              Live
            </span>
          )}
          {!loading && !isLive && entries.length === 0 && (
            <span className="text-xs text-[var(--c-text-3)]">No log yet — start a run to see output here</span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {LEVELS.map(l => (
            <button
              key={l}
              onClick={() => setFilter(l)}
              className={[
                'px-2 py-0.5 rounded text-xs font-mono transition-colors',
                filter === l
                  ? 'bg-[var(--c-surface-2)] text-[var(--c-text-1)]'
                  : 'text-[var(--c-text-3)] hover:text-[var(--c-text-2)]',
              ].join(' ')}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Log body */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-6 py-4 font-mono text-xs leading-5 bg-[#0d0f1a]"
      >
        {loading && (
          <span className="text-[var(--c-text-3)]">Loading…</span>
        )}

        {!loading && visible.length === 0 && (
          <span className="text-[var(--c-text-3)]">No entries match filter.</span>
        )}

        {visible.map((e, i) => {
          const ts       = fmtTs(e.ts)
          const levelCls = LEVEL_CLS[e.level] || 'text-[#8b8fa8]'
          const srcCls   = SRC_CLS[e.src]     || 'text-[var(--c-text-3)]'
          return (
            <div key={i} className="flex gap-3 hover:bg-white/[0.02] px-1 rounded">
              <span className="text-[#4a4e6a] w-16 shrink-0">{ts}</span>
              <span className={`w-14 shrink-0 ${levelCls}`}>{e.level}</span>
              <span className={`w-20 shrink-0 ${srcCls}`}>{e.src}</span>
              <span className="text-[#c8cce8] break-all whitespace-pre-wrap">{e.msg}</span>
            </div>
          )
        })}

        <div ref={bottomRef} />
      </div>

      {/* Scroll-to-bottom hint */}
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true)
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
          }}
          className="absolute bottom-8 right-8 bg-[var(--c-surface-2)] border border-[var(--c-border)] text-xs text-[var(--c-text-2)] px-3 py-1.5 rounded-full shadow hover:text-[var(--c-text-1)] transition-colors"
        >
          ↓ scroll to bottom
        </button>
      )}
    </div>
  )
}
