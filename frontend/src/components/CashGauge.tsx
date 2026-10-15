import { useEffect, useRef, useState } from 'react'
import type { Cash } from '../api'
import { money } from '../agents'

/** Brass pressure-gauge for the checking balance. The dial is decoration; the readout is the number. */
export function CashGauge({ cash }: { cash: Cash | null }) {
  const balance = cash?.balance ?? 0
  const max = Math.max(4000, Math.ceil(balance / 1000) * 1000)
  const angle = -120 + (Math.min(balance, max) / max) * 240
  const prev = useRef<number | null>(null)
  const [delta, setDelta] = useState<number | null>(null)

  useEffect(() => {
    if (cash == null) return
    if (prev.current !== null && cash.balance !== prev.current) {
      setDelta(cash.balance - prev.current)
      const t = setTimeout(() => setDelta(null), 6000)
      prev.current = cash.balance
      return () => clearTimeout(t)
    }
    prev.current = cash.balance
  }, [cash])

  const ticks = Array.from({ length: 9 }, (_, i) => -120 + i * 30)

  return (
    <div className="gauge" aria-label={`Checking balance ${money(balance)}`}>
      <svg viewBox="0 0 200 140" className="gauge-dial" aria-hidden="true">
        <defs>
          <radialGradient id="face" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stopColor="#fbf3dc" />
            <stop offset="100%" stopColor="#e6d5a8" />
          </radialGradient>
          <linearGradient id="bezel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#f1d27a" />
            <stop offset="50%" stopColor="#a87b2c" />
            <stop offset="100%" stopColor="#6f4b17" />
          </linearGradient>
        </defs>
        <circle cx="100" cy="92" r="78" fill="url(#bezel)" />
        <circle cx="100" cy="92" r="68" fill="url(#face)" />
        <path d="M 41 126 A 68 68 0 0 1 41 58" stroke="#a5372b" strokeWidth="6" fill="none" opacity=".55" transform="rotate(-30 100 92)" />
        {ticks.map((a, i) => (
          <g key={a} transform={`rotate(${a} 100 92)`}>
            <line x1="100" y1="30" x2="100" y2={i % 2 === 0 ? 42 : 38} stroke="#3b2a1a" strokeWidth={i % 2 === 0 ? 2.2 : 1.2} />
            {i % 2 === 0 && (
              <text x="100" y="52" textAnchor="middle" fontSize="9" fill="#3b2a1a" fontFamily="Cinzel" transform={`rotate(${-a} 100 52)`}>
                {((max / 8) * i) / 1000}k
              </text>
            )}
          </g>
        ))}
        <text x="100" y="118" textAnchor="middle" fontSize="8" fill="#6b5233" fontFamily="Cinzel" letterSpacing="1">CHECKING</text>
        <g className="needle" style={{ transform: `rotate(${angle}deg)` }}>
          <path d="M100 92 L97 88 L100 34 L103 88 Z" fill="#7a1f1f" />
        </g>
        <circle cx="100" cy="92" r="7" fill="url(#bezel)" stroke="#3b2a1a" strokeWidth="1" />
      </svg>
      <div className="gauge-readout">
        <span className="gauge-amount">{cash ? money(balance) : '—'}</span>
        {delta !== null && <span className={`gauge-delta ${delta < 0 ? 'down' : 'up'}`}>{delta < 0 ? '−' : '+'}{money(Math.abs(delta))}</span>}
      </div>
      {cash && (
        <div className="gauge-sub">
          {cash.outstanding_requests_total > 0
            ? <>Awaiting approval: {money(cash.outstanding_requests_total)} · after: {money(cash.balance_after_outstanding)}</>
            : <>No payments awaiting approval</>}
        </div>
      )}
    </div>
  )
}
