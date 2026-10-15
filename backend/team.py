"""Runs the team on tickets: reset the working DB, then let Boss work each open ticket."""

import json
import uuid
from typing import Any

from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from . import audit
from .agents import TeamDeps, TicketBudget, run_agent
from .config import HUMAN_APPROVAL_TOKEN, MODEL_NAME
from .mcp_client import SHOP_MCP, shop_connection
from .models import AuditEntry


async def mcp_call(tool: str, args: dict | None = None) -> Any:
    """Call an MCP tool directly (backend / human actions). Caller must hold SHOP_MCP open."""
    result = await SHOP_MCP.direct_call_tool(tool, args or {})
    return json.loads(result) if isinstance(result, str) else result


async def reset_working_db() -> dict:
    """Restore the working DB from the untouched original, via the human-only MCP tool."""
    async with shop_connection():
        return await mcp_call("reset_working_database", {"approval_token": HUMAN_APPROVAL_TOKEN})


async def _log_run(run_id: str, event: str, text: str, ticket_id: int | None = None, **extra) -> None:
    await audit.append(
        AuditEntry(
            timestamp=audit.now_iso(),
            run_id=run_id,
            ticket_id=ticket_id,
            agent="system",
            invocation_id=run_id,
            event=event,
            text=text,
            **extra,
        )
    )


async def resolve_ticket(ticket_id: int, run_id: str) -> dict:
    """Boss works one ticket, delegating as needed. Caller must hold the MCP connection open."""
    deps = TeamDeps(
        run_id=run_id,
        ticket_id=ticket_id,
        agent="boss",
        invocation_id=uuid.uuid4().hex[:12],
        budget=TicketBudget(),
    )
    usage = RunUsage()
    prompt = (
        f"Work ticket #{ticket_id}. Read it, coordinate the team, set its status honestly, "
        f"and return your TicketDecision."
    )
    try:
        decision = await run_agent("boss", prompt, deps, usage)
        result = {"ticket_id": ticket_id, "ok": True, "decision": decision.model_dump(mode="json")}
    except UsageLimitExceeded as exc:
        result = {"ticket_id": ticket_id, "ok": False, "error": f"Stopped: usage limit reached ({exc})"}
    except Exception as exc:
        result = {"ticket_id": ticket_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    result["usage"] = {"requests": usage.requests, "tool_calls": usage.tool_calls, "total_tokens": usage.total_tokens}
    return result


async def run_tickets(
    ticket_ids: list[int] | None = None, *, reset: bool = True, run_id: str | None = None
) -> dict:
    """Full ticket-resolution run. Resets the working DB first unless reset=False."""
    run_id = run_id or uuid.uuid4().hex[:12]
    async with shop_connection():
        if reset:
            restored = await mcp_call("reset_working_database", {"approval_token": HUMAN_APPROVAL_TOKEN})
            if not restored.get("ok"):
                raise RuntimeError(f"Reset failed: {restored}")
        if ticket_ids is None:
            ticket_ids = [t["id"] for t in await mcp_call("list_open_tickets")]
        await _log_run(run_id, "run_start", f"model={MODEL_NAME} reset={reset} tickets={ticket_ids}")
        results = [await resolve_ticket(tid, run_id) for tid in ticket_ids]
        await _log_run(run_id, "run_end", json.dumps([{k: r[k] for k in ("ticket_id", "ok")} for r in results]))
    return {"run_id": run_id, "results": results}
