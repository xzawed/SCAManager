# Contributing to SCAManager

Issues and PRs welcome. Security vulnerabilities → [SECURITY.md](SECURITY.md).

## Setup

Python 3.12, Node.js. PostgreSQL only to run the app; tests use in-memory SQLite.

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
cp .env.example .env
pip install -r requirements-dev.txt && npm install
npm run build        # Tailwind; fails quietly, css is gitignored
pre-commit install   # never pass --hook-type; it drops a stage
```

`uvicorn src.main:app --reload` needs `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID` ([env-vars.md](docs/reference/env-vars.md)).

## Branch and test

Every change, docs included, branches off updated `main` and lands via PR. New behaviour
arrives with a failing test.

```bash
git checkout -b fix/telegram-otp-expiry   # feat/ fix/ chore/ docs/
python -m pytest tests/unit           # while iterating
python -m pytest tests/integration    # real linters; pipeline/analyzer changes
python -m pytest e2e/ -p no:asyncio   # Playwright; local only, not in CI
```

## Before pushing

```bash
py -3 scripts/pre_push_gate.py --full
```

Runs the CI-enforced guards (`_INTEGRITY`, `_INTEGRITY_WITH_ARGS`, `_DIFF_SCOPED` in that file)
plus pylint, bandit, `pytest tests/unit`; without `--full`, guards only. It prints what it
cannot see (CodeQL, Codecov, TruffleHog, pip-audit, integration tests): green here is not green
CI.

Conventional Commits: `type(scope): summary`, imperative, ~72 chars, Korean fine. Never commit a
real token, key or chat ID — use `<REDACTED>`.

Comments are bilingual: Korean first, English next line (`# TODO`/`# type: ignore` excepted);
`scripts/check_bilingual_comments.py` reports.

## Open the PR

`gh pr create` fills [the template](.github/PULL_REQUEST_TEMPLATE.md). The body states **what a
reviewer verifies by hand**: visual and deploy-dependent behaviour is outside the suite. UI
changes list 4 themes (dark/light/pastel/catppuccin) × desktop/mobile.

Pre-commit enforces syncs: new `src/` file → [architecture.md](docs/architecture.md), new env
var → [env-vars.md](docs/reference/env-vars.md), changed test or lint numbers →
[STATE.md](docs/STATE.md) + README badges.
