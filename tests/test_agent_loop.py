"""Offline test of the agent loop: scripted models (no LLM calls) driving the real MCP server.

Checks delegation, MCP tool calls, delegation guards, role tool filtering, and audit logging.
"""

import asyncio
import json
from contextlib import ExitStack

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from backend import audit, team
from backend.agents import AGENTS
from backend.mcp_client import HUMAN_ONLY_TOOLS

seen_tools: dict[str, set[str]] = {}


def scripted(name: str, steps):
    """Build a FunctionModel that plays `steps[i]` on the i-th model call."""

    def fn(messages, info: AgentInfo) -> ModelResponse:
        seen_tools[name] = {t.name for t in info.function_tools}
        i = sum(isinstance(m, ModelResponse) for m in messages)
        tool, args = steps[i]
        if tool == "OUTPUT":
            tool = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool, args)])

    return FunctionModel(fn)


BOSS = [
    ("get_ticket", {"ticket_id": 103}),
    ("ask_agent", {"agent_name": "inventory", "question": "Can we fill 20 hoodies M?", "context": "CC-HOOD-NAVY M 20"}),
    ("OUTPUT", {"ticket_id": 103, "ticket_status": "blocked", "decision": "Short 12; vendor blocked."}),
]
INVENTORY = [
    ("check_stock_shortfall", {"sku": "CC-HOOD-NAVY", "size": "M", "qty_requested": 20}),
    ("ask_agent", {"agent_name": "boss", "question": "loop?", "context": "x"}),  # Boss is upstream -> refused
    ("OUTPUT", {"agent": "inventory", "ticket_id": 103, "status": "blocked", "summary": "8 on hand, 12 short."}),
]


def test_scripted_team_run(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "audit.json")
    with ExitStack() as stack:
        stack.enter_context(AGENTS["boss"].override(model=scripted("boss", BOSS)))
        stack.enter_context(AGENTS["inventory"].override(model=scripted("inventory", INVENTORY)))
        summary = asyncio.run(team.run_tickets([103]))

    result = summary["results"][0]
    assert result["ok"], result
    assert result["decision"]["ticket_status"] == "blocked"

    entries = json.loads((tmp_path / "audit.json").read_text())
    events = [(e["agent"], e["event"], e.get("ended")) for e in entries]
    assert ("Boss", "delegation", "delegated") in events
    assert ("Inventory", "delegation", "refused") in events  # cycle guard

    stock_step = next(e for e in entries if any(c["tool"] == "check_stock_shortfall" for c in e["tool_calls"]))
    call = stock_step["tool_calls"][0]
    assert stock_step["agent"] == "Inventory" and stock_step["ticket_id"] == 103
    assert call["result"]["qty_on_hand"] == 8 and call["result"]["shortfall"] == 12
    inv_start = next(e for e in entries if e["agent"] == "Inventory" and e["event"] == "agent_start")
    boss_start = next(e for e in entries if e["agent"] == "Boss" and e["event"] == "agent_start")
    assert inv_start["parent_invocation_id"] == boss_start["invocation_id"]

    # role filtering: each agent sees only its tools, and nobody gets the human approval tool
    assert "check_stock_shortfall" not in seen_tools["boss"]
    assert "execute_payment" not in seen_tools["inventory"]
    for tools in seen_tools.values():
        assert not tools & HUMAN_ONLY_TOOLS
        assert "ask_agent" in tools


def test_audit_keeps_existing_entries(tmp_path, monkeypatch):
    path = tmp_path / "audit.json"
    path.write_text(json.dumps([{"old": True}]))
    monkeypatch.setattr(audit, "AUDIT_PATH", path)
    from backend.models import AuditEntry

    asyncio.run(audit.append(AuditEntry(timestamp="t", run_id="r", ticket_id=1, agent="Boss", invocation_id="i", event="run_start")))
    data = json.loads(path.read_text())
    assert data[0] == {"old": True} and len(data) == 2

