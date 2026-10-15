"""Route tests: real FastAPI app + real MCP server on the working DB (reset before and after).
The run route uses a scripted Boss model, so no LLM tokens are spent."""

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from backend import audit
from backend.agents import AGENTS
from backend.main import app

HUMAN = {"approver": "Test Human", "note": "ok"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "audit.json")
    with TestClient(app) as c:
        assert c.post("/api/reset").json()["ok"]
        yield c
        c.post("/api/reset")


def make_request(client, kind, ref_id, ticket_id):
    from backend.team import mcp_call

    async def go():
        return await mcp_call("request_payment", {"kind": kind, "ref_id": ref_id, "ticket_id": ticket_id,
                                                  "requested_by": "Accounting", "reason": "test"})
    return client.portal.call(go)["request"]["id"]


def test_tickets_and_cash(client):
    tickets = client.get("/api/tickets").json()
    assert [(t["id"], t["is_open"]) for t in tickets] == [(101, True), (102, True), (103, True)]
    assert client.get("/api/cash").json()["balance"] == 3400.0


def test_approve_moves_cash_and_blocks_double_pay(client):
    rid = make_request(client, "invoice", 501, 101)
    assert client.get("/api/payments", params={"status": "pending_approval"}).json()[0]["id"] == rid
    r = client.post(f"/api/payments/{rid}/approve", json=HUMAN)
    assert r.status_code == 200 and r.json()["payment"]["approved_by"] == "Test Human"
    assert client.get("/api/cash").json()["balance"] == 2560.0
    assert client.post(f"/api/payments/{rid}/approve", json=HUMAN).status_code == 409
    assert client.post(f"/api/payments/{rid}/approve", json={"approver": ""}).status_code == 422


def test_insufficient_cash_refused(client):
    rent = make_request(client, "rent", 1, 102)
    inv = make_request(client, "invoice", 501, 101)
    assert client.post(f"/api/payments/{rent}/approve", json=HUMAN).status_code == 200  # 3400 -> 1000
    # Add a big obligation the remaining $1,000 can't cover: second month's rent after advancing next_due.
    rent2 = make_request(client, "rent", 1, 102)
    assert client.post(f"/api/payments/{inv}/approve", json=HUMAN).status_code == 200   # 1000 -> 160
    r = client.post(f"/api/payments/{rent2}/approve", json=HUMAN)
    assert r.status_code == 409 and "Insufficient cash" in r.json()["detail"]
    assert client.get("/api/cash").json()["balance"] == 160.0
    assert client.get("/api/payments", params={"status": "pending_approval"}).json()[0]["id"] == rent2


def test_reject_and_reset(client):
    rid = make_request(client, "rent", 1, 102)
    assert client.post(f"/api/payments/{rid}/reject", json=HUMAN).json()["request"]["status"] == "rejected"
    assert client.post("/api/reset").json()["cash"]["balance"] == 3400.0
    assert client.get("/api/payments").json() == []


def test_run_ticket_and_events(client):
    def boss(messages, info: AgentInfo) -> ModelResponse:
        i = sum(isinstance(m, ModelResponse) for m in messages)
        if i == 0:
            return ModelResponse(parts=[ToolCallPart("get_ticket", {"ticket_id": 102})])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "ticket_id": 102, "ticket_status": "in_progress", "decision": "scripted"})])

    with AGENTS["boss"].override(model=FunctionModel(boss)):
        run = client.post("/api/tickets/102/run", params={"wait": True}).json()
    assert run["status"] == "completed", run
    assert client.get(f"/api/runs/{run['run_id']}").json()["result"]["decision"]["decision"] == "scripted"

    ev = client.get("/api/events", params={"run_id": run["run_id"]}).json()
    kinds = [e["event"] for e in ev["events"]]
    assert kinds[0] == "run_start" and kinds[-1] == "run_end"
    step = next(e for e in ev["events"] if e["tools"] and e["tools"][0]["tool"] == "get_ticket")
    assert step["agent"] == "Boss" and step["tool_calls"][0]["result"]["id"] == 102
    assert client.get("/api/events", params={"after": ev["last_id"]}).json()["events"] == []
    assert client.post("/api/tickets/999/run").status_code == 404
