from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .errors import ConfigError

STATE_DIR = Path(os.environ.get("META_ADS_STATE_DIR", ".meta-ads"))


@dataclass
class Client:
    name: str
    ad_account: str
    page_id: str | None = None
    pixel_id: str | None = None
    instagram_actor_id: str | None = None


@dataclass
class Settings:
    access_token: str
    ad_account_ids: list[str]
    clients: dict[str, Client] = field(default_factory=dict)
    client: str | None = None  # selected client name
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
        if self.client:
            return self.clients[self.client].ad_account
        if not self.ad_account_ids:
            raise ConfigError(
                "No ad account configured. Add clients to clients.yaml (run `meta-ads whoami` to get the ids) "
                "or set META_AD_ACCOUNT_ID."
            )
        return self.ad_account_ids[0]

    def account_or_default(self, account: str | None) -> str:
        acct = account or self.default_account
        if not acct.startswith("act_"):
            acct = f"act_{acct}"
        return acct

    def select_client(self, name: str | None) -> "Settings":
        """Apply a client's ids (account, page, pixel, instagram) as the defaults."""
        if not name:
            return self
        if name not in self.clients:
            raise ConfigError(f"Unknown client '{name}'. Known: {', '.join(self.clients) or 'none'} (see clients.yaml).")
        c = self.clients[name]
        self.client = name
        self.page_id = c.page_id or self.page_id
        self.pixel_id = c.pixel_id or self.pixel_id
        self.instagram_actor_id = c.instagram_actor_id or self.instagram_actor_id
        return self


def _norm_act(a: str) -> str:
    a = str(a).strip()
    return a if a.startswith("act_") else f"act_{a}"


def load_clients(path: Path) -> tuple[dict[str, Client], str | None]:
    if not path.exists():
        return {}, None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    clients: dict[str, Client] = {}
    for name, c in (data.get("clients") or {}).items():
        if not c or "ad_account" not in c:
            raise ConfigError(f"clients.yaml: client '{name}' needs an ad_account.")
        clients[name] = Client(
            name=name,
            ad_account=_norm_act(c["ad_account"]),
            page_id=str(c["page_id"]) if c.get("page_id") else None,
            pixel_id=str(c["pixel_id"]) if c.get("pixel_id") else None,
            instagram_actor_id=str(c["instagram_actor_id"]) if c.get("instagram_actor_id") else None,
        )
    default = data.get("default")
    if default and default not in clients:
        raise ConfigError(f"clients.yaml: default '{default}' is not a listed client.")
    return clients, default


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def load_settings(require_token: bool = True, client: str | None = None) -> Settings:
    load_dotenv(override=False)
    token = _clean(os.environ.get("META_ACCESS_TOKEN"))
    via_proxy = (_clean(os.environ.get("META_TOKEN_VIA_PROXY")) or "").lower() in ("1", "true", "yes")
    if require_token and not token and not via_proxy:
        raise ConfigError(
            "META_ACCESS_TOKEN is not set (or set META_TOKEN_VIA_PROXY=1 if the token is an API credential "
            "on the cloud environment). See docs/RUNBOOK_META_SETUP.md Part F."
        )
    raw_accounts = _clean(os.environ.get("META_AD_ACCOUNT_ID")) or ""
    accounts = [_norm_act(a) for a in raw_accounts.split(",") if a.strip()]
    clients, default_client = load_clients(Path(os.environ.get("META_CLIENTS_FILE", "clients.yaml")))
    for c in clients.values():
        if c.ad_account not in accounts:
            accounts.append(c.ad_account)

    max_budget = _clean(os.environ.get("META_MAX_DAILY_BUDGET"))
    settings = Settings(
        access_token=token or "",
        ad_account_ids=accounts,
        clients=clients,
        page_id=_clean(os.environ.get("META_PAGE_ID")),
        instagram_actor_id=_clean(os.environ.get("META_INSTAGRAM_ACTOR_ID")),
        pixel_id=_clean(os.environ.get("META_PIXEL_ID")),
        api_version=_clean(os.environ.get("META_API_VERSION")) or "v23.0",
        budget_change_approval_pct=float(_clean(os.environ.get("META_BUDGET_CHANGE_APPROVAL_PCT")) or 10),
        max_daily_budget=float(max_budget) if max_budget else None,
        token_via_proxy=via_proxy,
    )
    return settings.select_client(client or default_client)
