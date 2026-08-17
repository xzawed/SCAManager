<div align="center">

# 🛡️ SCAManager

**Static analysis + Claude AI review on every GitHub push and PR — scored, notified, and gated.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-7028%2B_total_(6857_unit_%2B_171_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI_(120_pass_%2F_1_skip)-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)

[🇰🇷 한국어](README.ko.md)

</div>

---

Self-hosted FastAPI service on Python 3.12. A GitHub webhook fires on `push` and PR `opened` /
`synchronize` / `reopened`; the pipeline scores the change out of 100, records it, gates the PR, and
delivers the result. Only the Anthropic API and the channels you enable receive data
([SECURITY.md](SECURITY.md)).

## How a change flows

```
POST /webhooks/github → run_analysis_pipeline()  src/worker/pipeline.py
  ├─ asyncio.gather ─┬─ 25 static analyzers (pylint · bandit · semgrep · eslint · …)
  │                  └─ Claude review, checklists for 49 languages
  ├─ calculate_score() → score + grade → DB
  ├─ gate (PR events) → approve · request changes · squash merge
  └─ notify → independent channels; one failure blocks no other
```

## Scoring

| Category | Max | Rule |
|---|---|---|
| Code quality | 25 | error −3, warning −1 (cap 25) |
| Security | 20 | HIGH −7, LOW/MEDIUM −2 |
| Commit message · direction · test coverage | 15 · 25 · 15 | Claude 0–20 / 0–20 / 0–10, scaled |

Grades: A(90+) · B(75+) · C(60+) · D(45+) · F below 45. Without `ANTHROPIC_API_KEY` the three AI
rows fall back to 13 / 21 / 10, capping a run at 89 ([`src/constants.py`](src/constants.py)).

## Gate and delivery

Defaults: approve at 75, request changes below 50, squash-merge at 75. `approve_mode=auto` acts on
GitHub; `semi-auto` sends Telegram inline buttons. Borderline merges need a second-model pass and
stay blocked if it cannot run; those held by running CI are queued and retried.

Channels, per repo: Telegram · GitHub PR/commit comment · GitHub issue · Discord · Slack ·
Email · webhook · n8n. UI, notifications, and prompts: English, Korean, Japanese.

## Quick start

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install
make css-build       # Tailwind bundle — gitignored, 404s without it
cp .env.example .env
make run             # uvicorn :8000, migrations run at boot
```

`DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` are required to boot. `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET`, `SESSION_SECRET` (32+ random chars) have placeholder defaults, so the app
boots without them — but OAuth login will not work.

Log in with GitHub, **+ Add Repo**, pick a repository — the webhook is created for you.
Without the server: `python -m src.cli review --base main`.

## Deploy

**Railway** — connect the repo, add the PostgreSQL plugin, set the variables above plus
`ANTHROPIC_API_KEY` and an `https://` `APP_BASE_URL`; without it OAuth redirect and webhook
register as `http://` and fail ([runbook](docs/runbooks/railway.md)).

**On premises** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`;
`DATABASE_URL_FALLBACK` fails over to a secondary database.

## Docs

[Architecture](docs/architecture.md) · [Env vars](docs/reference/env-vars.md) ·
[Runbooks](docs/runbooks/) · [Workflow](docs/workflow/) · [Contributing](CONTRIBUTING.md)

Vulnerabilities: [private advisories](https://github.com/xzawed/SCAManager/security/advisories/new), not a public issue. [MIT License](LICENSE) © xzawed
