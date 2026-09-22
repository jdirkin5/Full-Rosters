from __future__ import annotations

from typing import Any

from ..client import MetaClient


def search_interests(client: MetaClient, q: str, limit: int = 15) -> list[dict[str, Any]]:
    rows = client.get("search", type="adinterest", q=q, limit=limit).get("data", [])
    return [{"id": r.get("id"), "name": r.get("name"), "audience_size": r.get("audience_size_upper_bound"),
             "path": " > ".join(r.get("path", []))} for r in rows]


def search_locations(client: MetaClient, q: str, types: list[str] | None = None, limit: int = 15) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"type": "adgeolocation", "q": q, "limit": limit}
    if types:
        params["location_types"] = types
    rows = client.get("search", **params).get("data", [])
    return [{"key": r.get("key"), "name": r.get("name"), "type": r.get("type"), "region": r.get("region"),
             "country": r.get("country_code")} for r in rows]


def build_targeting(*, countries: list[str] | None = None, cities: list[dict[str, Any]] | None = None,
                    regions: list[str] | None = None, zips: list[str] | None = None,
                    custom_locations: list[dict[str, Any]] | None = None,
                    age_min: int = 18, age_max: int = 65, genders: list[int] | None = None,
                    interests: list[dict[str, Any]] | None = None,
                    custom_audiences: list[str] | None = None, excluded_custom_audiences: list[str] | None = None,
                    platforms: list[str] | None = None, advantage_audience: bool = False,
                    extra: dict[str, Any] | None = None) -> dict[str, Any]:
    geo: dict[str, Any] = {}
    if countries:
        geo["countries"] = [c.upper() for c in countries]
    if cities:
        geo["cities"] = cities
    if regions:
        geo["regions"] = [{"key": r} for r in regions]
    if zips:
        geo["zips"] = [{"key": z} for z in zips]
    if custom_locations:
        geo["custom_locations"] = custom_locations
    t: dict[str, Any] = {"geo_locations": geo or {"countries": ["US"]}, "age_min": age_min, "age_max": age_max,
                         "targeting_automation": {"advantage_audience": 1 if advantage_audience else 0}}
    if genders:
        t["genders"] = genders
    if interests:
        t["flexible_spec"] = [{"interests": interests}]
    if custom_audiences:
        t["custom_audiences"] = [{"id": a} for a in custom_audiences]
    if excluded_custom_audiences:
        t["excluded_custom_audiences"] = [{"id": a} for a in excluded_custom_audiences]
    if platforms:
        t["publisher_platforms"] = platforms
    if extra:
        t.update(extra)
    return t
