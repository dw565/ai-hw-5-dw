# Campus Customs Multi-Agent Harness

## 1. Database

- **Original (read-only reset source):** `data/campus_customs.db`
- **Working copy (tools read/write here):** `data/campus_customs_new.db`, reset from the original before each full ticket-resolution run.

### Tables

**`desk`** — `date_today`, `notes`
The shop's "today" (2026-08-31); every overdue / due-soon check is measured against this, not the system clock.

**`tickets`** — `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
The work queue the Boss reads; the optional `sku` / `lease_id` / `invoice_id` fields tell it which specialist and which rows a ticket touches.

**`inventory`** — `sku`, `name`, `size`, `qty`, `location` (PK `sku`+`size`)
Inventory agent's source of truth for on-hand stock per size and where to pick it.

**`pricing`** — `sku`, `unit_cost`, `list_price`
Lets Accounting compute margins, restock costs, and how deep a discount can go before it loses money.

**`vendors`** — `id`, `name`, `specialty`, `lead_days`
Tells Inventory who can restock which product and how long it takes to arrive.

**`invoices`** — `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`
Bills the shop owes; an `open` invoice blocks that vendor from shipping new product, and a past-due one is a priority to pay.

**`leases`** — `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
Facilities' record of rent obligations and when the next payment is due.

**`cash_accounts`** — `name`, `balance`, `date`
The only money available; the pay tool must check this and refuse anything that would go negative.

**`payments`** — `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
Audit log of human-approved payments; `kind` + `ref_id` point back to the invoice or lease that was paid. Empty at start.

### Starting values worth knowing

| Item | Value |
|---|---|
| Today | 2026-08-31 |
| Checking balance | $3,400.00 |
| Invoice 501 (Bulldog Print Co) | $840.00, due 2026-08-28, **open → 3 days overdue** |
| Lease 1 rent (Elm City Properties) | $2,400.00, due 2026-09-02 (2 days out) |
| Tee CC-TEE-WHITE size S | 0 on hand |
| Hoodie CC-HOOD-NAVY size M | 8 on hand |
| Vendors | Bulldog Print Co (apparel, 5 days), Elm City Gifts (mugs/small goods, 3 days), QuickShip CT (courier, 1 day) |

## 2. Open Tickets and How They Connect

**#101 — customer_order (Tauhid Zaman): 1 × Bulldog tee, size S**
- `inventory`: CC-TEE-WHITE / S has qty 0, so the order can't be filled from stock.
- `invoice_id` 501: Bulldog Print Co's open, overdue $840 bill for a rush reprint of this exact item. Bulldog won't ship until it's paid.
- If 501 is paid today, a 5-day lead time puts the tee around 2026-09-05. Customer Service drafts an update to Tauhid.

**#102 — rent_notice (Elm City Properties): rent due**
- `lease_id` 1: Chapel Street shop, $2,400 due 2026-09-02.
- Not overdue yet, but it's the largest bill and has to be paid within 2 days. The payment needs human approval, then updates `payments`, `cash_accounts`, and `leases.next_due`.

**#103 — price_override (Yale AI Club): 20 × hoodie M, bulk discount**
- `inventory`: only 8 of CC-HOOD-NAVY / M on hand → **12 short**.
- `pricing`: $22 cost / $58 list (62% margin at list). Restocking 12 costs about $264.
- Restock vendor is Bulldog Print Co (apparel), which is also blocked by invoice 501.

### The cross-ticket constraint: cash

- Invoice 501 + rent = $840 + $2,400 = **$3,240**, which leaves **$160**.
- The $264 hoodie restock for #103 doesn't fit after both bills, so the agents have to prioritize. The pay tool must refuse rather than overdraw.
- All three tickets run through Accounting and the single checking account. #101 and #103 both depend on clearing invoice 501 with Bulldog Print Co.

## 3. First Three MCP Tools (Problem 3)

Server: `mcp_server/server.py` (FastMCP), reading `data/campus_customs_new.db`. These three read-only tools were the starting set. Section 5 has the full expanded list.

### `check_stock_shortfall(sku, size, qty_requested)`
- **Reads:** `inventory`, `pricing`
- **Unlocks:** #103 (and also confirms the gap on #101)
- **Why:** #103 asks for 20 × CC-HOOD-NAVY / M with a bulk discount. This tool reports only 8 on hand, a shortfall of 12, a $264 restock cost at $22/unit, and a $36 (62.1%) margin at the $58 list price. That's everything Inventory and Accounting need to size the gap and decide how much discount the shop can afford.

### `get_invoice_status(invoice_id)`
- **Reads:** `invoices`, `vendors`, `desk`
- **Unlocks:** #101
- **Why:** #101's tee (CC-TEE-WHITE / S, 0 on hand) is tied to invoice 501. This tool shows the $840 bill is 3 days overdue against `desk.date_today`, so Bulldog Print Co is blocked from shipping the reprint. It also reports their 5-day lead time, which lets the agents tell Tauhid when the tee could arrive once the bill is paid.

### `get_rent_status(lease_id)`
- **Reads:** `leases`, `desk`, `cash_accounts`
- **Unlocks:** #102
- **Why:** #102 is the Elm City Properties rent notice for lease 1. This tool shows $2,400 is due 2026-09-02, 2 days after the shop's today, and that checking ($3,400) can cover it with $1,000 left. Facilities and Accounting can then line up a payment for approval before it goes overdue.

## 4. Agent Team (Problem 5)

Built with **PydanticAI** (`pydantic-ai-slim` 2.56). Every agent uses **only `gpt-6-luna`** via Portkey (`https://api.portkey.ai/v1`, `PORTKEY_API_KEY` from the class `.env`), through `OpenAIResponsesModel`, with no temperature override. The model name is defined once, in `backend/config.py`.

| Agent | Code / prompt | Output type | MCP tools |
|---|---|---|---|
| **Boss** | `backend/agents/boss.py`, `backend/prompts/boss.md` | `TicketDecision` | get_shop_date, list_open_tickets, get_ticket, get_board, get_cash_position, list_payment_requests, add_board_note, update_ticket_status |
| **Inventory** | `backend/agents/inventory.py`, `backend/prompts/inventory.md` | `SpecialistReport` | get_shop_date, get_ticket, check_stock_shortfall, list_vendors, get_invoice_status, list_invoices, list_payment_requests, propose_purchase_order, add_board_note |
| **Accounting** | `backend/agents/accounting.py`, `backend/prompts/accounting.md` | `SpecialistReport` | get_shop_date, get_ticket, get_board, get_cash_position, list_invoices, get_invoice_status, check_stock_shortfall, evaluate_discount, get_rent_status, list_vendors, request_payment, propose_purchase_order, list_payment_requests, execute_payment, add_board_note |
| **Facilities** | `backend/agents/facilities.py`, `backend/prompts/facilities.md` | `SpecialistReport` | get_shop_date, get_ticket, get_rent_status, get_cash_position, list_payment_requests, request_payment, add_board_note |
| **Customer Service** | `backend/agents/customer_service.py`, `backend/prompts/customer_service.md` | `SpecialistReport` | get_shop_date, get_ticket, get_board, save_customer_draft |

- **Shared rules:** `backend/prompts/_shared_rules.md` is appended to every agent's prompt. It covers MCP-only facts, shop date, delegation, human approval for money, drafts only, honest status labels, and data safety.
- **Full connectivity:** every agent has an `ask_agent(agent_name, question, context)` tool and can delegate to any other agent (`backend/agents/base.py`). The teammate's structured report comes back as the tool result.
- **Data types (`backend/models.py`):** `SpecialistReport` and `TicketDecision` use explicit status values (`info` / `proposed` / `awaiting_approval` / `completed` / `blocked`; ticket: `in_progress` / `awaiting_approval` / `blocked` / `resolved`). The file also defines `AuditEntry` and `ToolCallRecord`.
- **Loop:** `run_agent()` drives each agent with `Agent.iter()`. Each model step (its text, tool calls, and their results) is written to the audit trail as it happens.
- **Runner:** `backend/team.py` / `python -m backend.run_tickets` resets the working DB from the original, opens one shared MCP connection, and has Boss work each open ticket in order.
- **Audit trail:** `output/audit_trail.json` is an append-only JSON array that keeps entries across runs. Each entry records `run_id`, `ticket_id`, `agent`, `invocation_id` / `parent_invocation_id` / `depth` (who delegated to whom), `event` (`run_start`, `agent_start`, `loop_step`, `delegation`, `agent_end`, `error`, `run_end`), `tool_calls` (tool, args, result, outcome), `delegation` (from / to / question / context, or the refusal reason), `ended` (`tool_calls`, `final_output`, `refused`, `delegated`, `limit_exceeded`, `error`), and token/request usage so far.

**Verification**
- `tests/` holds 10 pytest tests: MCP safety rules, plus a scripted no-LLM agent run through the real MCP server that checks delegation, the cycle guard, role tool filtering, and the audit trail.
- A live `gpt-6-luna` run on ticket #102 (run `dbb3d3ddda21`) went Boss → Facilities + Accounting → Customer Service. It created rent request #1 (`pending_approval`, $2,400), saved draft #1 (unsent), and set the ticket to `awaiting_approval`. Cash stayed at $3,400. Usage: 16 model requests, 27 tool calls, about 46k tokens.
- That run asked Facilities twice (once from Boss, once from Accounting), so the prompts now tell agents to delegate in dependency order and not re-ask for facts already in context.

## 5. MCP Tools (full list)

All tools live in `mcp_server/server.py` and use `data/campus_customs_new.db`. The server creates two workflow tables in the working copy if they're missing: `payment_requests` (payment / PO requests and human decisions) and `board_items` (notes, proposals, customer drafts).

| Tool | Tables read | Tables written | Purpose |
|---|---|---|---|
| `get_shop_date` | desk | — | Shop "today" |
| `list_tickets` | tickets | — | Every ticket with `is_open` (dashboard) |
| `list_open_tickets` | tickets | — | The board's open work |
| `get_ticket` | tickets | — | One ticket's details and links |
| `get_board` | tickets, board_items, payment_requests | — | Everything posted on a ticket |
| `check_stock_shortfall` | inventory, pricing, payment_requests | — | On-hand vs. requested, shortfall, restock cost, margin at list, stock **on order** from paid POs |
| `list_vendors` | vendors, invoices | — | Specialty, lead_days, blocked by open invoice |
| `list_invoices` | invoices, vendors, desk | — | Bills with days overdue |
| `get_invoice_status` | invoices, vendors, desk | — | One bill, and whether its vendor is blocked |
| `get_rent_status` | leases, desk, cash_accounts | — | Rent due date, days until due, can cash cover it |
| `get_cash_position` | cash_accounts, payment_requests | — | Balance and cash already committed to outstanding requests |
| `evaluate_discount` | pricing | — | Margin impact of a discount; read-only, grants nothing |
| `list_payment_requests` | payment_requests | — | Request statuses |
| `request_payment` | invoices, vendors, leases, cash_accounts, payment_requests | payment_requests | Invoice/rent request; amount from the DB; waits for a human |
| `propose_purchase_order` | vendors, invoices, inventory, pricing, desk, payment_requests | payment_requests | Restock PO; refuses blocked vendors; waits for a human |
| `record_human_decision` | payment_requests | payment_requests | **Human only.** Needs the approval token; never given to agents |
| `reset_working_database` | (original DB file) | entire working DB | **Human only.** Copies the untouched original over the working copy; needs the approval token |
| `execute_payment` | payment_requests, invoices, leases, cash_accounts, desk | payments, cash_accounts, invoices, leases, payment_requests, board_items | Pays an approved request in one transaction; a paid PO posts a System "PO placed" note |
| `add_board_note` | tickets | board_items | Internal notes and proposals |
| `save_customer_draft` | tickets | board_items | Customer message saved as a draft; never sent |
| `update_ticket_status` | tickets, payment_requests | tickets, board_items | Status change; refuses `resolved` while requests are outstanding |

After `execute_payment` succeeds:
- **Every kind:** a row is added to `payments` (with `approved_by` = the human), the `cash_accounts` balance drops and its date is set to shop today, and the request is marked `paid`.
- **Invoice:** `invoices.status` changes to `paid`, which unblocks that vendor.
- **Rent:** `leases.next_due` moves forward one month.
- **PO:** `expected_arrival` (shop today + vendor `lead_days`) was already stored on the request when it was proposed. Stock isn't added until delivery.

## 6. Safety

**Customer privacy**
- The only customer data is the requester names in `tickets`. Agents are told to share customer details only where the ticket needs them and to leave internal finances out of customer messages.
- Nothing is emailed or sent. `save_customer_draft` stores drafts with `status='draft'` and `sent: false` for a human to review.
- API keys come from the environment and are never written to code, logs, or the audit trail.

**Human control over money**
- Agents can only *request* payments and POs. Approval goes through `record_human_decision`, which requires a per-process `HUMAN_APPROVAL_TOKEN`. Only the backend and MCP server have that token; it's never in a prompt or tool argument an agent sees. The tool is also filtered out of every agent's toolset (`HUMAN_ONLY_TOOLS`), and the code raises an error if anyone tries to give it to an agent.
- `execute_payment` refuses unless status is `approved` and a human is recorded in `decided_by`.
- Amounts are always taken from the database (invoice amount, monthly rent, qty × unit_cost), never from the agent.
- Cash checks:
  - The balance is decremented with a conditional `UPDATE ... WHERE balance >= amount`, so it can never go negative.
  - A refusal rolls back the whole transaction.
  - No tool can add money.
- Duplicate protection: `request_payment` and `propose_purchase_order` won't create a second outstanding request for the same obligation. `execute_payment` re-checks that the invoice is still open, or that the rent period still matches `next_due`, before paying.

**Safe database updates**
- The original `data/campus_customs.db` is never opened for writing. The MCP server refuses to start a tool call if pointed at it.
- Every full run first copies the original over `data/campus_customs_new.db`.
- Payments run in a single `BEGIN IMMEDIATE` transaction: all the table updates happen together or not at all.
- Tickets can't be marked `resolved` while payment requests are outstanding.

**Limits on loops, delegation, and tokens** (`backend/config.py`)
- Delegation depth is capped at 2 (Boss → specialist → specialist).
- An agent can't delegate to itself or to anyone already upstream in its chain, so A→B→A loops are refused.
- Each ticket gets at most 8 delegations.
- Each ticket has a shared `UsageLimits` budget across all agents: 40 model requests, 60 tool calls, and 300k total tokens. If it's exceeded, the ticket stops and the stop is logged with `ended: limit_exceeded`.
- Each agent gets `retries=1`; each MCP tool gets `max_retries=1`.
- Each model request has a 90s timeout with 2 HTTP retries (`MODEL_TIMEOUT_SECONDS`), so a hung Portkey call fails fast instead of stalling a run for 10 minutes.
- Tests never touch the real working DB: `tests/conftest.py` points every test at a throwaway copy of the original.
- Refusals are logged and returned to the model as `ok: false`. Prompts tell agents to report refusals, not retry around them.

## 7. Backend Routes (Problem 7)

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`. It's then at `http://localhost:8000`, with interactive docs at `/docs`.

The app holds one MCP connection open for its whole lifetime, and every route reads and writes shop data through MCP tools. Human-only actions (approving payments, resetting the DB) use the backend's approval token, which agents never see. CORS allows any `localhost` / `127.0.0.1` origin for the React dev server.

| Method | URL | What it does |
|---|---|---|
| GET | `/api/health` | Liveness check: model name, and whether a run is in progress. |
| GET | `/api/tickets` | All tickets with status and `is_open` (open vs. resolved), via MCP `list_tickets`. |
| GET | `/api/tickets/{ticket_id}/board` | One ticket plus its notes, proposals, customer drafts, and payment requests (MCP `get_board`). |
| POST | `/api/tickets/{ticket_id}/run` | Runs the agent team (Boss first) on one ticket in the background and returns a `run_id` (202). `?wait=true` blocks until it finishes. Returns 409 if another run or reset is in progress. |
| GET | `/api/runs/{run_id}` | Status of a run (`queued` / `running` / `completed` / `failed`) and Boss's final `TicketDecision`. |
| GET | `/api/events` | Recent agent events from `output/audit_trail.json`: agent, what it said, tools used with outcomes, delegations, and how each step ended. Filters: `ticket_id`, `run_id`, `after` (incremental refresh cursor), `limit`. |
| GET | `/api/payments` | Payment / PO requests the agents prepared. Filters: `ticket_id`, `status`. |
| POST | `/api/payments/{request_id}/approve` | Human approval (body `{approver, note}`). This is the step that **actually moves cash**: it records the decision (`record_human_decision`), then calls `execute_payment`. It returns 409 without approving if cash can't cover the request, if the request isn't pending, or if the pay tool refuses. |
| POST | `/api/payments/{request_id}/reject` | Human rejection (body `{approver, note}`). No money moves. |
| GET | `/api/cash` | Current checking balance from `cash_accounts`, plus cash committed to outstanding requests. |
| POST | `/api/reset` | Restores `data/campus_customs_new.db` from the untouched original (MCP `reset_working_database`). Returns 409 during a run. |

**Rules the routes preserve:**
- Agents only *prepare* payments.
- Only the approve route moves cash, and only for a request a named human approved.
- Cash is checked before the approval is recorded and again inside the pay transaction, so the balance never goes negative.
- The same obligation can't be paid twice.
- Runs and resets are serialized with a lock, so two runs never interleave on the shared cash.

**Tests:** `tests/test_routes.py` runs the real app and MCP server on the working DB. The DB is reset before and after, and a scripted Boss stands in for the model, so no tokens are used. It covers tickets, cash, approve / double-pay, insufficient cash, reject, reset, run, and events. The full suite is 15 tests, all passing.

## 8. Dashboard (Problem 8)

`frontend/` is React 19 + Vite + TypeScript with a steampunk theme. Start it from `frontend/` with `npm run dev` (http://localhost:5173). It calls the backend at `http://localhost:8000`, and backend CORS explicitly allows `http://localhost:5173` / `http://127.0.0.1:5173`. Layout, aesthetic, agent identities, the resolved stamp, and the cash gauge are described in `output/design.md`.

| Dashboard feature | Backend route(s) |
|---|---|
| Ticket ledger with statuses and the RESOLVED stamp | `GET /api/tickets` |
| Lever to run the team on the selected ticket, then Boss's verdict | `POST /api/tickets/{id}/run`, `GET /api/runs/{run_id}` |
| Live agent roster and telegraph-tape activity (what each agent said, tool chips, delegations) | `GET /api/events?after=…` (polled 1.2s during a run) |
| Ledger of Deeds (per-agent summary of the latest run) | `GET /api/events` |
| Approvals column (approve & pay / reject, signed by a named human) | `GET /api/payments`, `POST /api/payments/{id}/approve`, `POST /api/payments/{id}/reject` |
| Brass cash gauge plus numeric readout; drops after approvals | `GET /api/cash` |
| Reset shop | `POST /api/reset` |
| Shop date and model badge | `GET /api/health` |

**Fixes made while testing the dashboard live:**
- On a re-run of #102 after the rent was paid, the agents marked it *blocked* instead of resolved. Two things in the data confused them:
  - Approval timestamps used the real clock (2026-10-14), which is later than the shop date (2026-08-31).
  - The advanced `next_due` (10/02) looked like a contradiction of the notice.
- The fixes:
  - MCP timestamps (`created_at`, `decided_at`) now use the shop date.
  - `get_rent_status` now returns `rent_payments_made` with a plain-language note.
  - The Boss and Facilities prompts now explain how to handle re-runs.
- After the fixes: run #102 → approve $2,400 → re-run, and Boss set **resolved**.

## 9. Final Full Run (Problem 9)

- **Reset:** marker `38bfa3fe471c` at 2026-10-14 23:56:42 UTC, done via the board's *Reset shop* (`POST /api/reset`, logged as a `reset` event). Starting checking balance **$3,400.00**.
- **Runs:** all on the React board with `gpt-6-luna`. Every payment and PO was approved by David Wingate on the dashboard.

| Ticket | Runs | Human approvals | Cash change | Final status |
|---|---|---|---|---|
| #101 Bulldog tee | `4f4cc2f71574`, `e68b68aa22fd` | #1 invoice 501 $840; #2 tee PO $8 | −$848.00 | resolved |
| #102 Rent due | `a08c76f0cfbf`, `e341e63f11b1`* | #3 rent $2,400 | −$2,400.00 | resolved |
| #103 Bulk hoodies | `034462b298a1` | none | $0.00 | resolved |

- **Ending checking balance:** **$152.00** = $3,400 − $3,248. This matches `cash_accounts` and the sum of `payments`.
- \* **#102's second run:** Boss resolved the ticket (`update_ticket_status` → `ok: true`), but its closing report timed out at Portkey, so that run is logged `ok: false`.
- **Evidence files:** `output/desk_tickets.html` (Actual sections and Cash tab), `output/resolved_tickets.json`, `output/resolved_board.html`, `output/screenshots/ticket_10{1,2,3}_resolved.png`, and `output/audit_trail.json` (history kept; the final run is everything after the reset marker).
- **Fixes made before or during Problem 9:**
  - **Resolution rules:** Boss now decides discounts and can resolve when nothing waits on a human and any delivery is already scheduled.
  - **On-order stock:** stock checks now show paid POs as on order.
  - **Model timeout:** each model call times out after 90s.
  - **Test isolation:** tests can no longer touch the real working DB.
- **Abandoned attempt:** reset `ddc2c3873f88` was dropped after a test run reset the working DB mid-run. It stays in the audit history but isn't used as evidence.
