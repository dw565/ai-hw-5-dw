"""Data types shared by the agent team, the audit trail, and (later) the API."""

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}

# What state a piece of work is actually in. Agents must not blur these.
WorkStatus = Literal[
    "info",               # findings only, nothing proposed or changed
    "proposed",           # a recommendation / draft exists, no approval needed or requested yet
    "awaiting_approval",  # a payment or PO request is waiting on a human
    "completed",          # a tool confirmed the change happened
    "blocked",            # can't proceed; blockers say why
]

TicketStatus = Literal["in_progress", "awaiting_approval", "blocked", "resolved"]


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service hands back."""

    agent: AgentName
    ticket_id: int
    status: WorkStatus
    summary: str = Field(description="2-4 sentences answering the question you were asked.")
    facts: list[str] = Field(
        default_factory=list,
        description="Verified facts, each naming the MCP tool it came from, e.g. 'qty_on_hand=8 (check_stock_shortfall)'.",
    )
    proposals: list[str] = Field(default_factory=list, description="Recommendations that still need a decision.")
    blockers: list[str] = Field(default_factory=list)
    payment_request_ids: list[int] = Field(default_factory=list, description="Requests created or referenced.")
    draft_ids: list[int] = Field(default_factory=list, description="Customer drafts saved on the board.")
    next_steps: list[str] = Field(default_factory=list)


class TicketDecision(BaseModel):
    """The Boss's final call on a ticket."""

    agent: Literal["boss"] = "boss"
    ticket_id: int
    ticket_status: TicketStatus
    decision: str = Field(description="What the shop will do and why, based on the team's findings.")
    dependencies: list[str] = Field(default_factory=list, description="What had to happen first, e.g. pay invoice before restock.")
    completed_actions: list[str] = Field(default_factory=list, description="Only actions a tool confirmed.")
    pending_human_approvals: list[int] = Field(default_factory=list, description="payment_request ids awaiting a human.")
    blockers: list[str] = Field(default_factory=list)
    customer_draft_ids: list[int] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    tool: str
    args: Any = None
    result: Any = None
    outcome: Literal["ok", "refused", "error", "retry", "output"] = "ok"


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json."""

    timestamp: str
    run_id: str
    ticket_id: int | None
    agent: str
    invocation_id: str
    parent_invocation_id: str | None = None
    depth: int = 0
    step: int | None = None
    event: Literal["reset", "run_start", "run_end", "agent_start", "loop_step", "delegation", "agent_end", "error"]
    text: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    delegation: dict[str, Any] | None = None
    ended: str | None = Field(
        default=None,
        description="How the step ended: tool_calls | final_output | refused | limit_exceeded | error | delegated",
    )
    usage: dict[str, Any] | None = None
