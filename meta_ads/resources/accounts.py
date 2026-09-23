from __future__ import annotations

from typing import Any

from ..client import MetaClient

ACCOUNT_FIELDS = "id,name,account_status,currency,timezone_name,amount_spent,balance,spend_cap"
PAGE_FIELDS = "id,name,category"

ACCOUNT_STATUS = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
                  8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
                  101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED"}


def me(client: MetaClient) -> dict[str, Any]:
    return client.get("me", fields="id,name")


def token_scopes(client: MetaClient) -> dict[str, Any]:
    if not client.settings.access_token:
        # Token lives in the environment's API credential; we never see it, so
        # debug_token is unavailable. /me/permissions still reports grants.
        perms = client.get("me/permissions").get("data", [])
        return {
            "type": "via API credential (proxy)",
            "app_id": None,
            "expires_at": "unknown (not visible in proxy mode)",
            "is_valid": True,
            "scopes": [p["permission"] for p in perms if p.get("status") == "granted"],
        }
    data = client.get("debug_token", input_token=client.settings.access_token).get("data", {})
    return {
        "type": data.get("type"),
        "app_id": data.get("app_id"),
        "expires_at": data.get("expires_at") or "never",
        "is_valid": data.get("is_valid"),
        "scopes": data.get("scopes", []),
    }


def ad_accounts(client: MetaClient) -> list[dict[str, Any]]:
    rows = client.get_all("me/adaccounts", fields=ACCOUNT_FIELDS)
    for r in rows:
        r["account_status"] = ACCOUNT_STATUS.get(r.get("account_status"), r.get("account_status"))
    return rows


def account(client: MetaClient, account_id: str) -> dict[str, Any]:
    r = client.get(account_id, fields=ACCOUNT_FIELDS)
    r["account_status"] = ACCOUNT_STATUS.get(r.get("account_status"), r.get("account_status"))
    return r


def pages(client: MetaClient) -> list[dict[str, Any]]:
    return client.get_all("me/accounts", fields=PAGE_FIELDS)


def pixels(client: MetaClient, account_id: str) -> list[dict[str, Any]]:
    return client.get_all(f"{account_id}/adspixels", fields="id,name,last_fired_time")


def currency_scale(currency: str | None) -> int:
    """Minor units per major unit. Meta budgets are in minor units (cents)."""
    zero_decimal = {"JPY", "KRW", "CLP", "ISK", "HUF", "TWD", "VND", "PYG", "COP"}
    return 1 if (currency or "").upper() in zero_decimal else 100
