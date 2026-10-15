import { useState } from 'react'
import type { PaymentRequest } from '../api'
import { agentMeta, money } from '../agents'

const KIND_LABEL: Record<PaymentRequest['kind'], string> = { invoice: 'Vendor invoice', rent: 'Rent', purchase_order: 'Purchase order' }

function describe(r: PaymentRequest) {
  if (r.kind === 'invoice') return `Invoice #${r.ref_id} · due ${r.period}`
  if (r.kind === 'rent') return `Lease #${r.ref_id} · due ${r.period}`
  return `${r.qty} × ${r.sku} ${r.size} · arrives ~${r.expected_arrival}`
}

export function Approvals({ requests, selectedTicket, onDecide, balance }: {
  requests: PaymentRequest[]
  selectedTicket: number | null
  onDecide: (id: number, approve: boolean, approver: string) => Promise<void>
  balance: number | null
}) {
  const [approver, setApprover] = useState(() => localStorage.getItem('approver') ?? '')
  const [busy, setBusy] = useState<number | null>(null)
  const pending = requests
    .filter((r) => r.status === 'pending_approval')
    .sort((a, b) => Number(b.ticket_id === selectedTicket) - Number(a.ticket_id === selectedTicket) || a.id - b.id)
  const decided = requests.filter((r) => r.status !== 'pending_approval').slice(-4).reverse()

  const decide = async (id: number, approve: boolean) => {
    setBusy(id)
    localStorage.setItem('approver', approver)
    await onDecide(id, approve, approver.trim())
    setBusy(null)
  }

  return (
    <section className="panel approvals" aria-labelledby="appr-h">
      <h2 id="appr-h" className="panel-title">
        Approvals {pending.length > 0 && <span className="count-badge">{pending.length}</span>}
      </h2>
      <label className="approver">
        Signing as
        <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" />
      </label>
      {pending.length === 0 && <p className="muted">No payments or purchases are waiting on you.</p>}
      <ul className="req-list">
        {pending.map((r) => {
          const by = agentMeta(r.requested_by)
          const short = balance !== null && balance < r.amount
          return (
            <li key={r.id} className={`req ${r.ticket_id === selectedTicket ? 'here' : ''}`}>
              <div className="req-top">
                <span className="req-kind">{KIND_LABEL[r.kind]}</span>
                <span className="req-amount">{money(r.amount)}</span>
              </div>
              <div className="req-payee">to {r.payee}</div>
              <div className="req-detail">{describe(r)} · ticket #{r.ticket_id}</div>
              {r.reason && <div className="req-reason">“{r.reason}”</div>}
              <div className="req-by" style={{ color: by?.ink }}>prepared by {r.requested_by}</div>
              {short && <div className="req-warn">Checking can't cover this; approval will be refused.</div>}
              <div className="req-actions">
                <button className="brass-btn approve" disabled={!approver.trim() || busy === r.id} onClick={() => decide(r.id, true)}>
                  {busy === r.id ? 'Stamping…' : 'Approve & pay'}
                </button>
                <button className="brass-btn ghost" disabled={!approver.trim() || busy === r.id} onClick={() => decide(r.id, false)}>
                  Reject
                </button>
              </div>
              {!approver.trim() && <div className="req-hint">Enter your name to sign.</div>}
            </li>
          )
        })}
      </ul>
      {decided.length > 0 && (
        <>
          <h3 className="sub-title">Recently decided</h3>
          <ul className="decided">
            {decided.map((r) => (
              <li key={r.id}>
                <span className={`mini-tag tag-${r.status}`}>{r.status}</span> {KIND_LABEL[r.kind]} {money(r.amount)}
                {r.decided_by && <span className="muted"> · {r.decided_by}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
