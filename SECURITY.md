# Security Policy


SCAManager reads your source, holds a GitHub OAuth token per repository, and can merge pull requests.

## Reporting

**Do not open a public issue, PR, or discussion.**

👉 **[Report a vulnerability](https://github.com/xzawed/SCAManager/security/advisories/new)** (Security tab → *Report a vulnerability*)

Include the impact, the commit SHA you tested, and reproduction steps or a PoC. Do not test a deployment you do not own, scan someone else's instance, or retain data that is not yours.

| Stage | Target |
|---|---|
| Acknowledgement | 5 days |
| Valid / not valid, rough severity | 14 days |
| Fix or mitigation, high impact | best effort, before features |
| Public advisory | after the fix, crediting you |

Single maintainer, no SLA, no bug bounty. Silence past 14 days means the notification was missed — ping the thread.

## Supported versions

No tagged releases. **`main` is the only supported version** — fixes land there; redeploy from `main`.

## Scope

**In scope** — anything letting an attacker bypass or replay webhook signature verification; bypass REST API, internal-cron, CLI-hook, or Telegram callback auth; reach another tenant's data; recover a stored OAuth token, API key, or webhook secret; merge a PR without meeting its score gate or under another commit's score; achieve command injection, path traversal, or SSRF via analyzed content; inject a link or command into a notification; or deny service pre-authentication.

**Out of scope:** your deployment config (exposed `.env`, reachable database, placeholder `SESSION_SECRET`); findings presupposing your API key, a session, or host filesystem access; third-party services and the analyzers themselves; scanner output without a PoC. Deliberate, not bugs: unescaped AI summaries on GitHub/Discord/Slack; `flake8` outside the merge gate; non-atomic approval (GitHub's review API takes no `sha`).

## Where your code goes

The control plane runs on your infrastructure; analysis still sends content outward.

| Destination | Sent | Turn off |
|---|---|---|
| **GitHub API**, always | changed files and diffs; outbound reviews, comments, issues, merges | unavoidable |
| **`DATABASE_URL`**, always | scores, AI summaries, analyzer messages, all derived from your source | self-hosted only if the database is |
| **Anthropic** `api.anthropic.com` | diff of changed files + commit message | unset `ANTHROPIC_API_KEY`, or `ai_review_enabled` per repo |
| **Telegram** `api.telegram.org` | score, grade, AI summary, issue messages | unset `TELEGRAM_BOT_TOKEN` |
| **Discord / Slack / n8n / webhook / SMTP** | same | blank the URL in Settings; unset `SMTP_*` |
| **OpenAI** `api.openai.com` | diff + AI summary, optional merge verifier | unset `OPENAI_API_KEY` — off by default |
| **Railway** `backboard.railway.app` | deployment status only | blank the repo's Railway token |
| **semgrep.dev** | ruleset fetch and anonymous CLI metrics (rule IDs and counts, **not** source); scans locally | `SEMGREP_SEND_METRICS=off`, or `semgrep` off `PATH` |

Every other analyzer is a local subprocess with no network flag; `golangci-lint` and `clippy` scaffold a throwaway project, so an uncached import may reach the Go or Rust registry.

Unset the AI and notification credentials and only GitHub and your database remain; the score then caps at 89 (grade B) on neutral AI defaults.

## Hardening

`SESSION_SECRET` 32+ random bytes (the default is a placeholder), `TOKEN_ENCRYPTION_KEY` with `STRICT_TOKEN_ENCRYPTION=true`, `ENVIRONMENT=production`, HTTPS `APP_BASE_URL`, `GITHUB_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, and an `INTERNAL_CRON_API_KEY` distinct from `API_KEY`. Keyless REST requests get `503` — never lift that with `API_AUTH_DISABLED=1` in production. Keep the database off the public internet (`DB_SSLMODE=require`), terminate TLS at a proxy, and review thresholds before `auto_merge`.

Full reference: [`docs/reference/env-vars.md`](docs/reference/env-vars.md).
