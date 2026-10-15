"""Facilities: leases, rent obligations, and shop space."""

from ..models import SpecialistReport
from .base import make_agent

MCP_TOOLS = {
    "get_shop_date",
    "get_ticket",
    "get_rent_status",
    "get_cash_position",
    "list_payment_requests",
    "request_payment",
    "add_board_note",
}

facilities = make_agent("facilities", SpecialistReport, MCP_TOOLS)
