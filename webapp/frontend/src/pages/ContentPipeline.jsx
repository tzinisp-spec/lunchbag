import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, Square, Pause, RotateCcw, ChevronDown, ChevronUp, CheckCircle, ArrowRight, AlertTriangle, Settings } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../lib/toast'
import ConfirmDialog from '../components/ConfirmDialog'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function getDefaultPlanningMonth() {
  const today = new Date()
  let month = today.getMonth() + 1   // 0-indexed → next month index (1-12)
  let year  = today.getFullYear()
  if (month > 12) { month = 1; year += 1 }
  return { month, year }
}

function fmtElapsed(sec) {
  if (!sec) return '0s'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}'`
  const h = Math.floor(m / 60), r = m % 60
  return r ? `${h}h ${r}'` : `${h}h`
}

const STATE_LABEL = { idle: 'Idle', running: 'Running', paused: 'Paused', stopping: 'Stopping' }
const STATE_CLS   = {
  idle:     'bg-[var(--c-surface-2)] text-[var(--c-text-3)]',
  running:  'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  paused:   'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30',
  stopping: 'bg-red-500/15 text-red-400 border border-red-500/30',
}

const STEPS = [
  { id: 'copywriter',       label: 'Copywriter' },
  { id: 'content_planner',  label: 'Content Planner' },
  { id: 'review_generator', label: 'Review Generator' },
  { id: 'sprint_report_p2', label: 'Content Plan Report' },
]

export default function ContentPipeline() {
  const { addToast } = useToast()
  const navigate = useNavigate()

  // Run state
  const [runStatus,   setRunStatus]   = useState(null)
  const [elapsed,     setElapsed]     = useState(0)
  const elapsedBase = useRef(null)

  // Shoot selection
  const [shoots,         setShoot]         = useState([])
  const [selectedShoot,  setSelectedShoot] = useState('')

  // Planning month
  const def = getDefaultPlanningMonth()
  const [planMonth, setPlanMonth] = useState(def.month)
  const [planYear,  setPlanYear]  = useState(def.year)

  // Completion — ephemeral, cleared on navigate away
  const [completed,     setCompleted]     = useState(null)  // { month, year } when done
  const prevStateRef    = useRef('idle')
  const runningPlanRef  = useRef(null)   // captures month/year at start time

  // Already-planned months + overwrite confirmation
  const [plannedMonths,   setPlannedMonths]   = useState(new Set())   // Set of "YYYY-MM"
  const [confirmOverwrite, setConfirmOverwrite] = useState(false)

  // Config accordion
  const [configOpen, setConfigOpen] = useState(true)

  // Log terminal
  const [lines, setLines] = useState([])
  const logRef  = useRef(null)
  const esRef   = useRef(null)

  const state    = runStatus?.state ?? 'idle'
  const isActive = state === 'running' || state === 'paused'

  // Collapse and lock config when a run starts
  useEffect(() => {
    if (isActive) setConfigOpen(false)
  }, [isActive])

  // ── Poll run status ──────────────────────────────────────────────────────
  const fetchStatus = useCallback(() => {
    api.p2Status()
      .then(s => {
        setRunStatus(s)
        if (s.state !== 'idle' && s.started_at) {
          elapsedBase.current = { started_at: s.started_at }
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchStatus()
    const id = setInterval(fetchStatus, 4000)
    return () => clearInterval(id)
  }, [fetchStatus])

  // ── Detect run completion ────────────────────────────────────────────────
  useEffect(() => {
    const prev = prevStateRef.current
    if (prev !== 'idle' && state === 'idle' && runningPlanRef.current) {
      setCompleted(runningPlanRef.current)
    }
    prevStateRef.current = state
  }, [state])

  // ── Load shoots on mount ─────────────────────────────────────────────────
  useEffect(() => {
    api.p2Shoots()
      .then(list => {
        setShoot(list)
        if (list.length > 0) setSelectedShoot(list[0].path)
      })
      .catch(() => {})
    // Load already-planned months so we can warn before overwriting
    api.contentPosts()
      .then(data => {
        const months = new Set()
        for (const post of data?.posts ?? []) {
          if (post.date) months.add(post.date.slice(0, 7))   // "YYYY-MM"
        }
        setPlannedMonths(months)
      })
      .catch(() => {})
  }, [])

  // ── Elapsed counter ──────────────────────────────────────────────────────
  useEffect(() => {
    if (state === 'idle') { setElapsed(0); return }
    if (state === 'paused') return
    const id = setInterval(() => {
      if (!elapsedBase.current) return
      const base = new Date(elapsedBase.current.started_at + 'Z').getTime()
      setElapsed(Math.floor((Date.now() - base) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [state])

  // ── SSE log stream ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!isActive) return
    const es = new EventSource(api.p2LogsUrl())
    esRef.current = es
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.done) { es.close(); return }
      if (data.line != null) setLines(prev => [...prev.slice(-999), data.line])
    }
    es.onerror = () => es.close()
    return () => { es.close(); esRef.current = null }
  }, [isActive])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lines])

  // ── Controls ─────────────────────────────────────────────────────────────
  const selectedMonthKey = `${planYear}-${String(planMonth).padStart(2, '0')}`
  const monthAlreadyPlanned = plannedMonths.has(selectedMonthKey)

  const doStart = async () => {
    try {
      await api.p2Start({ shoot_folder: selectedShoot, planning_month: selectedMonthKey })
      setLines([])
      setCompleted(null)
      runningPlanRef.current = { month: planMonth, year: planYear }
      fetchStatus()
      addToast('info', `Starting Content Planning for ${MONTHS[planMonth - 1]} ${planYear}`)
    } catch (e) {
      addToast('error', e.message || 'Failed to start')
    }
  }

  const handleStart = () => {
    if (monthAlreadyPlanned) {
      setConfirmOverwrite(true)
    } else {
      doStart()
    }
  }

  const handleStop = async () => {
    try {
      await api.p2Stop()
      fetchStatus()
      addToast('warning', 'Content pipeline stopped')
    } catch (e) {
      addToast('error', e.message || 'Failed to stop')
    }
  }

  const handlePause = async () => {
    try {
      await (state === 'paused' ? api.p2Resume() : api.p2Pause())
      fetchStatus()
    } catch (e) {
      addToast('error', e.message || 'Failed')
    }
  }

  const yearOptions = [def.year - 1, def.year, def.year + 1].filter(
    y => y >= new Date().getFullYear()
  )

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-5xl">

      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Workflow</p>
          <h1 className="text-xl text-[var(--c-text-1)] font-semibold">New Content Planning</h1>
        </div>
        <div className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATE_CLS[state] ?? STATE_CLS.idle}`}>
          {STATE_LABEL[state] ?? state}
          {state !== 'idle' && elapsed > 0 && (
            <span className="ml-1.5 opacity-70">{fmtElapsed(elapsed)}</span>
          )}
        </div>
      </div>

      {/* ── Active run panel ── */}
      {isActive && (
        <div className="mb-8 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--c-border)] bg-[var(--c-surface-2)]">
            <button
              onClick={handlePause}
              className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-[var(--c-border-2)] text-[var(--c-text-1b)] hover:bg-[var(--c-surface-3)] transition-colors"
            >
              {state === 'paused' ? <><RotateCcw size={13} /> Resume</> : <><Pause size={13} /> Pause</>}
            </button>
            <button
              onClick={handleStop}
              className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <Square size={13} /> Stop
            </button>
            {state === 'paused' && (
              <span className="ml-2 text-xs text-yellow-400 animate-pulse">⏸ Pipeline frozen</span>
            )}
          </div>
          <div
            ref={logRef}
            className="h-80 overflow-y-auto font-mono text-[11px] leading-relaxed text-[var(--c-text-2)] p-4 bg-[var(--c-page)]"
          >
            {lines.length === 0
              ? <span className="text-[var(--c-text-4)]">Waiting for output…</span>
              : lines.map((l, i) => <LogLine key={i} line={l} />)
            }
          </div>
        </div>
      )}

      {/* ── Success panel ── */}
      {!isActive && completed && (
        <div className="mb-8 bg-green-500/10 border border-green-500/30 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <CheckCircle size={22} className="text-green-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-[var(--c-text-1)] mb-1">
                Content planning for {MONTHS[completed.month - 1]} {completed.year} is ready
              </p>
              <p className="text-xs text-[var(--c-text-3)]">
                Copy, calendar, and review have been generated.
              </p>
            </div>
            <div className="flex flex-col gap-2 shrink-0">
              <button
                onClick={() => navigate('/content-planning')}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
              >
                View Content Planning <ArrowRight size={14} />
              </button>
              <button
                onClick={() => navigate('/content-plan-report')}
                className="flex items-center gap-2 bg-[var(--c-surface-2)] hover:bg-[var(--c-surface-3)] text-[var(--c-text-2)] text-sm font-medium px-4 py-2 rounded-lg transition-colors border border-[var(--c-border-2)]"
              >
                View Report <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Log replay when stopped ── */}
      {!isActive && lines.length > 0 && (
        <div className="mb-8 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[var(--c-border)] text-xs text-[var(--c-text-3)] uppercase tracking-wider">
            Last run output
          </div>
          <div
            ref={logRef}
            className="h-48 overflow-y-auto font-mono text-[11px] leading-relaxed text-[var(--c-text-2)] p-4 bg-[var(--c-page)]"
          >
            {lines.map((l, i) => <LogLine key={i} line={l} />)}
          </div>
        </div>
      )}

      {/* ── Pipeline steps ── */}
      <div className="mb-6 flex items-center gap-2">
        {STEPS.map((step, i) => (
          <div key={step.id} className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--c-surface)] border border-[var(--c-border)] text-xs text-[var(--c-text-3)]">
              <span className="w-4 h-4 rounded-full border border-[var(--c-border-2)] flex items-center justify-center text-[10px] text-[var(--c-text-4)]">{i + 1}</span>
              {step.label}
            </div>
            {i < STEPS.length - 1 && (
              <span className="text-[var(--c-text-4)] text-xs">→</span>
            )}
          </div>
        ))}
      </div>

      {/* ── Configuration ── */}
      <div className={`bg-[var(--c-surface)] border border-[var(--c-border)] rounded-xl overflow-hidden mb-6 ${isActive ? 'opacity-60' : ''}`}>
        <button
          onClick={isActive ? undefined : () => setConfigOpen(o => !o)}
          disabled={isActive}
          className={`w-full flex items-center gap-2 px-5 py-3.5 text-left transition-colors border-b border-[var(--c-border)] ${isActive ? 'cursor-not-allowed' : 'hover:bg-[var(--c-surface-2)]'}`}
        >
          <Settings size={14} className="text-[var(--c-text-3)]" />
          <span className="text-xs font-medium text-[var(--c-text-2)] uppercase tracking-wider flex-1">Configuration</span>
          {configOpen ? <ChevronUp size={13} className="text-[var(--c-text-4)]" /> : <ChevronDown size={13} className="text-[var(--c-text-4)]" />}
        </button>
        {configOpen && <div className="p-5"><div className="grid grid-cols-1 sm:grid-cols-2 gap-6">

          {/* Shoot selector */}
          <div>
            <label className="block text-xs text-[var(--c-text-3)] mb-1.5">Source Shoot</label>
            {shoots.length === 0 ? (
              <p className="text-sm text-[var(--c-text-4)] italic">No shoots found</p>
            ) : (
              <div className="relative">
                <select
                  value={selectedShoot}
                  onChange={e => setSelectedShoot(e.target.value)}
                  disabled={isActive}
                  className={selectCls}
                >
                  {shoots.map(s => (
                    <option key={s.path} value={s.path}>
                      {s.name} — {s.month}{s.latest ? ' (latest)' : ''}
                    </option>
                  ))}
                </select>
                <ChevronDown size={13} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--c-text-4)]" />
              </div>
            )}
            <p className="mt-1 text-xs text-[var(--c-text-4)]">Images from this shoot will be used for content</p>
          </div>

          {/* Planning month */}
          <div>
            <label className="block text-xs text-[var(--c-text-3)] mb-1.5">Plan For</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <select
                  value={planMonth}
                  onChange={e => setPlanMonth(Number(e.target.value))}
                  disabled={isActive}
                  className={selectCls}
                >
                  {MONTHS.map((m, i) => (
                    <option key={m} value={i + 1}>{m}</option>
                  ))}
                </select>
                <ChevronDown size={13} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--c-text-4)]" />
              </div>
              <div className="relative w-24">
                <select
                  value={planYear}
                  onChange={e => setPlanYear(Number(e.target.value))}
                  disabled={isActive}
                  className={selectCls}
                >
                  {yearOptions.map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
                <ChevronDown size={13} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--c-text-4)]" />
              </div>
            </div>
            {monthAlreadyPlanned ? (
              <p className="mt-1.5 flex items-center gap-1.5 text-xs text-orange-400">
                <AlertTriangle size={12} className="shrink-0" />
                {MONTHS[planMonth - 1]} {planYear} is already planned — starting will overwrite existing posts.
              </p>
            ) : (
              <p className="mt-1 text-xs text-[var(--c-text-4)]">4-week posting calendar will start on the first Monday of this month</p>
            )}
          </div>

        </div></div>}
      </div>

      {/* ── Start button ── */}
      {state === 'idle' && (
        <div className="flex justify-end">
          <button
            onClick={handleStart}
            disabled={!selectedShoot}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-6 py-2.5 rounded-xl transition-colors shadow-lg shadow-blue-900/20"
          >
            <Play size={14} /> Start Content Planning
          </button>
        </div>
      )}

      <ConfirmDialog
        open={confirmOverwrite}
        title={`Overwrite ${MONTHS[planMonth - 1]} ${planYear}?`}
        message={`${MONTHS[planMonth - 1]} ${planYear} already has a content plan. Starting a new run will replace all existing posts for this month. This cannot be undone.`}
        confirmLabel="Yes, overwrite"
        variant="warning"
        onConfirm={() => { setConfirmOverwrite(false); doStart() }}
        onCancel={() => setConfirmOverwrite(false)}
      />

    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

const selectCls = `w-full appearance-none bg-[var(--c-surface-2)] border border-[var(--c-border-2)] rounded-lg px-3 py-2 pr-8 text-sm text-[var(--c-text-1)] focus:outline-none focus:border-[var(--c-text-3)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed`

function LogLine({ line }) {
  let cls = 'text-[var(--c-text-2)]'
  if (/error|failed|fatal/i.test(line))               cls = 'text-red-400'
  else if (/warn/i.test(line))                         cls = 'text-yellow-400'
  else if (/✓|success|complete|done/i.test(line))      cls = 'text-green-400'
  else if (/^\[Phase 2\]|^\[Monitor\]/i.test(line))    cls = 'text-blue-400'
  else if (/copywriter|planner|review|sprint/i.test(line)) cls = 'text-[var(--c-text-1b)]'
  return <div className={cls}>{line || ' '}</div>
}
