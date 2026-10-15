"""Campus Customs FastAPI backend for the React dashboard.

Run from the backend/ folder:

    uvicorn main:app --reload --port 8000

Every shop lookup and update goes through the MCP server (one shared stdio connection held
open for the app's lifetime). Human-only actions (approving payments, resetting the DB) use the
backend's approval token, which agents never see.
"""

import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

# Allow `uvicorn main:app` from inside backend/ as well as `backend.main:app` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.config import HUMAN_APPROVAL_TOKEN, MODEL_NAME  # noqa: E402
from backend.mcp_client import shop_connection  # noqa: E402
from backend.models import AuditEntry  # noqa: E402
from backend.team import mcp_call, run_tickets  # noqa: E402

# One team run (or reset) at a time, so runs don't interleave on the shared cash.
_busy = asyncio.Lock()
RUNS: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_connection():
        yield


app = FastAPI(title="Campus Customs Backend", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",  # other local ports (e.g. vite --port)
    allow_methods=["*"],
    allow_headers=["*"],
)


class Decision(BaseModel):
    approver: str = Field(min_length=1, description="Name of the human clicking the button.")
    note: str = ""


def _fail_status(result: dict) -> None:
    if isinstance(result, dict) and result.get("ok") is False:
        raise HTTPException(status_code=409, detail=result["error"])


async def _get_request(request_id: int) -> dict:
    requests = await mcp_call("list_payment_requests", {})
    req = next((r for r in requests if r["id"] == request_id), None)
    if req is None:
        raise HTTPException(status_code=404, detail=f"No payment request with id={request_id}")
    return req


# ---------------------------------------------------------------------------
# Tickets and runs
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict:
    desk = await mcp_call("get_shop_date")
    return {"ok": True, "model": MODEL_NAME, "busy": _busy.locked(), "shop_date": desk["date_today"]}


@app.get("/api/tickets")
async def list_tickets() -> list[dict]:
    """All tickets with status and whether each is open or resolved."""
    return await mcp_call("list_tickets")


@app.get("/api/tickets/{ticket_id}/board")
async def ticket_board(ticket_id: int) -> dict:
    """The ticket plus its notes, proposals, customer drafts, and payment requests."""
    board = await mcp_call("get_board", {"ticket_id": ticket_id})
    if board.get("ok") is False:
        raise HTTPException(status_code=404, detail=board["error"])
    return board


async def _run_in_background(run_id: str, ticket_id: int) -> None:
    async with _busy:
        RUNS[run_id]["status"] = "running"
        try:
            summary = await run_tickets([ticket_id], reset=False, run_id=run_id)
            result = summary["results"][0]
            RUNS[run_id].update(status="completed" if result["ok"] else "failed", result=result)
        except Exception as exc:  # surfaced to the dashboard via /api/runs/{run_id}
            RUNS[run_id].update(status="failed", result={"ok": False, "error": f"{type(exc).__name__}: {exc}"})


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, wait: bool = Query(False, description="Block until the run finishes")) -> dict:
    """Start the agent team on one ticket. Poll /api/runs/{run_id} and /api/events for progress."""
    ticket = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if ticket.get("ok") is False:
        raise HTTPException(status_code=404, detail=ticket["error"])
    if _busy.locked():
        raise HTTPException(status_code=409, detail="A run or reset is already in progress.")
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "queued", "result": None}
    task = asyncio.create_task(_run_in_background(run_id, ticket_id))
    RUNS[run_id]["_task"] = task
    if wait:
        await task
    return _public_run(run_id)


def _public_run(run_id: str) -> dict:
    return {k: v for k, v in RUNS[run_id].items() if not k.startswith("_")}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id}")
    return _public_run(run_id)


# ---------------------------------------------------------------------------
# Agent events (audit trail)
# ---------------------------------------------------------------------------


def _event_view(index: int, e: dict) -> dict:
    delegation = e.get("delegation") or {}
    is_handoff = e.get("event") == "delegation"
    return {
        "id": index,
        "timestamp": e.get("timestamp"),
        "run_id": e.get("run_id"),
        "ticket_id": e.get("ticket_id"),
        "agent": e.get("agent"),
        "event": e.get("event"),
        "depth": e.get("depth", 0),
        "invocation_id": e.get("invocation_id"),
        "parent_invocation_id": e.get("parent_invocation_id"),
        "said": e.get("text"),
        "tools": [{"tool": c.get("tool"), "outcome": c.get("outcome")} for c in e.get("tool_calls", [])],
        "tool_calls": e.get("tool_calls", []),
        "delegation": {k: delegation.get(k) for k in ("from", "to", "question", "refused")} if is_handoff else None,
        "output": delegation.get("output") if e.get("event") == "agent_end" else None,
        "ended": e.get("ended"),
    }


@app.get("/api/events")
async def events(
    ticket_id: int | None = None,
    run_id: str | None = None,
    after: int = Query(-1, description="Only events with id > after (for incremental refresh)"),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """Recent agent events: who said what, which tools they called, delegations, and how each step ended."""
    try:
        raw = json.loads(audit.AUDIT_PATH.read_text()) if audit.AUDIT_PATH.exists() else []
    except json.JSONDecodeError:
        raw = []
    selected = [
        _event_view(i, e)
        for i, e in enumerate(raw)
        if i > after
        and (ticket_id is None or e.get("ticket_id") == ticket_id)
        and (run_id is None or e.get("run_id") == run_id)
    ]
    return {"events": selected[-limit:], "last_id": len(raw) - 1}


# ---------------------------------------------------------------------------
# Money: payment requests, human approval, cash
# ---------------------------------------------------------------------------


@app.get("/api/payments")
async def payments(
    ticket_id: int | None = None,
    status: Literal["pending_approval", "approved", "rejected", "paid"] | None = None,
) -> list[dict]:
    """Payment and purchase-order requests the agents prepared, with their approval status."""
    requests = await mcp_call("list_payment_requests", {"ticket_id": ticket_id} if ticket_id else {})
    return [r for r in requests if status is None or r["status"] == status]


@app.post("/api/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: Decision) -> dict:
    """A human approves a payment / PO; this is the step that actually moves cash.

    Refuses (409) without recording approval if cash can't cover it. The MCP pay tool
    re-checks cash inside its transaction, so the balance can never go negative.
    """
    req = await _get_request(request_id)
    if req["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Request {request_id} is '{req['status']}', not pending approval.")

    cash = await mcp_call("get_cash_position")
    account = next((a for a in cash["accounts"] if a["account"] == req["account"]), None)
    balance = account["balance"] if account else 0.0
    if balance < req["amount"]:
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient cash: {req['account']} has ${balance:,.2f}, request needs ${req['amount']:,.2f}. Not approved.",
        )

    decision = await mcp_call(
        "record_human_decision",
        {"request_id": request_id, "decision": "approved", "approver": body.approver,
         "approval_token": HUMAN_APPROVAL_TOKEN, "note": body.note},
    )
    _fail_status(decision)
    paid = await mcp_call("execute_payment", {"request_id": request_id})
    if paid.get("ok") is False:
        raise HTTPException(status_code=409, detail=f"Approved but payment refused: {paid['error']}")
    return {"ok": True, "request_id": request_id, "approved_by": body.approver, "payment": paid["payment"], "cash": paid["cash"]}


@app.post("/api/payments/{request_id}/reject")
async def reject_payment(request_id: int, body: Decision) -> dict:
    """A human rejects a payment / PO. No money moves."""
    await _get_request(request_id)
    decision = await mcp_call(
        "record_human_decision",
        {"request_id": request_id, "decision": "rejected", "approver": body.approver,
         "approval_token": HUMAN_APPROVAL_TOKEN, "note": body.note},
    )
    _fail_status(decision)
    return {"ok": True, "request": decision["request"]}


@app.get("/api/cash")
async def cash() -> dict:
    """Current checking balance from cash_accounts, plus what's committed to outstanding requests."""
    position = await mcp_call("get_cash_position")
    checking = next((a for a in position["accounts"] if a["account"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No checking account in cash_accounts")
    return checking


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


@app.post("/api/reset")
async def reset() -> dict:
    """Restore data/campus_customs_new.db from the untouched original for a fresh run."""
    if _busy.locked():
        raise HTTPException(status_code=409, detail="Can't reset while a run is in progress.")
    async with _busy:
        result = await mcp_call("reset_working_database", {"approval_token": HUMAN_APPROVAL_TOKEN})
    _fail_status(result)
    reset_id = uuid.uuid4().hex[:12]
    await audit.append(AuditEntry(
        timestamp=audit.now_iso(), run_id=reset_id, ticket_id=None, agent="system", invocation_id=reset_id,
        event="reset", text=f"Working DB restored from original. Checking balance ${result['cash']['balance']:,.2f}.",
    ))
    return result | {"reset_id": reset_id}
