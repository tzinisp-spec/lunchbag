import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ChevronRight } from 'lucide-react'
import { AGENTS, AGENT_MAP, COLOR_CLASSES } from '../lib/agents'

export default function AgentDetail() {
  const { agentId } = useParams()
  const navigate    = useNavigate()
  const agent       = AGENT_MAP[agentId]

  if (!agent) {
    return (
      <div className="p-4 sm:p-6 md:p-8">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-[var(--c-text-2)] hover:text-[var(--c-text-1)] text-sm mb-6">
          <ArrowLeft size={15} /> Back
        </button>
        <p className="text-[var(--c-text-3)]">Agent not found.</p>
      </div>
    )
  }

  const c    = COLOR_CLASSES[agent.color]
  const prev = agent.prev ? AGENT_MAP[agent.prev] : null
  const next = agent.next ? AGENT_MAP[agent.next] : null

  return (
    <div className="p-4 sm:p-6 md:p-8 md:max-w-4xl">

      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-[var(--c-text-2)] hover:text-[var(--c-text-1)] text-sm mb-8 transition-colors"
      >
        <ArrowLeft size={15} /> Back
      </button>

      {/* ── Header ── */}
      <div className={`rounded-xl border ${c.border} ${c.bg} px-8 py-7 mb-8 flex items-start gap-6`}>
        <div className={`w-16 h-16 rounded-2xl ${c.bg} border ${c.border} flex items-center justify-center text-3xl shrink-0`}>
          {agent.icon}
        </div>
        <div>
          <span className={`text-xs font-medium uppercase tracking-wider ${c.text} mb-2 block`}>
            {agent.role}
          </span>
          <h1 className="text-3xl text-[var(--c-text-1)] font-semibold mb-2">{agent.name}</h1>
          <p className="text-[var(--c-text-2)] text-sm italic">"{agent.tagline}"</p>
        </div>
      </div>

      {/* ── Goal ── */}
      <Section title="Goal">
        <div className={`rounded-lg border ${c.border} ${c.bg} px-6 py-5`}>
          <p className="text-[var(--c-text-1b)] text-sm leading-relaxed">{agent.goal}</p>
        </div>
      </Section>

      {/* ── What they do ── */}
      <Section title="What they do">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {agent.what_they_do.map((item, i) => (
            <div key={i} className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-5 py-4 flex gap-4">
              <span className="text-xl shrink-0 mt-0.5">{item.icon}</span>
              <div>
                <div className="text-[var(--c-text-1)] text-sm font-medium mb-1">{item.title}</div>
                <div className="text-[var(--c-text-3)] text-xs leading-relaxed">{item.text}</div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── Tasks ── */}
      <Section title="Tasks">
        <div className="space-y-2">
          {agent.tasks.map((task, i) => (
            <div key={i} className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-5 py-4 flex items-start gap-4">
              <div className={`w-6 h-6 rounded-full ${c.bg} border ${c.border} flex items-center justify-center shrink-0 mt-0.5`}>
                <span className={`text-xs font-bold ${c.text}`}>{i + 1}</span>
              </div>
              <div>
                <div className="text-[var(--c-text-1)] text-sm font-medium">{task.name}</div>
                <div className="text-[var(--c-text-3)] text-xs mt-0.5 leading-relaxed">{task.description}</div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── Skills ── */}
      <Section title="Skills">
        <div className="flex flex-wrap gap-2">
          {agent.skills.map((skill, i) => (
            <span key={i} className={`${c.badge} text-xs px-3 py-1.5 rounded-full font-medium`}>
              {skill}
            </span>
          ))}
        </div>
      </Section>

      {/* ── Workflow position ── */}
      <Section title="Workflow position">
        <div className="bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg p-5">
          <div className="flex items-center gap-1 overflow-x-auto pb-1">
            {AGENTS.map((a, i) => {
              const isCurrent = a.id === agent.id
              const ac = COLOR_CLASSES[a.color]
              return (
                <div key={a.id} className="flex items-center gap-1 shrink-0">
                  <Link
                    to={`/agents/${a.id}`}
                    className={`flex flex-col items-center gap-1.5 px-3 py-2.5 rounded-lg transition-colors ${
                      isCurrent
                        ? `${ac.bg} border ${ac.border}`
                        : 'hover:bg-[var(--c-surface-2)]'
                    }`}
                  >
                    <span className="text-lg">{a.icon}</span>
                    <span className={`text-xs font-medium text-center leading-tight ${isCurrent ? 'text-[var(--c-text-1)]' : 'text-[var(--c-text-3)]'}`} style={{ maxWidth: '72px' }}>
                      {a.name.split(' ').slice(-1)[0]}
                    </span>
                    {isCurrent && (
                      <span className={`w-1.5 h-1.5 rounded-full ${ac.dot}`} />
                    )}
                  </Link>
                  {i < AGENTS.length - 1 && (
                    <ChevronRight size={13} className="text-[var(--c-text-4)] shrink-0" />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </Section>

      {/* ── Prev / Next navigation ── */}
      <div className="flex gap-3 mt-2">
        {prev ? (
          <Link
            to={`/agents/${prev.id}`}
            className="flex-1 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-5 py-4 flex items-center gap-3 hover:bg-[var(--c-surface-2)] transition-colors"
          >
            <ArrowLeft size={15} className="text-[var(--c-text-3)] shrink-0" />
            <div>
              <div className="text-[var(--c-text-3)] text-xs">Previous agent</div>
              <div className="text-[var(--c-text-1)] text-sm font-medium">{prev.name}</div>
            </div>
          </Link>
        ) : <div className="flex-1" />}

        {next ? (
          <Link
            to={`/agents/${next.id}`}
            className="flex-1 bg-[var(--c-surface)] border border-[var(--c-border)] rounded-lg px-5 py-4 flex items-center justify-end gap-3 hover:bg-[var(--c-surface-2)] transition-colors"
          >
            <div className="text-right">
              <div className="text-[var(--c-text-3)] text-xs">Next agent</div>
              <div className="text-[var(--c-text-1)] text-sm font-medium">{next.name}</div>
            </div>
            <ArrowRight size={15} className="text-[var(--c-text-3)] shrink-0" />
          </Link>
        ) : <div className="flex-1" />}
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
