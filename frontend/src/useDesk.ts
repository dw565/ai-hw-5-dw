import { useCallback, useEffect, useRef, useState } from 'react'
import { api, API_BASE, type AgentEvent, type Cash, type Health, type PaymentRequest, type Run, type Ticket } from './api'

const FAST_MS = 1200
const SLOW_MS = 6000

/** Everything the desk shows, kept in sync with the backend by polling. */
export function useDesk() {
  const [health, setHealth] = useState<Health | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [payments, setPayments] = useState<PaymentRequest[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const lastId = useRef(-1)

  const running = run !== null && (run.status === 'queued' || run.status === 'running')

  const refreshBoard = useCallback(async () => {
    try {
      const [h, t, c, p] = await Promise.all([api.health(), api.tickets(), api.cash(), api.payments()])
      setHealth(h)
      setTickets(t)
      setCash(c)
      setPayments(p)
      setError(null)
    } catch (e) {
      setError(`Can't reach the backend at ${API_BASE}. Is uvicorn running? (${(e as Error).message})`)
    }
  }, [])

  const pulling = useRef(false)

  const pullEvents = useCallback(async () => {
    if (pulling.current) return // overlapping polls would append the same events twice
    pulling.current = true
    try {
      const { events: fresh, last_id } = await api.events(lastId.current)
      if (last_id < lastId.current) {
        // audit file was replaced; start over
        lastId.current = -1
        setEvents([])
        return
      }
      if (fresh.length) {
        setEvents((prev) => {
          const seen = new Set(prev.map((e) => e.id))
          return [...prev, ...fresh.filter((e) => !seen.has(e.id))]
        })
      }
      lastId.current = last_id
    } catch {
      /* surfaced by refreshBoard */
    } finally {
      pulling.current = false
    }
  }, [])

  // Initial load + background polling (faster while the team is working).
  useEffect(() => {
    void refreshBoard()
    void pullEvents()
  }, [refreshBoard, pullEvents])

  useEffect(() => {
    const ms = running ? FAST_MS : SLOW_MS
    const timer = setInterval(() => {
      void pullEvents()
      if (!running) void refreshBoard()
    }, ms)
    return () => clearInterval(timer)
  }, [running, pullEvents, refreshBoard])

  // While a run is active, follow its status; when it ends, refresh tickets / cash / requests.
  useEffect(() => {
    if (!run || !running) return
    const timer = setInterval(async () => {
      try {
        const latest = await api.run(run.run_id)
        if (latest.status !== 'queued' && latest.status !== 'running') {
          setRun(latest)
          await pullEvents()
          await refreshBoard()
        } else if (latest.status !== run.status) {
          setRun(latest)
        }
      } catch (e) {
        setError((e as Error).message)
      }
    }, FAST_MS)
    return () => clearInterval(timer)
  }, [run, running, pullEvents, refreshBoard])

  const startRun = useCallback(async (ticketId: number) => {
    setError(null)
    try {
      setRun(await api.runTicket(ticketId))
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  const decide = useCallback(
    async (id: number, approve: boolean, approver: string) => {
      setError(null)
      try {
        if (approve) await api.approve(id, approver)
        else await api.reject(id, approver)
      } catch (e) {
        setError((e as Error).message)
      }
      await refreshBoard()
    },
    [refreshBoard],
  )

  const reset = useCallback(async () => {
    setError(null)
    try {
      await api.reset()
      setRun(null)
    } catch (e) {
      setError((e as Error).message)
    }
    await refreshBoard()
  }, [refreshBoard])

  return { health, tickets, cash, payments, events, run, running, error, setError, startRun, decide, reset, refreshBoard }
}
