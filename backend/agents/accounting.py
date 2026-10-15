"""Accounting: cash, invoices, margins, and payment / PO requests for human approval."""

from ..models import SpecialistReport
from .base import make_agent

MCP_TOOLS = {
    "get_shop_date",
    "get_ticket",
    "get_board",
    "get_cash_position",
    "list_invoices",
    "get_invoice_status",
    "check_stock_shortfall",
    "evaluate_discount",
    "get_rent_status",
    "list_vendors",
    "request_payment",
    "propose_purchase_order",
    "list_payment_requests",
    "execute_payment",
    "add_board_note",
}

accounting = make_agent("accounting", SpecialistReport, MCP_TOOLS)
