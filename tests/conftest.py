import os

import pytest
import respx
from typer.testing import CliRunner

BASE = "https://graph.facebook.com/v23.0"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "TESTTOKEN")
    monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_111")
    monkeypatch.setenv("META_PAGE_ID", "page1")
    monkeypatch.setenv("META_API_VERSION", "v23.0")
    monkeypatch.setenv("META_ADS_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("META_MAX_DAILY_BUDGET", raising=False)
    # config.STATE_DIR is read at import; patch the module attr too.
    import meta_ads.config as cfg
    monkeypatch.setattr(cfg, "STATE_DIR", tmp_path / "state")
    return tmp_path


@pytest.fixture
def api():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{BASE}/act_111").respond(json={"id": "act_111", "name": "Test", "currency": "USD", "account_status": 1})
        yield mock


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli():
    from meta_ads.cli import app
    return app
