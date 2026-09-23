# Full Rosters: Meta ads tooling

This repo holds `meta-ads`, a CLI that manages the Meta (Facebook/Instagram)
ad account through the Marketing API. Claude Code operates it on the owner's
behalf. Read `.claude/skills/meta-ads/SKILL.md` for the command reference.

## Setup in a session

```
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
meta-ads whoami
```

Token and ids come from the cloud environment (see `.env.example`). The
preferred setup stores the token as an API credential on the environment
with `META_TOKEN_VIA_PROXY=1`, so the token never appears in the session at
all. If `whoami` fails, point the owner at `docs/RUNBOOK_META_SETUP.md`
instead of guessing.

## Operating rules (non-negotiable)

1. **Approval gate.** Some commands stop with `APPROVAL REQUIRED [id]` and
   exit code 3: activating anything, budget changes over 10% in either
   direction, setting a budget where none existed, and deletes. When that
   happens: show the owner the printed summary verbatim, ask "approve?", and
   only after they say yes re-run the same command with `--approve <id>`.
   Never pass `--approve` on your own initiative, never reuse an id, never
   paraphrase the summary.
2. **Paused by default.** Everything you create is PAUSED. Activation is a
   separate, gated step.
3. **Pausing is always allowed** without asking. If something looks wrong
   (runaway spend, broken link), pause first, then report.
4. **Dry-run before a build.** For `meta-ads build`, run `--dry-run` first
   and summarise what will be created before running it for real.
5. **Never print the token.** Do not echo `META_ACCESS_TOKEN`, do not write
   it into files, logs, commits or chat.
6. **Report in the owner's terms.** Budgets in dollars, not cents. Names
   before ids. Short tables.
7. **Do not widen the allowlist.** `META_AD_ACCOUNT_ID` is set by the owner.

## Tests

```
python -m pytest -q
```

All API calls in tests are mocked with `respx`; nothing touches Meta.
