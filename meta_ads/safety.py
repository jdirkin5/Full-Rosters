"""Safety rules, enforced in code.

1. Writes only go to allowlisted ad accounts.
2. Everything is created PAUSED.
3. Setting any status to ACTIVE needs approval. Pausing never does.
4. Budget changes larger than META_BUDGET_CHANGE_APPROVAL_PCT (default 10%)
   in either direction need approval. So does setting a budget where none
   existed.
5. A daily budget above META_MAX_DAILY_BUDGET (if set) is refused outright.
6. Deletes need approval.
"""
from __future__ import annotations

from typing import Any

from .config import Settings
from .errors import GuardrailError

ACTIVE = "ACTIVE"
PAUSED = "PAUSED"
BUDGET_FIELDS = ("daily_budget", "lifetime_budget")


def check_account(settings: Settings, account: str) -> str:
    acct = settings.account_or_default(account)
    if acct not in settings.ad_account_ids:
        raise GuardrailError(
            f"{acct} is not in the allowlist ({', '.join(settings.ad_account_ids)}). "
            "Add it to META_AD_ACCOUNT_ID to write to it."
        )
    return acct


def enforce_paused_on_create(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["status"] = PAUSED
    return payload


def check_daily_cap(settings: Settings, daily_budget_minor: int | None, currency_scale: int = 100) -> None:
    if daily_budget_minor is None or settings.max_daily_budget is None:
        return
    if daily_budget_minor / currency_scale > settings.max_daily_budget:
        raise GuardrailError(
            f"Daily budget {daily_budget_minor / currency_scale:.2f} exceeds the hard ceiling "
            f"META_MAX_DAILY_BUDGET={settings.max_daily_budget:.2f}. Refused even with approval."
        )


def budget_change_needs_approval(settings: Settings, old_minor: int | None, new_minor: int) -> tuple[bool, str]:
    """Return (needs_approval, reason)."""
    if not old_minor:
        return True, "no existing budget on this object (any new budget counts as a >10% change)"
    pct = abs(new_minor - old_minor) / old_minor * 100
    threshold = settings.budget_change_approval_pct
    if pct > threshold:
        return True, f"{pct:.1f}% change exceeds the {threshold:g}% threshold"
    return False, f"{pct:.1f}% change is within the {threshold:g}% threshold"


def status_change_needs_approval(new_status: str) -> bool:
    return new_status.upper() == ACTIVE


def fmt_money(minor: int | None, currency: str = "", scale: int = 100) -> str:
    if minor is None:
        return "-"
    return f"{minor / scale:,.2f} {currency}".strip()
