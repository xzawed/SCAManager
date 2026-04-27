<div align="center">

# 🛡️ SCAManager

**Automated Code Quality Analysis · AI Review · PR Gate Service for GitHub**

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-SQLAlchemy_2-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Claude AI](https://img.shields.io/badge/Claude_AI-Sonnet_4.6_(default)-CC6600?style=flat-square&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/xzawed/SCAManager/branch/main/graph/badge.svg)](https://codecov.io/gh/xzawed/SCAManager)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=xzawed_SCAManager&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=xzawed_SCAManager)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=xzawed_SCAManager&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=xzawed_SCAManager)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=xzawed_SCAManager&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=xzawed_SCAManager)

[![Tests](https://img.shields.io/badge/Tests-1732_passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-53_passing-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-10.00%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![bandit](https://img.shields.io/badge/bandit-HIGH_0-brightgreen?style=flat-square&logo=security&logoColor=white)](src/)
[![Coverage](https://img.shields.io/badge/Coverage-95%25-brightgreen?style=flat-square&logo=codecov&logoColor=white)](tests/)

[🇰🇷 한국어](README.ko.md)

</div>

---

## 📖 Overview

**SCAManager** automatically manages code quality for your GitHub repositories.

On every Push or PR event, it runs **static analysis** (pylint · flake8 · bandit · Semgrep · ESLint · ShellCheck · cppcheck · slither · rubocop · golangci-lint) and **Claude AI review** in parallel, producing a score out of 100 and a grade from A to F.

Results are delivered instantly via **Telegram · GitHub · Discord · Slack · Email · n8n**, and PRs can be automatically approved, rejected, or squash-merged based on the score.

For teams that push directly to `main`, it also supports **automatic commit comments** and **GitHub Issue creation** on low-scoring commits.

---

## 🎯 Why SCAManager?

Most code review tools make you choose between static analysis precision and AI understanding. SCAManager runs both in parallel and combines the results into a single score — then acts on it automatically.

**What makes it different:**

- **Self-hosted** — runs entirely on your own infrastructure; no vendor lock-in, no data leaves your environment
- **Static + AI in one pipeline** — 10 linters/analyzers run alongside Claude AI review; results feed into a single score
- **Score-based PR Gate** — automatically approve, reject, or request human decision via Telegram based on numeric thresholds
- **Approve from phone** — Telegram inline buttons let you review and merge PRs from anywhere, no laptop required
- **Push + PR analysis** — not just PRs; bare pushes also trigger analysis, auto-create GitHub Issues, and post commit comments
- **50-language AI review** — language-specific checklists for every supported language, not a generic prompt

**Best for:** Solo developers and small teams who want full control over their code quality pipeline.

---

## ✨ Features

### 🔍 Automated Code Analysis

| Analysis | Tools | Target |
|----------|-------|--------|
| Code Quality | pylint + flake8 + Semgrep + cppcheck + RuboCop + golangci-lint | `.py` + C/C++ (cppcheck) + `.rb` (RuboCop) + `.go` (golangci-lint) + **35+ languages** (Semgrep) |
| Security | bandit + Semgrep + slither + RuboCop Security cops + gosec (via golangci-lint) | `.py` files (tests excluded) + Solidity (slither) + Ruby / Go security rules |
| JS/TS Quality | ESLint (flat config) | `.js` `.mjs` `.ts` `.tsx` |
| Shell Quality | ShellCheck | `.sh` `.bash` and other shell scripts |
| Solidity | slither | `.sol` — reentrancy · tx.origin · weak-prng · Category-aware |
| Ruby | RuboCop | `.rb` — Security cops detected separately |
| Go | golangci-lint | `.go` — meta-linter (gosec / errcheck / staticcheck / unused, auto `go.mod`) |
| AI Review | Claude Sonnet 4.6 | **50 languages** with language-specific checklists |
| Commit Message | Claude AI | Push / PR messages |

- Handles `push` and PR (`opened` / `synchronize` / `reopened`) events automatically
- Static analysis and AI review run in **parallel** via `asyncio.gather()` — minimal latency
- Without `ANTHROPIC_API_KEY`, AI items use neutral defaults — **up to 89 points (grade B) without AI**

---

### 🏆 Scoring System

| Category | Points | Deduction Rule |
|----------|--------|----------------|
| 🧹 Code Quality | 25 | error −3 · warning −1 (CQ_WARNING_CAP = 25 combined cap) |
| 🔒 Security | 20 | HIGH −7 · LOW/MED −2 |
| 📝 Commit Message | 15 | Claude AI (0–20 → scaled to 0–15) |
| 🧠 Implementation Direction | 25 | Claude AI (0–20 → scaled to 0–25) |
| 🧪 Test Coverage | 15 | Claude AI (0–10 → scaled to 0–15; config/doc files exempt) |
| **Total** | **100** | |

**Grade Thresholds**

| Grade | Score | Meaning |
|-------|-------|---------|
| 🥇 A | 90+ | Excellent |
| 🥈 B | 75+ | Good |
| 🥉 C | 60+ | Average |
| ⚠️ D | 45+ | Needs improvement |
| 🚨 F | ≤ 44 | Critical |

---

### 🔔 Notification Channels

| Channel | Content | Configuration |
|---------|---------|---------------|
| 📱 Telegram | Score · AI summary · suggestions · static issues (HTML) | Default |
| 💬 GitHub PR Comment | Category/file feedback + score table | Per-repo |
| 📌 GitHub Commit Comment | AI review posted on push commits | Per-repo |
| 🐛 GitHub Issue | Auto-created on low score or bandit HIGH | Per-repo |
| 🎮 Discord | Embed-formatted notification | Per-repo |
| 💼 Slack | Attachment-formatted notification | Per-repo |
| 📧 Email | SMTP HTML email | Per-repo |
| 🔗 Generic Webhook | Generic JSON POST | Per-repo |
| 🔄 n8n | External workflow trigger (Issue → Claude CLI → auto PR) | Per-repo |

> **n8n Automation**: On Issue creation, n8n + Claude CLI automatically fixes the code and opens a PR. See [docs/integrations/n8n-auto-fix.md](docs/integrations/n8n-auto-fix.md).

All channels run independently via `asyncio.gather(return_exceptions=True)` — one channel failure never affects others.

---

### 📡 Telegram Insights (Phase 10)

Beyond real-time push/PR alerts, SCAManager's Telegram integration provides scheduled reports, trend detection, and interactive bot commands.

#### Weekly Report
Every Monday at 09:00 KST, SCAManager sends a weekly summary to each repo's configured Telegram chat:

```
📊 Weekly Report — owner/myrepo
Period: Apr 21 – Apr 27

Analyses: 12  |  Avg score: 81.4 (B)
High: 94 (A)  |  Low: 62 (C)

Top issues this week:
  · security: 8 occurrences
  · code_quality: 14 occurrences
```

#### Trend Alert
Every day at 12:00 KST, SCAManager checks the 7-day moving average. If it drops **10+ points** below the prior period (minimum 5 analyses required), a trend alert is sent automatically:

```
⚠️ Score trend alert — owner/myrepo
7-day moving avg dropped: 83.2 → 71.5 (−11.7)
Recent low-score analyses may need attention.
```

#### Bot Commands
After linking your Telegram account (see below), send these commands to the bot:

| Command | Description |
|---------|-------------|
| `/stats <repo>` | Weekly avg score, analysis count, top issues for the repo |
| `/settings <repo>` | Current gate mode, thresholds, and notification settings |
| `/connect <OTP>` | Link your Telegram account to your SCAManager profile |

#### Linking Your Telegram Account (`/connect` OTP flow)

1. Go to **Settings → Card ⑤ → Telegram Connection** and click **"🔗 Issue Code"**
2. A 6-digit OTP appears (valid for 5 minutes)
3. Send `/connect 123456` to the SCAManager bot in Telegram
4. The bot replies "✅ Account linked" — bot commands are now available

> Each new OTP immediately invalidates the previous one. The link is per-user, not per-repo.

---

### ⚡ PR Gate Engine

Score-based PR automation.

```
Analysis complete
    ├── [Auto mode]      score ≥ approve_threshold  → GitHub APPROVE
    │                    score < reject_threshold   → GitHub REQUEST_CHANGES
    │
    ├── [Semi-auto mode] Send Telegram inline buttons → manual approve/reject
    │
    └── [Auto Merge]     score ≥ merge_threshold    → squash merge
                         (independent of approve_mode)
```

| Setting | Behavior |
|---------|----------|
| `approve_mode="auto"` | Auto Approve / Request Changes by threshold |
| `approve_mode="semi-auto"` | Manual decision via Telegram buttons |
| `auto_merge=true` | Squash merge when threshold is met |

#### ♻️ CI-aware Auto Merge Retry (Phase 12)

When `auto_merge=true` and the merge fails because CI is still running (`mergeable_state=unstable` or `unknown`), SCAManager queues the PR for retry instead of giving up:

- First queue: Telegram "⏳ merge queued" notification (1×)
- Up to 30 retries over 24 hours via `check_suite.completed` webhook or 5-min cron
- Final result: Telegram success/failure notification (1×)

> **Existing repos** need Webhook re-registration (Settings → Card ⑤ → "Reinstall Webhook") to subscribe to `check_suite` events.

---

### 📊 Observability

Production-grade instrumentation for diagnostics and cost control.

| Layer | Module | What it captures |
|-------|--------|------------------|
| Exception tracking | `src/shared/observability.py` (Sentry) | Unhandled exceptions with PII scrubbing via `before_send` hook. Activated when `SENTRY_DSN` is set. |
| Claude API cost | `src/shared/claude_metrics.py` | Per-call model · input/output tokens · USD cost estimate · latency (structured log). |
| Pipeline timing | `src/shared/stage_metrics.py` | `stage_timer` context manager emits `duration_ms` + `status` per pipeline stage. |
| Auto-merge attempts | `src/shared/merge_metrics.py` + `merge_attempts` table | Every auto-merge attempt (success or failure) is persisted with `failure_reason` normalized tag (`branch_protection_blocked`, `unstable_ci`, `permission_denied`, …) + `score`/`threshold` snapshot. Phase F.1. |

All layers are optional — Sentry is skipped when `SENTRY_DSN` is empty, and the other three emit structured logs unconditionally so any log shipper (Datadog, CloudWatch, Grafana Loki) can parse them.

---

### 🖥️ Web Dashboard

All features accessible via browser after GitHub OAuth login.

- **Add Repository** — Webhook auto-created from a GitHub dropdown
- **Score History Chart** — Chart.js-based visualization
- **Analysis Detail** — AI review · category feedback · static analysis issues
- **Settings Page** — 🚀 One-click presets · 4-card Progressive Disclosure · toggle show/hide
- **Themes** — Dark / Light / Glass — all three fully supported

---

### 💻 CLI Code Review

Run a local code review instantly from the terminal.

```bash
# Compare against the last commit (default)
python -m src.cli review

# Compare against a specific branch
python -m src.cli review --base main

# Analyze staged changes only
python -m src.cli review --staged

# JSON output
python -m src.cli review --json
```

> Requires `ANTHROPIC_API_KEY` · Works in GitHub Actions, Codespaces, and regular terminals

---

### 🪝 CLI Hook (Local pre-push Auto Review)

A Git Hook that runs code review automatically on `git push`.

```bash
# Run once after registering the repo
git pull
bash .scamanager/install-hook.sh

# Every subsequent push triggers auto review
git push origin main
# → AI review printed to terminal
# → Saved to SCAManager dashboard automatically
```

- **No `ANTHROPIC_API_KEY` required** — uses the locally installed Claude Code CLI (`claude -p`)
- Results appear in the terminal and the dashboard simultaneously
- Push is never blocked — always exits with `0`

> **Requirements:** Claude Code CLI (`claude`) installed on Mac / Linux / Windows desktop
> Silently skipped in environments without the CLI (Codespaces · CI · mobile)

---

## 🛠️ Tech Stack

| Category | Technology |
|----------|------------|
| **Language** | Python 3.14 |
| **Web Framework** | FastAPI + Uvicorn |
| **Auth** | GitHub OAuth2 (authlib) + Starlette SessionMiddleware |
| **Database** | PostgreSQL · SQLAlchemy 2 · Alembic · FailoverSessionFactory |
| **AI (Server)** | Anthropic Claude API (claude-sonnet-4-6) |
| **AI (Local Hook)** | Claude Code CLI (`claude -p`) |
| **Static Analysis** | pylint · flake8 · bandit (Python) + Semgrep (22+) + ESLint (JS/TS) + ShellCheck (shell) + cppcheck (C/C++) + slither (Solidity) + RuboCop (Ruby) + golangci-lint (Go) |
| **Testing** | pytest · pytest-asyncio · httpx TestClient |
| **E2E Testing** | Playwright (Chromium) |
| **Web UI** | Jinja2 · Chart.js · CSS Variables (3 themes) |
| **Notifications** | Telegram · GitHub · Discord · Slack · Email · n8n · Webhook |
| **Deployment** | Railway / on-premises (systemd · nginx · Docker Compose) |

---

## 🚀 Getting Started

### 📋 Requirements

- Python **3.14** or later
- PostgreSQL
- GitHub OAuth App (Client ID / Client Secret)
- (Optional) Telegram Bot Token · SMTP server · ANTHROPIC_API_KEY

### ⬇️ Installation

```bash
git clone https://github.com/xzawed31/SCAManager.git
cd SCAManager

# Development environment (includes pytest + playwright)
pip install -r requirements-dev.txt

# Production environment (auto-detected by Railway)
pip install -r requirements.txt
```

### ⚙️ Environment Variables

```bash
cp .env.example .env
```

**Required**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection URL (`postgres://` auto-converted to `postgresql://`) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Default notification Chat ID |
| `GITHUB_CLIENT_ID` | GitHub OAuth App Client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App Client Secret |
| `SESSION_SECRET` | Session cookie signing key (**32+ random characters, required**) |

**Recommended**

| Variable | Description |
|----------|-------------|
| `APP_BASE_URL` | Deployment URL (`https://your-app.railway.app`) — applied to OAuth redirect URI and Webhook URL |
| `ANTHROPIC_API_KEY` | Claude AI review key (neutral defaults applied if omitted) |

**Optional**

| Variable | Description |
|----------|-------------|
| `API_KEY` | REST API auth key (X-API-Key header) |
| `GITHUB_TOKEN` | GitHub API token for legacy repos |
| `GITHUB_WEBHOOK_SECRET` | Webhook secret for legacy repos |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Email notification SMTP settings |
| `DATABASE_URL_FALLBACK` | Secondary DB URL for failover (single-engine mode if unset) |
| `DB_FAILOVER_PROBE_INTERVAL` | Primary DB recovery check interval in seconds (default 30) |
| `DB_SSLMODE` | PostgreSQL SSL mode (`require` / `disable`) |
| `DB_FORCE_IPV4` | Force IPv4 connection (`true` — Railway environments) |

### ▶️ Run

```bash
# Development server (auto-runs DB migration)
uvicorn src.main:app --reload --port 8000

# Or via Make
make run
```

---

## 🧪 Development Commands

```bash
make install            # Install dependencies
make test               # Full test suite (compact output)
make test-v             # Full test suite (verbose output)
make test-cov           # Tests + coverage report
make lint               # pylint + flake8 + bandit
make review             # CLI code review (HEAD~1)
make run                # Development server (port 8000)
make migrate            # Run DB migrations
make revision m="desc"  # Create new migration file
make install-playwright # Install Playwright + Chromium
make test-e2e           # E2E tests (headless)
make test-e2e-headed    # E2E tests (with browser)
```

---

## 🌐 URL Routes

```
/login                              → 🔑 GitHub OAuth login
/repos/add                          → ➕ Add repository
/                                   → 📊 Repository overview dashboard
/repos/{owner/repo}                 → 📈 Score history + analysis log
/repos/{owner/repo}/analyses/{id}   → 🔍 Analysis detail (AI review · feedback)
/repos/{owner/repo}/settings        → ⚙️  Gate · notifications · Hook settings
```

> All UI pages require login — unauthenticated requests redirect to `/login`

---

## 📡 API Endpoints

<details>
<summary>Expand full endpoint list</summary>

**Auth (OAuth)**
```
GET  /login                          Login page
GET  /auth/github                    Start GitHub OAuth
GET  /auth/callback                  GitHub OAuth callback
POST /auth/logout                    Logout
```

**Web Dashboard**
```
GET  /                               Repository list
GET  /repos/add                      Add repository page
GET  /repos/{repo}                   Repo detail (chart + history)
GET  /repos/{repo}/analyses/{id}     Analysis detail
GET  /repos/{repo}/settings          Settings page
POST /repos/add                      Register repo + auto-create Webhook + Hook files
POST /repos/{repo}/settings          Save settings
POST /repos/{repo}/reinstall-hook    Re-commit CLI Hook files
POST /repos/{repo}/reinstall-webhook Re-register Webhook
POST /repos/{repo}/delete            Delete repo (including Webhook + history)
```

**Webhook Receivers**
```
POST /webhooks/github                GitHub Webhook (HMAC-SHA256 verified)
POST /api/webhook/telegram           Telegram Gate callback (HMAC auth)
POST /webhooks/railway/{token}       Railway deploy event (token auth)
```

**REST API** (X-API-Key header required)
```
GET    /api/repos                    Repository list
GET    /api/repos/{repo}/analyses    Analysis history (skip · limit pagination)
PUT    /api/repos/{repo}/config      Update repo settings
DELETE /api/repos/{repo}             Delete repo (API mode — manual Webhook removal)
GET    /api/repos/{repo}/stats       Score statistics · trends
GET    /api/analyses/{id}            Analysis detail
```

**CLI Hook** (hook_token auth)
```
GET  /api/hook/verify                Verify hook registration
POST /api/hook/result                Save code review result
```

**User API** (OAuth session required)
```
POST /api/users/me/telegram-otp      Issue 6-digit OTP for Telegram /connect linking
```

**Internal Cron** (INTERNAL_CRON_API_KEY required)
```
POST /api/internal/cron/weekly       Trigger weekly Telegram summary report
POST /api/internal/cron/trend        Trigger trend alert check (7-day moving avg)
```

**Health Check**
```
GET  /health                         {"status":"ok"}
```

</details>

---

## 🏗️ Architecture

```
GitHub Push/PR
  └─ POST /webhooks/github  (HMAC-SHA256 verified, per-repo secret TTL-cached)
       └─ BackgroundTask: run_analysis_pipeline()
            ├─ Register repo in DB · SHA dedup check (idempotency)
            ├─ get_pr_files / get_push_files
            │
            ├─ asyncio.gather() ── parallel execution
            │    ├─ analyze_file() × N  (pylint · flake8 · bandit · semgrep · eslint · shellcheck · cppcheck · slither · rubocop · golangci-lint)
            │    └─ review_code()       (Claude AI — 50-language checklists, token budget 8000)
            │
            ├─ calculate_score()  →  score · grade
            ├─ Save Analysis to DB
            │
            ├─ run_gate_check()   [PR events only]
            │    ├─ pr_review_comment → GitHub PR comment
            │    ├─ approve_mode=auto → GitHub APPROVE / REQUEST_CHANGES
            │    ├─ approve_mode=semi → Telegram inline keyboard
            │    └─ auto_merge        → squash merge
            │
            └─ asyncio.gather(return_exceptions=True)  ── independent notifications
                 ├─ Telegram
                 ├─ GitHub Commit Comment  [push + commit_comment=on]
                 ├─ GitHub Issue           [score < threshold or bandit HIGH]
                 ├─ Discord
                 ├─ Slack
                 ├─ Generic Webhook
                 ├─ Email
                 └─ n8n
```

---

## ☁️ Deployment

### 🚂 Railway

1. Create a Railway project and connect this repository
2. Add the **PostgreSQL plugin** (`DATABASE_URL` is auto-generated)
3. Set environment variables in the **Variables** tab

```
TELEGRAM_BOT_TOKEN    = <your-token>
TELEGRAM_CHAT_ID      = <your-chat-id>
GITHUB_CLIENT_ID      = <oauth-client-id>
GITHUB_CLIENT_SECRET  = <oauth-client-secret>
SESSION_SECRET        = <random-32-chars>
APP_BASE_URL          = https://your-app.up.railway.app  ← required!
ANTHROPIC_API_KEY     = sk-ant-...                       ← recommended
```

4. Deploy — DB migrations run automatically on app startup (lifespan)

> ⚠️ Without `APP_BASE_URL`, the OAuth redirect URI and Webhook URL default to `http://`, causing auth failures.

### 🖥️ On-Premises

```bash
# Basic start command (--proxy-headers: trust reverse proxy IP)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

**DB Failover** — Set `DATABASE_URL_FALLBACK` to a secondary DB URL for automatic failover on primary failure. The `/health` endpoint returns `{"status": "ok"}` regardless of which DB is active.

See the [on-premises migration guide](docs/guides/onpremise-migration-guide.md) for details.

---

## 🔧 GitHub OAuth App Setup

1. **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
2. Fill in the fields:

| Field | Value |
|-------|-------|
| Application name | SCAManager |
| Homepage URL | `https://your-domain` |
| Authorization callback URL | `https://your-domain/auth/callback` |

3. Set **Client ID** and **Client Secret** as environment variables

> For local development, register `http://localhost:8000/auth/callback` as an additional callback URL or create a separate OAuth App.

---

## ➕ Adding a Repository

1. Log in → dashboard → click **+ Add Repo**
2. Select repository from the GitHub dropdown
3. Click **Create Webhook + Add Repo**
   - GitHub Webhook auto-created (with HMAC secret)
   - `.scamanager/config.json` and `install-hook.sh` auto-committed
4. Analysis starts automatically on next Push or PR ✅

### Webhook URL Change (e.g., after migrating deployment URL)

**Settings → CLI Hook card → 🔗 Re-register Webhook**
The Webhook is recreated based on the current `APP_BASE_URL`.

### Install CLI Hook (local pre-push)

```bash
git pull
bash .scamanager/install-hook.sh
# Auto code review runs on every subsequent git push
```

---

## 💻 GitHub Codespaces

```bash
# Ready immediately after container start (.env not needed — uses SQLite in-memory)
make test    # Full test suite
make lint    # Code quality check
make run     # Dev server (port 8000 auto-forwarded)

# CLI code review (requires ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-... python -m src.cli review
```

> Claude Code CLI is not available in Codespaces, so the **CLI Hook does not work** there.
> Use `python -m src.cli review` instead.

---

## 📄 License

[MIT License](LICENSE) © 2026 xzawed
