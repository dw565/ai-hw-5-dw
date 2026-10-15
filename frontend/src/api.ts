// Thin client for the FastAPI backend (backend/main.py). All numbers on screen come from here.

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'

export type TicketStatus = 'open' | 'in_progress' | 'awaiting_approval' | 'blocked' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  is_open: boolean
}

export interface Cash {
  account: string
  balance: number
  outstanding_requests_total: number
  balance_after_outstanding: number
  as_of: string
}

export interface PaymentRequest {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  period: string | null
  payee: string
  amount: number
  account: string
  ticket_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  expected_arrival: string | null
  reason: string | null
  requested_by: string
  status: 'pending_approval' | 'approved' | 'rejected' | 'paid'
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  payment_id: number | null
  created_at: string
}

export interface ToolCall {
  tool: string
  args: unknown
  result: unknown
  outcome: 'ok' | 'refused' | 'error' | 'retry' | 'output'
}

export interface AgentEvent {
  id: number
  timestamp: string
  run_id: string
  ticket_id: number | null
  agent: string
  event: 'reset' | 'run_start' | 'run_end' | 'agent_start' | 'loop_step' | 'delegation' | 'agent_end' | 'error'
  depth: number
  invocation_id: string
  parent_invocation_id: string | null
  said: string | null
  tools: { tool: string; outcome: ToolCall['outcome'] }[]
  tool_calls: ToolCall[]
  delegation: { from: string; to: string; question: string; refused: string | null } | null
  output: Record<string, unknown> | null
  ended: string | null
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'queued' | 'running' | 'completed' | 'failed'
  result: { ok: boolean; error?: string; decision?: Record<string, unknown>; usage?: Record<string, number> } | null
}

export interface Health {
  ok: boolean
  model: string
  busy: boolean
  shop_date: string
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return body as T
}

export const api = {
  health: () => call<Health>('/api/health'),
  tickets: () => call<Ticket[]>('/api/tickets'),
  cash: () => call<Cash>('/api/cash'),
  payments: () => call<PaymentRequest[]>('/api/payments'),
  events: (after: number) => call<{ events: AgentEvent[]; last_id: number }>(`/api/events?after=${after}&limit=1000`),
  runTicket: (id: number) => call<Run>(`/api/tickets/${id}/run`, { method: 'POST' }),
  run: (runId: string) => call<Run>(`/api/runs/${runId}`),
  approve: (id: number, approver: string, note = '') =>
    call<{ ok: boolean; cash: Cash }>(`/api/payments/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver, note }) }),
  reject: (id: number, approver: string, note = '') =>
    call<{ ok: boolean }>(`/api/payments/${id}/reject`, { method: 'POST', body: JSON.stringify({ approver, note }) }),
  reset: () => call<{ ok: boolean }>('/api/reset', { method: 'POST' }),
}
