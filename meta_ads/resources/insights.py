from __future__ import annotations

from typing import Any

from ..client import MetaClient

DEFAULT_FIELDS = "spend,impressions,reach,clicks,ctr,cpc,cpm,frequency,actions,cost_per_action_type"
PRESETS = ["today", "yesterday", "last_3d", "last_7d", "last_14d", "last_28d", "last_30d",
           "this_month", "last_month", "this_week_mon_today", "last_week_mon_sun", "maximum"]

RESULT_ACTIONS = ("lead", "purchase", "onsite_conversion.lead_grouped", "onsite_conversion.messaging_first_reply",
                  "link_click", "landing_page_view", "post_engagement", "video_view")


def insights(client: MetaClient, object_id: str, level: str = "campaign", preset: str | None = "last_7d",
             since: str | None = None, until: str | None = None, by_day: bool = False,
             fields: str = DEFAULT_FIELDS, limit: int = 200) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"level": level, "fields": f"{level}_name,{level}_id,{fields}"}
    if since or until:
        params["time_range"] = {"since": since, "until": until or since}
    else:
        params["date_preset"] = preset or "last_7d"
    if by_day:
        params["time_increment"] = 1
        params["fields"] = "date_start," + params["fields"]
    return client.get_all(f"{object_id}/insights", limit=limit, **params)


def flatten(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn the actions[] list into flat columns so it reads as a table."""
    out = []
    for r in rows:
        flat = {k: v for k, v in r.items() if k not in ("actions", "cost_per_action_type")}
        actions = {a["action_type"]: a["value"] for a in r.get("actions", []) if "action_type" in a}
        costs = {a["action_type"]: a["value"] for a in r.get("cost_per_action_type", []) if "action_type" in a}
        for key in RESULT_ACTIONS:
            if key in actions:
                short = key.split(".")[-1]
                flat[short] = actions[key]
                if key in costs:
                    flat[f"cost_per_{short}"] = costs[key]
        out.append(flat)
    return out
