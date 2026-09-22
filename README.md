# Full Rosters: Meta ads from Claude Code

`meta-ads` is a small Python CLI that manages a Meta (Facebook/Instagram) ad
account through the Marketing API. Claude Code runs it on your behalf; you
approve the big moves.

- Setup and token: `docs/RUNBOOK_META_SETUP.md`
- Design and safety rules: `docs/ARCHITECTURE.md`
- Command reference: `.claude/skills/meta-ads/SKILL.md`
- Example campaign spec: `examples/campaign.yaml`

```
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
meta-ads whoami
python -m pytest -q
```
