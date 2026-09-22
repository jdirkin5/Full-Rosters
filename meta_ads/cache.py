"""Small local cache of stable ids (accounts, pages, pixels, audiences).

Saves Claude from re-listing the same things every session.
"""
from __future__ import annotations

import json
from typing import Any

from .config import Settings


def _path(settings: Settings):
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    return settings.state_dir / "cache.json"


def read(settings: Settings) -> dict[str, Any]:
    p = _path(settings)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {}


def update(settings: Settings, **entries: Any) -> dict[str, Any]:
    data = read(settings)
    data.update(entries)
    _path(settings).write_text(json.dumps(data, indent=2, default=str))
    return data
