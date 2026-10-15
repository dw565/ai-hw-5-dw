"""Campus Customs MCP server.

Exposes shop-operations tools to the agent team. All tools read from and write
to the working database (data/campus_customs_new.db), never the original.

Safety rules enforced here (not just in agent prompts):
- Payments only execute after a human decision recorded with the approval token,
  which is held by the backend and never shown to agents.
- Payments refuse if cash is insufficient; balances can never go negative.
- The same invoice / rent period can't be paid twice.
- Amounts come from the database, never from the caller.
- Vendors with an open invoice can't receive new purchase orders.
- Tickets can't be marked resolved while payment requests are outstanding.
"""

import calendar
import hmac
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
DB_PATH = Path(os.getenv("CAMPUS_DB", PROJECT_ROOT / "data" / "campus_customs_new.db"))

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "blocked", "resolved")
OUTSTANDING_REQUEST_STATUSES = ("pending_approval", "approved")

mcp = FastMCP("campus-customs")

# Tables the agent workflow adds to the working copy. They're created on demand,
# so a fresh copy of the original database picks them up automatically.
_EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER NOT NULL,         -- invoice id | lease id | vendor id
    period TEXT,                     -- invoice due_date | lease next_due being paid
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    ticket_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    expected_arrival TEXT,
    reason TEXT,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending_approval | approved | rejected | paid
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    payment_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS board_items (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    kind TEXT NOT NULL,              -- note | proposal | customer_draft
    recipient TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL,            -- posted | draft
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    if DB_PATH.resolve() == ORIGINAL_DB.resolve():
        raise RuntimeError("Refusing to use the original database; point CAMPUS_DB at the working copy.")
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_EXTRA_SCHEMA)
    return conn


def _today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' comes from desk.date_today, not the system clock."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()["date_today"])


def _now(conn: sqlite3.Connection) -> str:
    """Shop-dated timestamp: desk.date_today plus the wall-clock time, so records never look
    'later than today' to the agents."""
    clock = datetime.now(timezone.utc).strftime("%H:%M:%S")
    return f"{_today(conn).isoformat()}T{clock}"


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


def _fail(reason: str, **extra) -> dict:
    return {"ok": False, "error": reason, **extra}


def _rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def _open_invoice_count(conn: sqlite3.Connection, vendor_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,)
    ).fetchone()[0]


def _cash_summary(conn: sqlite3.Connection, account: str = "checking") -> dict:
    row = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    balance = row["balance"] if row else 0.0
    committed = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM payment_requests WHERE account = ? AND status IN {OUTSTANDING_REQUEST_STATUSES}",
        (account,),
    ).fetchone()[0]
    return {
        "account": account,
        "balance": balance,
        "outstanding_requests_total": round(committed, 2),
        "balance_after_outstanding": round(balance - committed, 2),
    }


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@mcp.tool
def get_shop_date() -> dict:
    """Return the shop's 'today' (desk.date_today) and any desk notes. Use this, never the computer's clock."""
    with closing(_connect()) as conn:
        row = conn.execute("SELECT date_today, notes FROM desk").fetchone()
    return {"date_today": row["date_today"], "notes": row["notes"]}


@mcp.tool
def list_tickets() -> list[dict]:
    """List every ticket (open or resolved) with its status and an is_open flag."""
    with closing(_connect()) as conn:
        tickets = _rows(conn.execute("SELECT * FROM tickets ORDER BY id"))
    for t in tickets:
        t["is_open"] = t["status"] != "resolved"
    return tickets


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List every ticket that isn't resolved, with its type, requester, subject, and linked ids."""
    with closing(_connect()) as conn:
        return _rows(conn.execute("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY id"))


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Return one ticket's full row (type, requester, sku/size/qty, lease_id, invoice_id, status, notes)."""
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else _fail(f"No ticket with id={ticket_id}")


@mcp.tool
def check_stock_shortfall(sku: str, size: str, qty_requested: int) -> dict:
    """Check on-hand stock for a SKU/size against a requested quantity.

    Returns qty on hand, the shortfall, unit cost, list price, margin at list,
    and the cost to restock the shortfall. Use for customer orders and bulk
    or discount requests.
    """
    with closing(_connect()) as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if item is None:
            return _fail(f"No inventory row for sku={sku} size={size}")
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        pos = _rows(conn.execute(
            """SELECT id AS request_id, payee AS vendor, qty, status, expected_arrival FROM payment_requests
               WHERE kind = 'purchase_order' AND sku = ? AND size = ? AND status IN ('pending_approval', 'approved', 'paid')""",
            (sku, size),
        ))

    shortfall = max(qty_requested - item["qty"], 0)
    on_order = [po for po in pos if po["status"] == "paid"]  # paid PO = order placed with the vendor
    qty_on_order = sum(po["qty"] for po in on_order)
    result = {
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "location": item["location"],
        "qty_on_hand": item["qty"],
        "qty_requested": qty_requested,
        "can_fill_from_stock": shortfall == 0,
        "shortfall": shortfall,
        "on_order": on_order,
        "qty_on_order": qty_on_order,
        "shortfall_after_on_order": max(shortfall - qty_on_order, 0),
        "pos_awaiting_approval": [po for po in pos if po["status"] != "paid"],
    }
    if price is not None:
        unit_cost, list_price = price["unit_cost"], price["list_price"]
        result.update(
            unit_cost=unit_cost,
            list_price=list_price,
            margin_per_unit_at_list=round(list_price - unit_cost, 2),
            margin_pct_at_list=round((list_price - unit_cost) / list_price * 100, 1),
            restock_cost_for_shortfall=round(shortfall * unit_cost, 2),
        )
    return result


@mcp.tool
def list_vendors() -> list[dict]:
    """List vendors with specialty, lead time in days, open invoice count/total, and whether
    they're blocked from shipping new product (any open invoice blocks them)."""
    with closing(_connect()) as conn:
        vendors = _rows(conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"))
        for v in vendors:
            total = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE vendor_id = ? AND status = 'open'",
                (v["id"],),
            ).fetchone()[0]
            v["open_invoices"] = _open_invoice_count(conn, v["id"])
            v["open_invoice_total"] = total
            v["blocked_from_shipping"] = v["open_invoices"] > 0
    return vendors


@mcp.tool
def list_invoices(status: Literal["open", "paid", "all"] = "open") -> list[dict]:
    """List vendor invoices (default: open ones) with vendor name and days overdue vs. shop today."""
    with closing(_connect()) as conn:
        today = _today(conn)
        sql = """SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id"""
        params: tuple = ()
        if status != "all":
            sql += " WHERE i.status = ?"
            params = (status,)
        invoices = _rows(conn.execute(sql + " ORDER BY i.due_date", params))
    for inv in invoices:
        days = (today - date.fromisoformat(inv["due_date"])).days
        inv["days_overdue"] = max(days, 0) if inv["status"] == "open" else 0
    return invoices


@mcp.tool
def get_invoice_status(invoice_id: int) -> dict:
    """Look up a vendor invoice and whether it blocks that vendor from shipping.

    Returns the amount, due date, days overdue (vs desk.date_today), the
    vendor's specialty and lead time, and whether the vendor is blocked
    because it has any open invoice.
    """
    with closing(_connect()) as conn:
        today = _today(conn)
        inv = conn.execute(
            """SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description,
                      v.name AS vendor_name, v.specialty, v.lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return _fail(f"No invoice with id={invoice_id}")
        open_count = _open_invoice_count(conn, inv["vendor_id"])

    days_overdue = (today - date.fromisoformat(inv["due_date"])).days
    return {
        "invoice_id": inv["id"],
        "description": inv["description"],
        "amount": inv["amount"],
        "status": inv["status"],
        "due_date": inv["due_date"],
        "today": today.isoformat(),
        "is_overdue": inv["status"] == "open" and days_overdue > 0,
        "days_overdue": max(days_overdue, 0),
        "vendor_id": inv["vendor_id"],
        "vendor_name": inv["vendor_name"],
        "vendor_specialty": inv["specialty"],
        "vendor_lead_days": inv["lead_days"],
        "vendor_open_invoices": open_count,
        "vendor_blocked_from_shipping": open_count > 0,
    }


@mcp.tool
def get_rent_status(lease_id: int) -> dict:
    """Look up a lease's rent due date and whether cash can cover it.

    Returns monthly rent, next due date, days until due (vs desk.date_today),
    and checking balance before/after paying.
    """
    with closing(_connect()) as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return _fail(f"No lease with id={lease_id}")
        accounts = conn.execute("SELECT name, balance FROM cash_accounts").fetchall()
        paid = _rows(conn.execute(
            """SELECT r.id AS request_id, r.period, r.amount, r.ticket_id, p.paid_at, p.approved_by
               FROM payment_requests r JOIN payments p ON p.id = r.payment_id
               WHERE r.kind = 'rent' AND r.ref_id = ? AND r.status = 'paid' ORDER BY r.period""",
            (lease_id,),
        ))

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    balances = {a["name"]: a["balance"] for a in accounts}
    checking = balances.get("checking", 0.0)
    return {
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "lease_notes": lease["notes"],
        "today": today.isoformat(),
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
        "cash_balances": balances,
        "checking_can_cover_rent": checking >= lease["monthly_rent"],
        "checking_after_rent": round(checking - lease["monthly_rent"], 2),
        "rent_payments_made": paid,
        "note": (
            f"Rent for period(s) {', '.join(r['period'] for r in paid)} already paid; next_due advanced to {lease['next_due']}."
            if paid else "No rent payments recorded for this lease yet."
        ),
    }


@mcp.tool
def get_cash_position() -> dict:
    """Return every cash account's balance plus the total of payment requests still awaiting
    approval or execution, so agents can see what cash is already spoken for."""
    with closing(_connect()) as conn:
        accounts = _rows(conn.execute("SELECT name, balance, date FROM cash_accounts"))
        summaries = [_cash_summary(conn, a["name"]) | {"as_of": a["date"]} for a in accounts]
    return {"accounts": summaries}


@mcp.tool
def evaluate_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Compute the margin impact of selling `qty` units of `sku` at `discount_pct` off list price.

    Returns discounted unit price, revenue, cost, gross margin ($ and %), and the
    margin given up versus list. Read-only: it doesn't approve or record a discount.
    """
    if not 0 <= discount_pct < 100:
        return _fail("discount_pct must be between 0 and 100")
    with closing(_connect()) as conn:
        price = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if price is None:
        return _fail(f"No pricing row for sku={sku}")
    unit_cost, list_price = price["unit_cost"], price["list_price"]
    unit_price = round(list_price * (1 - discount_pct / 100), 2)
    revenue = round(unit_price * qty, 2)
    cost = round(unit_cost * qty, 2)
    margin = round(revenue - cost, 2)
    return {
        "sku": sku,
        "qty": qty,
        "discount_pct": discount_pct,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "discounted_unit_price": unit_price,
        "revenue": revenue,
        "cost": cost,
        "gross_margin": margin,
        "gross_margin_pct": round(margin / revenue * 100, 1) if revenue else None,
        "margin_given_up_vs_list": round((list_price - unit_price) * qty, 2),
        "sells_below_cost": unit_price < unit_cost,
        "breakeven_discount_pct": round((1 - unit_cost / list_price) * 100, 1),
    }


@mcp.tool
def list_payment_requests(ticket_id: int | None = None) -> list[dict]:
    """List payment / purchase-order requests (optionally for one ticket) with their approval status."""
    with closing(_connect()) as conn:
        if ticket_id is None:
            return _rows(conn.execute("SELECT * FROM payment_requests ORDER BY id"))
        return _rows(conn.execute("SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,)))


@mcp.tool
def get_board(ticket_id: int) -> dict:
    """Return everything posted on the board for a ticket: the ticket row, agent notes,
    proposals, customer drafts, and payment requests."""
    with closing(_connect()) as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return _fail(f"No ticket with id={ticket_id}")
        items = _rows(conn.execute("SELECT * FROM board_items WHERE ticket_id = ? ORDER BY id", (ticket_id,)))
        requests = _rows(conn.execute("SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,)))
    return {"ticket": dict(ticket), "board_items": items, "payment_requests": requests}


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@mcp.tool
def request_payment(
    kind: Literal["invoice", "rent"],
    ref_id: int,
    ticket_id: int,
    requested_by: str,
    reason: str,
    account: str = "checking",
) -> dict:
    """Create a payment request for a vendor invoice (ref_id = invoice id) or a lease's next rent
    (ref_id = lease id). The amount is taken from the database. The request waits for HUMAN
    approval; nothing is paid by this tool."""
    with closing(_connect()) as conn:
        if kind == "invoice":
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,),
            ).fetchone()
            if inv is None:
                return _fail(f"No invoice with id={ref_id}")
            if inv["status"] != "open":
                return _fail(f"Invoice {ref_id} is already '{inv['status']}'; nothing to pay.")
            amount, period, payee = inv["amount"], inv["due_date"], inv["vendor_name"]
        else:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return _fail(f"No lease with id={ref_id}")
            amount, period, payee = lease["monthly_rent"], lease["next_due"], lease["landlord"]

        existing = conn.execute(
            "SELECT * FROM payment_requests WHERE kind = ? AND ref_id = ? AND period = ? AND status != 'rejected'",
            (kind, ref_id, period),
        ).fetchone()
        if existing is not None:
            return _fail(
                f"A request for this {kind} already exists (request {existing['id']}, status '{existing['status']}').",
                existing_request=dict(existing),
            )

        cash_before = _cash_summary(conn, account)
        cur = conn.execute(
            """INSERT INTO payment_requests (kind, ref_id, period, payee, amount, account, ticket_id,
                   reason, requested_by, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', ?)""",
            (kind, ref_id, period, payee, amount, account, ticket_id, reason, requested_by, _now(conn)),
        )
        conn.commit()
        request = dict(conn.execute("SELECT * FROM payment_requests WHERE id = ?", (cur.lastrowid,)).fetchone())
        cash_after = _cash_summary(conn, account)

    return {
        "ok": True,
        "status": "pending_approval",
        "message": "Request created. It needs human approval before any money moves.",
        "request": request,
        "cash_covers_this_request_now": cash_before["balance"] >= amount,
        "cash_covers_all_outstanding_requests": cash_after["balance_after_outstanding"] >= 0,
        "cash": cash_after,
    }


@mcp.tool
def propose_purchase_order(
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    ticket_id: int,
    requested_by: str,
    reason: str,
    account: str = "checking",
) -> dict:
    """Propose a restock purchase order. Cost = qty x pricing.unit_cost; expected arrival =
    shop today + vendor lead_days. Once a human approves it and it's paid, the order counts as placed
    (shown as on_order by check_stock_shortfall). Refuses if the vendor has an open unpaid invoice. The PO waits
    for HUMAN approval; nothing is ordered or paid by this tool."""
    if qty <= 0:
        return _fail("qty must be positive")
    with closing(_connect()) as conn:
        today = _today(conn)
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return _fail(f"No vendor with id={vendor_id}")
        open_count = _open_invoice_count(conn, vendor_id)
        if open_count:
            return _fail(
                f"{vendor['name']} has {open_count} open unpaid invoice(s) and won't ship new product until paid.",
                blocked_by="open_invoice",
            )
        item = conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if item is None or price is None:
            return _fail(f"Unknown sku/size {sku}/{size} or missing pricing")
        existing = conn.execute(
            f"""SELECT id, status FROM payment_requests WHERE kind = 'purchase_order' AND ticket_id = ?
                AND sku = ? AND size = ? AND status IN {OUTSTANDING_REQUEST_STATUSES}""",
            (ticket_id, sku, size),
        ).fetchone()
        if existing is not None:
            return _fail(f"An outstanding PO for this ticket/sku/size already exists (request {existing['id']}).")

        amount = round(qty * price["unit_cost"], 2)
        arrival = date.fromordinal(today.toordinal() + vendor["lead_days"]).isoformat()
        cur = conn.execute(
            """INSERT INTO payment_requests (kind, ref_id, period, payee, amount, account, ticket_id, sku, size,
                   qty, expected_arrival, reason, requested_by, status, created_at)
               VALUES ('purchase_order', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', ?)""",
            (vendor_id, today.isoformat(), vendor["name"], amount, account, ticket_id, sku, size, qty,
             arrival, reason, requested_by, _now(conn)),
        )
        conn.commit()
        request = dict(conn.execute("SELECT * FROM payment_requests WHERE id = ?", (cur.lastrowid,)).fetchone())
        cash = _cash_summary(conn, account)

    return {
        "ok": True,
        "status": "pending_approval",
        "message": "Purchase order proposed. It needs human approval before it's placed or paid.",
        "request": request,
        "cash_covers_all_outstanding_requests": cash["balance_after_outstanding"] >= 0,
        "cash": cash,
    }


def _check_token(approval_token: str) -> bool:
    expected = os.getenv("HUMAN_APPROVAL_TOKEN", "")
    return bool(expected) and hmac.compare_digest(approval_token, expected)


@mcp.tool
def reset_working_database(approval_token: str) -> dict:
    """HUMAN USE ONLY (dashboard / backend). Restore the working database from the untouched
    original. Requires the human approval token; never given to agents."""
    if not _check_token(approval_token):
        return _fail("Invalid approval token. Only a human can reset the database.")
    if DB_PATH.resolve() == ORIGINAL_DB.resolve():
        return _fail("Refusing to overwrite the original database.")
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    with closing(_connect()) as conn:
        cash = _cash_summary(conn)
        open_tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE status != 'resolved'").fetchone()[0]
    return {"ok": True, "message": "Working database restored from the original.", "cash": cash, "open_tickets": open_tickets}


@mcp.tool
def record_human_decision(
    request_id: int,
    decision: Literal["approved", "rejected"],
    approver: str,
    approval_token: str,
    note: str = "",
) -> dict:
    """HUMAN USE ONLY (dashboard / backend). Record a person's approval or rejection of a payment
    request. Requires the human approval token, which agents never have."""
    if not _check_token(approval_token):
        return _fail("Invalid approval token. Only a human reviewer can approve or reject payments.")
    if not approver.strip():
        return _fail("approver name is required")
    with closing(_connect()) as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return _fail(f"No payment request with id={request_id}")
        if req["status"] != "pending_approval":
            return _fail(f"Request {request_id} is '{req['status']}', not pending approval.")
        conn.execute(
            "UPDATE payment_requests SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (decision, approver.strip(), _today(conn).isoformat(), note, request_id),
        )
        conn.commit()
        req = dict(conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone())
    return {"ok": True, "request": req}


@mcp.tool
def execute_payment(request_id: int) -> dict:
    """Pay a request that a HUMAN has already approved. Refuses if not approved, already paid,
    the obligation is already settled, or cash is insufficient (balances never go negative).
    On success: inserts into payments, reduces the cash balance, and marks the invoice paid /
    advances the lease's next_due / records the PO as placed."""
    with closing(_connect()) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
            if req is None:
                raise _Refuse(f"No payment request with id={request_id}")
            if req["status"] == "paid":
                raise _Refuse(f"Request {request_id} was already paid (payment {req['payment_id']}).")
            if req["status"] != "approved" or not req["decided_by"]:
                raise _Refuse(f"Request {request_id} is '{req['status']}'. A human must approve it before payment.")

            today = _today(conn)
            if req["kind"] == "invoice":
                inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
                if inv is None or inv["status"] != "open":
                    raise _Refuse(f"Invoice {req['ref_id']} is not open; refusing to pay it twice.")
            elif req["kind"] == "rent":
                lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
                if lease is None or lease["next_due"] != req["period"]:
                    raise _Refuse(f"Rent for lease {req['ref_id']} period {req['period']} is already settled.")

            # Conditional update: the balance can never go negative, even under concurrent calls.
            cur = conn.execute(
                "UPDATE cash_accounts SET balance = ROUND(balance - ?, 2), date = ? WHERE name = ? AND balance >= ?",
                (req["amount"], today.isoformat(), req["account"], req["amount"]),
            )
            if cur.rowcount != 1:
                bal = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)).fetchone()
                raise _Refuse(
                    f"Insufficient cash in '{req['account']}': balance {bal['balance'] if bal else 0:.2f}, "
                    f"payment {req['amount']:.2f}. Payment refused."
                )

            ref_for_payment = req["id"] if req["kind"] == "purchase_order" else req["ref_id"]
            pay = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (req["kind"], ref_for_payment, req["amount"], req["account"], today.isoformat(), req["decided_by"]),
            )
            if req["kind"] == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            elif req["kind"] == "rent":
                next_due = _add_month(date.fromisoformat(req["period"])).isoformat()
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, req["ref_id"]))
            conn.execute(
                "UPDATE payment_requests SET status = 'paid', payment_id = ? WHERE id = ?",
                (pay.lastrowid, request_id),
            )
            if req["kind"] == "purchase_order" and req["ticket_id"] is not None:
                conn.execute(
                    "INSERT INTO board_items (ticket_id, author, kind, body, status, created_at) VALUES (?, 'System', 'note', ?, 'posted', ?)",
                    (req["ticket_id"],
                     f"PO request #{req['id']} placed with {req['payee']}: {req['qty']} x {req['sku']} {req['size']}, "
                     f"paid ${req['amount']:.2f} (approved by {req['decided_by']}). Expected arrival {req['expected_arrival']}.",
                     _now(conn)),
                )
            conn.execute("COMMIT")
        except _Refuse as refusal:
            conn.execute("ROLLBACK")
            return _fail(str(refusal))
        except Exception:
            conn.execute("ROLLBACK")
            raise

        payment = dict(conn.execute("SELECT * FROM payments WHERE id = ?", (pay.lastrowid,)).fetchone())
        cash = _cash_summary(conn, req["account"])
    return {"ok": True, "status": "completed", "payment": payment, "cash": cash}


class _Refuse(Exception):
    """A rule-based refusal inside execute_payment's transaction."""


@mcp.tool
def add_board_note(
    ticket_id: int,
    author: str,
    body: str,
    kind: Literal["note", "proposal"] = "note",
) -> dict:
    """Post an internal finding or proposal (e.g. a discount recommendation) on a ticket's board.
    Proposals are not approvals."""
    with closing(_connect()) as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return _fail(f"No ticket with id={ticket_id}")
        cur = conn.execute(
            "INSERT INTO board_items (ticket_id, author, kind, body, status, created_at) VALUES (?, ?, ?, ?, 'posted', ?)",
            (ticket_id, author, kind, body, _now(conn)),
        )
        conn.commit()
    return {"ok": True, "board_item_id": cur.lastrowid}


@mcp.tool
def save_customer_draft(ticket_id: int, author: str, recipient: str, subject: str, body: str) -> dict:
    """Save a customer / vendor / landlord message as a DRAFT on the ticket's board.
    Nothing is sent; a human reviews drafts on the dashboard."""
    with closing(_connect()) as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return _fail(f"No ticket with id={ticket_id}")
        cur = conn.execute(
            """INSERT INTO board_items (ticket_id, author, kind, recipient, subject, body, status, created_at)
               VALUES (?, ?, 'customer_draft', ?, ?, ?, 'draft', ?)""",
            (ticket_id, author, recipient, subject, body, _now(conn)),
        )
        conn.commit()
    return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "sent": False}


@mcp.tool
def update_ticket_status(
    ticket_id: int,
    status: Literal["open", "in_progress", "awaiting_approval", "blocked", "resolved"],
    author: str,
    note: str,
) -> dict:
    """Set a ticket's status and post the reason on its board. Refuses 'resolved' while any
    payment request for the ticket is still pending approval or approved-but-unpaid."""
    with closing(_connect()) as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return _fail(f"No ticket with id={ticket_id}")
        if status == "resolved":
            outstanding = _rows(conn.execute(
                f"SELECT id, kind, amount, status FROM payment_requests WHERE ticket_id = ? AND status IN {OUTSTANDING_REQUEST_STATUSES}",
                (ticket_id,),
            ))
            if outstanding:
                return _fail(
                    "Can't resolve: payment requests are still outstanding.", outstanding_requests=outstanding
                )
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO board_items (ticket_id, author, kind, body, status, created_at) VALUES (?, ?, 'note', ?, 'posted', ?)",
            (ticket_id, author, f"Status -> {status}: {note}", _now(conn)),
        )
        conn.commit()
    return {"ok": True, "ticket_id": ticket_id, "status": status}


if __name__ == "__main__":
    mcp.run(show_banner=False)
