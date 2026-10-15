"""Append-only audit trail at output/audit_trail.json (a JSON array kept across runs)."""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

from .config import AUDIT_PATH
from .models import AuditEntry

_MAX_FIELD_CHARS = 4000
_lock = asyncio.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _clip(value: Any) -> Any:
    """Keep entries readable: very long strings are truncated, structure is preserved."""
    if isinstance(value, str) and len(value) > _MAX_FIELD_CHARS:
        return value[:_MAX_FIELD_CHARS] + f"... [truncated {len(value) - _MAX_FIELD_CHARS} chars]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value]
    return value


def _read_all() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text() or "[]")
    except json.JSONDecodeError:
        # Never silently drop history: keep the unreadable file aside and start a new one.
        AUDIT_PATH.rename(AUDIT_PATH.with_suffix(f".corrupt-{int(datetime.now().timestamp())}.json"))
        return []
    return data if isinstance(data, list) else []


async def append(entry: AuditEntry) -> None:
    async with _lock:
        entries = _read_all()
        entries.append(_clip(entry.model_dump(mode="json")))
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=2))
        os.replace(tmp, AUDIT_PATH)
