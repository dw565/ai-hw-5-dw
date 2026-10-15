import { useMemo, useState } from 'react'
import { STATUS_LABEL, money } from './agents'
import { ActivityFeed } from './components/ActivityFeed'
import { AgentRoster } from './components/AgentRoster'
import { AgentSummary } from './components/AgentSummary'
import { Approvals } from './components/Approvals'
import { CashGauge } from './components/CashGauge'
import { Gear } from './components/Emblems'
import { TicketList } from './components/TicketList'
import { useDesk } from './useDesk'

export default function App() {
  const desk = useDesk()
  const { tickets, events, run, running } = desk
  // ?ticket=102 opens the board on that ticket (handy for links and screenshots).
  const [selected, setSelectedState] = useState<number | null>(() => Number(new URLSearchParams(location.search).get('ticket')) || null)
  const setSelected = (id: number) => {
    setSelectedState(id)
    history.replaceState(null, '', `?ticket=${id}`)
  }
  const selectedId = selected ?? tickets[0]?.id ?? null
  const ticket = tickets.find((t) => t.id === selectedId) ?? null

  // Latest run on this ticket: the one in flight, else the newest one in the audit trail.
  const runId = useMemo(() => {
    if (run && run.ticket_id === selectedId) return run.run_id
    for (let i = events.length - 1; i >= 0; i--) if (events[i].ticket_id === selectedId) return events[i].run_id
    return null
  }, [events, run, selectedId])

  const feed = useMemo(
    () => (runId ? events.filter((e) => e.run_id === runId && (e.ticket_id === selectedId || e.ticket_id === null)) : []),
    [events, runId, selectedId],
  )

  const { active, involved } = useMemo(() => {
    const open = new Map<string, string>()
    const seen = new Set<string>()
    for (const e of feed) {
      if (e.agent === 'system') continue
      seen.add(e.agent)
      if (e.event === 'agent_start') open.set(e.invocation_id, e.agent)
      if (e.event === 'agent_end' || e.event === 'error') open.delete(e.invocation_id)
    }
    const live = running && run?.ticket_id === selectedId ? new Set(open.values()) : new Set<string>()
    return { active: live, involved: seen }
  }, [feed, running, run, selectedId])

  const runHere = run && run.ticket_id === selectedId ? run : null
  const decision = runHere?.result?.decision as { ticket_status?: string; decision?: string } | undefined
  const pendingHere = desk.payments.filter((p) => p.ticket_id === selectedId && p.status === 'pending_approval')

  return (
    <div className={`desk ${running ? 'is-running' : ''}`}>
      <header className="masthead">
        <div className="mast-gears" aria-hidden="true">
          <Gear className="mg g1" teeth={12} />
          <Gear className="mg g2" teeth={8} />
        </div>
        <div className="nameplate">
          <h1>Campus Customs</h1>
          <p className="tagline">Operations Desk · Est. on Chapel Street</p>
          <p className="mast-meta">
            Shop date <b>{desk.health?.shop_date ?? '—'}</b> · agents run on <code>{desk.health?.model ?? '—'}</code>
          </p>
        </div>
        <CashGauge cash={desk.cash} />
        <button
          className="brass-btn reset"
          disabled={running}
          onClick={() => window.confirm('Restore the working database to the original values?') && desk.reset()}
          title="Restore data/campus_customs_new.db from the original"
        >
          Reset shop
        </button>
      </header>

      {desk.error && (
        <div className="alert" role="alert">
          {desk.error} <button className="link" onClick={() => desk.setError(null)}>dismiss</button>
        </div>
      )}

      <main className="grid">
        <TicketList tickets={tickets} selected={selectedId} onSelect={setSelected} runningTicket={running ? run?.ticket_id ?? null : null} />

        <div className="center">
          {ticket && (
            <section className={`panel ticket-head status-${ticket.status}`}>
              <div className="th-text">
                <div className="th-no">Ticket No. {ticket.id} · {ticket.requester}</div>
                <h2 className="th-subject">{ticket.subject}</h2>
                <p className="th-notes">{ticket.notes}</p>
                <span className={`status-tag tag-${ticket.status}`}>{STATUS_LABEL[ticket.status] ?? ticket.status}</span>
                {pendingHere.length > 0 && (
                  <span className="th-pending">· {pendingHere.length} payment{pendingHere.length > 1 ? 's' : ''} awaiting your approval ({money(pendingHere.reduce((s, p) => s + p.amount, 0))})</span>
                )}
              </div>
              <button
                className={`lever ${running && run?.ticket_id === ticket.id ? 'pulled' : ''}`}
                disabled={running || ticket.status === 'resolved'}
                onClick={() => desk.startRun(ticket.id)}
              >
                <span className="lever-handle" aria-hidden="true" />
                <span className="lever-label">
                  {running && run?.ticket_id === ticket.id ? 'Team at work…' : runId ? 'Run the team again' : 'Set the team to work'}
                </span>
              </button>
              {ticket.status === 'resolved' && <div className="stamp big" aria-label="Resolved">Resolved</div>}
            </section>
          )}

          {runHere && !running && runHere.result && (
            <div className={`verdict ${runHere.result.ok ? '' : 'failed'}`} role="status">
              {runHere.result.ok ? (
                <>
                  <b>Boss's verdict: {STATUS_LABEL[decision?.ticket_status ?? ''] ?? decision?.ticket_status}.</b> {decision?.decision}
                  {ticket && ticket.status !== 'resolved' && (
                    <div className="verdict-next">
                      Not closed yet. {pendingHere.length > 0 ? 'Approve the pending payment(s), then ' : ''}run the team again when the blocker clears so Boss can close it.
                    </div>
                  )}
                </>
              ) : (
                <><b>The run failed.</b> {runHere.result.error}</>
              )}
            </div>
          )}

          <AgentRoster active={active} involved={involved} />
          <ActivityFeed events={feed} running={running} />
          <AgentSummary events={feed} />
        </div>

        <aside className="side">
          <Approvals requests={desk.payments} selectedTicket={selectedId} onDecide={desk.decide} balance={desk.cash?.balance ?? null} />
        </aside>
      </main>

      <footer className="foot">All figures and activity are read live from the backend at <code>localhost:8000</code>. Nothing is sent to customers or vendors; drafts stay on the board.</footer>
    </div>
  )
}
