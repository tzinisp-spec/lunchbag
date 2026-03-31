import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api'

export default function ContentPlanReport() {
  const navigate    = useNavigate()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    api.contentPlanReport()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="p-8 flex items-center justify-center h-64">
      <div className="text-[var(--c-text-3)] text-sm">Loading report…</div>
    </div>
  )

  if (error || data?.error) return (
    <div className="p-8">
      <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-[var(--c-text-3)] hover:text-[var(--c-text-1)] text-sm mb-6 transition-colors">
        <ArrowLeft size={16} /> Back
      </button>
      <div className="text-[var(--c-text-3)]">No content planning report available yet.</div>
    </div>
  )

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-5xl">

      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-[var(--c-text-3)] hover:text-[var(--c-text-1)] text-sm mb-6 transition-colors"
      >
        <ArrowLeft size={16} /> Back
      </button>

      {/* Header */}
      <div className="mb-8">
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Content Planning Report</p>
        <h1 className="text-xl text-[var(--c-text-1)] font-semibold font-mono">{data.sprint_id || 'Unknown Run'}</h1>
        <div className="flex items-center gap-4 mt-2 text-xs text-[var(--c-text-3)]">
          {data.date && <span>{data.date}</span>}
          {data.started && data.completed && (
            <span>{data.started} → {data.completed}</span>
          )}
          {data.runtime && <span className="text-[var(--c-text-2)]">{data.runtime} total</span>}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <SummaryCard label="Images Approved" value={data.images_approved || '—'} />
        <SummaryCard label="Runtime"         value={data.runtime        || '—'} accent="blue" />
        <SummaryCard label="API Calls"       value={data.api?.total_calls > 0 ? data.api.total_calls.toLocaleString() : '—'} />
        <SummaryCard label="Total Cost"      value={data.api?.total_cost > 0 ? `$${data.api.total_cost.toFixed(4)}` : '—'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

        {/* Step timings */}
        {data.steps?.length > 0 && (
          <Section title="Step Timing">
            <div className="space-y-2">
              {data.steps.map((s, i) => (
                <div key={i} className="flex items-center justify-between gap-3 py-1.5 border-b border-[var(--c-border)] last:border-0">
                  <span className="text-[var(--c-text-2)] text-sm">{s.name}</span>
                  <span className="text-[var(--c-text-1)] text-sm font-mono shrink-0">{s.duration}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* API costs */}
        {data.api && (
          <Section title="API Usage & Cost">
            <div className="space-y-3">
              {[data.api.image_model, data.api.text_model].filter(m => m?.calls > 0).map((model, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--c-border)]">
                  <div>
                    <div className="text-sm text-[var(--c-text-1b)]">{model.name}</div>
                    <div className="text-xs text-[var(--c-text-3)]">{model.calls.toLocaleString()} calls</div>
                  </div>
                  <div className="text-sm font-mono text-[var(--c-text-1)]">
                    {model.cost > 0 ? `$${model.cost.toFixed(4)}` : '—'}
                  </div>
                </div>
              ))}
              <div className="flex items-center justify-between pt-1">
                <div>
                  <div className="text-sm font-semibold text-[var(--c-text-1)]">Total</div>
                  <div className="text-xs text-[var(--c-text-3)]">{data.api.total_calls.toLocaleString()} calls</div>
                </div>
                <div className="text-sm font-semibold font-mono text-[var(--c-text-1)]">
                  {data.api.total_cost > 0 ? `$${data.api.total_cost.toFixed(4)}` : '—'}
                </div>
              </div>
            </div>
          </Section>
        )}
      </div>

      {/* Recommendations */}
      {data.recommendations?.length > 0 && (
        <Section title="Recommendations">
          <ul className="space-y-2">
            {data.recommendations.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-[var(--c-text-2)]">
                <span className="text-[var(--c-text-4)] shrink-0 mt-0.5">→</span>
                {r}
              </li>
            ))}
          </ul>
        </Section>
      )}

    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function SummaryCard({ label, value, accent }) {
  const valCls = accent === 'orange' ? 'text-orange-400'
               : accent === 'blue'   ? 'text-blue-400'
               : 'text-[var(--c-text-1)]'
  return (
    <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-4">
      <div className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-2">{label}</div>
      <div className={`text-2xl font-semibold leading-none ${valCls}`}>{value}</div>
    </div>
  )
}

function Section({ title, children, className = '' }) {
  return (
    <div className={`bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-5 ${className}`}>
      <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-4">{title}</p>
      {children}
    </div>
  )
}
