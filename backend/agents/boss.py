"""Boss: reads tickets, coordinates the team, and makes the final call."""

from ..models import TicketDecision
from .base import make_agent

MCP_TOOLS = {
    "get_shop_date",
    "list_open_tickets",
    "get_ticket",
    "get_board",
    "get_cash_position",
    "list_payment_requests",
    "add_board_note",
    "update_ticket_status",
}

boss = make_agent("boss", TicketDecision, MCP_TOOLS)
