# Contributing to SCAManager

Issues and pull requests are welcome. **Security vulnerabilities do not go here** — see
[SECURITY.md](SECURITY.md).

## Setup

Python 3.12 and Node.js. PostgreSQL only to run the app; the tests use in-memory SQLite.

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
cp .env.example .env
pip install -r requirements-dev.txt && npm install
npm run build                                    # Tailwind bundle
pre-commit install                               # installs both hook stages
```

Do **not** pass `--hook-type`: `default_install_hook_types` already installs both stages, and
naming one overrides that default so the other is silently dropped. `npm run build` fails quietly —
`src/static/css/dist/tailwind.css` is gitignored yet `base.html` links it unconditionally.

The app needs `DATABASE_URL`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
([env-vars.md](docs/reference/env-vars.md)); then `uvicorn src.main:app --reload`.

## Branch

Every change, docs included, goes through a branch and a PR.

```bash
git checkout main && git pull
git checkout -b fix/telegram-otp-expiry     # feat/ fix/ chore/ docs/
```

## Test

```bash
python -m pytest tests/unit           # while iterating
python -m pytest tests/integration    # real linters; required for pipeline/analyzer changes
python -m pytest e2e/ -p no:asyncio   # Playwright; local only, not in CI
```

New behaviour arrives with a test that fails without it. `testpaths = tests` in `pytest.ini`
keeps a bare `pytest` out of `e2e/`.

## Before pushing

```bash
py -3 scripts/pre_push_gate.py --full
```

It runs the guards CI enforces (`_INTEGRITY`, `_INTEGRITY_WITH_ARGS` and `_DIFF_SCOPED` in that
file are the source of truth) plus pylint, bandit and `pytest tests/unit`; drop `--full` for
guards only. It prints the CI axes it cannot see — CodeQL, Codecov, TruffleHog, pip-audit,
`tests/integration` — so green here is not green CI.

Commits follow Conventional Commits: `type(scope): summary`, imperative, ~72 chars; Korean is
fine. Never put a real token, key or chat ID in one — use `<REDACTED>`.

## Code comments (bilingual)

Korean first, English on the next line:

```python
# 같은 SHA가 이미 분석된 경우 건너뜀
# Skip if the same SHA was already analyzed
```

A convention, not a gate (`python scripts/check_bilingual_comments.py` reports on it). `# TODO`
and `# type: ignore` stay English-only; if you cannot write Korean, write English and say so in
the PR.

## Open the PR

`gh pr create` fills [the template](.github/PULL_REQUEST_TEMPLATE.md); work through it. The body
must say **what a reviewer verifies by hand** — visual, deploy-dependent and third-party
behaviour is outside the suite. UI changes list four themes (dark / light / pastel /
catppuccin) × desktop and mobile.

A pre-commit hook enforces each: a new file under `src/` →
[architecture.md](docs/architecture.md); a new environment variable →
[env-vars.md](docs/reference/env-vars.md); a changed test count, coverage or pylint score →
[STATE.md](docs/STATE.md), then the README badges.

Licensed under the [MIT License](LICENSE).
