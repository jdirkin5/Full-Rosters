# Meta Ads Management from Claude Code

Goal: describe a campaign in plain language, have Claude Code assemble it in the
Meta ad account through the Marketing API, and leave everything PAUSED for a
human to review and switch on.

## Architecture

```
You (chat)  ->  Claude Code  ->  meta-ads CLI (this repo)  ->  Meta Marketing API
                                  |
                                  +-- guardrails (paused-only, budget cap, account allowlist)
                                  +-- audit log (every write call, local JSONL)
                                  +-- cached IDs (account, page, pixel, audiences)
```

Layers, all inside `meta_ads/` (Python package):

| Layer | File | Responsibility |
|---|---|---|
| Transport | `client.py` | HTTPS to `graph.facebook.com/<version>`, token auth, pagination, rate-limit backoff, error mapping |
| Resources | `accounts.py`, `campaigns.py`, `adsets.py`, `ads.py`, `creatives.py`, `audiences.py`, `insights.py` | One thin module per Marketing API object, field lists chosen for compact output |
| Spec | `spec.py` | A YAML/JSON campaign spec (objective, audience, budget, creative, dates) validated with pydantic, then built into campaign -> ad set -> creative -> ad |
| Guardrails | `safety.py` | Every create is `status=PAUSED`. Activation is refused. Budgets above a configured cap are refused. Writes only go to allowlisted ad account IDs. `--dry-run` prints the calls without sending. |
| Audit | `audit.py` | Appends every write (endpoint, payload, response id, timestamp) to `.meta-ads/audit.jsonl` |
| CLI | `cli.py` | `meta-ads whoami`, `meta-ads campaigns list`, `meta-ads build spec.yaml`, `meta-ads insights ...` |
| Claude instructions | `CLAUDE.md` + `.claude/skills/meta-ads/SKILL.md` | Tells future sessions which commands exist, so Claude never has to read source to operate the tool |

Why a CLI inside the repo rather than a browser, the official SDK, or an MCP server:

- No browser automation. The API is the supported path and is far more reliable.
- No `facebook-business` SDK. It is large, lags API versions, and its objects
  produce huge outputs. A thin `httpx` client with explicit field lists is
  smaller, testable, and pinned to one API version we control.
- CLI first, MCP later if wanted. A CLI is versioned, testable with mocked
  HTTP, and auditable. Wrapping it as an MCP server is a small follow-up.

## Token use

Two different tokens matter.

### 1. The Meta access token (the key)

- Type: System User token generated in Meta Business Settings. These do not
  expire, so there is no refresh flow to build.
- Scopes: `ads_management`, `ads_read`, `business_management`,
  `pages_show_list`, `pages_read_engagement`, `pages_manage_ads`. Add
  `instagram_basic` if ads run under an Instagram account.
- Asset access: the System User must be assigned the ad account (Manage),
  the Page (Manage), and the Pixel if conversions are tracked. This is the
  step people get stuck on.
- Storage: environment variable `META_ACCESS_TOKEN`. In Claude Code on the
  web, set it as a secret on the environment. Locally, a git-ignored `.env`.
  Never in the repo, never in the audit log, never echoed by the CLI.
- Companion config: `META_AD_ACCOUNT_ID` (`act_...`), `META_PAGE_ID`,
  `META_API_VERSION`, `META_MAX_DAILY_BUDGET_CENTS`.

### 2. Claude's context tokens (cost per session)

- Compact output by default: tables and summaries, never raw JSON dumps.
  `--json` is opt-in.
- Explicit `fields=` on every request and small default page sizes.
- Cached IDs in `.meta-ads/cache.json` so Claude does not re-list accounts,
  pages, pixels, and audiences every session.
- The skill file lists commands and examples, so Claude operates the tool
  without reading its source.

## Safety rules (enforced in code, not by convention)

1. Every campaign, ad set, and ad is created with `status=PAUSED`.
2. The CLI has no command that sets a status to `ACTIVE`.
3. Daily and lifetime budgets above `META_MAX_DAILY_BUDGET_CENTS` are rejected.
4. Writes are only sent to ad account IDs in the allowlist.
5. `--dry-run` is available on every write command.
6. Every write is appended to the audit log.

## Build steps

### Step 0: Meta side (you do this once, roughly 20 minutes)

1. Meta Business Settings -> Users -> System Users -> Add. Role: Admin.
2. Business Settings -> Accounts -> Apps. Create or pick an app and add the
   Marketing API product to it (system user tokens are issued against an app).
3. On the System User -> Assign Assets: the ad account (Manage), the Page
   (Manage), the Pixel (if any).
4. System User -> Generate Token. Pick the app, check the scopes above,
   choose "never expires". Copy the token once.
5. Note the ad account ID (`act_` + number) and the Page ID.
6. Put the token and IDs into the Claude Code environment secrets (web) or
   a local `.env`.
7. Confirm the environment's network policy allows `graph.facebook.com`.

### Step 1: Scaffold (this repo)

Python 3.12, `pyproject.toml`, deps: `httpx`, `pydantic`, `typer`, `pyyaml`,
`python-dotenv`. Dev: `pytest`, `respx` for mocked HTTP. Git-ignore `.env`
and `.meta-ads/`.

### Step 2: Client and read-only commands

`whoami` (verifies the token and prints the scopes and assets it can see),
`accounts list`, `campaigns list`, `adsets list`, `ads list`,
`insights` (spend, impressions, clicks, CPC, results by date range).
This step proves the token is scoped correctly before anything is written.

### Step 3: Write commands with guardrails

`campaign create`, `adset create`, `creative create` (with image upload),
`ad create`. All PAUSED. Budget cap, allowlist, dry-run, and audit log wired in.

### Step 4: Spec-driven build

`meta-ads build campaign.yaml`: one file describing objective, audience
(location, age, interests, or a saved/custom audience), budget, schedule,
creative (image, primary text, headline, CTA, landing URL). The CLI assembles
the whole tree and prints the IDs for review in Ads Manager.

### Step 5: Audiences and reporting

Custom audiences from customer lists (hashed client-side), lookalikes,
saved audiences. Insights reports grouped by campaign, ad set, ad, and day.

### Step 6: Documentation and tests

`CLAUDE.md`, the skill file, `docs/RUNBOOK.md` for the Meta-side setup, and
unit tests for the client, guardrails, and spec builder against mocked HTTP.
