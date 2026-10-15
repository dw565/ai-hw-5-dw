"""Paths, model, and safety limits shared by the backend."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"
MCP_SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "server.py"
AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# PORTKEY_API_KEY lives in the class-level .env (two folders up from this project).
load_dotenv(PROJECT_ROOT.parent.parent / ".env")
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = "gpt-6-luna"  # the ONLY model any agent may use

# Human approval token: generated per backend process and passed only to the MCP
# server's environment. Agents never see it, so they can't approve payments.
HUMAN_APPROVAL_TOKEN = os.getenv("HUMAN_APPROVAL_TOKEN") or secrets.token_urlsafe(32)

# Loop / delegation / token limits (per ticket; delegations share the ticket's budget).
MAX_DELEGATION_DEPTH = 2          # Boss -> specialist -> specialist, no deeper
MAX_DELEGATIONS_PER_TICKET = 8
TICKET_USAGE_LIMITS = UsageLimits(
    request_limit=40,             # model calls across all agents on one ticket
    tool_calls_limit=60,
    total_tokens_limit=300_000,
)
AGENT_RETRIES = 1
MODEL_TIMEOUT_SECONDS = 90  # per model request; a hung Portkey call fails fast and is retried
MODEL_HTTP_RETRIES = 2


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna via Portkey's OpenAI-compatible endpoint. No temperature override."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set (expected in the class-level .env).")
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL,
        api_key=api_key,
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_HTTP_RETRIES,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
