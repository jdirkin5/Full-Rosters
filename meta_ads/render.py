"""Compact plain-text output. Tables by default, JSON on request."""
from __future__ import annotations

import json
from typing import Any, Iterable


def to_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def _cell(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, (dict, list)):
        s = json.dumps(v, separators=(",", ":"), default=str)
        return s if len(s) <= 60 else s[:57] + "..."
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def table(rows: Iterable[dict[str, Any]], columns: list[str] | None = None) -> str:
    rows = list(rows)
    if not rows:
        return "(no results)"
    cols = columns or list(rows[0].keys())
    matrix = [[_cell(r.get(c)) for c in cols] for r in rows]
    widths = [max(len(c), *(len(m[i]) for m in matrix)) for i, c in enumerate(cols)]
    line = "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    out = [line, "  ".join("-" * w for w in widths)]
    for m in matrix:
        out.append("  ".join(m[i].ljust(widths[i]) for i in range(len(cols))))
    return "\n".join(out)


def kv(obj: dict[str, Any]) -> str:
    width = max((len(k) for k in obj), default=0)
    return "\n".join(f"{k.ljust(width)}  {_cell(v) if not isinstance(v, (dict, list)) else json.dumps(v, default=str)}"
                     for k, v in obj.items())
