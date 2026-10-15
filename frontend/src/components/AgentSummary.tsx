import type { AgentEvent } from '../api'
import { AGENTS } from '../agents'

interface Deed {
  steps: number
  tools: Map<string, number>
  askedOf: string[]
  report: string | null
  status: string | null
}

/** "Ledger of Deeds": a short per-agent summary of the latest run on this ticket. */
export function AgentSummary({ events }: { events: AgentEvent[] }) {
  const deeds = new Map<string, Deed>()
  const get = (name: string) => {
    if (!deeds.has(name)) deeds.set(name, { steps: 0, tools: new Map(), askedOf: [], report: null, status: null })
    return deeds.get(name)!
  }
  for (const e of events) {
    if (e.agent === 'system') continue
    const d = get(e.agent)
    if (e.event === 'loop_step') {
      d.steps += 1
      for (const c of e.tool_calls) {
        if (c.tool === 'final_result' || c.tool === 'ask_agent') continue
        d.tools.set(c.tool, (d.tools.get(c.tool) ?? 0) + 1)
      }
    } else if (e.event === 'delegation' && e.delegation && !e.delegation.refused) {
      d.askedOf.push(e.delegation.to)
    } else if (e.event === 'agent_end') {
      d.report = e.said
      d.status = e.ended
    }
  }

  const involved = AGENTS.filter((a) => deeds.has(a.name))
  return (
    <section className="panel deeds" aria-labelledby="deeds-h">
      <h2 id="deeds-h" className="panel-title">Ledger of Deeds <span className="panel-sub">latest run</span></h2>
      {involved.length === 0 ? (
        <p className="muted">Each agent's summary appears here once the team has worked this ticket.</p>
      ) : (
        <ul className="deed-list">
          {involved.map((a) => {
            const d = deeds.get(a.name)!
            const asked = [...new Set(d.askedOf)].map((k) => AGENTS.find((x) => x.key === k)?.name ?? k)
            return (
              <li key={a.key} className="deed" style={{ ['--ink' as string]: a.ink }}>
                <a.Emblem className="deed-emblem" />
                <div className="deed-body">
                  <div className="deed-head">
                    <b>{a.name}</b>
                    {d.status && <span className={`mini-tag tag-${d.status}`}>{d.status.replace('_', ' ')}</span>}
                  </div>
                  {d.report && <p className="deed-report">{d.report}</p>}
                  <p className="deed-stats">
                    {d.steps} step{d.steps === 1 ? '' : 's'}
                    {d.tools.size > 0 && <> · tools: {[...d.tools.entries()].map(([t, n]) => (n > 1 ? `${t} ×${n}` : t)).join(', ')}</>}
                    {asked.length > 0 && <> · asked {asked.join(', ')}</>}
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
