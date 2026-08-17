<div align="center">

# 🛡️ SCAManager

**Static analysis + Claude AI review on every GitHub push and PR — scored, notified, gated.**

[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/Tests-7111%2B_total_(6940_unit_%2B_171_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[🇰🇷 한국어](README.ko.md)

</div>

Self-hosted FastAPI service on Python 3.12. Nothing leaves the machine except calls to the
Anthropic API and to the notification channels you switch on ([SECURITY.md](SECURITY.md)).

## Pipeline

```
POST /webhooks/github — HMAC-SHA256, per-repo secret · push, PR opened/synchronize/reopened
 └─ run_analysis_pipeline()  src/worker/pipeline.py
    gather   25 static analyzers (27 languages) + Claude review (49 language checklists)
    score    calculate_score() → DB
    gate     PR approve · request changes · Telegram buttons · squash merge
    notify   channels are independent — one failing does not stop the rest
```

Analyzer binaries that the deployment is contracted to install are treated as a deployment
regression when missing: the run is marked incomplete and auto-merge is blocked, rather than
scoring a clean 100 with nothing having run.

## Scoring

Out of 100 — code quality 25 (error −3, warning −1) · security 20 (HIGH −7, LOW/MEDIUM −2) ·
commit message 15 · direction 25 · tests 15. The last three come from Claude as raw 0–20 / 0–20 /
0–10 and are scaled. Grades: **A** 90+ · **B** 75+ · **C** 60+ · **D** 45+ · **F** below 45.

Without `ANTHROPIC_API_KEY` those three rows fall back to 13 / 21 / 10, which caps a run at 89 —
so a missing key can never look like an A. Source of truth: [`src/constants.py`](src/constants.py).

## Gate and delivery

Approve at ≥75, request changes below 50, squash-merge at ≥75. `approve_mode=auto` acts on GitHub
immediately; `semi-auto` asks first via Telegram buttons. Scores inside the borderline band above
the merge threshold need a second-model pass and stay blocked if it cannot run. Merges held by
in-flight CI are queued and retried.

Channels are configured per repository and fire independently: Telegram · GitHub (review, comment,
issue) · Discord · Slack · Email · webhook · n8n. UI, notifications and prompts: **en · ko · ja**.

## Quick start

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install         # pip + npm
make css-build       # Tailwind bundle — gitignored, pages 404 without it
cp .env.example .env
make run             # uvicorn :8000, migrations at boot
```

No `make` on the machine? The targets are thin wrappers — see [Makefile](Makefile), or run
`py -3 -m pip install -r requirements.txt -r requirements-dev.txt`, `npm ci && npm run build`,
`py -3 -m uvicorn src.main:app --reload`.

Boot requires `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — the only settings with no
default. `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and `SESSION_SECRET` (32+ random chars) ship
with placeholders, so the process starts but OAuth login does not work until you replace them.

Then log in, choose **+ Add Repo**, and the webhook is created for you; the next push is analyzed.
Without a server at all: `python -m src.cli review --base main`.

## Deploy

**Railway** — connect the repo, add the PostgreSQL plugin, set the variables above plus
`ANTHROPIC_API_KEY` and an `https://` `APP_BASE_URL`. On `http://` the value is registered as-is and
both OAuth redirect and webhook delivery fail ([runbook](docs/runbooks/railway.md)).

**On premises** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.
`DATABASE_URL_FALLBACK` enables automatic failover to a secondary database.

## Docs

[Architecture](docs/architecture.md) · [Environment variables](docs/reference/env-vars.md) ·
[Runbooks](docs/runbooks/) · [Contributing](CONTRIBUTING.md) · [Current numbers](docs/STATE.md)

Found a vulnerability? Open a
[private advisory](https://github.com/xzawed/SCAManager/security/advisories/new) — never a public
issue ([SECURITY.md](SECURITY.md)).

[MIT](LICENSE) © xzawed
