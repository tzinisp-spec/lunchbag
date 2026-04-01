import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { api } from '../lib/api'

export default function PhotoshootReport() {
  const navigate    = useNavigate()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    api.photoshootReport()
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
      <div className="text-[var(--c-text-3)]">No photoshoot report available yet.</div>
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
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Photoshoot Report</p>
        <h1 className="text-xl text-[var(--c-text-1)] font-semibold font-mono">{data.sprint_id || 'Unknown Sprint'}</h1>
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
        <SummaryCard label="Images Generated"   value={data.images_generated || '—'} />
        <SummaryCard label="Images Approved"    value={data.images_approved  || '—'} />
        <SummaryCard label="First-Pass Rate"    value={data.pass_rate        || '—'} accent="blue" />
        <SummaryCard label="Needs Review"       value={data.needs_review     || '0'} accent={parseInt(data.needs_review) > 0 ? 'orange' : null} />
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

        {/* Image quality */}
        {data.quality && (
          <Section title="Image Quality">
            <div className="space-y-2">
              {[
                { label: 'Total reviewed',       value: data.quality.total_reviewed },
                { label: 'First-pass approval',  value: data.quality.first_pass,    color: 'green'  },
                { label: 'Fixed by editing',      value: data.quality.fixed,         color: 'yellow' },
                { label: 'Final approval rate',   value: data.quality.final_rate,    color: 'blue'   },
                { label: 'Flagged for review',    value: data.quality.flagged,       color: parseInt(data.quality.flagged) > 0 ? 'orange' : null },
                { label: 'Flagged by batch',      value: data.quality.flagged_batch, color: parseInt(data.quality.flagged_batch) > 0 ? 'orange' : null },
              ].filter(r => r.value).map((row, i) => (
                <div key={i} className="flex items-center justify-between gap-3 py-1.5 border-b border-[var(--c-border)] last:border-0">
                  <span className="text-[var(--c-text-2)] text-sm">{row.label}</span>
                  <span className={`text-sm font-mono shrink-0 ${QUAL_COLOR[row.color] ?? 'text-[var(--c-text-1)]'}`}>
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
            {data.fix_attempts?.length > 0 && (
              <div className="mt-4 pt-3 border-t border-[var(--c-border)]">
                <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-2">Fix Attempt Distribution</p>
                <div className="space-y-1.5">
                  {data.fix_attempts.map((a, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-[var(--c-text-3)]">{a.label}</span>
                      <span className="text-[var(--c-text-1b)] font-mono">{a.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Section>
        )}
      </div>

      {/* Per-image breakdown */}
      {(data.images?.approved_first?.length > 0 ||
        data.images?.approved_fixed?.length > 0 ||
        data.images?.flagged?.length > 0) && (
        <div className="mb-8">
          <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-4">Per-Image Quality Report</p>

          <div className="space-y-4">

            {/* Approved first pass */}
            {data.images.approved_first.length > 0 && (
              <ImageGroup
                icon={<CheckCircle size={13} className="text-green-400" />}
                title={`Approved — First Pass (${data.images.approved_first.length})`}
                color="green"
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 p-3">
                  {data.images.approved_first.map((f, i) => (
                    <span key={i} className="font-mono text-[11px] text-[var(--c-text-2)] truncate">{f}</span>
                  ))}
                </div>
              </ImageGroup>
            )}

            {/* Approved after fix */}
            {data.images.approved_fixed.length > 0 && (
              <ImageGroup
                icon={<CheckCircle size={13} className="text-yellow-400" />}
                title={`Approved — After Automated Fix (${data.images.approved_fixed.length})`}
                color="yellow"
              >
                <div className="divide-y divide-[var(--c-border)]">
                  {data.images.approved_fixed.map((img, i) => (
                    <div key={i} className="p-3">
                      <div className="font-mono text-[11px] text-[var(--c-text-1b)] mb-1">{img.image}</div>
                      {img.failures && img.failures !== 'None' && (
                        <div className="text-[11px] text-[var(--c-text-3)] mb-1">
                          <span className="text-[var(--c-text-4)]">Issue: </span>{img.failures}
                        </div>
                      )}
                      {img.fix && (
                        <div className="text-[11px] text-[var(--c-text-3)]">
                          <span className="text-[var(--c-text-4)]">Fix: </span>{img.fix}
                        </div>
                      )}
                      {img.attempts > 0 && (
                        <div className="text-[10px] text-yellow-400/70 mt-0.5">attempt {img.attempts}</div>
                      )}
                    </div>
                  ))}
                </div>
              </ImageGroup>
            )}

            {/* Flagged */}
            {data.images.flagged.length > 0 && (
              <ImageGroup
                icon={<AlertTriangle size={13} className="text-orange-400" />}
                title={`Flagged for Manual Review (${data.images.flagged.length})`}
                color="orange"
              >
                <div className="divide-y divide-[var(--c-border)]">
                  {data.images.flagged.map((img, i) => (
                    <div key={i} className="p-3">
                      <div className="font-mono text-[11px] text-[var(--c-text-1b)] mb-1">{img.image}</div>
                      {img.failure && (
                        <div className="text-[11px] text-[var(--c-text-3)]">
                          <span className="text-[var(--c-text-4)]">Issue: </span>{img.failure}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </ImageGroup>
            )}
          </div>
        </div>
      )}

      {/* API costs */}
      {data.api && (
        <Section title="API Usage & Cost" className="mb-8">
          <div className="space-y-3">
            {[data.api.image_model, data.api.text_model].map((model, i) => (
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

      {/* Recommendations */}
      {data.recommendations?.length > 0 && (
        <Section title="Recommendations for Next Sprint">
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

const QUAL_COLOR = {
  green:  'text-green-400',
  yellow: 'text-yellow-400',
  blue:   'text-blue-400',
  orange: 'text-orange-400',
}

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

const BORDER_COLOR = {
  green:  'border-green-400/30',
  yellow: 'border-yellow-400/30',
  orange: 'border-orange-400/30',
}

const BG_COLOR = {
  green:  'bg-green-400/5',
  yellow: 'bg-yellow-400/5',
  orange: 'bg-orange-400/5',
}

function ImageGroup({ icon, title, color, children }) {
  const [open, setOpen] = useState(true)
  return (
    <div className={`border rounded-lg overflow-hidden ${BORDER_COLOR[color] ?? 'border-[var(--c-border)]'}`}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-2 px-4 py-3 text-left ${BG_COLOR[color] ?? ''} hover:brightness-110 transition-all`}
      >
        {icon}
        <span className="text-sm font-medium text-[var(--c-text-1)]">{title}</span>
        <span className="ml-auto text-[var(--c-text-4)] text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="bg-[var(--c-surface)]">
          {children}
        </div>
      )}
    </div>
  )
}
