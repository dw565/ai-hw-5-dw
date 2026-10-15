"""Build output/resolved_tickets.json for the final full run from the working DB + audit trail.

    .venv/bin/python scripts/build_resolved.py 38bfa3fe471c
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_run import ROOT, extract  # noqa: E402

DB = ROOT / "data" / "campus_customs_new.db"

# Short, human-written outcome per ticket and per-agent contribution, checked against the audit trail.
NARRATIVE = {
    101: {
        "outcome": "Tee out of stock (0 of 1). Overdue invoice 501 ($840) was blocking Bulldog Print Co, so it was paid first; "
                   "then a 1-unit restock PO ($8) was placed. Arrives ~2026-09-05; customer draft #5 explains the timing.",
        "agents": {
            "Boss": "Ran two passes. Pass 1 coordinated Inventory → Accounting on invoice 501 and the follow-up PO, then set awaiting_approval. "
                    "Pass 2 confirmed both payments, confirmed the PO is on order, and resolved the ticket.",
            "Inventory": "Found 0 on hand / short 1 and identified Bulldog Print Co (5-day lead) as blocked by invoice 501. Asked Accounting about the invoice. "
                         "After it was paid, proposed PO #2 (1 × CC-TEE-WHITE S, $8). In pass 2, confirmed the PO is on_order, expected 2026-09-05.",
            "Accounting": "Verified invoice 501 ($840, 3 days overdue) and that cash covered it, then created payment request #1. Later confirmed it was paid.",
            "Customer Service": "Drafted the reply to Tauhid Zaman (draft #2 while the PO was pending). Updated it to draft #5 once the restock was ordered (expected 9/5, not guaranteed). Nothing sent.",
        },
    },
    102: {
        "outcome": "Rent of $2,400 for lease 1 (due 2026-09-02) was requested, approved, and paid. lease.next_due advanced to 2026-10-02. "
                   "The landlord acknowledgement is draft #11.",
        "agents": {
            "Boss": "Pass 1: asked Facilities for lease facts and Accounting for the payment request, then set awaiting_approval. "
                    "Pass 2: confirmed the payment and set the ticket to resolved (tool-confirmed). Its closing report then timed out at Portkey (see notes).",
            "Facilities": "Confirmed lease 1: Chapel Street shop, $2,400/month, due 2026-09-02 (2 days, not overdue), no lease notes.",
            "Accounting": "Checked cash ($2,552 after ticket 101) and created rent payment request #3, noting $152 would remain.",
            "Customer Service": "Drafted the landlord note (draft #8 while pending), then draft #11 confirming the rent is recorded as paid. Nothing sent.",
        },
    },
    103: {
        "outcome": "Boss offered the 8 hoodies in stock at a 5% bulk discount ($55.10 each, $440.80). The remaining 12 were declined, because the $264 restock "
                   "exceeds the $152 left in checking. No money moved. Customer draft #17 states the offer.",
        "agents": {
            "Boss": "Asked Inventory, then Accounting, then made the final call: 5% off the 8 in stock, no restock of 12 (cash). "
                    "Posted the decision and resolved.",
            "Inventory": "Found 8 on hand vs 20 requested (short 12), nothing on order. Bulldog Print Co is unblocked with a 5-day lead.",
            "Accounting": "Ran evaluate_discount at 5/10/15/20%. Recommended 5% ($662 margin, 60.1% on 20). Flagged that the 12-unit restock ($264) "
                          "exceeds the $152 uncommitted cash (could cover at most 6 units).",
            "Customer Service": "Drafted the reply to Yale AI Club offering 8 at $55.10. Said plainly that 12 aren't available, and made no future promises. Nothing sent.",
        },
    },
}


def main(reset_id: str) -> None:
    run = extract(reset_id)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    tickets = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM tickets")}
    requests = [dict(r) for r in conn.execute("SELECT * FROM payment_requests ORDER BY id")]
    payments = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM payments")}
    balance = conn.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]

    out = {
        "final_run": {
            "reset_marker": reset_id,
            "reset_at": run["reset"]["timestamp"],
            "model": "gpt-6-luna",
            "starting_checking_balance": 3400.00,
            "ending_checking_balance": balance,
            "evidence_note": "All evidence comes from this run only (everything in output/audit_trail.json after the reset entry above). "
                             "An earlier attempt (reset marker ddc2c3873f88) was abandoned after a test run reset the working DB mid-run. "
                             "It remains in the audit history but is not used here.",
        },
        "tickets": [],
    }
    for tid in (101, 102, 103):
        t = run["tickets"][tid]
        reqs = [r for r in requests if r["ticket_id"] == tid]
        out["tickets"].append({
            "ticket_id": tid,
            "subject": tickets[tid]["subject"],
            "requester": tickets[tid]["requester"],
            "final_status": tickets[tid]["status"],
            "outcome": NARRATIVE[tid]["outcome"],
            "runs": [{"run_id": r["run_id"], "started": r["start"], "ended": r["end"],
                      "boss_final_status": r["boss_status"] or "resolved via update_ticket_status; closing report timed out"} for r in t["runs"]],
            "agent_contributions": [
                {"agent": a, "contribution": NARRATIVE[tid]["agents"].get(a, ""), "tools_used": t["tools"].get(a, {})}
                for a in t["agents"]
            ],
            "delegations": [{"from": d["from"], "to": d["to"], "question": d["question"]} for d in t["delegations"]],
            "human_approvals": [
                {"request_id": r["id"], "kind": r["kind"], "payee": r["payee"], "amount": r["amount"],
                 "requested_by": r["requested_by"], "approved_by": r["decided_by"], "decided_at": r["decided_at"],
                 "status": r["status"], "payment_id": r["payment_id"],
                 "paid_at": payments.get(r["payment_id"], {}).get("paid_at")}
                for r in reqs
            ],
            "cash_change": -round(sum(r["amount"] for r in reqs if r["status"] == "paid"), 2),
        })
    out["tickets"][1]["notes"] = (
        "In run e341e63f11b1, Boss's update_ticket_status(resolved) returned ok: true at 00:06:32Z. Its final summary call to Portkey "
        "then timed out (ModelAPIError after the 90s timeout and retries), so that run is logged ok: false. The ticket's resolved status "
        "is real and tool-confirmed; only Boss's closing report is missing."
    )
    (ROOT / "output" / "resolved_tickets.json").write_text(json.dumps(out, indent=2))
    print("wrote output/resolved_tickets.json", [(t["ticket_id"], t["final_status"], t["cash_change"]) for t in out["tickets"]], "end", balance)


if __name__ == "__main__":
    main(sys.argv[1])
