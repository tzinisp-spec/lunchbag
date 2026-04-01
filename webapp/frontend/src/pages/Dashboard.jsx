import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../lib/api'
import { AGENTS } from '../lib/agents'
import StatusBadge from '../components/StatusBadge'

function fmt(n) {
  return n?.toLocaleString() ?? '—'
}

// Agent metadata lookup
const AGENT_META = Object.fromEntries(AGENTS.map(a => [a.id, a]))

const AGENT_INITIALS = {
  orchestrator: 'CO',
  trend_scout:  'TS',
  strategist:   'CS',
  director:     'VD',
  photographer: 'PH',
  photo_editor: 'PE',
}

function relTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)   return 'just now'
  if (m < 60)  return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24)  return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [data,         setData]         = useState(null)
  const [activity,     setActivity]     = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [period,       setPeriod]       = useState('latest')   // 'latest' | 'all' | month key
  const [visibleCount, setVisibleCount] = useState(20)
  const navigate = useNavigate()
  const pollRef  = useRef(null)

  const loadActivity = () =>
    api.activity().then(setActivity).catch(console.error)

  const isLive = (activity?.is_live ?? false) || (data?.is_live ?? false)

  // When a run becomes active: switch Overview to "latest" and reset activity
  const prevIsLive = useRef(isLive)
  useEffect(() => {
    if (prevIsLive.current !== isLive) {
      if (isLive) setPeriod('latest')
      setVisibleCount(20)
      prevIsLive.current = isLive
    }
  }, [isLive])

  useEffect(() => {
    Promise.all([
      api.dashboard().then(setData),
      loadActivity(),
    ]).finally(() => setLoading(false))
  }, [])

  // Poll faster when a run is active; also refresh overview stats
  useEffect(() => {
    const interval = isLive ? 3000 : 8000
    pollRef.current = setInterval(() => {
      loadActivity()
      if (isLive) api.dashboard().then(setData).catch(console.error)
    }, interval)
    return () => clearInterval(pollRef.current)
  }, [isLive])

  if (loading) return <Loading />

  const d      = data ?? {}
  const events = activity?.events ?? []
  const tasks  = activity?.tasks  ?? []

  // Pick stats for selected period
  const stats = period === 'latest' ? (d.latest ?? {})
              : period === 'all'    ? (d.all_time ?? {})
              : (d.by_month?.[period] ?? {})

  const months = d.available_months ?? []

  return (
    <div className="p-4 sm:p-6 md:p-8">

      {/* Header */}
      <div className="mb-8">
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Dashboard</p>
        <h1 className="text-2xl text-[var(--c-text-1)] font-semibold">COMAP</h1>
      </div>

      {/* Overview */}
      <div className="mb-10">
        {/* Section header + period selector */}
        <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">
              Overview
              {(() => {
                let label = ''
                if (period === 'latest' && stats?.phase === 'content_planning')
                  label = stats.plan_label || 'Content Planning'
                else if (period === 'latest' && stats?.name)
                  label = stats.name
                else if (period && period !== 'latest' && period !== 'all') {
                  const [y, m] = period.split('-')
                  label = new Date(+y, +m - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
                }
                return label ? <span className="normal-case ml-1 text-[var(--c-text-4)] font-normal tracking-normal">({label})</span> : null
              })()}
            </p>
            {isLive && period === 'latest' && <LiveBadge />}
          </div>
          <PeriodSelector value={period} onChange={setPeriod} months={months} disabled={isLive} stats={stats} />
        </div>

        {/* 5 Detail tiles */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">

          {stats.phase === 'content_planning' ? (
            <DetailTile
              title="Content Plan"
              main={fmt(stats.total_images)}
              mainLabel="posts planned"
              items={[
                { label: 'Single posts', value: fmt(stats.approved),      color: 'green' },
                { label: 'Carousels',    value: fmt(stats.needs_review),  color: 'muted' },
              ]}
            />
          ) : (
            <DetailTile
              title="Produced Images"
              main={fmt(stats.total_images)}
              mainLabel={period === 'all' ? `across ${stats.shoot_count ?? d.shoots} shoots` : 'total images'}
              items={[
                { label: 'Approved',     value: fmt(stats.approved),     color: 'green'  },
                { label: 'Needs review', value: fmt(stats.needs_review), color: (stats.needs_review > 0) ? 'orange' : 'muted' },
                ...(stats.regen > 0 ? [{ label: 'Regen', value: fmt(stats.regen), color: 'red' }] : []),
              ]}
            />
          )}

          <DetailTile
            title="Processing Time"
            main={stats.runtime ?? '—'}
            mainLabel="total"
            items={stats.phase === 'content_planning' ? [
              ...(stats.time_copywriter       ? [{ label: 'Copywriter',     value: stats.time_copywriter       }] : []),
              ...(stats.time_content_planner  ? [{ label: 'Content Plan',   value: stats.time_content_planner  }] : []),
              ...(stats.time_review_generator ? [{ label: 'Review Gen',     value: stats.time_review_generator }] : []),
            ] : [
              { label: 'Brief',        value: stats.time_brief        || '—' },
              { label: 'Generation',   value: stats.time_generation   || '—' },
              { label: 'Photo Editor', value: stats.time_photo_editor || '—' },
              ...(stats.time_copywriter       ? [{ label: 'Copywriter',   value: stats.time_copywriter       }] : []),
              ...(stats.time_content_planner  ? [{ label: 'Content Plan', value: stats.time_content_planner  }] : []),
              ...(stats.time_review_generator ? [{ label: 'Review Gen',   value: stats.time_review_generator }] : []),
            ]}
          />

          <DetailTile
            title="API Calls"
            main={fmt(stats.total_calls) || '—'}
            mainLabel="total calls"
            items={[
              ...(stats.image_model_name ? [{ label: modelShortName(stats.image_model_name), value: fmt(stats.calls_image_model) || '—' }] : []),
              { label: modelShortName(stats.text_model_name),  value: fmt(stats.calls_text_model)  || '—' },
            ].filter(i => i.value !== '0')}
          />

          <DetailTile
            title="Cost"
            main={stats.total_cost > 0 ? `$${stats.total_cost.toFixed(2)}` : '—'}
            mainLabel="total"
            items={[
              { label: modelShortName(stats.image_model_name), value: stats.cost_image_model > 0 ? `$${stats.cost_image_model.toFixed(2)}` : '—' },
              { label: modelShortName(stats.text_model_name),  value: stats.cost_text_model  > 0 ? `$${stats.cost_text_model.toFixed(2)}`  : '—' },
            ]}
          />

          <DetailTile
            title="Errors"
            main={stats.errors_total > 0 ? stats.errors_total : (stats.errors ?? '0')}
            mainLabel="total issues"
            items={[
              { label: 'Fixed',        value: stats.errors_fixed   ?? '0', color: 'green'  },
              { label: 'Needs review', value: stats.errors_flagged ?? '0', color: (parseInt(stats.errors_flagged) > 0) ? 'orange' : 'muted' },
            ]}
          />

        </div>
      </div>

      {/* ── Two-column live feed ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">

        {/* Recent Activities */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <p className="text-xs font-semibold text-[var(--c-text-3)] uppercase tracking-widest">Recent Activity</p>
            {isLive && <LiveBadge />}
          </div>
          <div className="border border-[var(--c-border)] rounded-xl overflow-hidden divide-y divide-[var(--c-border)]">
            {events.length === 0 ? (
              <div className="px-4 py-6 text-[var(--c-text-4)] text-sm">No activity yet.</div>
            ) : (
              <>
                {events.slice(0, visibleCount).map(ev => <ActivityRow key={ev.id} event={ev} />)}
                {events.length > visibleCount && (
                  <button
                    onClick={() => setVisibleCount(c => c + 10)}
                    className="w-full px-4 py-2 text-xs text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-row-hover)] transition-colors font-mono"
                  >
                    show {Math.min(10, events.length - visibleCount)} more
                    <span className="text-[var(--c-text-4)] ml-1">({events.length - visibleCount} remaining)</span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Recent Tasks */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <p className="text-xs font-semibold text-[var(--c-text-3)] uppercase tracking-widest">Recent Tasks</p>
            {isLive && <LiveBadge />}
          </div>
          <div className="border border-[var(--c-border)] rounded-xl overflow-hidden divide-y divide-[var(--c-border)]">
            {tasks.length === 0 ? (
              <div className="px-4 py-6 text-[var(--c-text-4)] text-sm">No tasks recorded yet.</div>
            ) : (
              tasks.map((task, i) => (
                <TaskRow key={i} task={task} navigate={navigate} />
              ))
            )}
          </div>
        </div>

      </div>

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
              className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-5 py-4 flex items-center gap-4 hover:bg-[var(--c-surface-2)] transition-colors cursor-pointer group"
            >
              <div className="w-9 h-9 rounded-full bg-[var(--c-surface-2)] flex items-center justify-center shrink-0 text-lg">
                {a.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[var(--c-text-1)] text-sm font-medium">{a.name}</div>
                <div className="text-[var(--c-text-3)] text-xs truncate">{a.role}</div>
              </div>
              <ChevronRight size={15} className="text-[var(--c-text-4)] group-hover:text-[var(--c-text-2)] transition-colors shrink-0" />
            </div>
          ))}
        </div>
      </Section>

    </div>
  )
}

// ── Activity row ──────────────────────────────────────────────────────────────

const OUTCOME_CFG = {
  pass:    { symbol: '✓', cls: 'text-green-400',  label: 'PASS'    },
  fixed:   { symbol: '✓', cls: 'text-yellow-400', label: 'FIXED'   },
  flagged: { symbol: '✗', cls: 'text-red-400',    label: 'FLAGGED' },
  regen:   { symbol: '✗', cls: 'text-red-500',    label: 'REGEN'   },
  summary: { symbol: '●', cls: 'text-blue-400',   label: ''        },
}

function LiveBadge() {
  return (
    <span className="flex items-center gap-1 text-[10px] font-semibold text-green-400 bg-green-400/10 border border-green-400/30 px-1.5 py-0.5 rounded">
      <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse inline-block" />
      LIVE
    </span>
  )
}

const CHILD_OUTCOME = {
  pass:          { sym: '✓', cls: 'text-green-400'  },
  fixed:         { sym: '✓', cls: 'text-yellow-400' },
  flagged:       { sym: '⚠', cls: 'text-orange-400' },
  flagged_batch: { sym: '⚠', cls: 'text-orange-400' },
  regen:         { sym: '✗', cls: 'text-red-400'    },
}

function ReviewChildren({ children }) {
  return (
    <div className="border-t border-[var(--c-border)] bg-[var(--c-surface)]">
      {children.map((c, i) => {
        const cfg = CHILD_OUTCOME[c.outcome] ?? { sym: '·', cls: 'text-[var(--c-text-4)]' }
        return (
          <div key={i} className="flex items-start gap-2 px-4 pl-10 py-1 font-mono text-[11px] hover:bg-[var(--c-row-hover)]">
            <span className={`shrink-0 w-3 font-bold ${cfg.cls}`}>{cfg.sym}</span>
            <span className="text-[var(--c-text-3)] shrink-0 w-14">{c.ref}</span>
            <span className="text-[var(--c-text-2)] flex-1 min-w-0 truncate">{c.detail}</span>
          </div>
        )
      })}
    </div>
  )
}

function ActivityRow({ event }) {
  const [expanded, setExpanded] = useState(true)
  const cfg = OUTCOME_CFG[event.outcome] ?? OUTCOME_CFG.summary

  if (event.type === 'live_banner') {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-green-400/5 border-b border-green-400/20 font-mono text-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse shrink-0" />
        <span className="text-green-400 font-semibold shrink-0">{event.ref}</span>
        <span className="text-[var(--c-text-3)] flex-1 min-w-0 truncate">{event.detail}</span>
        <span className="text-green-400/60 shrink-0">running…</span>
      </div>
    )
  }

  if (event.type === 'progress') {
    const PROG = {
      start:    { sym: '▶', cls: 'text-blue-400'   },
      retry:    { sym: '↻', cls: 'text-yellow-400' },
      complete: { sym: '✓', cls: 'text-green-400'  },
      fail:     { sym: '✗', cls: 'text-red-400'    },
      update:   { sym: '◎', cls: 'text-blue-300 animate-pulse' },
    }
    const p        = PROG[event.progress_type] ?? { sym: '·', cls: 'text-[var(--c-text-4)]' }
    const children = event.children ?? []
    const hasKids  = children.length > 0

    return (
      <div>
        <div
          className={`flex items-start gap-2 px-4 py-1.5 transition-colors font-mono text-xs ${hasKids ? 'cursor-pointer hover:bg-[var(--c-row-hover)]' : 'hover:bg-[var(--c-row-hover)]'}`}
          onClick={hasKids ? () => setExpanded(e => !e) : undefined}
        >
          <span className={`shrink-0 w-4 font-bold ${p.cls}`}>{p.sym}</span>
          <span className="text-[var(--c-text-2)] flex-1 min-w-0 truncate">{event.detail}</span>
          {hasKids && (
            expanded
              ? <ChevronUp size={12} className="text-[var(--c-text-4)] shrink-0 mt-0.5" />
              : <ChevronDown size={12} className="text-[var(--c-text-4)] shrink-0 mt-0.5" />
          )}
          {!hasKids && <span className="text-[var(--c-text-4)] shrink-0 tabular-nums">{relTime(event.timestamp)}</span>}
        </div>
        {hasKids && expanded && <ReviewChildren children={children} />}
      </div>
    )
  }

  if (event.type === 'image') {
    return (
      <div className="flex items-start gap-2 px-4 py-1.5 hover:bg-[var(--c-row-hover)] transition-colors font-mono text-xs">
        {/* Symbol */}
        <span className={`shrink-0 w-4 ${cfg.cls} font-bold`}>{cfg.symbol}</span>
        {/* Outcome label */}
        <span className={`shrink-0 w-14 ${cfg.cls} font-semibold`}>{cfg.label}</span>
        {/* Ref */}
        <span className="text-[var(--c-text-1b)] shrink-0 w-16">{event.ref}</span>
        {/* Detail / fail reason */}
        <span className="text-[var(--c-text-3)] flex-1 min-w-0 truncate">
          {event.fail_reason || event.detail || ''}
        </span>
        {/* Time */}
        <span className="text-[var(--c-text-4)] shrink-0 tabular-nums">{relTime(event.timestamp)}</span>
      </div>
    )
  }

  if (event.type === 'review_summary') {
    return (
      <div className="flex items-center gap-2 px-4 py-2 hover:bg-[var(--c-row-hover)] transition-colors border-t border-[var(--c-border)] font-mono text-xs">
        <span className="text-blue-400 shrink-0">↳</span>
        <span className="text-[var(--c-text-2)] flex-1 min-w-0 truncate">{event.detail}</span>
        <span className="text-[var(--c-text-4)] shrink-0 tabular-nums">{relTime(event.timestamp)}</span>
      </div>
    )
  }

  // sprint summary
  return (
    <div className="flex items-center gap-2 px-4 py-2 hover:bg-[var(--c-row-hover)] transition-colors border-t border-[var(--c-border)] font-mono text-xs">
      <span className="text-purple-400 shrink-0">🚀</span>
      <span className="text-[var(--c-text-1b)] font-semibold shrink-0">{event.ref}</span>
      <span className="text-[var(--c-text-3)] flex-1 min-w-0 truncate">· {event.detail}</span>
      <span className="text-[var(--c-text-4)] shrink-0 tabular-nums">{relTime(event.timestamp)}</span>
    </div>
  )
}

// ── Task row ──────────────────────────────────────────────────────────────────

function TaskRow({ task, navigate }) {
  const initials = AGENT_INITIALS[task.agent] ?? '??'
  const running  = task.status === 'running' || task.status === 'in_progress'
  const done     = task.status === 'completed'
  const failed   = task.status === 'failed'
  const pending  = !running && !done && !failed

  const dotCls = running ? 'text-blue-400 animate-pulse'
               : done    ? 'text-green-400'
               : failed  ? 'text-red-400'
               :           'text-[var(--c-text-4)]'

  const symbol = running ? '○' : done ? '✓' : failed ? '✗' : '·'

  // Determine action link
  const hasImages = task.shoot_link && task.shoot_set != null
  const hasReport = task.report_ready

  return (
    <div className="flex items-center gap-3 px-4 py-2 font-mono text-xs">
      <span className={`shrink-0 w-3 font-bold ${dotCls}`}>{symbol}</span>

      <div className="flex-1 min-w-0 flex items-center gap-2 overflow-hidden">
        <span className={`truncate ${
          pending ? 'text-[var(--c-text-4)]'
          : failed  ? 'text-red-400'
          : 'text-[var(--c-text-1b)]'
        }`}>
          {task.task}
        </span>
        {hasImages && (
          <button
            onClick={() => navigate(`${task.shoot_link}?set=${task.shoot_set}`)}
            className="shrink-0 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
          >
            See the images →
          </button>
        )}
        {hasReport && (
          <button
            onClick={() => navigate(task.report_type === 'content_plan' ? '/content-plan-report' : '/photoshoot-report')}
            className="shrink-0 text-[10px] text-purple-400 hover:text-purple-300 transition-colors"
          >
            See the report →
          </button>
        )}
      </div>

      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
        pending
          ? 'bg-[var(--c-surface)] text-[var(--c-text-4)] border border-[var(--c-border)]'
          : 'bg-[var(--c-surface-2)] border border-[var(--c-border-2)] text-[var(--c-text-2)]'
      }`}>
        {initials}
      </span>

      <span className={`shrink-0 tabular-nums w-24 text-right ${pending ? 'text-[var(--c-text-4)]' : 'text-[var(--c-text-3)]'}`}>
        {task.duration}
      </span>
    </div>
  )
}

// ── Shoot row ─────────────────────────────────────────────────────────────────

function ShootRow({ shoot, onClick }) {
  return (
    <div
      className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-6 py-4 flex items-center justify-between hover:bg-[var(--c-surface-2)] transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div>
        <div className="text-[var(--c-text-1)] font-medium">{shoot.name}</div>
        <div className="text-[var(--c-text-3)] text-sm mt-0.5">{shoot.date || shoot.month}</div>
      </div>
      <div className="flex items-center gap-8">
        <div className="text-center hidden sm:block">
          <div className="text-[var(--c-text-1)] font-semibold">{shoot.approved}</div>
          <div className="text-[var(--c-text-3)] text-xs">approved</div>
        </div>
        <div className="text-center hidden sm:block">
          <div className="text-[var(--c-text-1)] font-semibold">{shoot.total_images}</div>
          <div className="text-[var(--c-text-3)] text-xs">total</div>
        </div>
        {shoot.total_cost > 0 && (
          <div className="text-center hidden md:block">
            <div className="text-[var(--c-text-1)] font-semibold">${shoot.total_cost.toFixed(2)}</div>
            <div className="text-[var(--c-text-3)] text-xs">cost</div>
          </div>
        )}
        <StatusBadge status={shoot.status} dot />
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

// ── Period selector ───────────────────────────────────────────────────────────

function PeriodSelector({ value, onChange, months, disabled, stats }) {
  return (
    <div className={`flex items-center gap-1 flex-wrap ${disabled ? 'opacity-40 pointer-events-none' : ''}`}>
      {[
        { key: 'latest', label: value === 'latest' && stats?.phase === 'content_planning' ? 'Latest Content Plan' : 'Latest Run' },
        { key: 'all',    label: 'All Time'   },
      ].map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
            value === key
              ? 'bg-[var(--c-surface-3)] text-[var(--c-text-1)]'
              : 'text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)]'
          }`}
        >
          {label}
        </button>
      ))}
      {months.length > 0 && (
        <div className="relative">
          <select
            value={months.includes(value) ? value : ''}
            onChange={e => e.target.value && onChange(e.target.value)}
            className={`appearance-none text-xs pl-3 pr-7 py-1.5 rounded-lg transition-colors cursor-pointer bg-transparent border-0 outline-none text-[var(--c-text-1)] dark:bg-gray-900 ${
              months.includes(value)
                ? 'bg-[var(--c-surface-3)] text-[var(--c-text-1)]'
                : 'text-[var(--c-text-3)] hover:text-[var(--c-text-1)] hover:bg-[var(--c-surface-2)]'
            }`}
            style={{ backgroundImage: 'none' }}
          >
            <option value="" disabled className="dark:text-white">By month…</option>
            {months.map(m => (
              <option key={m} value={m} className="dark:text-white">{m}</option>
            ))}
          </select>
          <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--c-text-3)] pointer-events-none" />
        </div>
      )}
    </div>
  )
}

// ── Detail tile (same as ShootDetail) ─────────────────────────────────────────

const VALUE_COLOR = {
  green:  'text-green-400',
  orange: 'text-orange-400',
  red:    'text-red-400',
  muted:  'text-[var(--c-text-4)]',
}

function DetailTile({ title, main, mainLabel, items = [] }) {
  return (
    <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-5 flex flex-col">
      <div className="text-[var(--c-text-3)] text-xs uppercase tracking-wider mb-3">{title}</div>
      <div className="text-2xl text-[var(--c-text-1)] font-semibold leading-none">{main}</div>
      {mainLabel && <div className="text-[var(--c-text-4)] text-xs mt-1">{mainLabel}</div>}
      {items.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--c-border)] space-y-1.5 flex-1">
          {items.map((item, i) => (
            <div key={i} className="flex items-center justify-between gap-2">
              <span className="text-[var(--c-text-3)] text-xs truncate">{item.label}</span>
              <span className={`text-xs font-medium shrink-0 ${VALUE_COLOR[item.color] ?? 'text-[var(--c-text-1b)]'}`}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function modelShortName(name) {
  if (!name) return 'Unknown'
  if (/image/i.test(name)) return 'Gemini Image'
  const m = name.match(/gemini[- ]?([\d.]+[^\s]*)/i)
  return m ? `Gemini ${m[1]}` : name
}

// ── Misc helpers ──────────────────────────────────────────────────────────────

function Section({ label, children }) {
  return (
    <div className="mb-10">
      <SectionLabel>{label}</SectionLabel>
      {children}
    </div>
  )
}

function SectionLabel({ children }) {
  return <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-4">{children}</p>
}

function Loading() {
  return (
    <div className="p-8 flex items-center justify-center h-64">
      <div className="text-[var(--c-text-3)] text-sm">Loading…</div>
    </div>
  )
}

function Empty({ text }) {
  return <div className="text-[var(--c-text-4)] text-sm py-4">{text}</div>
}
