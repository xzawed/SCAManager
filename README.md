<div align="center">

# 🛡️ SCAManager

**Static analysis + Claude AI review on every GitHub push and PR — scored, notified, gated.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-7028%2B_total_(6857_unit_%2B_171_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI_(120_pass_%2F_1_skip)-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)

[🇰🇷 한국어](README.ko.md)

</div>

Self-hosted FastAPI service, Python 3.12. A webhook on `push` and PR `opened`/`synchronize`/`reopened` runs
`src/worker/pipeline.py`: 25 static analyzers plus a Claude review, 49 languages → score → gate → notify.
Only the Anthropic API and the channels you enable receive data ([SECURITY.md](SECURITY.md)).

## Scoring

Out of 100: code quality 25 (error −3, warning −1) · security 20 (HIGH −7, LOW/MEDIUM −2) ·
commit message 15 · direction 25 · tests 15 (Claude 0–20 / 0–20 / 0–10, scaled).
Grades: A(90+) · B(75+) · C(60+) · D(45+) · F below 45. Without `ANTHROPIC_API_KEY` those three AI
rows fall back to 13 / 21 / 10, capping a run at 89 ([`src/constants.py`](src/constants.py)).

## Gate

Approve ≥75, request changes <50, squash-merge ≥75. `approve_mode=auto` acts on GitHub, `semi-auto`
asks via Telegram. Borderline merges need a second-model pass and stay blocked if it cannot run;
those held by CI are queued and retried.

Channels per repo, independent: Telegram · GitHub · Discord · Slack · Email · webhook · n8n.
UI and prompts: en · ko · ja.

## Quick start

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install
make css-build       # Tailwind bundle — gitignored, 404s without it
cp .env.example .env
make run             # uvicorn :8000, migrations at boot
```

Boot requires `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET`, `SESSION_SECRET` (32+ chars) have placeholder defaults — the app boots,
OAuth login does not. Log in, **+ Add Repo**, pick a repo — the webhook is created.
No server: `python -m src.cli review --base main`.

## Deploy

**Railway** — connect the repo, add the PostgreSQL plugin, set the above plus `ANTHROPIC_API_KEY`
and an `https://` `APP_BASE_URL`; on `http://` OAuth redirect and webhook registration fail
([runbook](docs/runbooks/railway.md)). **On premises** —
`uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`; `DATABASE_URL_FALLBACK` =
secondary database.

[Architecture](docs/architecture.md) · [Env vars](docs/reference/env-vars.md) ·
[Contributing](CONTRIBUTING.md). Vulnerabilities →
[private advisory](https://github.com/xzawed/SCAManager/security/advisories/new), never public.
[MIT](LICENSE) © xzawed
