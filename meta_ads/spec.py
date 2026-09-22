"""Describe a whole campaign in one YAML file; the tool assembles the tree.

campaign -> ad set -> creative -> ad. Everything is created PAUSED.
See examples/campaign.yaml.
"""
from __future__ import annotations

from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from .client import MetaClient
from .config import Settings
from .resources import creatives as cr
from .resources import objects as ob
from .resources import targeting as tg
from .resources.accounts import account as get_account, currency_scale
from . import safety

Objective = Literal["OUTCOME_AWARENESS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT",
                    "OUTCOME_LEADS", "OUTCOME_APP_PROMOTION", "OUTCOME_SALES"]

# Sensible optimization defaults per objective when the spec does not say.
DEFAULT_OPTIMIZATION = {
    "OUTCOME_AWARENESS": ("REACH", None),
    "OUTCOME_TRAFFIC": ("LINK_CLICKS", "WEBSITE"),
    "OUTCOME_ENGAGEMENT": ("POST_ENGAGEMENT", None),
    "OUTCOME_LEADS": ("LEAD_GENERATION", "ON_AD"),
    "OUTCOME_SALES": ("OFFSITE_CONVERSIONS", "WEBSITE"),
    "OUTCOME_APP_PROMOTION": ("APP_INSTALLS", None),
}


class Budget(BaseModel):
    daily: float | None = None       # whole currency units, e.g. 25.00
    lifetime: float | None = None
    level: Literal["campaign", "adset"] = "adset"

    @model_validator(mode="after")
    def one_of(self):
        if (self.daily is None) == (self.lifetime is None):
            raise ValueError("budget needs exactly one of daily or lifetime")
        return self


class Audience(BaseModel):
    countries: list[str] | None = None
    regions: list[str] | None = None
    cities: list[dict[str, Any]] | None = None       # [{key, radius, distance_unit}]
    zips: list[str] | None = None
    custom_locations: list[dict[str, Any]] | None = None  # [{latitude, longitude, radius, distance_unit}]
    age_min: int = 18
    age_max: int = 65
    genders: list[int] | None = None                 # [1]=men, [2]=women
    interests: list[dict[str, Any]] | None = None    # [{id, name}] from `targeting interests`
    custom_audiences: list[str] | None = None
    excluded_custom_audiences: list[str] | None = None
    platforms: list[str] | None = None               # facebook, instagram, audience_network, messenger
    advantage_audience: bool = False
    extra: dict[str, Any] | None = None


class Creative(BaseModel):
    primary_text: str
    headline: str | None = None
    description: str | None = None
    link: str
    cta: str = "LEARN_MORE"
    image_path: str | None = None
    image_url: str | None = None
    image_hash: str | None = None
    video_id: str | None = None
    name: str | None = None
    extra: dict[str, Any] | None = None


class AdSetSpec(BaseModel):
    name: str
    audience: Audience = Field(default_factory=Audience)
    optimization_goal: str | None = None
    billing_event: str = "IMPRESSIONS"
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP"
    bid_amount: float | None = None
    destination_type: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    promoted_object: dict[str, Any] | None = None
    ads: list[Creative]
    extra: dict[str, Any] | None = None


class CampaignSpec(BaseModel):
    name: str
    objective: Objective
    special_ad_categories: list[str] = Field(default_factory=list)
    budget: Budget
    adsets: list[AdSetSpec]
    account: str | None = None
    page_id: str | None = None
    extra: dict[str, Any] | None = None


def load_spec(path: str) -> CampaignSpec:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return CampaignSpec.model_validate(data)


def plan(settings: Settings, spec: CampaignSpec, scale: int = 100) -> list[dict[str, Any]]:
    """Return the ordered list of API calls the build would make (for dry-run and tests)."""
    acct = settings.account_or_default(spec.account)
    page_id = spec.page_id or settings.page_id
    if not page_id:
        raise ValueError("page_id is required (spec.page_id or META_PAGE_ID)")

    calls: list[dict[str, Any]] = []
    camp: dict[str, Any] = {
        "name": spec.name,
        "objective": spec.objective,
        "special_ad_categories": spec.special_ad_categories,
        "buying_type": "AUCTION",
    }
    if spec.budget.level == "campaign":
        if spec.budget.daily is not None:
            camp["daily_budget"] = int(round(spec.budget.daily * scale))
        else:
            camp["lifetime_budget"] = int(round(spec.budget.lifetime * scale))
    if spec.extra:
        camp.update(spec.extra)
    calls.append({"step": "campaign", "path": f"{acct}/campaigns", "payload": safety.enforce_paused_on_create(camp)})

    default_goal, default_dest = DEFAULT_OPTIMIZATION[spec.objective]
    for i, aspec in enumerate(spec.adsets):
        a = aspec.audience
        adset: dict[str, Any] = {
            "name": aspec.name,
            "campaign_id": "$campaign_id",
            "billing_event": aspec.billing_event,
            "optimization_goal": aspec.optimization_goal or default_goal,
            "bid_strategy": aspec.bid_strategy,
            "targeting": tg.build_targeting(
                countries=a.countries, cities=a.cities, regions=a.regions, zips=a.zips,
                custom_locations=a.custom_locations, age_min=a.age_min, age_max=a.age_max,
                genders=a.genders, interests=a.interests, custom_audiences=a.custom_audiences,
                excluded_custom_audiences=a.excluded_custom_audiences, platforms=a.platforms,
                advantage_audience=a.advantage_audience, extra=a.extra),
        }
        dest = aspec.destination_type or default_dest
        if dest:
            adset["destination_type"] = dest
        if aspec.bid_amount is not None:
            adset["bid_amount"] = int(round(aspec.bid_amount * scale))
        if spec.budget.level == "adset":
            if spec.budget.daily is not None:
                adset["daily_budget"] = int(round(spec.budget.daily * scale))
            else:
                adset["lifetime_budget"] = int(round(spec.budget.lifetime * scale))
        if aspec.start_time:
            adset["start_time"] = aspec.start_time
        if aspec.end_time:
            adset["end_time"] = aspec.end_time
        elif spec.budget.lifetime is not None:
            raise ValueError(f"ad set '{aspec.name}': lifetime budgets require end_time")
        promoted = aspec.promoted_object
        if promoted is None:
            if spec.objective == "OUTCOME_SALES" and settings.pixel_id:
                promoted = {"pixel_id": settings.pixel_id, "custom_event_type": "PURCHASE"}
            elif spec.objective in ("OUTCOME_LEADS", "OUTCOME_ENGAGEMENT"):
                promoted = {"page_id": page_id}
        if promoted:
            adset["promoted_object"] = promoted
        if aspec.extra:
            adset.update(aspec.extra)
        calls.append({"step": f"adset[{i}]", "path": f"{acct}/adsets", "payload": safety.enforce_paused_on_create(adset)})

        for j, c in enumerate(aspec.ads):
            if c.image_path:
                calls.append({"step": f"image[{i}.{j}]", "path": f"{acct}/adimages", "payload": {"file": c.image_path}})
            elif c.image_url:
                calls.append({"step": f"image[{i}.{j}]", "path": f"{acct}/adimages", "payload": {"url": c.image_url}})
            creative = cr.build_link_creative(
                page_id=page_id, link=c.link, message=c.primary_text, headline=c.headline,
                description=c.description, image_hash=c.image_hash or ("$image_hash" if (c.image_path or c.image_url) else None),
                video_id=c.video_id, cta=c.cta, instagram_actor_id=settings.instagram_actor_id,
                name=c.name, extra=c.extra)
            calls.append({"step": f"creative[{i}.{j}]", "path": f"{acct}/adcreatives", "payload": creative})
            ad = {"name": c.name or f"{aspec.name} - ad {j + 1}", "adset_id": f"$adset_id[{i}]",
                  "creative": {"creative_id": f"$creative_id[{i}.{j}]"}}
            calls.append({"step": f"ad[{i}.{j}]", "path": f"{acct}/ads", "payload": safety.enforce_paused_on_create(ad)})
    return calls


def build(client: MetaClient, settings: Settings, spec: CampaignSpec, on_step=None) -> dict[str, Any]:
    """Execute the plan against the API, resolving ids as they are created."""
    acct = settings.account_or_default(spec.account)
    info = get_account(client, acct)
    scale = currency_scale(info.get("currency"))
    calls = plan(settings, spec, scale=scale)

    # Hard daily ceiling applies to any budget in the plan.
    for c in calls:
        safety.check_daily_cap(settings, c["payload"].get("daily_budget"), scale)

    ids: dict[str, str] = {}
    last_image_hash: str | None = None
    created: dict[str, Any] = {"campaign_id": None, "adsets": [], "ads": [], "creatives": [], "account": acct}

    for c in calls:
        step, path, payload = c["step"], c["path"], dict(c["payload"])
        if step.startswith("image"):
            r = cr.upload_image(client, acct, path=payload.get("file"), url=payload.get("url"))
            last_image_hash = r.get("hash")
            if on_step:
                on_step(step, r)
            continue
        # resolve placeholders
        payload = _resolve(payload, ids, last_image_hash)
        r = client.post(path, **payload)
        if on_step:
            on_step(step, r)
        if step == "campaign":
            ids["$campaign_id"] = r["id"]
            created["campaign_id"] = r["id"]
        elif step.startswith("adset"):
            ids[f"$adset_id[{step[6:-1]}]"] = r["id"]
            created["adsets"].append(r["id"])
        elif step.startswith("creative"):
            ids[f"$creative_id[{step[9:-1]}]"] = r["id"]
            created["creatives"].append(r["id"])
            last_image_hash = None
        elif step.startswith("ad["):
            created["ads"].append(r["id"])
    return created


def _resolve(obj: Any, ids: dict[str, str], image_hash: str | None) -> Any:
    if isinstance(obj, dict):
        return {k: _resolve(v, ids, image_hash) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve(v, ids, image_hash) for v in obj]
    if isinstance(obj, str):
        if obj == "$image_hash":
            if not image_hash:
                raise ValueError("image upload did not return a hash")
            return image_hash
        return ids.get(obj, obj)
    return obj
