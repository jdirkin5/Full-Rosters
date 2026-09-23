import httpx
import pytest
import respx

from meta_ads.client import MetaClient
from meta_ads.config import load_settings
from meta_ads.errors import ApiError

BASE = "https://graph.facebook.com/v23.0"


def test_get_adds_token_and_encodes_json_params():
    s = load_settings()
    with respx.mock() as mock:
        route = mock.get(f"{BASE}/act_111/campaigns").respond(json={"data": [{"id": "1"}]})
        out = MetaClient(s).get("act_111/campaigns", fields="id", effective_status=["ACTIVE"])
    assert out["data"][0]["id"] == "1"
    req = route.calls[0].request
    assert "access_token=TESTTOKEN" in str(req.url)
    assert 'effective_status=%5B%22ACTIVE%22%5D' in str(req.url)


def test_error_surface():
    s = load_settings()
    with respx.mock() as mock:
        mock.get(f"{BASE}/me").respond(400, json={"error": {"message": "Invalid OAuth access token.", "code": 190,
                                                            "fbtrace_id": "abc"}})
        with pytest.raises(ApiError) as e:
            MetaClient(s).get("me")
    assert e.value.code == 190
    assert "Invalid OAuth" in str(e.value)
    assert "abc" in str(e.value)


def test_pagination_follows_next():
    s = load_settings()
    with respx.mock() as mock:
        route = mock.get(f"{BASE}/act_111/ads")
        route.side_effect = [
            httpx.Response(200, json={"data": [{"id": "1"}],
                                      "paging": {"next": f"{BASE}/act_111/ads?after=x&access_token=TESTTOKEN"}}),
            httpx.Response(200, json={"data": [{"id": "2"}]}),
        ]
        rows = MetaClient(s).get_all("act_111/ads", fields="id")
    assert [r["id"] for r in rows] == ["1", "2"]
    assert route.call_count == 2


def test_retries_rate_limit(monkeypatch):
    monkeypatch.setattr("meta_ads.client.time.sleep", lambda *_: None)
    s = load_settings()
    with respx.mock() as mock:
        route = mock.get(f"{BASE}/me")
        route.side_effect = [
            httpx.Response(400, json={"error": {"message": "rate", "code": 17}}),
            httpx.Response(200, json={"id": "me"}),
        ]
        assert MetaClient(s).get("me")["id"] == "me"
    assert route.call_count == 2


def test_proxy_mode_sends_no_token(monkeypatch):
    monkeypatch.delenv("META_ACCESS_TOKEN")
    monkeypatch.setenv("META_TOKEN_VIA_PROXY", "1")
    s = load_settings()
    assert s.token_via_proxy and not s.access_token
    with respx.mock() as mock:
        route = mock.get(f"{BASE}/me").respond(json={"id": "1"})
        MetaClient(s).get("me")
    assert "access_token" not in str(route.calls[0].request.url)


def test_proxy_mode_whoami_uses_permissions(monkeypatch):
    monkeypatch.delenv("META_ACCESS_TOKEN")
    monkeypatch.setenv("META_TOKEN_VIA_PROXY", "1")
    from meta_ads.resources.accounts import token_scopes
    s = load_settings()
    with respx.mock() as mock:
        mock.get(f"{BASE}/me/permissions").respond(json={"data": [
            {"permission": "ads_management", "status": "granted"},
            {"permission": "pages_manage_ads", "status": "declined"}]})
        out = token_scopes(MetaClient(s))
    assert out["scopes"] == ["ads_management"]
