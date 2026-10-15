import type { Ticket } from '../api'
import { STATUS_LABEL } from '../agents'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

function detail(t: Ticket): string {
  if (t.sku) return `${t.qty ?? '?'} × ${t.sku} · ${t.size}`
  if (t.lease_id) return `Lease #${t.lease_id}`
  return ''
}

export function TicketList({ tickets, selected, onSelect, runningTicket }: {
  tickets: Ticket[]
  selected: number | null
  onSelect: (id: number) => void
  runningTicket: number | null
}) {
  return (
    <section className="panel ledger" aria-labelledby="tickets-h">
      <h2 id="tickets-h" className="panel-title">Ticket Ledger</h2>
      <ul className="ticket-list">
        {tickets.map((t) => (
          <li key={t.id}>
            <button
              className={`ticket-card ${selected === t.id ? 'selected' : ''} status-${t.status}`}
              onClick={() => onSelect(t.id)}
              aria-pressed={selected === t.id}
            >
              <span className="ticket-no">No. {t.id}</span>
              <span className="ticket-type">{TYPE_LABEL[t.type] ?? t.type}</span>
              <span className="ticket-subject">{t.subject}</span>
              <span className="ticket-meta">{t.requester}{detail(t) && ` · ${detail(t)}`}</span>
              <span className={`status-tag tag-${t.status}`}>
                {runningTicket === t.id ? 'Team at work…' : STATUS_LABEL[t.status] ?? t.status}
              </span>
              {t.status === 'resolved' && <span className="stamp small" aria-hidden="true">Resolved</span>}
            </button>
          </li>
        ))}
        {tickets.length === 0 && <li className="muted">No tickets loaded yet.</li>}
      </ul>
    </section>
  )
}
