import pytest

from meta_ads.config import load_settings
from meta_ads.errors import ConfigError

BASE = "https://graph.facebook.com/v23.0"


@pytest.fixture
def clients_file(tmp_path, monkeypatch):
    f = tmp_path / "clients.yaml"
    f.write_text("""
default: alpha
clients:
  alpha:
    ad_account: 111
    page_id: p-alpha
    pixel_id: px-alpha
  beta:
    ad_account: act_222
    page_id: p-beta
""")
    monkeypatch.setenv("META_CLIENTS_FILE", str(f))
    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("META_PAGE_ID", raising=False)
    return f


def test_clients_extend_allowlist_and_default(clients_file):
    s = load_settings()
    assert s.ad_account_ids == ["act_111", "act_222"]
    assert s.client == "alpha"
    assert s.default_account == "act_111"
    assert s.page_id == "p-alpha" and s.pixel_id == "px-alpha"


def test_select_client(clients_file):
    s = load_settings(client="beta")
    assert s.default_account == "act_222" and s.page_id == "p-beta"
    with pytest.raises(ConfigError):
        load_settings(client="nope")


def test_no_account_at_all_is_ok_until_needed(monkeypatch, tmp_path):
    monkeypatch.setenv("META_CLIENTS_FILE", str(tmp_path / "missing.yaml"))
    monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
    s = load_settings()
    assert s.ad_account_ids == []
    with pytest.raises(ConfigError):
        _ = s.default_account


def test_client_flag_routes_commands(clients_file, api, runner, cli):
    api.get(f"{BASE}/act_222").respond(json={"id": "act_222", "name": "Beta", "currency": "USD"})
    route = api.get(f"{BASE}/act_222/campaigns").respond(json={"data": []})
    r = runner.invoke(cli, ["--client", "beta", "campaigns", "list"])
    assert r.exit_code == 0, r.output
    assert route.call_count == 1
