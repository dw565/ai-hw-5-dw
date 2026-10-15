import { AGENTS } from '../agents'
import { Gear } from './Emblems'

/** The five stations. An active agent's gear spins and its chimney puffs steam. */
export function AgentRoster({ active, involved }: { active: Set<string>; involved: Set<string> }) {
  return (
    <div className="roster" role="list" aria-label="Agents">
      {AGENTS.map((a) => {
        const isActive = active.has(a.name)
        const wasInvolved = involved.has(a.name)
        return (
          <div
            key={a.key}
            role="listitem"
            className={`agent-card ${isActive ? 'active' : ''} ${wasInvolved ? 'involved' : ''}`}
            style={{ ['--ink' as string]: a.ink }}
            aria-label={`${a.name}${isActive ? ' (working)' : ''}`}
          >
            <div className="agent-emblem">
              <a.Emblem className="emblem" />
              <Gear className="agent-gear" teeth={8} />
              {isActive && (
                <span className="steam" aria-hidden="true">
                  <i /><i /><i />
                </span>
              )}
            </div>
            <div className="agent-name">{a.name}</div>
            <div className="agent-title">{a.title}</div>
            <div className="agent-state">{isActive ? 'At work' : wasInvolved ? 'Reported in' : 'Standing by'}</div>
          </div>
        )
      })}
    </div>
  )
}
