import { useEffect, useRef, type ReactNode } from 'react'
import type { AgentEvent, ToolCall } from '../api'
import { agentMeta } from '../agents'

const OUTCOME_MARK: Record<ToolCall['outcome'], string> = { ok: '✓', refused: '✕', error: '!', retry: '↻', output: '✎' }

function time(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function ToolChip({ call }: { call: ToolCall }) {
  const label = call.tool === 'final_result' ? 'files report' : call.tool === 'ask_agent' ? 'ask_agent' : call.tool
  return (
    <details className={`tool-chip outcome-${call.outcome}`}>
      <summary>
        <span className="tool-mark">{OUTCOME_MARK[call.outcome]}</span>
        {label}
      </summary>
      <div className="tool-detail">
        <div><b>args</b><pre>{JSON.stringify(call.args, null, 2)}</pre></div>
        {call.tool !== 'final_result' && <div><b>result</b><pre>{JSON.stringify(call.result, null, 2)}</pre></div>}
      </div>
    </details>
  )
}

function EventRow({ e }: { e: AgentEvent }) {
  const meta = agentMeta(e.agent)
  const style = { ['--ink' as string]: meta?.ink ?? '#5a4630', marginLeft: `${e.depth * 18}px` }

  if (e.event === 'run_start' || e.event === 'run_end') {
    return <li className="feed-divider">{e.event === 'run_start' ? '⚙ The team assembles' : '⚙ The team stands down'} · {time(e.timestamp)}</li>
  }

  let body: ReactNode
  if (e.event === 'agent_start') {
    body = <p className="feed-said"><i>takes up the task:</i> {e.said}</p>
  } else if (e.event === 'delegation' && e.delegation) {
    const to = agentMeta(e.delegation.to)
    body = (
      <p className="feed-said">
        <span className="handoff">➜ asks <b style={{ color: to?.ink }}>{to?.name ?? e.delegation.to}</b></span>
        {e.delegation.refused ? <span className="refused"> — refused: {e.delegation.refused}</span> : <>: “{e.delegation.question}”</>}
      </p>
    )
  } else if (e.event === 'loop_step') {
    const calls = e.tool_calls.filter((c) => c.tool !== 'final_result')
    const files = e.tool_calls.some((c) => c.tool === 'final_result')
    body = (
      <>
        {e.said && <p className="feed-said">{e.said}</p>}
        {calls.length > 0 && <div className="tool-row">{calls.map((c, i) => <ToolChip key={i} call={c} />)}</div>}
        {files && calls.length === 0 && <p className="feed-said muted"><i>files a report</i></p>}
      </>
    )
  } else if (e.event === 'agent_end') {
    body = (
      <p className="feed-said report">
        <span className={`mini-tag tag-${e.ended}`}>{(e.ended ?? '').replace('_', ' ')}</span> {e.said}
      </p>
    )
  } else if (e.event === 'error') {
    body = <p className="feed-said refused">⚠ {e.said}</p>
  }

  return (
    <li className={`feed-row ev-${e.event}`} style={style}>
      <div className="feed-head">
        {meta && <meta.Emblem className="feed-emblem" />}
        <span className="feed-agent">{e.agent}</span>
        <span className="feed-time">{time(e.timestamp)}</span>
      </div>
      {body}
    </li>
  )
}

export function ActivityFeed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (running) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [events.length, running])

  return (
    <section className="panel tape" aria-labelledby="feed-h" aria-live="polite">
      <h2 id="feed-h" className="panel-title">Live Activity <span className="panel-sub">telegraph tape</span></h2>
      {events.length === 0 ? (
        <p className="muted empty">No activity for this ticket yet. Pull the lever to set the team to work.</p>
      ) : (
        <ol className="feed">
          {events.map((e) => <EventRow key={e.id} e={e} />)}
        </ol>
      )}
      <div ref={end} />
    </section>
  )
}
