<div align="center">

# 🛡️ SCAManager

**Static analysis + Claude AI review on every GitHub push and PR — scored, notified, and gated.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/Tests-7284%2B_total_(7113_unit_%2B_171_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI_(120_pass_%2F_1_skip)-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)

[🇰🇷 한국어](README.ko.md)

</div>

---

Self-hosted FastAPI service. A GitHub webhook fires on `push` and on PR `opened` / `synchronize` /
`reopened`; the pipeline scores the change out of 100, records it, gates the PR, and delivers the
result. Everything runs on your infrastructure — only the Anthropic API and the channels you turn on
receive data ([SECURITY.md](SECURITY.md)).

## How a change flows

```
POST /webhooks/github          HMAC-SHA256, per-repo secret
  └─ run_analysis_pipeline()   src/worker/pipeline.py
       ├─ asyncio.gather ─┬─ 25 static analyzers (pylint · bandit · semgrep · eslint · tsc ·
       │                  │   shellcheck · cppcheck · slither · rubocop · golangci-lint · …)
       │                  └─ Claude review, per-language checklists for 49 languages
       ├─ calculate_score() → score + grade → DB
       ├─ gate  (PR events)   approve · request changes · Telegram buttons · squash merge
       └─ notify              channels are independent; one failure never blocks another
```

## Scoring

| Category | Max | How it moves |
|---|---|---|
| Code quality | 25 | error −3, warning −1 (warning cap 25) |
| Security | 20 | HIGH −7, LOW/MEDIUM −2 |
| Commit message | 15 | Claude 0–20, scaled |
| Implementation direction | 25 | Claude 0–20, scaled |
| Test coverage | 15 | Claude 0–10, scaled |

Grades: **A** ≥ 90 · **B** ≥ 75 · **C** ≥ 60 · **D** ≥ 45 · **F** below 45. Without
`ANTHROPIC_API_KEY` the three AI rows take neutral defaults (13 / 21 / 10), capping a run at 89.
Source: [`src/constants.py`](src/constants.py).

## Gate and delivery

Defaults: approve at 75, request changes below 50, squash-merge at 75. `approve_mode=auto` acts on
GitHub directly; `semi-auto` sends Telegram inline buttons instead. Scores just above the merge
threshold get a second-model verification pass and stay blocked if it cannot run; merges failing on
still-running CI are queued and retried.

Channels, per repository: Telegram · GitHub PR comment · GitHub commit comment · GitHub issue ·
Discord · Slack · Email · generic webhook · n8n. UI, notifications, and prompts speak English,
Korean, and Japanese.

## Quick start

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install                        # pip + npm
make css-build                      # Tailwind bundle — gitignored, 404s without it
python -m pip install pre-commit && python -m pre_commit install
cp .env.example .env                # then fill it in
make run                            # uvicorn :8000, migrations run at startup
```

`DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` are required to boot. `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET`, `SESSION_SECRET` (32+ random chars) have placeholder defaults, so the
process starts without them but OAuth login will not work.

Log in with GitHub, click **+ Add Repo**, pick the repository — the webhook is created for you and
the next push is analyzed. Reviewing locally, without the server:

```bash
python -m src.cli review --base main    # needs ANTHROPIC_API_KEY
```

## Deploy

**Railway** — connect the repo, add the PostgreSQL plugin, set the variables above plus
`ANTHROPIC_API_KEY` and `APP_BASE_URL`. Point `APP_BASE_URL` at your `https://` URL: without it the
OAuth redirect and webhook register as `http://` and both fail
([`docs/runbooks/railway.md`](docs/runbooks/railway.md)).

**On premises** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`. Set
`DATABASE_URL_FALLBACK` for automatic failover to a secondary database.

## Documentation

[`docs/architecture.md`](docs/architecture.md) module map and data flow ·
[`docs/workflow/`](docs/workflow/) procedures per area ·
[`docs/reference/env-vars.md`](docs/reference/env-vars.md) every variable ·
[`docs/runbooks/`](docs/runbooks/) operations · [`docs/STATE.md`](docs/STATE.md) current numbers ·
[CONTRIBUTING.md](CONTRIBUTING.md)

Report vulnerabilities via [private advisories](https://github.com/xzawed/SCAManager/security/advisories/new), not a public issue. [MIT License](LICENSE) © xzawed
