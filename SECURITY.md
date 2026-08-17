# Security Policy

No tagged releases: **`main` is the only supported version**; redeploy from `main`.

## Reporting

**Do not open a public issue, PR, or discussion.**
👉 **[Report a vulnerability](https://github.com/xzawed/SCAManager/security/advisories/new)**

Include impact, the commit SHA tested, and steps or a PoC. Test only deployments you own and keep no data that is not yours.

Targets: ack 5 days, verdict 14 days, high-impact fix before features, advisory after the fix crediting you. Single maintainer, no SLA, no bounty; ping the thread if silent past 14 days.

## Scope

**In scope:** webhook-signature bypass or replay; auth bypass on the REST API, internal-cron, CLI hook, or Telegram callbacks; cross-tenant data access; recovery of a stored OAuth token, API key, or webhook secret; merging a PR below its score gate or under a stale score; command injection, path traversal, or SSRF via analyzed content; notification injection; pre-auth DoS.

**Out of scope:** your deployment config; findings presupposing your API key, session, or filesystem access; third-party services and the analyzers; scanner output without a PoC. Deliberate: unescaped AI summaries in notifications; `flake8` outside the merge gate; non-atomic approval.

## Where your code goes

| Destination | Sent | Off |
|---|---|---|
| **GitHub API**, **`DATABASE_URL`** | files, diffs, scores, summaries, analyzer messages | unavoidable; self-host the DB |
| **Anthropic**, **OpenAI** | diff + commit message | unset `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (OpenAI off by default) |
| **Telegram**, **Discord / Slack / n8n / webhook / SMTP** | score, grade, AI summary | unset `TELEGRAM_BOT_TOKEN`; blank URLs in Settings; unset `SMTP_*` |
| **Railway**, **semgrep.dev** | deploy status; rulesets + anonymous metrics, **not** source | blank the Railway token; `SEMGREP_SEND_METRICS=off` |

Other analyzers run locally; `golangci-lint` and `clippy` may fetch uncached Go/Rust dependencies. Unset AI and notification credentials and only GitHub and the database remain.

## Hardening

`SESSION_SECRET` 32+ random bytes, `TOKEN_ENCRYPTION_KEY` with `STRICT_TOKEN_ENCRYPTION=true`, `ENVIRONMENT=production`, HTTPS `APP_BASE_URL`, `GITHUB_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `INTERNAL_CRON_API_KEY` distinct from `API_KEY`. Never set `API_AUTH_DISABLED=1` in production (keyless REST otherwise gets `503`). Keep the database off the public internet (`DB_SSLMODE=require`), terminate TLS at a proxy, review thresholds before `auto_merge`. See [`docs/reference/env-vars.md`](docs/reference/env-vars.md).
