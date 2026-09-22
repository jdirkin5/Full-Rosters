"""Human approval gate.

Any operation the safety rules classify as "big" (activation, budget swings
above the threshold, deletes) does not run on the first call. Instead the tool
writes a pending record, prints a summary and an approval id, and exits.

Claude relays the summary to the human. Only after the human says yes does
Claude re-run the same command with --approve <id>. The id is a hash of the
exact change, so approving one change never authorises a different one.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import ApprovalRequired, GuardrailError

APPROVAL_TTL = timedelta(hours=24)


def _canonical(kind: str, target: str, change: dict[str, Any]) -> str:
    return json.dumps({"kind": kind, "target": target, "change": change},
                      sort_keys=True, separators=(",", ":"), default=str)


def approval_id_for(kind: str, target: str, change: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(kind, target, change).encode()).hexdigest()[:10]


def _pending_dir(settings: Settings) -> Path:
    d = settings.state_dir / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d


def require(settings: Settings, kind: str, target: str, change: dict[str, Any],
            summary: str, approve: str | None) -> str:
    """Return the approval id if `approve` matches this exact change, else raise.

    Raises ApprovalRequired (with the id) when no approval was supplied, and
    GuardrailError when an approval id was supplied but does not match.
    """
    aid = approval_id_for(kind, target, change)
    pending = _pending_dir(settings) / f"{aid}.json"

    if approve is None:
        record = {
            "id": aid,
            "kind": kind,
            "target": target,
            "change": change,
            "summary": summary,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        pending.write_text(json.dumps(record, indent=2, default=str))
        raise ApprovalRequired(aid, summary)

    if approve != aid:
        raise GuardrailError(
            f"Approval id {approve} does not match this change (expected {aid}). "
            "The change may differ from what was approved. Re-run without --approve to get a fresh id."
        )
    if not pending.exists():
        raise GuardrailError(
            f"No pending record for approval {aid}. Re-run without --approve first so the human sees the summary."
        )
    created = datetime.fromisoformat(json.loads(pending.read_text())["created_at"])
    if datetime.now(timezone.utc) - created > APPROVAL_TTL:
        pending.unlink()
        raise GuardrailError(f"Approval {aid} expired (older than 24h). Re-run without --approve.")
    pending.unlink()
    return aid


def list_pending(settings: Settings) -> list[dict[str, Any]]:
    out = []
    for p in sorted(_pending_dir(settings).glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except ValueError:
            continue
    return out


def clear_pending(settings: Settings) -> int:
    n = 0
    for p in _pending_dir(settings).glob("*.json"):
        p.unlink()
        n += 1
    return n
