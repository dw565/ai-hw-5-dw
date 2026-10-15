// Hand-drawn SVG emblems, one per agent. Strokes use currentColor (the agent's ink);
// brass highlights use the --brass CSS variable.

type P = { className?: string }

export function Gear({ className, teeth = 10 }: P & { teeth?: number }) {
  const r1 = 40
  const r2 = 48
  const pts: string[] = []
  for (let i = 0; i < teeth * 2; i++) {
    const a = (Math.PI * i) / teeth
    const r = i % 2 === 0 ? r2 : r1
    const da = Math.PI / teeth / 2.4
    pts.push(`${50 + r * Math.cos(a - da)},${50 + r * Math.sin(a - da)}`)
    pts.push(`${50 + r * Math.cos(a + da)},${50 + r * Math.sin(a + da)}`)
  }
  return (
    <svg viewBox="0 0 100 100" className={className} aria-hidden="true">
      <polygon points={pts.join(' ')} fill="currentColor" />
      <circle cx="50" cy="50" r="22" fill="var(--wood-dark)" />
      <circle cx="50" cy="50" r="9" fill="currentColor" />
    </svg>
  )
}

/** Boss — top hat and monocle on a chain. */
export function MonocleEmblem({ className }: P) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect x="18" y="6" width="28" height="22" rx="2" fill="currentColor" />
      <rect x="18" y="22" width="28" height="4" fill="var(--brass)" />
      <rect x="10" y="27" width="44" height="5" rx="2.5" fill="currentColor" />
      <circle cx="40" cy="44" r="10" fill="rgba(255,248,225,.35)" stroke="var(--brass)" strokeWidth="3.5" />
      <path d="M36 40 a6 6 0 0 1 6 -2" stroke="#fff" strokeWidth="1.6" fill="none" opacity=".8" />
      <path d="M30.5 47 C 22 52, 18 55, 16 60" stroke="var(--brass)" strokeWidth="1.6" strokeDasharray="2 2" fill="none" />
      <circle cx="24" cy="44" r="4" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

/** Inventory — stacked shipping crates with a gear. */
export function CrateEmblem({ className }: P) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <g stroke="currentColor" strokeWidth="2.4" fill="var(--paper-dark)">
        <rect x="6" y="32" width="26" height="24" />
        <rect x="32" y="32" width="26" height="24" />
        <rect x="19" y="10" width="26" height="22" />
      </g>
      <g stroke="currentColor" strokeWidth="1.8">
        <path d="M6 32 L32 56 M32 32 L58 56 M19 10 L45 32" />
      </g>
      <g transform="translate(40 2) scale(.24)" color="var(--brass)">
        <Gear />
      </g>
    </svg>
  )
}

/** Accounting — open ledger with a quill. */
export function LedgerEmblem({ className }: P) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M32 16 C 24 11, 12 11, 5 14 V 52 C 12 49, 24 49, 32 54 Z" fill="var(--paper)" stroke="currentColor" strokeWidth="2.4" />
      <path d="M32 16 C 40 11, 52 11, 59 14 V 52 C 52 49, 40 49, 32 54 Z" fill="var(--paper)" stroke="currentColor" strokeWidth="2.4" />
      <g stroke="currentColor" strokeWidth="1.3" opacity=".7">
        <path d="M10 22 H27 M10 28 H27 M10 34 H27 M10 40 H23" />
        <path d="M37 22 H54 M37 28 H54 M37 34 H50" />
      </g>
      <path d="M48 44 L60 6 C 62 12, 60 22, 52 36 Z" fill="var(--brass)" stroke="currentColor" strokeWidth="1.5" />
      <path d="M48 44 L46 50" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

/** Facilities — boiler engine with a crossed wrench. */
export function EngineEmblem({ className }: P) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect x="8" y="22" width="34" height="30" rx="8" fill="currentColor" />
      <g fill="var(--brass)">
        <circle cx="14" cy="28" r="1.8" /><circle cx="36" cy="28" r="1.8" />
        <circle cx="14" cy="46" r="1.8" /><circle cx="36" cy="46" r="1.8" />
      </g>
      <circle cx="25" cy="37" r="7" fill="var(--paper)" stroke="var(--brass)" strokeWidth="2" />
      <path d="M25 37 L29 33" stroke="currentColor" strokeWidth="1.8" />
      <rect x="15" y="10" width="7" height="12" fill="currentColor" />
      <rect x="13" y="8" width="11" height="4" rx="1" fill="var(--brass)" />
      <path d="M42 34 H50 V 50" stroke="currentColor" strokeWidth="4" fill="none" />
      <g transform="rotate(-40 50 22)">
        <rect x="47.5" y="14" width="5" height="26" rx="2" fill="var(--brass)" stroke="currentColor" strokeWidth="1.2" />
        <path d="M44 10 a6 6 0 1 0 12 0 l-3 0 l0 4 l-6 0 l0 -4 z" fill="var(--brass)" stroke="currentColor" strokeWidth="1.2" />
      </g>
    </svg>
  )
}

/** Customer Service — telegraph key sending sparks. */
export function TelegraphEmblem({ className }: P) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect x="4" y="46" width="56" height="10" rx="2" fill="currentColor" />
      <rect x="10" y="40" width="10" height="6" fill="var(--brass)" />
      <path d="M14 40 L46 32" stroke="var(--brass)" strokeWidth="4" strokeLinecap="round" />
      <circle cx="48" cy="31" r="6" fill="currentColor" stroke="var(--brass)" strokeWidth="2" />
      <rect x="44" y="40" width="8" height="6" fill="var(--brass)" />
      <g stroke="var(--brass)" strokeWidth="2" strokeLinecap="round">
        <path d="M50 18 L54 10 M56 22 L62 18 M44 18 L42 10" />
      </g>
      <path d="M8 34 h3 m3 0 h8 m3 0 h3" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}
