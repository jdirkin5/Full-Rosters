import json

import pytest

from meta_ads import approvals, safety
from meta_ads.config import load_settings
from meta_ads.errors import ApprovalRequired, GuardrailError


def test_budget_threshold():
    s = load_settings()
    assert safety.budget_change_needs_approval(s, 1000, 1100)[0] is False   # exactly 10%
    assert safety.budget_change_needs_approval(s, 1000, 1101)[0] is True
    assert safety.budget_change_needs_approval(s, 1000, 850)[0] is True     # decreases count too
    assert safety.budget_change_needs_approval(s, None, 500)[0] is True     # new budget


def test_account_allowlist():
    s = load_settings()
    assert safety.check_account(s, None) == "act_111"
    assert safety.check_account(s, "111") == "act_111"
    with pytest.raises(GuardrailError):
        safety.check_account(s, "act_999")


def test_create_always_paused():
    assert safety.enforce_paused_on_create({"status": "ACTIVE"})["status"] == "PAUSED"


def test_daily_cap(monkeypatch):
    monkeypatch.setenv("META_MAX_DAILY_BUDGET", "50")
    s = load_settings()
    safety.check_daily_cap(s, 5000)
    with pytest.raises(GuardrailError):
        safety.check_daily_cap(s, 5001)


def test_approval_flow():
    s = load_settings()
    change = {"status": "ACTIVE"}
    with pytest.raises(ApprovalRequired) as e:
        approvals.require(s, "activate", "123", change, "ACTIVATE 123", None)
    aid = e.value.approval_id
    assert len(aid) == 10
    assert [p["id"] for p in approvals.list_pending(s)] == [aid]

    # wrong id refused
    with pytest.raises(GuardrailError):
        approvals.require(s, "activate", "123", change, "x", "0000000000")
    # different change under same id refused
    with pytest.raises(GuardrailError):
        approvals.require(s, "activate", "124", change, "x", aid)
    # right id accepted once, then consumed
    assert approvals.require(s, "activate", "123", change, "x", aid) == aid
    assert approvals.list_pending(s) == []
    with pytest.raises(GuardrailError):
        approvals.require(s, "activate", "123", change, "x", aid)
