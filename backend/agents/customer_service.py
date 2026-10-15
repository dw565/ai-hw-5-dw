"""Customer Service: drafts customer messages from verified findings. Nothing is sent."""

from ..models import SpecialistReport
from .base import make_agent

MCP_TOOLS = {
    "get_shop_date",
    "get_ticket",
    "get_board",
    "save_customer_draft",
}

customer_service = make_agent("customer_service", SpecialistReport, MCP_TOOLS)
