# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that gives the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service) shared tools for reading and updating shop data. Every shop lookup and update goes through this server. There's no separate tools layer, so the shop rules (shop date, human approval, cash checks) are enforced in one place.

## Database

- Uses the **working copy** `data/campus_customs_new.db` (relative to the project root).
- Override the path with the `CAMPUS_DB` environment variable.
- Refuses to run against the original `data/campus_customs.db`, which is kept untouched as the reset source.
- Creates two workflow tables in the working copy if they're missing:
  - `payment_requests`: payment / PO requests and human decisions.
  - `board_items`: agent notes, proposals, and customer drafts.

## Tools

**Read**

| Tool | Inputs | Returns |
|---|---|---|
| `get_shop_date` | — | `desk.date_today` (the shop's "today") |
| `list_tickets` | — | Every ticket with an `is_open` flag |
| `list_open_tickets` | — | All non-resolved tickets |
| `get_ticket` | `ticket_id` | One ticket row |
| `get_board` | `ticket_id` | Ticket, board notes/drafts, and payment requests |
| `check_stock_shortfall` | `sku`, `size`, `qty_requested` | On-hand qty, shortfall, unit cost, list price, margin, restock cost |
| `list_vendors` | — | Specialty, lead days, open invoices, `blocked_from_shipping` |
| `list_invoices` | `status` (`open`/`paid`/`all`) | Invoices with vendor and days overdue |
| `get_invoice_status` | `invoice_id` | One invoice, days overdue, and whether its vendor is blocked |
| `get_rent_status` | `lease_id` | Rent, next due, days until due, cash coverage |
| `get_cash_position` | — | Balances, plus cash committed to outstanding requests |
| `evaluate_discount` | `sku`, `qty`, `discount_pct` | Discounted price, revenue, cost, margin, margin given up |
| `list_payment_requests` | `ticket_id` (optional) | Payment/PO requests and their status |

**Write**

| Tool | What it does | Guardrails |
|---|---|---|
| `request_payment` | Creates an invoice or rent payment request | Amount comes from the DB; no duplicates; status `pending_approval` |
| `propose_purchase_order` | Creates a restock PO request (qty × unit cost, arrival = today + lead days) | Refuses vendors with an open invoice; no duplicates |
| `record_human_decision` | Records a human's approve/reject | **Human only**: needs `HUMAN_APPROVAL_TOKEN`, never given to agents |
| `reset_working_database` | Copies the original DB over the working copy | **Human only**: needs `HUMAN_APPROVAL_TOKEN`; never overwrites the original |
| `execute_payment` | Pays an approved request: inserts into `payments`, reduces cash, marks invoice paid / advances lease `next_due` | Must be human-approved; refuses if cash is insufficient (never negative); no double payment; single transaction |
| `add_board_note` | Posts a note or proposal on a ticket | Proposals aren't approvals |
| `save_customer_draft` | Saves a customer message as a draft | Never sent |
| `update_ticket_status` | Sets ticket status and logs why | Refuses `resolved` while requests are outstanding |

## Run

```bash
.venv/bin/python mcp_server/server.py
```

The server runs over stdio. Claude Code connects through `.mcp.json`. The backend (`backend/mcp_client.py`) starts its own copy and passes it `CAMPUS_DB` and the human approval token.

Tests: `.venv/bin/python -m pytest tests`
