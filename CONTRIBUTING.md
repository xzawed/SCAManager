# Contributing

Vulnerabilities → `SECURITY.md`.

## Setup

Python 3.12, Node.js. PostgreSQL only to run the app; tests use in-memory SQLite.

```bash
git clone https://github.com/xzawed/SCAManager.git
cp .env.example .env && pip install -r requirements-dev.txt && npm install
npm run build        # Tailwind; fails quietly, css is gitignored
pre-commit install   # never pass --hook-type; it drops a stage
```

`uvicorn src.main:app --reload` needs `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID` (`docs/reference/env-vars.md`).

## Branch, test, push

Docs included: branch off updated `main` (`feat/ fix/ chore/ docs/`), failing test first, PR.

`python -m pytest tests/unit` is the loop; `tests/integration` = real linters
(pipeline/analyzer); `e2e/ -p no:asyncio` = Playwright — run it in a **separate process** from
`tests/` (different `asyncio_mode`). It also runs in CI as the required check `E2E (Playwright)`.

Pre-push: `py -3 scripts/pre_push_gate.py --full` — guards (`_INTEGRITY*`,
`_DIFF_SCOPED` there); `--full` adds pylint, bandit, `pytest tests/unit`. Prints what it
cannot see (CodeQL, Codecov, TruffleHog, pip-audit, integration tests): green here ≠ green CI.

Commits: `type(scope): summary`, imperative, ~72 chars, Korean fine; no real token/key/chat
ID (`<REDACTED>`). Comments: Korean first, English next line (`# TODO`-style tags excepted);
`scripts/i18n_comments/check_bilingual.py src/ --report` measures the rate.

## PR

`gh pr create` fills `.github/PULL_REQUEST_TEMPLATE.md`. Body: **what a reviewer verifies by
hand** — visual and deploy-dependent behaviour is outside the suite; UI changes list 4 themes
(dark/light/pastel/catppuccin) × desktop/mobile.

Pre-commit enforces: new `src/` file → `docs/architecture.md`, new env var → env-vars.md,
test/lint numbers → `docs/STATE.md` + README badges.
