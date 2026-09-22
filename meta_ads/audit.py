from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings

REDACT_KEYS = {"access_token", "token"}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("<redacted>" if k in REDACT_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def log_write(settings: Settings, action: str, target: str, payload: dict[str, Any] | None,
              result: Any, approval_id: str | None = None, dry_run: bool = False) -> None:
    """Append one line per write call to .meta-ads/audit.jsonl."""
    path: Path = settings.state_dir / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action,
        "target": target,
        "payload": _redact(payload or {}),
        "result": _redact(result) if not isinstance(result, Exception) else {"error": str(result)},
        "approval_id": approval_id,
        "dry_run": dry_run,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
