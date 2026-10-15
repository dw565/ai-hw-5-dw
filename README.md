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
  github_url.txt         submission URL
  screenshots/
tests/                   pytest: MCP safety rules, agent loop, API routes
scripts/                 screenshot / evidence helpers
```

## Setup and running

### 1. Install dependencies

```bash
git clone https://github.com/dw565/ai-hw-5-dw.git && cd ai-hw-5-dw
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Requires Python 3.12 and Node 20+. On Windows, use `.venv\Scripts\python` wherever this README says `.venv/bin/python`.

### 2. Set up `PORTKEY_API_KEY`

```bash
cp .env.example .env
# edit .env and set PORTKEY_API_KEY=<your Portkey key>
```

`backend/config.py` loads `.env` from the repo root (and also from a class-level `.env` two folders up, if present). The real `.env` is git-ignored. Every agent calls **only `gpt-6-luna`** through Portkey's OpenAI-compatible endpoint (`https://api.portkey.ai/v1`). The model is set in one place: `MODEL_NAME` in `backend/config.py`.

### 3. Database: original vs. working copy

- `data/campus_customs.db` is the **original**, never written to. The MCP server refuses to point at it.
- `data/campus_customs_new.db` is the **working copy** the tools update. In this repo it holds the **final results** of the submitted run.

For a clean run of your own, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The dashboard's **Reset shop** button (`POST /api/reset`) does the same thing through the MCP server, and so does `python -m backend.run_tickets`, which resets before a full run. Either way you overwrite the submitted final results, so `git checkout data/campus_customs_new.db` restores them.

### 4. Start the MCP server

The backend **starts its own MCP server automatically** over stdio (`backend/mcp_client.py`). For the dashboard flow you don't need to start it yourself.

To run or inspect the server on its own:

```bash
.venv/bin/python mcp_server/server.py        # FastMCP over stdio, uses data/campus_customs_new.db
```

To use the tools from **Claude Code**, open the repo root as the project. `.mcp.json` registers the `campus-customs` server with repo-relative paths (`.venv/bin/python mcp_server/server.py`), so it works on any machine once `.venv` exists at the repo root. Approve the server when Claude Code asks, and restart the session if it was already open.

### 5. Start FastAPI

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

The backend serves at `http://localhost:8000`, with interactive docs at `/docs`. CORS allows the Vite dev server on `http://localhost:5173`.

### 6. Start the React dashboard

```bash
cd frontend
npm run dev            # http://localhost:5173  (calls http://localhost:8000; override with VITE_API_BASE)
```

### 7. A full three-ticket run

1. **Reset first:** click **Reset shop** on the dashboard. Checking returns to $3,400 and tickets 101–103 reopen.
2. Select **#101** and pull the lever (**Set the team to work**). The activity feed shows each agent, every delegation, and every MCP tool call as it happens.
3. Approve anything the agents request (see below), then pull the lever again. Boss confirms the payments and resolves the ticket once nothing is waiting on a human.
4. Repeat for **#102** and **#103**. A resolved ticket gets a RESOLVED stamp. Every step is appended to `output/audit_trail.json`.

CLI alternative, without the dashboard and without approvals:

```bash
.venv/bin/python -m backend.run_tickets            # resets the DB, then runs all open tickets
```

### How human payment approval works

1. Agents can only **prepare** money movements:
   - Accounting or Facilities call `request_payment` for an invoice or rent.
   - Inventory or Accounting call `propose_purchase_order` for a restock.
   - The amount always comes from the database, and the request is saved with status `pending_approval`.
2. The request appears in the dashboard's **Approvals** column. A person types their name under **Signing as** and clicks **Approve & pay** (or **Reject**).
3. Approval calls `POST /api/payments/{id}/approve`. The backend first checks that cash covers the amount (if not, it returns 409 and records nothing). It then records the decision with `record_human_decision` and calls `execute_payment`.
4. `record_human_decision` needs a per-process `HUMAN_APPROVAL_TOKEN`. Only the backend and the MCP server have it; it isn't in the repo, a prompt, or any agent's toolset. So **an agent saying "approved" can't move money**.
5. `execute_payment` runs as one transaction:
   - It pays only approved requests.
   - It refuses if the balance would go negative.
   - It refuses if the obligation is already paid.
   - It writes a row to `payments` and reduces `cash_accounts`.
   - It marks the invoice paid, moves the lease's `next_due` forward, or marks the PO as placed.

   The cash gauge on the dashboard drops right after the approval.

### Tests

```bash
.venv/bin/python -m pytest tests
```

The tests use a throwaway copy of the original database, never `data/`. The agent-loop and route tests use scripted models, so they don't make real model calls.

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
