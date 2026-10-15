"""Inventory: stock by SKU/size, shortfalls, vendors, and lead times."""

from ..models import SpecialistReport
from .base import make_agent

MCP_TOOLS = {
    "get_shop_date",
    "get_ticket",
    "check_stock_shortfall",
    "list_vendors",
    "get_invoice_status",
    "list_invoices",
    "propose_purchase_order",
    "list_payment_requests",
    "add_board_note",
}

inventory = make_agent("inventory", SpecialistReport, MCP_TOOLS)
