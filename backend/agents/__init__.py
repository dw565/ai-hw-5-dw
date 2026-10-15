"""The five-agent Campus Customs team. Importing this package registers every agent."""

from .accounting import accounting
from .base import AGENTS, TeamDeps, TicketBudget, run_agent
from .boss import boss
from .customer_service import customer_service
from .facilities import facilities
from .inventory import inventory

__all__ = [
    "AGENTS",
    "TeamDeps",
    "TicketBudget",
    "run_agent",
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
]
