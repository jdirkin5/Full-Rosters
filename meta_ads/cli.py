"""meta-ads command line.

Every write command:
  - only touches allowlisted ad accounts,
  - supports --dry-run,
  - is appended to .meta-ads/audit.jsonl,
  - and, when the safety rules call for it, stops with an approval id until
    re-run with --approve <id> after the human says yes.
"""
from __future__ import annotations

import csv
import json
from typing import Any, Optional

import typer

from . import __version__, approvals, audit, cache, render, safety
from .client import MetaClient
from .config import Settings, load_settings
from .errors import ApprovalRequired, ConfigError, GuardrailError, MetaAdsError
from .resources import accounts as ac
from .resources import audiences as au
from .resources import creatives as cr
from .resources import insights as ins
from .resources import objects as ob
from .resources import targeting as tg
from . import spec as sp

class _Group(typer.core.TyperGroup):
    """Map tool errors to exit codes: 3 = approval required, 2 = refused, 1 = API/other error."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except ApprovalRequired as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(3)
        except (GuardrailError, ConfigError) as e:
            typer.echo(f"REFUSED: {e}", err=True)
            raise typer.Exit(2)
        except MetaAdsError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)


app = typer.Typer(help="Manage Meta ads from the terminal, with human-approval gates.", cls=_Group,
                  no_args_is_help=True, pretty_exceptions_enable=False, rich_markup_mode=None)

JSON_OPT = typer.Option(False, "--json", help="Print raw JSON instead of a table.")
ACCOUNT_OPT = typer.Option(None, "--account", "-a", help="Ad account id (act_...). Defaults to META_AD_ACCOUNT_ID.")
DRY_OPT = typer.Option(False, "--dry-run", help="Show the API call without sending it.")
APPROVE_OPT = typer.Option(None, "--approve", help="Approval id from a previous run, after the human said yes.")


# -- shared helpers ------------------------------------------------------------

def _ctx() -> tuple[Settings, MetaClient]:
    settings = load_settings()
    return settings, MetaClient(settings)


def _out(rows: Any, as_json: bool, columns: list[str] | None = None) -> None:
    if as_json:
        typer.echo(render.to_json(rows))
    elif isinstance(rows, list):
        typer.echo(render.table(rows, columns))
    elif isinstance(rows, dict):
        typer.echo(render.kv(rows))
    else:
        typer.echo(str(rows))


def _account_info(settings: Settings, client: MetaClient, acct: str) -> tuple[str, int]:
    c = cache.read(settings).get("accounts", {}).get(acct)
    if c and c.get("currency"):
        return c["currency"], ac.currency_scale(c["currency"])
    info = ac.account(client, acct)
    accounts = cache.read(settings).get("accounts", {})
    accounts[acct] = {"name": info.get("name"), "currency": info.get("currency")}
    cache.update(settings, accounts=accounts)
    return info.get("currency", ""), ac.currency_scale(info.get("currency"))


def _write(settings: Settings, client: MetaClient, action: str, target: str, payload: dict[str, Any],
           dry_run: bool, approval_id: str | None, fn) -> Any:
    if dry_run:
        typer.echo(f"DRY RUN {action} {target}")
        typer.echo(render.to_json(payload))
        audit.log_write(settings, action, target, payload, None, approval_id, dry_run=True)
        return None
    try:
        result = fn()
    except MetaAdsError as e:
        audit.log_write(settings, action, target, payload, e, approval_id)
        raise
    audit.log_write(settings, action, target, payload, result, approval_id)
    return result


def _fail(e: Exception, code: int = 1) -> None:
    typer.echo(str(e), err=True)
    raise typer.Exit(code)


def run():
    app()


# -- top level -----------------------------------------------------------------

@app.command()
def version():
    """Print the tool version."""
    typer.echo(__version__)


@app.command()
def whoami(as_json: bool = JSON_OPT):
    """Verify the token: who it is, its scopes, and the ad accounts and pages it can see."""
    settings, client = _ctx()
    me = ac.me(client)
    scopes = ac.token_scopes(client)
    accts = ac.ad_accounts(client)
    pages = ac.pages(client)
    needed = {"ads_management", "ads_read", "business_management", "pages_read_engagement", "pages_show_list"}
    missing = sorted(needed - set(scopes.get("scopes", [])))
    allow = set(settings.ad_account_ids)
    visible = {a["id"] for a in accts}
    cache.update(settings, accounts={a["id"]: {"name": a.get("name"), "currency": a.get("currency")} for a in accts},
                 pages={p["id"]: p.get("name") for p in pages})
    report = {
        "user": f"{me.get('name')} ({me.get('id')})",
        "token_type": scopes.get("type"),
        "expires": scopes.get("expires_at"),
        "scopes": ", ".join(scopes.get("scopes", [])),
        "missing_scopes": ", ".join(missing) or "none",
        "ad_accounts": [{"id": a["id"], "name": a.get("name"), "status": a.get("account_status"),
                         "currency": a.get("currency"), "allowlisted": a["id"] in allow} for a in accts],
        "pages": [{"id": p["id"], "name": p.get("name")} for p in pages],
        "allowlist_not_visible": sorted(allow - visible) or "none",
        "page_id_configured": settings.page_id or "NOT SET",
    }
    if as_json:
        typer.echo(render.to_json(report))
        return
    for k in ("user", "token_type", "expires", "scopes", "missing_scopes", "page_id_configured", "allowlist_not_visible"):
        typer.echo(f"{k:22}  {report[k]}")
    typer.echo("\nAd accounts:")
    typer.echo(render.table(report["ad_accounts"]))
    typer.echo("\nPages:")
    typer.echo(render.table(report["pages"]))


# -- accounts / pages ----------------------------------------------------------

accounts_app = typer.Typer(help="Ad accounts, pages, pixels.")
app.add_typer(accounts_app, name="accounts")


@accounts_app.command("list")
def accounts_list(as_json: bool = JSON_OPT):
    """List ad accounts the token can see."""
    _, client = _ctx()
    _out(ac.ad_accounts(client), as_json, ["id", "name", "account_status", "currency", "timezone_name", "amount_spent"])


@accounts_app.command("pages")
def accounts_pages(as_json: bool = JSON_OPT):
    """List Pages the token can act for."""
    _, client = _ctx()
    _out(ac.pages(client), as_json)


@accounts_app.command("pixels")
def accounts_pixels(account: Optional[str] = ACCOUNT_OPT, as_json: bool = JSON_OPT):
    """List pixels on an ad account."""
    settings, client = _ctx()
    _out(ac.pixels(client, settings.account_or_default(account)), as_json)


# -- campaigns / adsets / ads (shared command set) -----------------------------

def _register_object_commands(kind: ob.Kind, parent_flag: str | None):
    sub = typer.Typer(help=f"{kind.name.capitalize()}s: list, get, create, update, budget, pause, activate, delete.")
    app.add_typer(sub, name=kind.edge)

    @sub.command("list")
    def _list(account: Optional[str] = ACCOUNT_OPT,
              parent: Optional[str] = typer.Option(None, "--in", help=f"Only inside this {parent_flag}." if parent_flag else "(unused)"),
              status: Optional[str] = typer.Option(None, help="Comma list: ACTIVE,PAUSED,ARCHIVED,..."),
              limit: int = typer.Option(50), as_json: bool = JSON_OPT):
        settings, client = _ctx()
        acct = settings.account_or_default(account)
        currency, scale = _account_info(settings, client, acct)
        rows = ob.list_objects(client, kind, acct, parent, status.split(",") if status else None, limit)
        if not as_json:
            for r in rows:
                for f in ("daily_budget", "lifetime_budget"):
                    if r.get(f):
                        r[f] = safety.fmt_money(int(r[f]), currency, scale)
                if isinstance(r.get("creative"), dict):
                    r["creative"] = r["creative"].get("id")
        _out(rows, as_json)

    @sub.command("get")
    def _get(object_id: str, as_json: bool = JSON_OPT):
        _, client = _ctx()
        _out(ob.get_object(client, kind, object_id), as_json)

    @sub.command("update")
    def _update(object_id: str,
                name: Optional[str] = typer.Option(None),
                field: list[str] = typer.Option([], "--set", help="Raw field=value (JSON values allowed). Not for status or budgets."),
                dry_run: bool = DRY_OPT):
        """Rename or set other non-budget, non-status fields."""
        settings, client = _ctx()
        payload: dict[str, Any] = {}
        if name:
            payload["name"] = name
        for kv in field:
            k, _, v = kv.partition("=")
            if k in ("status", "daily_budget", "lifetime_budget"):
                raise GuardrailError(f"Use the budget / pause / activate commands for {k}.")
            try:
                payload[k] = json.loads(v)
            except ValueError:
                payload[k] = v
        if not payload:
            _fail(ValueError("nothing to update"))
        r = _write(settings, client, f"{kind.name}.update", object_id, payload, dry_run, None,
                   lambda: ob.update_object(client, object_id, payload))
        if r is not None:
            typer.echo(render.to_json(r))

    @sub.command("budget")
    def _budget(object_id: str,
                daily: Optional[float] = typer.Option(None, help="New daily budget in whole currency units."),
                lifetime: Optional[float] = typer.Option(None, help="New lifetime budget in whole currency units."),
                dry_run: bool = DRY_OPT, approve: Optional[str] = APPROVE_OPT):
        """Change a budget. Changes over the threshold (default 10%) need approval."""
        if (daily is None) == (lifetime is None):
            _fail(ValueError("give exactly one of --daily or --lifetime"))
        settings, client = _ctx()
        obj = ob.get_object(client, kind, object_id)
        acct = settings.account_or_default(None)
        currency, scale = _account_info(settings, client, acct)
        field_name = "daily_budget" if daily is not None else "lifetime_budget"
        new_minor = int(round((daily if daily is not None else lifetime) * scale))
        old_field, old_minor = ob.current_budget(obj)
        if field_name == "daily_budget":
            safety.check_daily_cap(settings, new_minor, scale)
        needs, reason = safety.budget_change_needs_approval(settings, old_minor if old_field == field_name else None, new_minor)
        payload = {field_name: new_minor}
        summary = (f"{kind.name} {object_id} '{obj.get('name')}': {field_name} "
                   f"{safety.fmt_money(old_minor if old_field == field_name else None, currency, scale)} -> "
                   f"{safety.fmt_money(new_minor, currency, scale)} ({reason})")
        approval_id = None
        if needs and not dry_run:
            approval_id = approvals.require(settings, "budget", object_id, payload, summary, approve)
        typer.echo(summary)
        r = _write(settings, client, f"{kind.name}.budget", object_id, payload, dry_run, approval_id,
                   lambda: ob.update_object(client, object_id, payload))
        if r is not None:
            typer.echo("OK " + render.to_json(r))

    @sub.command("pause")
    def _pause(object_id: str, dry_run: bool = DRY_OPT):
        """Pause. Never needs approval."""
        settings, client = _ctx()
        payload = {"status": safety.PAUSED}
        r = _write(settings, client, f"{kind.name}.pause", object_id, payload, dry_run, None,
                   lambda: ob.update_object(client, object_id, payload))
        if r is not None:
            typer.echo("OK paused " + object_id)

    @sub.command("activate")
    def _activate(object_id: str, dry_run: bool = DRY_OPT, approve: Optional[str] = APPROVE_OPT):
        """Set status ACTIVE. Always needs approval."""
        settings, client = _ctx()
        obj = ob.get_object(client, kind, object_id)
        acct = settings.account_or_default(None)
        currency, scale = _account_info(settings, client, acct)
        bf, bm = ob.current_budget(obj)
        summary = (f"ACTIVATE {kind.name} {object_id} '{obj.get('name')}' "
                   f"(current status {obj.get('status')}, {bf or 'no budget'} {safety.fmt_money(bm, currency, scale)})")
        payload = {"status": safety.ACTIVE}
        approval_id = None
        if not dry_run:
            approval_id = approvals.require(settings, "activate", object_id, payload, summary, approve)
        typer.echo(summary)
        r = _write(settings, client, f"{kind.name}.activate", object_id, payload, dry_run, approval_id,
                   lambda: ob.update_object(client, object_id, payload))
        if r is not None:
            typer.echo("OK activated " + object_id)

    @sub.command("delete")
    def _delete(object_id: str, dry_run: bool = DRY_OPT, approve: Optional[str] = APPROVE_OPT):
        """Delete. Always needs approval."""
        settings, client = _ctx()
        obj = ob.get_object(client, kind, object_id)
        summary = f"DELETE {kind.name} {object_id} '{obj.get('name')}' (status {obj.get('status')})"
        approval_id = None
        if not dry_run:
            approval_id = approvals.require(settings, "delete", object_id, {"delete": True}, summary, approve)
        typer.echo(summary)
        r = _write(settings, client, f"{kind.name}.delete", object_id, {"delete": True}, dry_run, approval_id,
                   lambda: ob.delete_object(client, object_id))
        if r is not None:
            typer.echo("OK deleted " + object_id)

    return sub


campaigns_app = _register_object_commands(ob.CAMPAIGN, None)
adsets_app = _register_object_commands(ob.ADSET, "campaign id")
ads_app = _register_object_commands(ob.AD, "ad set id")


@campaigns_app.command("create")
def campaign_create(name: str = typer.Option(...),
                    objective: str = typer.Option(..., help="OUTCOME_TRAFFIC, OUTCOME_LEADS, OUTCOME_SALES, OUTCOME_ENGAGEMENT, OUTCOME_AWARENESS, OUTCOME_APP_PROMOTION"),
                    daily: Optional[float] = typer.Option(None, help="Campaign-level daily budget (CBO)."),
                    lifetime: Optional[float] = typer.Option(None),
                    special: str = typer.Option("", help="Comma list of special ad categories (HOUSING, CREDIT, EMPLOYMENT, ...)"),
                    account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    """Create a campaign (PAUSED)."""
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    _, scale = _account_info(settings, client, acct)
    payload: dict[str, Any] = {"name": name, "objective": objective.upper(), "buying_type": "AUCTION",
                               "special_ad_categories": [s.strip().upper() for s in special.split(",") if s.strip()]}
    if daily is not None:
        payload["daily_budget"] = int(round(daily * scale))
        safety.check_daily_cap(settings, payload["daily_budget"], scale)
    if lifetime is not None:
        payload["lifetime_budget"] = int(round(lifetime * scale))
    payload = safety.enforce_paused_on_create(payload)
    r = _write(settings, client, "campaign.create", acct, payload, dry_run, None,
               lambda: ob.create_object(client, ob.CAMPAIGN, acct, payload))
    if r is not None:
        typer.echo("OK created campaign " + r["id"])


@adsets_app.command("create")
def adset_create(name: str = typer.Option(...), campaign: str = typer.Option(..., help="Campaign id."),
                 daily: Optional[float] = typer.Option(None), lifetime: Optional[float] = typer.Option(None),
                 optimization_goal: str = typer.Option("LINK_CLICKS"),
                 billing_event: str = typer.Option("IMPRESSIONS"),
                 countries: str = typer.Option("US", help="Comma list of country codes."),
                 age_min: int = typer.Option(18), age_max: int = typer.Option(65),
                 interests: str = typer.Option("", help="Comma list of interest ids from `targeting interests`."),
                 custom_audiences: str = typer.Option("", help="Comma list of custom audience ids."),
                 platforms: str = typer.Option("", help="Comma list: facebook,instagram,..."),
                 start_time: Optional[str] = typer.Option(None), end_time: Optional[str] = typer.Option(None),
                 destination_type: Optional[str] = typer.Option(None),
                 targeting_json: Optional[str] = typer.Option(None, help="Full targeting JSON (overrides the flags above)."),
                 account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    """Create an ad set (PAUSED)."""
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    _, scale = _account_info(settings, client, acct)
    if targeting_json:
        targeting = json.loads(targeting_json)
    else:
        targeting = tg.build_targeting(
            countries=[c.strip() for c in countries.split(",") if c.strip()], age_min=age_min, age_max=age_max,
            interests=[{"id": i.strip()} for i in interests.split(",") if i.strip()] or None,
            custom_audiences=[a.strip() for a in custom_audiences.split(",") if a.strip()] or None,
            platforms=[p.strip() for p in platforms.split(",") if p.strip()] or None)
    payload: dict[str, Any] = {"name": name, "campaign_id": campaign, "billing_event": billing_event.upper(),
                               "optimization_goal": optimization_goal.upper(),
                               "bid_strategy": "LOWEST_COST_WITHOUT_CAP", "targeting": targeting}
    if daily is not None:
        payload["daily_budget"] = int(round(daily * scale))
        safety.check_daily_cap(settings, payload["daily_budget"], scale)
    if lifetime is not None:
        payload["lifetime_budget"] = int(round(lifetime * scale))
    for k, v in (("start_time", start_time), ("end_time", end_time), ("destination_type", destination_type)):
        if v:
            payload[k] = v
    payload = safety.enforce_paused_on_create(payload)
    r = _write(settings, client, "adset.create", acct, payload, dry_run, None,
               lambda: ob.create_object(client, ob.ADSET, acct, payload))
    if r is not None:
        typer.echo("OK created ad set " + r["id"])


@ads_app.command("create")
def ad_create(name: str = typer.Option(...), adset: str = typer.Option(..., help="Ad set id."),
              creative: str = typer.Option(..., help="Creative id."),
              account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    """Create an ad from an existing creative (PAUSED)."""
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    payload = safety.enforce_paused_on_create({"name": name, "adset_id": adset, "creative": {"creative_id": creative}})
    r = _write(settings, client, "ad.create", acct, payload, dry_run, None,
               lambda: ob.create_object(client, ob.AD, acct, payload))
    if r is not None:
        typer.echo("OK created ad " + r["id"])


# -- creatives -----------------------------------------------------------------

creatives_app = typer.Typer(help="Ad creatives and image uploads.")
app.add_typer(creatives_app, name="creatives")


@creatives_app.command("list")
def creatives_list(account: Optional[str] = ACCOUNT_OPT, limit: int = typer.Option(25), as_json: bool = JSON_OPT):
    settings, client = _ctx()
    rows = cr.list_creatives(client, settings.account_or_default(account), limit)
    _out(rows, as_json, ["id", "name", "status", "thumbnail_url"])


@creatives_app.command("upload-image")
def creatives_upload(path: Optional[str] = typer.Option(None, help="Local image file."),
                     url: Optional[str] = typer.Option(None, help="Or a public image URL."),
                     account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    """Upload an image; prints the image hash to use in creatives."""
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    payload = {"path": path, "url": url}
    r = _write(settings, client, "image.upload", acct, payload, dry_run, None,
               lambda: cr.upload_image(client, acct, path=path, url=url))
    if r is not None:
        typer.echo(render.kv(r))


@creatives_app.command("create")
def creatives_create(link: str = typer.Option(...), primary_text: str = typer.Option(...),
                     headline: Optional[str] = typer.Option(None), description: Optional[str] = typer.Option(None),
                     image_hash: Optional[str] = typer.Option(None), video_id: Optional[str] = typer.Option(None),
                     cta: str = typer.Option("LEARN_MORE", help="One of: " + ", ".join(cr.CTA_TYPES)),
                     name: Optional[str] = typer.Option(None), page: Optional[str] = typer.Option(None, help="Page id (defaults to META_PAGE_ID)."),
                     account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    """Create a link ad creative (image or video)."""
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    page_id = page or settings.page_id
    if not page_id:
        _fail(ConfigError("META_PAGE_ID is not set and --page not given"))
    payload = cr.build_link_creative(page_id=page_id, link=link, message=primary_text, headline=headline,
                                     description=description, image_hash=image_hash, video_id=video_id, cta=cta,
                                     instagram_actor_id=settings.instagram_actor_id, name=name)
    r = _write(settings, client, "creative.create", acct, payload, dry_run, None,
               lambda: cr.create_creative(client, acct, payload))
    if r is not None:
        typer.echo("OK created creative " + r["id"])


# -- audiences -----------------------------------------------------------------

aud_app = typer.Typer(help="Custom, lookalike and saved audiences.")
app.add_typer(aud_app, name="audiences")


@aud_app.command("list")
def aud_list(account: Optional[str] = ACCOUNT_OPT, saved: bool = typer.Option(False, help="List saved audiences instead."),
             as_json: bool = JSON_OPT):
    settings, client = _ctx()
    acct = settings.account_or_default(account)
    rows = au.list_saved(client, acct) if saved else au.list_custom(client, acct)
    _out(rows, as_json)


@aud_app.command("create")
def aud_create(name: str = typer.Option(...), description: str = typer.Option(""),
               account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    """Create an empty customer-list custom audience."""
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    payload = {"name": name, "description": description}
    r = _write(settings, client, "audience.create", acct, payload, dry_run, None,
               lambda: au.create_custom(client, acct, name, description))
    if r is not None:
        typer.echo("OK created audience " + r["id"])


@aud_app.command("add-users")
def aud_add_users(audience_id: str, csv_path: str = typer.Option(..., "--csv", help="CSV with columns like email, phone, fn, ln."),
                  schema: str = typer.Option("EMAIL", help="Comma list of columns to send: EMAIL,PHONE,FN,LN,ZIP,..."),
                  dry_run: bool = DRY_OPT):
    """Hash a customer CSV locally (SHA-256) and upload it to a custom audience."""
    settings, client = _ctx()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = [s.strip().upper() for s in schema.split(",")]
    payload = {"csv": csv_path, "schema": cols, "rows": len(rows)}
    r = _write(settings, client, "audience.add_users", audience_id, payload, dry_run, None,
               lambda: au.add_users(client, audience_id, rows, cols))
    if r is not None:
        typer.echo(render.kv(r))


@aud_app.command("lookalike")
def aud_lookalike(name: str = typer.Option(...), source: str = typer.Option(..., help="Origin custom audience id."),
                  country: str = typer.Option("US"), ratio: float = typer.Option(0.01, help="0.01 = top 1%."),
                  account: Optional[str] = ACCOUNT_OPT, dry_run: bool = DRY_OPT):
    settings, client = _ctx()
    acct = safety.check_account(settings, account)
    payload = {"name": name, "origin_audience_id": source, "country": country, "ratio": ratio}
    r = _write(settings, client, "audience.lookalike", acct, payload, dry_run, None,
               lambda: au.create_lookalike(client, acct, name, source, country, ratio))
    if r is not None:
        typer.echo("OK created lookalike " + r["id"])


# -- targeting search ----------------------------------------------------------

tgt_app = typer.Typer(help="Look up interest and location ids for targeting.")
app.add_typer(tgt_app, name="targeting")


@tgt_app.command("interests")
def tgt_interests(q: str, limit: int = typer.Option(15), as_json: bool = JSON_OPT):
    _, client = _ctx()
    _out(tg.search_interests(client, q, limit), as_json)


@tgt_app.command("locations")
def tgt_locations(q: str, types: str = typer.Option("", help="Comma list: country,region,city,zip"),
                  limit: int = typer.Option(15), as_json: bool = JSON_OPT):
    _, client = _ctx()
    _out(tg.search_locations(client, q, [t for t in types.split(",") if t] or None, limit), as_json)


# -- insights ------------------------------------------------------------------

@app.command()
def insights(object_id: Optional[str] = typer.Argument(None, help="Account, campaign, ad set or ad id. Defaults to the account."),
             level: str = typer.Option("campaign", help="campaign | adset | ad | account"),
             preset: str = typer.Option("last_7d", help="One of: " + ", ".join(ins.PRESETS)),
             since: Optional[str] = typer.Option(None, help="YYYY-MM-DD (with --until)"),
             until: Optional[str] = typer.Option(None),
             by_day: bool = typer.Option(False, help="One row per day."),
             account: Optional[str] = ACCOUNT_OPT, as_json: bool = JSON_OPT):
    """Performance: spend, impressions, clicks, CPC, results."""
    settings, client = _ctx()
    target = object_id or settings.account_or_default(account)
    rows = ins.insights(client, target, level=level, preset=preset, since=since, until=until, by_day=by_day)
    if as_json:
        typer.echo(render.to_json(rows))
        return
    flat = ins.flatten(rows)
    typer.echo(render.table(flat))


# -- spec build ----------------------------------------------------------------

@app.command()
def build(spec_path: str = typer.Argument(..., help="YAML campaign spec (see examples/campaign.yaml)."),
          dry_run: bool = DRY_OPT):
    """Build a whole campaign (campaign, ad sets, creatives, ads) from a YAML spec. Everything is PAUSED."""
    settings, client = _ctx()
    spec = sp.load_spec(spec_path)
    acct = safety.check_account(settings, spec.account)
    if dry_run:
        calls = sp.plan(settings, spec)
        for c in calls:
            typer.echo(f"\n== {c['step']}  POST {c['path']}")
            typer.echo(render.to_json(c["payload"]))
        audit.log_write(settings, "build", acct, {"spec": spec_path, "steps": len(calls)}, None, dry_run=True)
        return

    def on_step(step, r):
        typer.echo(f"{step:16} -> {r.get('id') or r.get('hash') or r}")

    try:
        created = sp.build(client, settings, spec, on_step=on_step)
    except MetaAdsError as e:
        audit.log_write(settings, "build", acct, {"spec": spec_path}, e)
        raise
    audit.log_write(settings, "build", acct, {"spec": spec_path}, created)
    typer.echo("\nCreated (all PAUSED):")
    typer.echo(render.kv(created))
    typer.echo(f"\nReview in Ads Manager, then: meta-ads campaigns activate {created['campaign_id']}")


# -- pending approvals ---------------------------------------------------------

pending_app = typer.Typer(help="Changes waiting for human approval.")
app.add_typer(pending_app, name="pending")


@pending_app.command("list")
def pending_list(as_json: bool = JSON_OPT):
    settings = load_settings(require_token=False)
    rows = approvals.list_pending(settings)
    _out(rows, as_json, ["id", "kind", "target", "summary", "created_at"])


@pending_app.command("clear")
def pending_clear():
    settings = load_settings(require_token=False)
    typer.echo(f"cleared {approvals.clear_pending(settings)} pending approval(s)")


@app.command()
def audit_log(last: int = typer.Option(20, help="Show the last N write entries.")):
    """Show recent write calls from .meta-ads/audit.jsonl."""
    settings = load_settings(require_token=False)
    p = settings.state_dir / "audit.jsonl"
    if not p.exists():
        typer.echo("(no audit entries yet)")
        return
    lines = p.read_text(encoding="utf-8").splitlines()[-last:]
    rows = []
    for ln in lines:
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        rows.append({"ts": e["ts"], "action": e["action"], "target": e["target"],
                     "approval": e.get("approval_id") or "-", "dry_run": e.get("dry_run"),
                     "result": e.get("result")})
    typer.echo(render.table(rows))


if __name__ == "__main__":
    run()
