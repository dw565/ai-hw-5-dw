"""Extract per-ticket facts for the final full run (everything after a given reset marker)."""

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def extract(reset_id: str) -> dict:
    events = json.loads((ROOT / "output" / "audit_trail.json").read_text())
    start = next(i for i, e in enumerate(events) if e["event"] == "reset" and e["run_id"] == reset_id)
    final = events[start:]
    run_ticket = {e["run_id"]: e["ticket_id"] for e in final if e.get("ticket_id")}
    tickets: dict[int, dict] = {}
    for e in final:
        tid = run_ticket.get(e["run_id"])
        if tid is None:
            continue
        t = tickets.setdefault(tid, {"runs": OrderedDict(), "delegations": [], "tools": {}, "agents": OrderedDict()})
        run = t["runs"].setdefault(e["run_id"], {"run_id": e["run_id"], "start": e["timestamp"], "end": None, "boss_status": None})
        run["end"] = e["timestamp"]
        if e["agent"] != "system":
            t["agents"].setdefault(e["agent"], {"summaries": [], "statuses": []})
        if e["event"] == "delegation":
            d = e["delegation"]
            t["delegations"].append({"run_id": e["run_id"], "from": e["agent"], "to": d["to"], "question": d["question"], "refused": d.get("refused")})
        if e["event"] == "loop_step":
            c = t["tools"].setdefault(e["agent"], Counter())
            for call in e["tool_calls"]:
                if call["tool"] not in ("final_result",):
                    c[call["tool"]] += 1
        if e["event"] == "agent_end":
            out = e["delegation"]["output"]
            a = t["agents"][e["agent"]]
            a["summaries"].append({"run_id": e["run_id"], "text": out.get("summary") or out.get("decision")})
            a["statuses"].append(out.get("status") or out.get("ticket_status"))
            if e["agent"] == "Boss" and e["depth"] == 0:
                run["boss_status"] = out.get("ticket_status")
                run["boss_output"] = out
    for t in tickets.values():
        t["runs"] = list(t["runs"].values())
        t["tools"] = {k: dict(v) for k, v in t["tools"].items()}
    return {"reset": events[start], "tickets": tickets}


if __name__ == "__main__":
    data = extract(sys.argv[1])
    print(json.dumps(data, indent=1, default=str)[: int(sys.argv[2]) if len(sys.argv) > 2 else None])
