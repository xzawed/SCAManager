# Security Policy

🇰🇷 [한국어 문서](SECURITY.ko.md)

SCAManager reads your source code, holds a GitHub OAuth token for every connected repository, and can
approve and merge pull requests on your behalf. A vulnerability here is a supply-chain problem for
whoever runs it, so please report responsibly.

---

## Reporting a vulnerability

**Do not open a public issue, pull request, or discussion for a security vulnerability.**

Report it privately through GitHub:

👉 **[Report a vulnerability](https://github.com/xzawed/SCAManager/security/advisories/new)**
(Repository → *Security* tab → *Report a vulnerability*)

This opens a private advisory visible only to you and the maintainer. It keeps the disclosure history
attached to the repository and lets us issue a fix and a public advisory together.

**Please include:**

- What the vulnerability is, and the impact you believe it has
- The commit SHA you tested against (there are no tagged releases — see below)
- Reproduction steps, ideally a minimal proof of concept
- Your deployment shape if it matters (Railway / on-premises, PostgreSQL version, reverse proxy)

**Please do not:**

- Test against a deployment you do not own
- Run automated scanners against someone else's hosted instance
- Exfiltrate, modify, or retain data that is not yours

### What to expect

This is a single-maintainer project, not a vendor with an on-call rotation. These are honest targets,
not a contractual SLA:

| Stage | Target |
|-------|--------|
| Acknowledgement | Within 5 days |
| Initial assessment (valid / not valid, rough severity) | Within 14 days |
| Fix or documented mitigation for a confirmed high-impact issue | Best effort, prioritized above feature work |
| Public advisory | After a fix lands, credited to you unless you prefer otherwise |

If you do not hear back within 14 days, please ping the advisory thread — it means the notification was
missed, not that the report was ignored.

---

## Supported versions

There are no tagged releases. **`main` is the only supported version.** Fixes land on `main`; if you run
SCAManager, redeploy from `main` to pick them up. Reports against older commits are welcome, but the fix
will be made against current `main`.

---

## Scope

**In scope** — anything in this repository that lets an attacker:

- Bypass GitHub webhook signature verification, or replay a webhook
- Bypass REST API, internal-cron, CLI-hook, or Telegram callback authentication
- Read or act on another tenant's repositories, analyses, or settings (cross-tenant access)
- Recover a stored GitHub OAuth token, API key, or webhook secret
- Cause a pull request to be approved or merged without meeting the configured score gate,
  or get an unanalyzed commit merged under a different commit's score
- Achieve command injection, path traversal, or SSRF via analyzed content, webhook payloads,
  commit messages, or repository names
- Inject content into an outbound notification that acts as a command or a credential-harvesting link
- Deny service pre-authentication (for example, unbounded memory growth from forged input)

**Out of scope:**

- Vulnerabilities in your own deployment configuration — an exposed `.env`, a database reachable from
  the internet, a missing reverse proxy, a `SESSION_SECRET` left at its placeholder value.
  See [Hardening a deployment](#hardening-a-deployment).
- Findings that require an attacker to already hold your admin API key, a valid OAuth session, or
  filesystem access to the host
- Vulnerabilities in third-party services SCAManager talks to (GitHub, Anthropic, Telegram, Discord,
  Slack, Railway) — report those to the service
- Vulnerabilities in the static analyzers themselves (pylint, semgrep, eslint, …) — report upstream
- Missing security headers or best-practice deviations with no demonstrated impact
- Automated scanner output submitted without a working proof of concept
- The known trade-offs documented in [Known trade-offs](#known-trade-offs) below

---

## Where your code goes

SCAManager is self-hosted, which means the **control plane** — the pipeline, the database, the web
dashboard, the static analyzers — runs entirely on your infrastructure. It does not mean your code
stays there. Analysis inherently sends content outward, to services *you* configure.

Here is the complete list.

### Always active

| Destination | What is sent | Why |
|-------------|--------------|-----|
| **GitHub API** (`api.github.com`, plus `github.com/login/oauth/*` for sign-in) | Requests for changed files and diffs; outbound PR reviews, PR comments, commit comments, issues, and merges | This is where the code already lives — it is the event source and the action target |
| **Your `DATABASE_URL`** | Scores, AI review summaries, and analyzer issue messages — all derived from your source — are persisted here | Required for the service to function. Note this is only "self-hosted" if the database is: pointing `DATABASE_URL` at Supabase or another managed provider sends this content there. |

### Active when configured

| Destination | What is sent | How to disable |
|-------------|--------------|----------------|
| **Anthropic API** (`api.anthropic.com`) | The **diff of changed files** plus the commit message, for AI review | Leave `ANTHROPIC_API_KEY` unset — AI items fall back to neutral defaults and the score ceiling drops to 89 (grade B). Per-repository: turn off `ai_review_enabled` in Settings. |
| **Telegram Bot API** (`api.telegram.org`) | Score, grade, AI summary, suggestions, and static-analysis issue messages | Unset `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` |
| **Discord / Slack / generic webhook / n8n** | Score, grade, AI summary, and issue messages | Per-repository opt-in; blank the URL in Settings |
| **Your SMTP server** | The same content as an HTML email | Unset `SMTP_*` |
| **OpenAI or an OpenAI-compatible endpoint** | Diff and AI review summary, for the optional second-LLM merge verifier | Leave `OPENAI_API_KEY` unset — the verifier is off by default. `VERIFIER_BASE_URL` redirects it to another provider. |
| **Railway API** | Deployment status queries only — no source code | Leave the per-repository Railway API token blank |
| **semgrep.dev** | Semgrep fetches its `p/default` ruleset from the registry, and with a registry ruleset its CLI also reports anonymous usage metrics (rule IDs and finding counts — **not** your source). Your code is scanned locally. | Uninstall the `semgrep` binary — the analyzer skips itself when it is not on `PATH`. Or set `SEMGREP_SEND_METRICS=off` in the service environment to suppress the metrics leg. |

### Analyzers that stay on the host

The other 24 registered analyzers — pylint, flake8, bandit, ESLint, ShellCheck, cppcheck, slither,
RuboCop, golangci-lint and the rest — run as local subprocesses against a temporary file. **Semgrep is
the one exception** and is listed in the table above.

We invoke none of the 24 with a network flag. Two of them build a throwaway project around the file
under analysis (`golangci-lint` writes a minimal `go.mod`, `clippy` scaffolds a temporary Cargo
project), so if the analyzed code imports a package that is not already in the local module or crate
cache, the underlying toolchain may reach its package registry. No source code is sent — only the
ordinary dependency resolution any Go or Rust build would perform.

### Reducing third-party egress

Leave `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, and all channel URLs unset, and do not
install `semgrep`. That removes every AI vendor, every notification vendor, and the semgrep registry.
You keep static analysis, scoring, and the dashboard.

Two things remain, and calling this configuration "zero egress" would be wrong:

- **GitHub**, which is unavoidable — it is both the event source and the action target.
- **Your database**, if `DATABASE_URL` points somewhere off-host (Supabase, a managed PostgreSQL). It
  persists scores, AI summaries, and analyzer issue messages, and those messages are derived from your
  source. Point it at a database you control to close this.
- Plus the Go and Rust registry case described just above, if you analyze those languages.

The score ceiling in this configuration is 89 (grade B). The three AI-scored categories are worth 55
points combined; without an API key they are awarded a neutral default of 44, so 11 points are
unreachable. The remaining 45 points come from static analysis and are unaffected.

---

## What SCAManager does to protect you

Stated plainly so you can check the claims against the code rather than trusting the list.

| Area | Control |
|------|---------|
| Webhook authenticity | GitHub webhooks require a valid `X-Hub-Signature-256`; a missing, malformed, or mismatched signature returns `401`, including when the configured secret is empty. Telegram gate callbacks are HMAC-authenticated per event. |
| REST API | **Fail-closed.** With `API_KEY` unset every request returns `503` rather than allowing anonymous access; bypassing that requires the explicit `API_AUTH_DISABLED=1` opt-out, intended for local development only. Key comparison is timing-safe. |
| Internal cron endpoints | A separate `INTERNAL_CRON_API_KEY`, not the admin key. Unset means `503`. |
| Token storage | GitHub OAuth tokens are encrypted at rest with Fernet when `TOKEN_ENCRYPTION_KEY` is set. `STRICT_TOKEN_ENCRYPTION=1` refuses to start in production without it. |
| Merge safety | Auto-merge is bound to the exact commit that was scored. A merge sends that SHA to GitHub, which rejects the merge if the branch head moved. If the head has already drifted when the merge is attempted, the attempt is dropped without merging *or* queuing a retry; a retry already in the queue is abandoned when it detects the drift. Either way the new commit is never merged under the old commit's score — it gets re-gated by its own `synchronize` webhook. |
| Injection into analyzed content | The pre-push hook passes commit messages and diffs through environment variables and argv rather than interpolating them into shell or heredoc text — an earlier version was vulnerable to shell metacharacters in a commit message. |
| Outbound notification injection | Untrusted analyzer messages are escaped per channel before being placed into Markdown or Slack mrkdwn, so a crafted filename or finding cannot inject links or `@channel` mentions. |
| SSRF | Outbound requests to user-supplied webhook URLs go through a validating client that resolves and checks the destination. Trusted APIs use a separate pooled client. |
| Rate limiting | The repository, stats, report, issue-registration, and CLI-hook routes carry per-route limits. Not every HTTP route does — the admin, user, and internal-cron routes rely on their authentication instead, and webhook receivers are deliberately unlimited because they arrive from a small set of provider IPs. |
| Pre-auth resource growth | The per-repository webhook secret cache is bounded, because it is keyed by an attacker-controllable repository name and is consulted before signature verification. |
| Production hardening | HSTS, `Secure` cookies, and a hidden `/docs` are forced by `ENVIRONMENT=production`, independent of whether `APP_BASE_URL` is correct. |
| Health endpoint | `GET /health` returns `{"status":"ok"}` and nothing else — no version, dependency, or database detail. |
| Supply chain | CodeQL, TruffleHog, and `bandit -r src/` run in CI; Dependabot tracks dependencies. Semgrep is **not** a CI job here — it is a runtime analyzer applied to the repositories SCAManager reviews. |

---

## Known trade-offs

Reporting these is not necessary — they are deliberate, documented decisions. Reporting a way to
*escalate* one of them beyond what is described here very much is.

- **AI summaries are not Markdown-escaped** on the GitHub, Discord, and Slack channels. The AI summary
  is written by Claude from your diff, and escaping it would mangle the intentional formatting that
  makes reviews readable. This leaves a second-order path — a prompt injection in a diff could persuade
  the model to emit Markdown that renders as a link. Telegram and email escape everything, so the
  channels are asymmetric here.
- **`flake8` is not part of the merge gate.** pylint and bandit are. The subset of flake8 that catches
  real defects runs in a separate CI job.
- **E2E tests are not wired into CI.** They run locally only.
- **The approve action cannot be made atomic.** GitHub's review API has no equivalent of the merge
  API's `sha` parameter, so a review can in principle be recorded against a head that moved a moment
  earlier. SCAManager checks the head immediately before posting and skips the review on a mismatch;
  a residual race remains, and the next `synchronize` webhook re-gates the new head.

---

## Hardening a deployment

If you run SCAManager, these are on you rather than on the code:

- Set `SESSION_SECRET` to 32+ random bytes (`openssl rand -hex 32`). The built-in default is a
  placeholder and must never reach production.
- Set `TOKEN_ENCRYPTION_KEY`, and consider `STRICT_TOKEN_ENCRYPTION=1` so the app refuses to start
  without it rather than silently storing OAuth tokens in plaintext.
- Set `APP_BASE_URL` to your HTTPS URL and `ENVIRONMENT=production`. Without them the OAuth redirect
  and webhook URLs fall back to `http://`.
- Set `API_KEY` if you use the REST API, and **never** set `API_AUTH_DISABLED=1` outside local development.
- Set `GITHUB_WEBHOOK_SECRET` and `TELEGRAM_WEBHOOK_SECRET`.
- Keep the database off the public internet, and use `DB_SSLMODE=require` for managed PostgreSQL.
- Terminate TLS at a reverse proxy and run uvicorn with `--proxy-headers`.
- Review the auto-merge thresholds before enabling `auto_merge`. Auto-merge means a numeric score is
  authorized to put code on your default branch.

Full variable reference: [`docs/reference/env-vars.md`](docs/reference/env-vars.md).

---

## Credit

Reporters are credited in the published advisory unless they ask not to be. There is no bug bounty —
this is an unfunded personal project, and I would rather be honest about that up front than imply a
reward that does not exist.
