# Campus Customs Operations Desk: Design Notes

The dashboard (`frontend/`, React + Vite + TypeScript) is a Victorian shop operations desk: dark wood, brass fittings, cream ledger paper, and a few machines that come alive while the agents work. The steampunk styling stays in the frame, borders, and motion. The text and controls stay plain, large, and high-contrast, so it's easy to operate.

## Layout

The page is three columns under a brass masthead, so the three things you need (tickets, live activity, approvals) are always visible without scrolling sideways.

| Area | What it holds | Why it's there |
|---|---|---|
| **Masthead** | Shop name plate with turning gears, the shop date (`desk.date_today` from the backend), the model name, the **cash gauge**, and a *Reset shop* button | Money and "today" are global context, so they sit above everything |
| **Left: Ticket Ledger** | One paper card per ticket: number, type, subject, requester, SKU/lease, and a status tag | It's the to-do list, so it reads top-down like a ledger page |
| **Center** | Selected ticket header with a big **lever** ("Set the team to work"), Boss's verdict, the **agent roster**, the **Live Activity** tape, and the **Ledger of Deeds** summary | The center is where the work happens: pull the lever, watch it play out, read the outcome |
| **Right: Approvals** | "Signing as" name field, pending payment / PO cards with **Approve & pay** / **Reject**, and recently decided items | Money decisions are the human's job, so they get their own column with a pulsing count badge |

Below 1100px the columns stack in the same order: tickets, then work, then approvals.

## Aesthetic choices

- **Materials:**
  - Panels are cream paper (`#f6ecd2`) in brass frames with a rivet in each corner (pure CSS radial gradients).
  - The background is a dark wood grain made of layered CSS gradients.
  - Buttons are polished brass with a pressed-down state.
  - The approve button is green enamel, so the one irreversible action is unmistakable.
- **Type:**
  - *Cinzel* for engraved headings and labels.
  - *EB Garamond* for body text: a readable book face at 16–19px.
  - *Special Elite* (typewriter) for telegraph and stamp details.
  - *IBM Plex Mono* for money and tool names, so numbers line up and read cleanly.
  - All fonts are bundled locally via `@fontsource`, so the page works offline.
- **Motion:** always purposeful, and switched off for `prefers-reduced-motion`.
  - The masthead gears turn slowly at idle and speed up while a run is in progress.
  - An active agent's card lifts, glows in its own ink color, bobs its emblem, spins its little gear, and puffs **steam** from the top.
  - New telegraph-tape entries tick in from the left.
  - The cash gauge needle swings with a springy overshoot when the balance changes.
- **Contrast and accessibility:**
  - Body text is dark brown ink on cream.
  - Status is never shown by color alone; every tag also has a word.
  - Buttons have visible focus rings, and the activity feed is an `aria-live` region.

## How the agents are distinguished

Each agent has a fixed **ink color**, a **title**, and a hand-drawn **SVG emblem**. All three are reused everywhere that agent appears: roster card, activity rows (colored left rule plus a small emblem), delegation arrows, the Ledger of Deeds, and "prepared by" on approval cards.

| Agent | Title | Emblem | Ink |
|---|---|---|---|
| Boss | The Proprietor | Top hat with a monocle on a chain | Oxblood `#7a1f1f` |
| Inventory | The Stockkeeper | Stacked shipping crates with a brass gear | Verdigris green `#2f5d45` |
| Accounting | The Ledgerman | Open ledger with a quill | Ink blue `#26446b` |
| Facilities | The Engineer | Riveted boiler with a pressure dial and a crossed wrench | Rust copper `#8a4214` |
| Customer Service | The Telegraphist | Telegraph key sending sparks | Plum `#5e2f63` |

Each roster card shows one of three states:
- **At work:** steam, a spinning gear, and a glow.
- **Reported in:** the agent took part in this run.
- **Standing by:** the agent wasn't involved and is slightly faded.

This makes it obvious when Boss *didn't* involve someone. For example, Facilities stays "Standing by" on the tee order.

In the **Live Activity** tape, delegated work is indented by depth, so Boss → Inventory → Accounting reads as a visible chain. Hand-offs appear as "➜ asks **Accounting**: '…'". Tool calls are brass chips (✓ ok, ✕ refused, ↻ retry); clicking a chip unrolls the exact arguments and result JSON from the audit trail. Each agent's final report appears with a status tag (*info / proposed / awaiting approval / completed / blocked*). These are the same honest labels the agents are required to use.

The **Ledger of Deeds** condenses the latest run into one entry per involved agent: their final report, step count, which tools they used (with counts), and whom they asked for help.

## Resolved tickets

A ticket is shown as resolved **only** when the backend's `tickets.status` is `resolved`. The dashboard never infers it. When that happens:
- A red, double-bordered, slightly rotated rubber **RESOLVED** stamp thumps onto the ticket's ledger card and, in large type, across the ticket header.
- The lever is disabled.

When a run ends without resolution, a **verdict card** shows Boss's actual `TicketDecision` and explains what's still needed, for example: "Not closed yet. Approve the pending payment(s), then run the team again…". That matches the real flow:
1. Agents prepare a payment.
2. A human approves it.
3. A re-run lets Boss confirm it's paid and close the ticket.

We verified this end to end on ticket #102: run → $2,400 rent request → approve → re-run → Boss set `resolved` → stamp.

## Cash display

The checking balance sits in the masthead as a **brass pressure gauge** with a cream dial and an oxblood needle. Directly underneath is a back-lit amber **numeric readout** (`$3,400.00`) in a monospaced font. The dial is atmosphere; the readout is the number you trust, and it's large and exact.

- **Under the readout:** a line showing how much is awaiting approval and what the balance would be afterward, e.g. "Awaiting approval: $840.00 · after: $2,560.00".
- **After an approval:**
  - The dashboard re-fetches `/api/cash`.
  - The needle swings down.
  - A red **−$840.00** tag rises and fades next to the readout, so you can *see* the money leave.
- **Approval cards warn ahead of time:** if checking can't cover a request, the card says so before you click. The backend refuses it regardless (no negative balances).

Every number comes from the backend:
- `/api/cash` for the balance.
- `/api/payments` for requests.
- `/api/tickets` for statuses.
- `/api/events` for activity.
- `/api/runs/{id}` for the verdict.

The page polls every 1.2s while a run is going and every 6s otherwise. It only fetches *new* events each time, using the `after` cursor.

## Why a human would enjoy using it

- **It tells a story you can follow.** Pull a lever, and you watch the Proprietor put on his monocle and hand work to the Stockkeeper, who asks the Ledgerman about an unpaid bill. Each step is a line on the telegraph tape. Multi-agent runs are usually opaque; here the delegation chain is literally drawn.
- **The human is clearly in charge of money.** Approvals sit in their own column with a pulsing badge. You sign with your name, and the gauge visibly drops when you approve. The interface makes it obvious that no money moves until a person stamps it.
- **Honest by construction.** Statuses, stamps, and numbers all come straight from the backend. A ticket can't look done until the database says it's done, and blocked or refused steps are shown in red rather than hidden.
- **Detail on demand.** The surface reads like a ledger. Clicking any tool chip reveals the raw arguments and results for auditing, without cluttering the default view.
- **It's charming without getting in the way.** Brass, steam, and rubber stamps make a dry ops workflow feel like running a little Victorian shop, while the layout, type sizes, and contrast stay those of a practical tool.

## Running it

```bash
# terminal 1 — backend (from backend/)
uvicorn main:app --reload --port 8000
# terminal 2 — dashboard (from frontend/)
npm run dev        # http://localhost:5173
```

The frontend calls `http://localhost:8000`; override it with `VITE_API_BASE`. Backend CORS allows `http://localhost:5173` (and other local ports).
