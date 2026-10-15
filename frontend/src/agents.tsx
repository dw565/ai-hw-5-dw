import type { ComponentType } from 'react'
import { CrateEmblem, EngineEmblem, LedgerEmblem, MonocleEmblem, TelegraphEmblem } from './components/Emblems'

export interface AgentMeta {
  key: string
  name: string // matches the backend's display name in events
  title: string
  station: string
  ink: string // CSS color used for this agent everywhere
  Emblem: ComponentType<{ className?: string }>
}

export const AGENTS: AgentMeta[] = [
  { key: 'boss', name: 'Boss', title: 'The Proprietor', station: 'Reads tickets · makes the final call', ink: '#7a1f1f', Emblem: MonocleEmblem },
  { key: 'inventory', name: 'Inventory', title: 'The Stockkeeper', station: 'Stock, shortfalls & vendors', ink: '#2f5d45', Emblem: CrateEmblem },
  { key: 'accounting', name: 'Accounting', title: 'The Ledgerman', station: 'Cash, margins & payment requests', ink: '#26446b', Emblem: LedgerEmblem },
  { key: 'facilities', name: 'Facilities', title: 'The Engineer', station: 'Leases, rent & the premises', ink: '#8a4214', Emblem: EngineEmblem },
  { key: 'customer_service', name: 'Customer Service', title: 'The Telegraphist', station: 'Drafts letters to patrons', ink: '#5e2f63', Emblem: TelegraphEmblem },
]

const BY_NAME = new Map(AGENTS.map((a) => [a.name, a]))
const BY_KEY = new Map(AGENTS.map((a) => [a.key, a]))

export function agentMeta(nameOrKey: string | null | undefined): AgentMeta | undefined {
  if (!nameOrKey) return undefined
  return BY_NAME.get(nameOrKey) ?? BY_KEY.get(nameOrKey)
}

export const money = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  awaiting_approval: 'Awaiting approval',
  blocked: 'Blocked',
  resolved: 'Resolved',
}
