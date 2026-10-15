# Campus Customs Multi-Agent Operations (HW5)

A five-agent team that runs a small Yale apparel shop's ticket board: customer orders, rent, unpaid vendor bills, and discount requests. A human watches and approves money on a steampunk React dashboard.

- **MCP server** (`mcp_server/`, FastMCP): every shop lookup and update goes through these tools.
- **Backend** (`backend/`, FastAPI + PydanticAI): five agents — Boss, Inventory, Accounting, Facilities, and Customer Service. Any agent can delegate to any other.
- **Dashboard** (`frontend/`, React + Vite + TypeScript): pick a ticket, run the team, watch each agent work, approve payments, and watch cash drop.

Every agent uses **only `gpt-6-luna`** through Portkey (`PORTKEY_API_KEY`).

## Final results

The full run (reset, then tickets 101 → 102 → 103) is documented in `output/`. All three tickets were resolved, and every payment was approved by a human on the dashboard.

| Ticket | Outcome | Cash |
|---|---|---|
| #101 Bulldog tee | Paid the overdue $840 invoice blocking the vendor, then ordered 1 tee ($8), expected 2026-09-05 | −$848 |
| #102 Rent | Paid $2,400 rent for lease 1; next due date advanced to 2026-10-02 | −$2,400 |
| #103 Bulk hoodies | Boss offered the 8 hoodies in stock at 5% off; restocking 12 ($264) was unaffordable | $0 |

Checking went from **$3,400.00 → $152.00**, reconciled against the `payments` table and `cash_accounts`.

## Repository layout

```
AI_prompts.md            prompts used for each problem
requirements.txt         Python dependencies
.env.example             PORTKEY_API_KEY template (real key never committed)
.mcp.json                MCP connection for Claude Code (campus-customs server)
data/
  campus_customs.db      original database (untouched; reset source)
  campus_customs_new.db  working copy, holding the final run's results
mcp_server/              FastMCP server (server.py) + README
backend/
  main.py                FastAPI routes for the dashboard
  models.py              Pydantic data types (reports, decisions, audit entries)
  agents/                boss.py, inventory.py, accounting.py, facilities.py, customer_service.py, base.py (loop + delegation)
  prompts/               boss.md, inventory.md, accounting.md, facilities.md, customer_service.md, _shared_rules.md
  team.py, run_tickets.py, mcp_client.py, audit.py, config.py
frontend/                React + Vite + TypeScript dashboard
output/
  harness.md             tables, MCP tools, agents, routes, dashboard, safety, final run
  desk_tickets.html      per-ticket Expected vs Actual, Cash, Reflection (double-click to open)
  resolved_board.html    real screenshots of the resolved board (double-click to open)
  resolved_tickets.json  per-ticket outcome, agent contributions, approvals
  audit_trail.json       append-only log of every agent step (full history)
  design.md              dashboard design notes
  mcp_smoke.json         MCP connection smoke test
  screenshots/
tests/                   pytest: MCP safety rules, agent loop, API routes
scripts/                 screenshot / evidence helpers
```

## Running it

```bash
# 1. Python env (Python 3.12)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env           # add your PORTKEY_API_KEY (or keep it in the class-level .env)

# 2. Backend, from backend/
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000

# 3. Dashboard, from frontend/ (new terminal)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

On the dashboard:
1. Click **Reset shop** to restore `campus_customs_new.db` from the original.
2. Select a ticket and pull the lever to run the team.
3. Approve payments in the **Approvals** column, and watch the cash gauge.

You can also run without the dashboard: `.venv/bin/python -m backend.run_tickets` resets the working DB and runs all open tickets from the CLI.

Tests: `.venv/bin/python -m pytest tests`. They use a throwaway copy of the database and never touch `data/`.

## Shop rules enforced in the tools

- "Today" is `desk.date_today` (2026-08-31), not the computer's clock.
- **Payments:**
  - Agents can only *request* payments and POs. A human approves them through the dashboard, using a token that agents never see.
  - The pay tool refuses if cash is insufficient, so balances never go negative. It also never pays the same obligation twice.
- **Vendors:** a vendor with an open unpaid invoice can't get a new PO.
- **Out of scope:**
  - Only outgoing cash is modeled; there's no revenue.
  - Customer and vendor messages are saved as drafts and never sent.
- **Limits:** delegation depth, delegations per ticket, a token/request budget per ticket, and a 90s timeout per model call.

See `output/harness.md` for the full tool, agent, route, and safety reference.
