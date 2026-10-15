"""Safety-rule tests for the MCP tools, run against a throwaway copy of the original DB."""

import shutil
import sqlite3

import pytest

from mcp_server import server

TOKEN = "test-token"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "shop.db"
    shutil.copy(server.ORIGINAL_DB, db)
    monkeypatch.setattr(server, "DB_PATH", db)
    monkeypatch.setenv("HUMAN_APPROVAL_TOKEN", TOKEN)
    return db


def q(db, sql):
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def approve(request_id):
    return server.record_human_decision(request_id, "approved", "Test Human", TOKEN)


def test_read_tools_match_db():
    assert server.get_shop_date()["date_today"] == "2026-08-31"
    assert [t["id"] for t in server.list_open_tickets()] == [101, 102, 103]
    vendors = {v["id"]: v for v in server.list_vendors()}
    assert vendors[1]["blocked_from_shipping"] and not vendors[2]["blocked_from_shipping"]
    assert server.list_invoices()[0]["days_overdue"] == 3
    d = server.evaluate_discount("CC-HOOD-NAVY", 20, 10)
    assert d["discounted_unit_price"] == 52.2 and d["gross_margin"] == 604.0


def test_payment_needs_human_token_and_approval(temp_db):
    req = server.request_payment("invoice", 501, 101, "Accounting", "overdue")
    assert req["ok"] and req["request"]["amount"] == 840.0
    rid = req["request"]["id"]
    assert not server.execute_payment(rid)["ok"]  # not approved yet
    assert not server.record_human_decision(rid, "approved", "Agent", "guess")["ok"]
    assert approve(rid)["ok"]
    paid = server.execute_payment(rid)
    assert paid["ok"] and paid["payment"]["approved_by"] == "Test Human"
    assert q(temp_db, "SELECT balance FROM cash_accounts")[0][0] == 2560.0
    assert q(temp_db, "SELECT status FROM invoices WHERE id=501")[0][0] == "paid"
    assert not server.execute_payment(rid)["ok"]  # no double pay
    assert not server.request_payment("invoice", 501, 101, "Accounting", "again")["ok"]


def test_rent_advances_lease_and_cannot_repeat(temp_db):
    rid = server.request_payment("rent", 1, 102, "Facilities", "due 9/2")["request"]["id"]
    assert not server.request_payment("rent", 1, 102, "Facilities", "dup")["ok"]
    approve(rid)
    assert server.execute_payment(rid)["ok"]
    assert q(temp_db, "SELECT next_due FROM leases WHERE id=1")[0][0] == "2026-10-02"


def test_insufficient_cash_refused_and_never_negative(temp_db):
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE cash_accounts SET balance = 100")
    rid = server.request_payment("invoice", 501, 101, "Accounting", "x")["request"]["id"]
    approve(rid)
    res = server.execute_payment(rid)
    assert not res["ok"] and "Insufficient cash" in res["error"]
    assert q(temp_db, "SELECT balance FROM cash_accounts")[0][0] == 100
    assert q(temp_db, "SELECT COUNT(*) FROM payments")[0][0] == 0


def test_po_blocked_by_open_invoice_then_allowed():
    blocked = server.propose_purchase_order(1, "CC-HOOD-NAVY", "M", 12, 103, "Inventory", "restock")
    assert not blocked["ok"] and blocked["blocked_by"] == "open_invoice"
    rid = server.request_payment("invoice", 501, 101, "Accounting", "x")["request"]["id"]
    approve(rid)
    server.execute_payment(rid)
    po = server.propose_purchase_order(1, "CC-HOOD-NAVY", "M", 12, 103, "Inventory", "restock")
    assert po["ok"] and po["request"]["amount"] == 264.0
    assert po["request"]["expected_arrival"] == "2026-09-05"


def test_cannot_resolve_with_outstanding_requests():
    server.request_payment("rent", 1, 102, "Facilities", "x")
    assert not server.update_ticket_status(102, "resolved", "Boss", "done")["ok"]
    assert server.update_ticket_status(102, "awaiting_approval", "Boss", "waiting")["ok"]


def test_drafts_are_never_sent():
    d = server.save_customer_draft(101, "Customer Service", "Tauhid Zaman", "Your tee", "Hi")
    assert d["status"] == "draft" and d["sent"] is False


def test_refuses_original_db(monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", server.ORIGINAL_DB)
    with pytest.raises(RuntimeError):
        server.get_shop_date()


def test_paid_po_shows_on_order_and_posts_note():
    rid = server.request_payment("invoice", 501, 101, "Accounting", "x")["request"]["id"]
    approve(rid)
    server.execute_payment(rid)
    po = server.propose_purchase_order(1, "CC-TEE-WHITE", "S", 1, 101, "Accounting", "restock")["request"]["id"]
    assert server.check_stock_shortfall("CC-TEE-WHITE", "S", 1)["pos_awaiting_approval"][0]["request_id"] == po
    approve(po)
    assert server.execute_payment(po)["ok"]
    s = server.check_stock_shortfall("CC-TEE-WHITE", "S", 1)
    assert s["qty_on_order"] == 1 and s["shortfall_after_on_order"] == 0
    assert s["on_order"][0]["expected_arrival"] == "2026-09-05"
    notes = server.get_board(101)["board_items"]
    assert any(n["author"] == "System" and "placed with Bulldog Print Co" in n["body"] for n in notes)
