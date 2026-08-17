# Security Policy

No releases — **only `main` is supported**; redeploy from it.

## Reporting

**No public issue/PR/discussion** — [report privately](https://github.com/xzawed/SCAManager/security/advisories/new).

Include impact, the tested SHA, steps or a PoC. Test only deployments you own; keep no data that isn't yours.

Ack 5 days, verdict 14 days, advisory after fix. No SLA/bounty (single maintainer); nudge the thread after 14 silent days.

## Scope

**In:** webhook-signature bypass/replay; auth bypass (REST, internal-cron, CLI hook, Telegram callback); cross-tenant reads; stored-credential recovery; merge below the score gate or on a stale score; injection/traversal/SSRF/notification-injection via analyzed content; pre-auth DoS.

**Out:** your deploy config; findings presupposing your key, session, or shell; third-party services and the analyzers; scanner output without a PoC. Deliberate, not a bug: unescaped AI summaries in notifications.

## Data egress

- **GitHub API**, **`DATABASE_URL`** — files, diffs, scores, summaries; unavoidable, self-host the DB.
- **Anthropic**/**OpenAI** — diff + commit message; unset `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` (OpenAI off by default).
- **Telegram**, **Discord/Slack/n8n/webhook/SMTP** — score, grade, AI summary; unset `TELEGRAM_BOT_TOKEN`/`SMTP_*`, blank Settings URLs.
- **Railway**/**semgrep.dev** — deploy status; rulesets + anon metrics, **not** source; blank the Railway token, `SEMGREP_SEND_METRICS=off`.
- Other analyzers are local; `golangci-lint`/`clippy` fetch uncached deps.

## Hardening

`SESSION_SECRET` 32+ random bytes · `TOKEN_ENCRYPTION_KEY` + `STRICT_TOKEN_ENCRYPTION=true` · `ENVIRONMENT=production` · HTTPS `APP_BASE_URL` · `GITHUB_WEBHOOK_SECRET` · `TELEGRAM_WEBHOOK_SECRET` · `INTERNAL_CRON_API_KEY` ≠ `API_KEY` · `DB_SSLMODE=require`, DB not public · review thresholds before `auto_merge`. Never `API_AUTH_DISABLED=1` in production (keyless REST then `503`). [env-vars.md](docs/reference/env-vars.md)
