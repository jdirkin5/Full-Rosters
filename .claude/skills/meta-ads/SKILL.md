---
name: meta-ads
description: Manage the Meta (Facebook/Instagram) ad account with the meta-ads CLI. Use for any request about campaigns, ad sets, ads, budgets, audiences, creatives or ad performance.
---

# meta-ads command reference

Activate the venv first: `. .venv/bin/activate` (create it with
`python3 -m venv .venv && pip install -e ".[dev]"` if missing).
Every command accepts `--json` for raw output and `--help` for flags.
Money flags are whole currency units (`--daily 25` = $25.00).

## Verify
- `meta-ads whoami` — token identity, scopes, visible ad accounts and pages.

## Read
- `meta-ads campaigns list [--status ACTIVE,PAUSED] [--limit N]`
- `meta-ads adsets list --in <campaign_id>` / `meta-ads ads list --in <adset_id>`
- `meta-ads campaigns get <id>` (same for `adsets`, `ads`)
- `meta-ads insights [<id>] --level campaign|adset|ad --preset last_7d [--by-day]`
- `meta-ads insights --since 2026-09-01 --until 2026-09-21 --level adset`
- `meta-ads creatives list`, `meta-ads audiences list [--saved]`, `meta-ads accounts pixels`
- `meta-ads targeting interests "youth basketball"`, `meta-ads targeting locations "Chicago" --types city`
- `meta-ads audit-log --last 20`, `meta-ads pending list`

## Write (always PAUSED on create, allowlisted accounts only, `--dry-run` available)
- `meta-ads build spec.yaml [--dry-run]` — whole campaign from YAML (see `examples/campaign.yaml`)
- `meta-ads campaigns create --name "..." --objective OUTCOME_LEADS [--daily 25]`
- `meta-ads adsets create --name "..." --campaign <id> --daily 25 --countries US --age-min 25 --interests <id,id>`
- `meta-ads creatives upload-image --path file.jpg` (prints image hash)
- `meta-ads creatives create --link URL --primary-text "..." --headline "..." --image-hash <hash> --cta SIGN_UP`
- `meta-ads ads create --name "..." --adset <id> --creative <id>`
- `meta-ads campaigns update <id> --name "..."` (also `--set field=value` for other non-budget fields)
- `meta-ads audiences create --name "..."`, `meta-ads audiences add-users <id> --csv list.csv --schema EMAIL,PHONE`
- `meta-ads audiences lookalike --name "..." --source <audience_id> --country US --ratio 0.01`

## Gated (stop with `APPROVAL REQUIRED [id]`, exit 3; re-run with `--approve <id>` after the owner says yes)
- `meta-ads campaigns activate <id>` (same for `adsets`, `ads`) — always gated
- `meta-ads adsets budget <id> --daily 40` — gated when the change is over 10% or there was no budget
- `meta-ads campaigns delete <id>` — always gated
- `meta-ads campaigns pause <id>` — never gated

## Approval flow, exactly
1. Run the command. It prints a one-line summary and an id, and exits 3.
2. Show the owner that summary word for word and ask for approval.
3. Owner says yes -> re-run the identical command with `--approve <id>`.
4. Owner says no or changes the ask -> run the new command; a new id is issued.
Ids are a hash of the exact change and expire after 24h.

## Exit codes
0 ok · 1 API or other error (message includes Meta's code and fbtrace_id) · 2 refused by a safety rule · 3 approval required

## Reading Meta errors
- code 190: token invalid -> owner redoes the runbook Part D.
- code 100 / 200 / 10: permission or asset assignment -> runbook Part C.
- code 17 / 32 / 613 / 80004: rate limit, the client already retried; wait a minute.
- "Invalid parameter" on create: read `error_user_msg` in the output; it names the field.
