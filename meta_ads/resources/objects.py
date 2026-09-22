"""Campaigns, ad sets and ads share the same read/update/status/budget shape."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..client import MetaClient


@dataclass(frozen=True)
class Kind:
    name: str            # "campaign" | "adset" | "ad"
    edge: str            # "campaigns" | "adsets" | "ads"
    list_fields: str
    get_fields: str


CAMPAIGN = Kind(
    "campaign", "campaigns",
    "id,name,status,effective_status,objective,daily_budget,lifetime_budget,bid_strategy,created_time",
    "id,name,status,effective_status,objective,daily_budget,lifetime_budget,budget_remaining,"
    "bid_strategy,buying_type,special_ad_categories,start_time,stop_time,created_time,updated_time",
)
ADSET = Kind(
    "adset", "adsets",
    "id,name,status,effective_status,campaign_id,daily_budget,lifetime_budget,optimization_goal,start_time,end_time",
    "id,name,status,effective_status,campaign_id,daily_budget,lifetime_budget,budget_remaining,"
    "billing_event,optimization_goal,bid_strategy,bid_amount,targeting,promoted_object,"
    "destination_type,start_time,end_time,created_time,updated_time",
)
AD = Kind(
    "ad", "ads",
    "id,name,status,effective_status,adset_id,campaign_id,creative{id,name}",
    "id,name,status,effective_status,adset_id,campaign_id,creative{id,name,object_story_spec,thumbnail_url},"
    "created_time,updated_time",
)
KINDS = {k.name: k for k in (CAMPAIGN, ADSET, AD)}


def list_objects(client: MetaClient, kind: Kind, account_id: str, parent_id: str | None = None,
                 status: list[str] | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if parent_id:
        path = f"{parent_id}/{kind.edge}"
    else:
        path = f"{account_id}/{kind.edge}"
    params: dict[str, Any] = {"fields": kind.list_fields}
    if status:
        params["effective_status"] = [s.upper() for s in status]
    return client.get_all(path, limit=limit, **params)


def get_object(client: MetaClient, kind: Kind, object_id: str) -> dict[str, Any]:
    return client.get(object_id, fields=kind.get_fields)


def create_object(client: MetaClient, kind: Kind, account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return client.post(f"{account_id}/{kind.edge}", **payload)


def update_object(client: MetaClient, object_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return client.post(object_id, **payload)


def delete_object(client: MetaClient, object_id: str) -> dict[str, Any]:
    return client.delete(object_id)


def current_budget(obj: dict[str, Any]) -> tuple[str | None, int | None]:
    """Return (field, minor_units) for whichever budget the object carries."""
    for f in ("daily_budget", "lifetime_budget"):
        v = obj.get(f)
        if v not in (None, "", "0", 0):
            return f, int(v)
    return None, None
