"""The one MCP connection every agent shares. All shop lookups and updates go through it."""

import os
import sys
from contextlib import asynccontextmanager

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from . import config
from .config import HUMAN_APPROVAL_TOKEN, MCP_SERVER_SCRIPT, PROJECT_ROOT

# Tools only a human (via the backend / dashboard) may use. Never handed to an agent.
HUMAN_ONLY_TOOLS = frozenset({"record_human_decision", "reset_working_database"})


def _new_client() -> Client:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "CAMPUS_DB": str(config.WORKING_DB),  # read at connect time so tests can point elsewhere
        "HUMAN_APPROVAL_TOKEN": HUMAN_APPROVAL_TOKEN,
    }
    transport = StdioTransport(
        command=sys.executable,
        args=[str(MCP_SERVER_SCRIPT)],
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    return Client(transport)


SHOP_MCP = MCPToolset(_new_client(), id="campus-customs", max_retries=1)


@asynccontextmanager
async def shop_connection():
    """Hold the shared MCP connection open. Opening it from scratch builds a fresh client,
    so the toolset works across event loops (CLI runs, the API server, tests)."""
    if not SHOP_MCP.is_running:
        SHOP_MCP.client = _new_client()
        SHOP_MCP.__dict__.pop("_enter_lock", None)  # lock is bound to the previous event loop
    async with SHOP_MCP:
        yield SHOP_MCP


def role_toolset(allowed: set[str]):
    """A filtered view of the shared MCP toolset exposing only one role's tools."""
    leaked = allowed & HUMAN_ONLY_TOOLS
    if leaked:
        raise ValueError(f"Agents may not be given human-only tools: {sorted(leaked)}")
    return SHOP_MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)
