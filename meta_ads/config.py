from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigError

STATE_DIR = Path(os.environ.get("META_ADS_STATE_DIR", ".meta-ads"))


@dataclass
class Settings:
    access_token: str
    ad_account_ids: list[str]
    page_id: str | None = None
    instagram_actor_id: str | None = None
    pixel_id: str | None = None
    api_version: str = "v23.0"
    budget_change_approval_pct: float = 10.0
    max_daily_budget: float | None = None  # whole currency units
    token_via_proxy: bool = False  # token attached by the cloud environment's API credential, not by us
    state_dir: Path = field(default_factory=lambda: STATE_DIR)

    @property
    def default_account(self) -> str:
        return self.ad_account_ids[0]

    def account_or_default(self, account: str | None) -> str:
        acct = account or self.default_account
        if not acct.startswith("act_"):
            acct = f"act_{acct}"
        return acct


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def load_settings(require_token: bool = True) -> Settings:
    load_dotenv(override=False)
    token = _clean(os.environ.get("META_ACCESS_TOKEN"))
    via_proxy = (_clean(os.environ.get("META_TOKEN_VIA_PROXY")) or "").lower() in ("1", "true", "yes")
    if require_token and not token and not via_proxy:
        raise ConfigError(
            "META_ACCESS_TOKEN is not set (or set META_TOKEN_VIA_PROXY=1 if the token is an API credential "
            "on the cloud environment). See docs/RUNBOOK_META_SETUP.md Part F."
        )
    raw_accounts = _clean(os.environ.get("META_AD_ACCOUNT_ID")) or ""
    accounts = []
    for a in raw_accounts.split(","):
        a = a.strip()
        if not a:
            continue
        accounts.append(a if a.startswith("act_") else f"act_{a}")
    if not accounts:
        raise ConfigError("META_AD_ACCOUNT_ID is not set (format: act_1234567890).")

    max_budget = _clean(os.environ.get("META_MAX_DAILY_BUDGET"))
    return Settings(
        access_token=token or "",
        ad_account_ids=accounts,
        page_id=_clean(os.environ.get("META_PAGE_ID")),
        instagram_actor_id=_clean(os.environ.get("META_INSTAGRAM_ACTOR_ID")),
        pixel_id=_clean(os.environ.get("META_PIXEL_ID")),
        api_version=_clean(os.environ.get("META_API_VERSION")) or "v23.0",
        budget_change_approval_pct=float(_clean(os.environ.get("META_BUDGET_CHANGE_APPROVAL_PCT")) or 10),
        max_daily_budget=float(max_budget) if max_budget else None,
        token_via_proxy=via_proxy,
    )
