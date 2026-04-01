import { useEffect, useState } from 'react'
import { FileText, Calendar, CheckCircle2, Ban, Megaphone } from 'lucide-react'
import { api } from '../lib/api'

// ── Pillar colour palette ────────────────────────────────────────────────────

const PILLAR_COLORS = [
  { bg: 'bg-blue-500',    text: 'text-blue-400',    soft: 'bg-blue-500/10',    border: 'border-blue-500/20'    },
  { bg: 'bg-emerald-500', text: 'text-emerald-400', soft: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  { bg: 'bg-violet-500',  text: 'text-violet-400',  soft: 'bg-violet-500/10',  border: 'border-violet-500/20'  },
  { bg: 'bg-orange-500',  text: 'text-orange-400',  soft: 'bg-orange-500/10',  border: 'border-orange-500/20'  },
  { bg: 'bg-teal-500',    text: 'text-teal-400',    soft: 'bg-teal-500/10',    border: 'border-teal-500/20'    },
  { bg: 'bg-pink-500',    text: 'text-pink-400',    soft: 'bg-pink-500/10',    border: 'border-pink-500/20'    },
]

// Maps the month keys from copy_strategy.md to month numbers (1-12)
const SEASON_MONTHS = {
  'JANUARY-FEBRUARY':  [1, 2],
  'MARCH':             [3],
  'APRIL-MAY':         [4, 5],
  'JUNE-AUGUST':       [6, 7, 8],
  'SEPTEMBER':         [9],
  'OCTOBER-NOVEMBER':  [10, 11],
  'DECEMBER':          [12],
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function Org() {
  const [data,     setData]     = useState(null)
  const [concept,  setConcept]  = useState(null)
  const [products, setProducts] = useState([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    Promise.all([
      api.brand(),
      api.concept().catch(() => null),
      api.products().catch(() => []),
    ]).then(([brand, con, prods]) => {
      setData(brand)
      setConcept(con)
      setProducts(prods ?? [])
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  const { files = [], voice = {}, calendar = {}, upcoming_events = [] } = data ?? {}
  const currentMonth  = new Date().getMonth() + 1   // 1–12
  const currentSeason = voice.seasonal?.find(s =>
    (SEASON_MONTHS[s.months] ?? []).includes(currentMonth)
  )

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-5xl">

      {/* ── Header ── */}
      <div className="mb-6">
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-1">Brand</p>
        <h1 className="text-2xl text-[var(--c-text-1)] font-semibold">The Lunch Bags</h1>
        <p className="text-[var(--c-text-3)] text-sm mt-1">
          Brand identity and content strategy used by the AI agents — review before each sprint
        </p>
      </div>

      {/* ── File freshness ── */}
      {(files.length > 0 || concept) && (
        <div className="flex flex-wrap gap-3 mb-8">
          {files.map(f => <FreshnessCard key={f.name} file={f} />)}
          {concept && (
            <FreshnessCard file={{ name: 'concept.md', last_modified: concept.last_modified }} />
          )}
        </div>
      )}

      {/* ── Today's context ── */}
      {(currentSeason || upcoming_events.length > 0) && (
        <Section title="Today's Context">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {currentSeason && (
              <InfoCard>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />
                  <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Active Season</span>
                </div>
                <div className="text-[var(--c-text-1)] font-semibold mb-1">
                  {fmtMonthKey(currentSeason.months)}
                </div>
                {currentSeason.tone && (
                  <div className="text-blue-400 text-sm italic mb-2">{currentSeason.tone}</div>
                )}
                <p className="text-[var(--c-text-2)] text-sm leading-relaxed">{currentSeason.context}</p>
              </InfoCard>
            )}

            {upcoming_events.length > 0 && (
              <InfoCard>
                <div className="flex items-center gap-2 mb-3">
                  <Calendar size={13} className="text-[var(--c-text-3)]" />
                  <span className="text-xs text-[var(--c-text-3)] uppercase tracking-wider">Upcoming (30 days)</span>
                </div>
                <div className="space-y-2.5">
                  {upcoming_events.map((ev, i) => (
                    <div key={i} className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        {ev.posting === 'pause'
                          ? <Ban size={12} className="text-red-400 shrink-0" />
                          : <CheckCircle2 size={12} className="text-green-400 shrink-0" />
                        }
                        <span className="text-[var(--c-text-1)] text-sm truncate">{ev.name}</span>
                      </div>
                      <div className="shrink-0 flex items-center gap-2">
                        {ev.posting === 'pause' && (
                          <span className="text-xs bg-red-500/10 text-red-400 border border-red-500/20 px-1.5 py-0.5 rounded">
                            no post
                          </span>
                        )}
                        <span className="text-[var(--c-text-3)] text-xs tabular-nums">
                          {ev.days_until === 0 ? 'today' : `${ev.days_until}d`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </InfoCard>
            )}

          </div>
        </Section>
      )}

      {/* ── Sprint Concept ── */}
      {concept && (
        <Section title="Current Sprint Concept">
          <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-5 mb-4">
            <div className="flex items-start justify-between gap-4 mb-3">
              <h2 className="text-[var(--c-text-1)] font-semibold text-lg">{concept.title}</h2>
            </div>
            {concept.narrative && (
              <p className="text-[var(--c-text-2)] text-sm leading-relaxed">{concept.narrative}</p>
            )}
          </div>

          {concept.sets?.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
              {concept.sets.map(set => (
                <div key={set.number} className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-[var(--c-text-3)] bg-[var(--c-surface-2)] px-2 py-0.5 rounded">
                      Set {set.number}
                    </span>
                    <span className="text-[var(--c-text-1)] text-sm font-medium">{set.name}</span>
                  </div>
                  {set.location && (
                    <p className="text-[var(--c-text-3)] text-xs mb-1.5">
                      <span className="text-[var(--c-text-2)]">Location: </span>{set.location}
                    </p>
                  )}
                  {set.energy && (
                    <p className="text-[var(--c-text-3)] text-xs mb-1.5">
                      <span className="text-[var(--c-text-2)]">Energy: </span>{set.energy}
                    </p>
                  )}
                  {set.props && (
                    <p className="text-[var(--c-text-3)] text-xs">
                      <span className="text-[var(--c-text-2)]">Props: </span>{set.props}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {concept.visual_direction?.length > 0 && (
            <InfoCard label="Visual Direction">
              <ul className="space-y-1.5">
                {concept.visual_direction.map((d, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-[var(--c-text-4)] mt-0.5 shrink-0 select-none">–</span>
                    <span className="text-[var(--c-text-2)] text-sm leading-snug">{d}</span>
                  </li>
                ))}
              </ul>
            </InfoCard>
          )}
        </Section>
      )}

      {/* ── Product References ── */}
      {products.length > 0 && (
        <Section title="Product References">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
            {products.map(p => (
              <div key={p.filename} className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg overflow-hidden">
                <div className="aspect-square bg-[var(--c-surface-2)]">
                  <img
                    src={api.imageUrl(p.path)}
                    alt={p.name}
                    className="w-full h-full object-cover"
                    onError={e => { e.target.style.display = 'none' }}
                  />
                </div>
                <div className="px-2 py-1.5">
                  <p className="text-[var(--c-text-3)] text-xs truncate">{p.name}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── Brand Identity ── */}
      <Section title="Brand Identity">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <InfoCard label="Who We Are">
            <p className="text-[var(--c-text-2)] text-sm leading-relaxed">{voice.who_we_are}</p>
          </InfoCard>
          <InfoCard label="Who We Talk To">
            <p className="text-[var(--c-text-2)] text-sm leading-relaxed">{voice.who_we_talk_to}</p>
          </InfoCard>
        </div>
      </Section>

      {/* ── Voice & Beliefs ── */}
      <Section title="Voice & Core Beliefs">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <InfoCard label="Brand Voice">
            <p className="text-[var(--c-text-2)] text-sm leading-relaxed">{voice.brand_voice}</p>
          </InfoCard>
          <InfoCard label="Core Beliefs">
            <ul className="space-y-2">
              {voice.core_beliefs?.map((b, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-blue-400 mt-0.5 shrink-0 select-none">–</span>
                  <span className="text-[var(--c-text-2)] text-sm leading-snug">{b}</span>
                </li>
              ))}
            </ul>
          </InfoCard>
        </div>
      </Section>

      {/* ── Caption Guidelines ── */}
      <Section title="Caption Guidelines">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <InfoCard label="Rules" accentBorder="border-green-500/20">
            <ul className="space-y-2">
              {voice.caption_rules?.map((r, i) => (
                <li key={i} className="flex items-start gap-2">
                  <CheckCircle2 size={13} className="text-green-400 mt-0.5 shrink-0" />
                  <span className="text-[var(--c-text-2)] text-sm leading-snug">{r}</span>
                </li>
              ))}
            </ul>
          </InfoCard>
          <InfoCard label="Never" accentBorder="border-red-500/20">
            <ul className="space-y-2">
              {voice.caption_never?.map((r, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Ban size={12} className="text-red-400 mt-0.5 shrink-0" />
                  <span className="text-[var(--c-text-2)] text-sm leading-snug">{r}</span>
                </li>
              ))}
            </ul>
          </InfoCard>
        </div>
      </Section>

      {/* ── Content Pillars ── */}
      <Section title="Content Pillars">
        {voice.pillars?.length > 0 && (
          <>
            {/* Stacked bar */}
            <div className="flex h-4 rounded-lg overflow-hidden gap-px mb-3 bg-[var(--c-surface-2)]">
              {voice.pillars.map((p, i) => (
                <div
                  key={p.name}
                  style={{ width: `${p.pct}%` }}
                  className={PILLAR_COLORS[i]?.bg ?? 'bg-gray-500'}
                  title={`${p.name}: ${p.pct}%`}
                />
              ))}
            </div>
            {/* Legend */}
            <div className="flex flex-wrap gap-x-5 gap-y-1 mb-5">
              {voice.pillars.map((p, i) => (
                <div key={p.name} className="flex items-center gap-1.5">
                  <div className={`w-2.5 h-2.5 rounded-sm ${PILLAR_COLORS[i]?.bg ?? 'bg-gray-500'}`} />
                  <span className="text-xs text-[var(--c-text-3)]">
                    {p.name} <span className="text-[var(--c-text-4)]">{p.pct}%</span>
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Pillar cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {voice.pillars?.map((p, i) => {
            const c = PILLAR_COLORS[i] ?? PILLAR_COLORS[0]
            return (
              <div key={p.name} className={`bg-[var(--c-surface)] border ${c.border} rounded-lg p-4`}>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className={`text-sm font-medium ${c.text}`}>{p.name}</span>
                  <span className={`text-xs font-bold ${c.text} ${c.soft} px-2 py-0.5 rounded-full shrink-0`}>
                    {p.pct}%
                  </span>
                </div>
                {p.description && (
                  <p className="text-[var(--c-text-3)] text-xs leading-relaxed mb-2">{p.description}</p>
                )}
                {p.goal && (
                  <p className="text-[var(--c-text-4)] text-xs">
                    <span className="text-[var(--c-text-3)]">Goal: </span>{p.goal}
                  </p>
                )}
                {p.tone && (
                  <p className="text-[var(--c-text-4)] text-xs mt-0.5">
                    <span className="text-[var(--c-text-3)]">Tone: </span>{p.tone}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </Section>

      {/* ── Posting Schedule ── */}
      <Section title="Posting Schedule">
        <div className="flex flex-wrap gap-4">
          {voice.posting_slots?.map((slot, i) => (
            <div key={i} className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-5 py-4 flex items-center gap-4">
              <div className="text-2xl font-bold text-[var(--c-text-1)] tabular-nums leading-none">{slot.time}</div>
              <div>
                <div className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-2">{slot.label}</div>
                <div className="flex gap-1.5 flex-wrap">
                  {slot.days.map(d => (
                    <span key={d} className="text-xs bg-[var(--c-surface-2)] text-[var(--c-text-2)] px-2 py-0.5 rounded font-medium">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── Seasonal Guide ── */}
      <Section title="Seasonal Guide">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {voice.seasonal?.map((s, i) => {
            const isActive = (SEASON_MONTHS[s.months] ?? []).includes(currentMonth)
            return (
              <div
                key={i}
                className={`rounded-lg p-4 border ${
                  isActive
                    ? 'bg-blue-500/5 border-blue-500/20'
                    : 'bg-[var(--c-surface)] border-[var(--c-border)]'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className={`text-xs font-semibold ${isActive ? 'text-blue-400' : 'text-[var(--c-text-2)]'}`}>
                    {fmtMonthKey(s.months)}
                  </span>
                  {isActive && (
                    <span className="text-[8px] bg-blue-500 text-white px-1.5 py-0.5 rounded-full uppercase font-bold tracking-wide shrink-0">
                      now
                    </span>
                  )}
                </div>
                {s.tone && (
                  <p className="text-[var(--c-text-3)] text-xs italic mb-1.5">{s.tone}</p>
                )}
                <p className="text-[var(--c-text-2)] text-xs leading-relaxed">{s.context}</p>
              </div>
            )
          })}
        </div>
      </Section>

      {/* ── Greek Calendar ── */}
      <Section title="Greek Calendar">
        <div className="space-y-4">

          <InfoCard label="Fixed Holidays">
            <div className="divide-y divide-[var(--c-border)]">
              {calendar.holidays?.map((h, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 gap-3 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-[var(--c-text-3)] text-xs tabular-nums shrink-0 w-10">
                      {fmtDate(h.date)}
                    </span>
                    <span className="text-[var(--c-text-1)] text-sm">{h.name}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      h.type === 'national'
                        ? 'bg-blue-500/10 text-blue-400'
                        : 'bg-purple-500/10 text-purple-400'
                    }`}>
                      {h.type}
                    </span>
                    {h.posting === 'pause' && (
                      <span className="text-xs bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-0.5 rounded flex items-center gap-1">
                        <Ban size={10} /> no post
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </InfoCard>

          <InfoCard label="Commercial Periods">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {calendar.commercial_periods?.map((cp, i) => (
                <div key={i} className="flex gap-3">
                  <Megaphone size={13} className="text-[var(--c-text-3)] shrink-0 mt-0.5" />
                  <div>
                    <div className="text-[var(--c-text-1)] text-sm font-medium">{cp.name}</div>
                    <div className="text-[var(--c-text-3)] text-xs mt-0.5">{cp.note}</div>
                  </div>
                </div>
              ))}
            </div>
          </InfoCard>

        </div>
      </Section>

    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtMonthKey(key) {
  return key
    .split('-')
    .map(m => m[0] + m.slice(1).toLowerCase())
    .join(' – ')
}

function fmtDate(mmdd) {
  const [mm, dd] = mmdd.split('-')
  return new Date(2000, parseInt(mm, 10) - 1, parseInt(dd, 10))
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// ── Sub-components ────────────────────────────────────────────────────────────

function FreshnessCard({ file }) {
  const days  = Math.floor((Date.now() - new Date(file.last_modified).getTime()) / 86_400_000)
  const state = days < 30 ? 'recent' : days < 90 ? 'aging' : 'stale'
  const cls   = {
    recent: 'text-green-400 border-green-500/20 bg-green-500/5',
    aging:  'text-orange-400 border-orange-500/20 bg-orange-500/5',
    stale:  'text-red-400 border-red-500/20 bg-red-500/5',
  }[state]
  const label = { recent: 'Up to date', aging: 'Review soon', stale: 'Needs review' }[state]

  return (
    <div className={`flex items-center gap-3 border rounded-lg px-4 py-3 ${cls}`}>
      <FileText size={14} className="shrink-0" />
      <div className="min-w-0">
        <div className="text-[var(--c-text-1)] text-sm font-medium truncate">{file.name}</div>
        <div className="text-xs mt-0.5">
          {label} · {days === 0 ? 'updated today' : `${days}d ago`}
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="mb-8">
      <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-4">{title}</p>
      {children}
    </div>
  )
}

function InfoCard({ label, children, accentBorder }) {
  return (
    <div className={`bg-[var(--c-surface)] border ${accentBorder ?? 'border-[var(--c-border)]'} rounded-lg p-5`}>
      {label && (
        <p className="text-xs text-[var(--c-text-3)] uppercase tracking-wider mb-3">{label}</p>
      )}
      {children}
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
