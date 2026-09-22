import json

BASE = "https://graph.facebook.com/v23.0"


def _last_audit(tmp_path):
    lines = (tmp_path / "state" / "audit.jsonl").read_text().splitlines()
    return json.loads(lines[-1])


def test_campaigns_list_formats_budget(api, runner, cli):
    api.get(f"{BASE}/act_111/campaigns").respond(json={"data": [
        {"id": "c1", "name": "Spring", "status": "PAUSED", "effective_status": "PAUSED",
         "objective": "OUTCOME_TRAFFIC", "daily_budget": "2500"}]})
    r = runner.invoke(cli, ["campaigns", "list"])
    assert r.exit_code == 0, r.output
    assert "25.00 USD" in r.output
    assert "Spring" in r.output


def test_campaign_create_is_paused_and_audited(api, runner, cli, env):
    route = api.post(f"{BASE}/act_111/campaigns").respond(json={"id": "c9"})
    r = runner.invoke(cli, ["campaigns", "create", "--name", "X", "--objective", "outcome_traffic", "--daily", "20"])
    assert r.exit_code == 0, r.output
    body = route.calls[0].request.content.decode()
    assert "status=PAUSED" in body
    assert "daily_budget=2000" in body
    assert "OUTCOME_TRAFFIC" in body
    assert _last_audit(env)["action"] == "campaign.create"


def test_create_refuses_unlisted_account(api, runner, cli):
    r = runner.invoke(cli, ["campaigns", "create", "--name", "X", "--objective", "OUTCOME_TRAFFIC", "-a", "act_999"])
    assert r.exit_code != 0
    assert "allowlist" in (r.output + str(r.exception))


def test_budget_small_change_goes_through(api, runner, cli):
    api.get(f"{BASE}/as1").respond(json={"id": "as1", "name": "Set", "daily_budget": "10000"})
    route = api.post(f"{BASE}/as1").respond(json={"success": True})
    r = runner.invoke(cli, ["adsets", "budget", "as1", "--daily", "105"])
    assert r.exit_code == 0, r.output
    assert "daily_budget=10500" in route.calls[0].request.content.decode()


def test_budget_big_change_needs_approval_then_applies(api, runner, cli, env):
    api.get(f"{BASE}/as1").respond(json={"id": "as1", "name": "Set", "daily_budget": "10000"})
    route = api.post(f"{BASE}/as1").respond(json={"success": True})

    r = runner.invoke(cli, ["adsets", "budget", "as1", "--daily", "150"])
    assert r.exit_code == 3, r.output
    assert "APPROVAL REQUIRED" in r.output
    assert route.call_count == 0
    aid = r.output.split("APPROVAL REQUIRED [")[1].split("]")[0]

    r = runner.invoke(cli, ["adsets", "budget", "as1", "--daily", "150", "--approve", aid])
    assert r.exit_code == 0, r.output
    assert "daily_budget=15000" in route.calls[0].request.content.decode()
    assert _last_audit(env)["approval_id"] == aid


def test_approval_id_bound_to_exact_change(api, runner, cli):
    api.get(f"{BASE}/as1").respond(json={"id": "as1", "name": "Set", "daily_budget": "10000"})
    route = api.post(f"{BASE}/as1").respond(json={"success": True})
    r = runner.invoke(cli, ["adsets", "budget", "as1", "--daily", "150"])
    aid = r.output.split("APPROVAL REQUIRED [")[1].split("]")[0]
    # try to sneak a different amount through with the approved id
    r = runner.invoke(cli, ["adsets", "budget", "as1", "--daily", "300", "--approve", aid])
    assert r.exit_code == 2, r.output
    assert route.call_count == 0


def test_activate_requires_approval_pause_does_not(api, runner, cli):
    api.get(f"{BASE}/c1").respond(json={"id": "c1", "name": "Camp", "status": "PAUSED"})
    route = api.post(f"{BASE}/c1").respond(json={"success": True})
    r = runner.invoke(cli, ["campaigns", "activate", "c1"])
    assert r.exit_code == 3
    assert route.call_count == 0
    r = runner.invoke(cli, ["campaigns", "pause", "c1"])
    assert r.exit_code == 0, r.output
    assert "status=PAUSED" in route.calls[0].request.content.decode()


def test_dry_run_sends_nothing(api, runner, cli):
    route = api.post(f"{BASE}/act_111/campaigns").respond(json={"id": "x"})
    r = runner.invoke(cli, ["campaigns", "create", "--name", "X", "--objective", "OUTCOME_LEADS", "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "DRY RUN" in r.output
    assert route.call_count == 0


def test_insights_flattens_actions(api, runner, cli):
    api.get(f"{BASE}/act_111/insights").respond(json={"data": [
        {"campaign_name": "Camp", "campaign_id": "c1", "spend": "12.50", "impressions": "1000", "clicks": "40",
         "actions": [{"action_type": "lead", "value": "3"}],
         "cost_per_action_type": [{"action_type": "lead", "value": "4.17"}]}]})
    r = runner.invoke(cli, ["insights"])
    assert r.exit_code == 0, r.output
    assert "cost_per_lead" in r.output and "4.17" in r.output


def test_build_from_spec(api, runner, cli, tmp_path):
    spec = tmp_path / "c.yaml"
    spec.write_text("""
name: Fall Tryouts
objective: OUTCOME_LEADS
budget: {daily: 30}
adsets:
  - name: Parents 25-55
    audience:
      countries: [US]
      age_min: 25
      age_max: 55
      interests: [{id: "6003", name: Basketball}]
    ads:
      - primary_text: Tryouts open now
        headline: Register today
        link: https://example.com/tryouts
        image_url: https://example.com/a.jpg
""")
    camp = api.post(f"{BASE}/act_111/campaigns").respond(json={"id": "c1"})
    adset = api.post(f"{BASE}/act_111/adsets").respond(json={"id": "as1"})
    img = api.post(f"{BASE}/act_111/adimages").respond(json={"images": {"a.jpg": {"hash": "H1", "url": "u"}}})
    creative = api.post(f"{BASE}/act_111/adcreatives").respond(json={"id": "cr1"})
    ad = api.post(f"{BASE}/act_111/ads").respond(json={"id": "ad1"})

    r = runner.invoke(cli, ["build", str(spec), "--dry-run"])
    assert r.exit_code == 0, r.output
    assert camp.call_count == 0

    r = runner.invoke(cli, ["build", str(spec)])
    assert r.exit_code == 0, r.output
    assert "status=PAUSED" in camp.calls[0].request.content.decode()
    adset_body = adset.calls[0].request.content.decode()
    assert "campaign_id=c1" in adset_body and "daily_budget=3000" in adset_body and "LEAD_GENERATION" in adset_body
    assert "image_hash%22%3A+%22H1" in creative.calls[0].request.content.decode() or "H1" in creative.calls[0].request.content.decode()
    ad_body = ad.calls[0].request.content.decode()
    assert "adset_id=as1" in ad_body and "cr1" in ad_body and "status=PAUSED" in ad_body
    assert "campaigns activate c1" in r.output
