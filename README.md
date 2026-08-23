<div align="center">

# 🛡️ SCAManager

**Static analysis + Claude AI review on every GitHub push and PR — scored, notified, gated.**

[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/Tests-7340%2B_total_(7150_unit_%2B_190_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[🇰🇷 한국어](README.ko.md)

</div>

You point it at a GitHub repository. From then on every push and pull request is analyzed, scored
out of 100, and — if you let it — approved, merged, or sent back for changes automatically.
It runs on your own machine or your own Railway project; there is no hosted service.

## What you get

**Analysis** — 25 static analyzers over 27 languages, plus a Claude review that follows a
per-language checklist (49 of them). A contracted analyzer that is missing marks the run
incomplete and blocks auto-merge, rather than scoring high on nothing having run.

<sub>c · clojure · cpp · csharp · css · dart · dockerfile · elixir · go · html · java · javascript ·
kotlin · php · powershell · protobuf · python · ruby · rust · scala · shell · solidity · sql ·
swift · terraform · typescript · yaml</sub>

**A score** — out of 100, with a grade, per commit, stored and trended.

**A web UI** — dashboard, per-repository history, per-analysis detail, and settings, in
**en · ko · ja**, four themes.

**A gate** — approve the PR, request changes, or squash-merge it, by score. Off until you turn
it on per repository.

**Notifications** — Telegram · Discord · Slack · Email · webhook · n8n ·
GitHub commit comment · GitHub issue, configured per repository.


<div align="center">

<!-- 재생성 / regenerate: py -3 scripts/capture_readme_hero.py -->
![SCAManager dashboard](docs/readme/dashboard.png)

<sub>Local instance with a seeded 7-day history — not what first boot looks like.
AI cost reads $0.00 because the seed makes no API calls.</sub>

</div>

## Quick start

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install         # pip install -r requirements-dev.txt + npm install
make css-build       # Tailwind bundle (gitignored — build it once)
cp .env.example .env
make run             # uvicorn on :8000, migrations at boot
```

No `make`? Each target is one or two commands — read them off the [Makefile](Makefile).

`.env.example` ships placeholders for the database and Telegram, but **`SESSION_SECRET` is empty
and an empty one refuses to boot** — generate it with `openssl rand -hex 32`. Add
`ANTHROPIC_API_KEY`, or the AI half of every score falls back to neutral defaults. The GitHub
sign-in below needs `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` from an OAuth app; leave them
empty only if you are staying on the CLI.

Then open <http://localhost:8000>, sign in with GitHub, and choose **+ Add Repository**. That
registers the webhook, and the next push to that repository is analyzed. Which channels fire and
whether the gate acts on its own are per repository — **⚙️ Settings** on the repository page.

**Without a server**, review your working tree before you push:

```bash
python -m src.cli review --base main   # or --staged
python -m src.cli review --json        # --no-ai skips the Claude call
```

## Pipeline

```
POST /webhooks/github — HMAC-SHA256, per-repo secret · push, PR opened/synchronize/reopened
 └─ gather   static analyzers + Claude review
    score    calculate_score() → DB
    gate     PR approve · request changes · Telegram buttons · squash merge
    notify   per-repository channels
```

## Scoring

Out of 100 — code quality 25 (error −3, warning −1) · security 20 (HIGH −7, LOW/MEDIUM −2) ·
commit message 15 · direction 25 · tests 15. The last three come from the AI review.
Grades: **A** 90+ · **B** 75+ · **C** 60+ · **D** 45+ · **F** below 45.

With no usable AI result those three fall back to neutral defaults, so a perfect static run tops
out at 89 — a B. A genuine API or parse error stores no score at all.

## Gate and delivery

Defaults: approve at ≥75, request changes below 50, squash-merge at ≥75 — and both actions ship
off. `approve_mode=auto` acts on GitHub
immediately; `semi-auto` asks first via Telegram buttons. Merges blocked by in-flight CI are
queued and retried.

Notification channels fire independently, so one broken webhook does not silence the rest.

## Deploy

**Railway** — connect the repo, add the PostgreSQL plugin, set the variables above plus
`ANTHROPIC_API_KEY` and an `https://` `APP_BASE_URL`. On `http://` both OAuth redirect and webhook
delivery fail ([runbook](docs/runbooks/railway.md)).

**On premises** — `uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers`.

Self-hosted is not airtight: diffs and scores reach GitHub, your database, Anthropic, and whichever
channels you enable. Full table and how to switch each off:
[SECURITY.md](SECURITY.md#data-egress).

## Docs

[Architecture](docs/architecture.md) · [Environment variables](docs/reference/env-vars.md) ·
[Runbooks](docs/runbooks/) · [Contributing](CONTRIBUTING.md) · [Current numbers](docs/STATE.md)

Vulnerabilities → [private advisory](https://github.com/xzawed/SCAManager/security/advisories/new),
never a public issue. [MIT](LICENSE) © xzawed
