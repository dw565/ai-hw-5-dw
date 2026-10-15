"""Shared agent machinery: construction, the audited agent loop, and delegation.

Every agent gets the same `ask_agent` tool, so any agent can delegate to any other
(full connectivity). Guards keep that from spiraling: no self-delegation, no
delegating to an agent already in the current chain, a depth cap, a per-ticket
delegation cap, and a shared per-ticket token / request budget.
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage

from .. import audit
from ..config import (
    AGENT_RETRIES,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_TICKET,
    PROMPTS_DIR,
    TICKET_USAGE_LIMITS,
    build_model,
)
from ..mcp_client import role_toolset
from ..models import AGENT_DISPLAY_NAMES, AgentName, AuditEntry, ToolCallRecord

AGENTS: dict[str, Agent] = {}


@dataclass
class TicketBudget:
    """Shared by every agent working on one ticket."""

    delegations: int = 0


@dataclass
class TeamDeps:
    run_id: str
    ticket_id: int
    agent: str
    invocation_id: str
    parent_invocation_id: str | None = None
    depth: int = 0
    chain: tuple[str, ...] = ()
    budget: TicketBudget = field(default_factory=TicketBudget)


def load_instructions(name: str) -> str:
    shared = (PROMPTS_DIR / "_shared_rules.md").read_text()
    role = (PROMPTS_DIR / f"{name}.md").read_text()
    return f"{role}\n\n{shared}"


def make_agent(name: AgentName, output_type: type[BaseModel], mcp_tools: set[str]) -> Agent:
    agent = Agent(
        build_model(),
        name=name,
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=load_instructions(name),
        toolsets=[role_toolset(mcp_tools)],
        retries=AGENT_RETRIES,
    )

    @agent.tool
    async def ask_agent(ctx: RunContext[TeamDeps], agent_name: AgentName, question: str, context: str) -> dict:
        """Delegate a focused question to a teammate who has the expertise.

        agent_name: boss | inventory | accounting | facilities | customer_service
        question: one clear question you need answered or task you need done.
        context: the ticket facts they need (ids, sku/size/qty, amounts you've verified).
        """
        return await delegate(ctx, agent_name, question, context)

    AGENTS[name] = agent
    return agent


def _parse(content: Any) -> Any:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content


def _outcome(result: Any) -> str:
    return "refused" if isinstance(result, dict) and result.get("ok") is False else "ok"


async def _log(deps: TeamDeps, **fields) -> None:
    await audit.append(
        AuditEntry(
            timestamp=audit.now_iso(),
            run_id=deps.run_id,
            ticket_id=deps.ticket_id,
            agent=AGENT_DISPLAY_NAMES.get(deps.agent, deps.agent),
            invocation_id=deps.invocation_id,
            parent_invocation_id=deps.parent_invocation_id,
            depth=deps.depth,
            **fields,
        )
    )


def _usage_dict(usage: RunUsage) -> dict:
    return {"requests": usage.requests, "tool_calls": usage.tool_calls, "total_tokens": usage.total_tokens}


async def run_agent(name: str, prompt: str, deps: TeamDeps, usage: RunUsage) -> BaseModel:
    """Run one agent's loop, writing an audit entry for every model step and its tool results."""
    agent = AGENTS[name]
    await _log(deps, event="agent_start", text=prompt)

    step = 0
    pending: dict[str, Any] | None = None  # the model step whose tool results we're waiting on

    async def flush(ended: str) -> None:
        nonlocal pending
        if pending is not None:
            await _log(
                deps,
                event="loop_step",
                step=pending["step"],
                text=pending["text"],
                tool_calls=list(pending["calls"].values()),
                ended=ended,
                usage=_usage_dict(usage),
            )
            pending = None

    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=TICKET_USAGE_LIMITS) as run:
            async for node in run:
                if Agent.is_call_tools_node(node):
                    step += 1
                    parts = node.model_response.parts
                    calls = {
                        p.tool_call_id: ToolCallRecord(tool=p.tool_name, args=_parse(p.args))
                        for p in parts
                        if isinstance(p, ToolCallPart)
                    }
                    text = "\n".join(p.content for p in parts if isinstance(p, TextPart)) or None
                    pending = {"step": step, "text": text, "calls": calls}
                elif Agent.is_model_request_node(node) and pending is not None:
                    for part in node.request.parts:
                        record = pending["calls"].get(getattr(part, "tool_call_id", None))
                        if record is None:
                            continue
                        if isinstance(part, ToolReturnPart):
                            record.result = _parse(part.content)
                            record.outcome = "output" if part.tool_name == "final_result" else _outcome(record.result)
                        elif isinstance(part, RetryPromptPart):
                            record.result = part.model_response()
                            record.outcome = "retry"
                    refused = any(c.outcome in ("refused", "retry") for c in pending["calls"].values())
                    await flush("refused" if refused else "tool_calls")
            output = run.result.output
    except UsageLimitExceeded as exc:
        await flush("limit_exceeded")
        await _log(deps, event="error", text=f"Usage limit exceeded: {exc}", ended="limit_exceeded", usage=_usage_dict(usage))
        raise
    except Exception as exc:
        await flush("error")
        await _log(deps, event="error", text=f"{type(exc).__name__}: {exc}", ended="error", usage=_usage_dict(usage))
        raise

    for record in (pending or {}).get("calls", {}).values():
        record.outcome = "output"
    await flush("final_output")
    await _log(
        deps,
        event="agent_end",
        text=getattr(output, "summary", None) or getattr(output, "decision", None),
        ended=getattr(output, "status", None) or getattr(output, "ticket_status", None),
        delegation={"output": output.model_dump(mode="json")},
        usage=_usage_dict(usage),
    )
    return output


async def delegate(ctx: RunContext[TeamDeps], target: str, question: str, context: str) -> dict:
    caller = ctx.deps
    refusal = None
    if target not in AGENTS:
        refusal = f"Unknown agent '{target}'."
    elif target == caller.agent:
        refusal = "You can't delegate to yourself; answer with your own tools."
    elif target in caller.chain:
        refusal = f"{AGENT_DISPLAY_NAMES[target]} is already working on this request upstream; answer with what you have."
    elif caller.depth >= MAX_DELEGATION_DEPTH:
        refusal = "Delegation depth limit reached; answer with what you have and note what's unverified."
    elif caller.budget.delegations >= MAX_DELEGATIONS_PER_TICKET:
        refusal = "Delegation budget for this ticket is used up; answer with what you have."

    delegation_info = {"from": caller.agent, "to": target, "question": question, "context": context}
    if refusal:
        await _log(caller, event="delegation", delegation=delegation_info | {"refused": refusal}, ended="refused")
        return {"ok": False, "error": refusal}

    caller.budget.delegations += 1
    child = TeamDeps(
        run_id=caller.run_id,
        ticket_id=caller.ticket_id,
        agent=target,
        invocation_id=uuid.uuid4().hex[:12],
        parent_invocation_id=caller.invocation_id,
        depth=caller.depth + 1,
        chain=caller.chain + (caller.agent,),
        budget=caller.budget,
    )
    await _log(caller, event="delegation", delegation=delegation_info | {"child_invocation_id": child.invocation_id}, ended="delegated")
    prompt = (
        f"Ticket #{caller.ticket_id}. {AGENT_DISPLAY_NAMES[caller.agent]} asks:\n{question}\n\n"
        f"Context from {AGENT_DISPLAY_NAMES[caller.agent]}:\n{context}"
    )
    try:
        report = await run_agent(target, prompt, child, ctx.usage)
    except UsageLimitExceeded:
        raise  # the whole ticket is out of budget; stop everything
    except Exception as exc:  # a teammate failing shouldn't crash the caller
        return {"ok": False, "error": f"{AGENT_DISPLAY_NAMES[target]} failed: {type(exc).__name__}: {exc}"}
    return {"ok": True, "report": report.model_dump(mode="json")}
