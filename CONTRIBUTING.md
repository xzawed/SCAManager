# Contributing to SCAManager

Thanks for taking the time to look at this project. SCAManager is a self-hosted code-quality service —
issues, bug reports, and pull requests are all welcome.

🇰🇷 [한국어 문서](CONTRIBUTING.ko.md)

> **Security vulnerabilities do not belong here.** Do not open a public issue or PR for them —
> see [SECURITY.md](SECURITY.md) for the private reporting process.

---

## Table of contents

- [Ways to contribute](#ways-to-contribute)
- [Local setup](#local-setup)
- [Running tests](#running-tests)
- [Lint and the phase gate](#lint-and-the-phase-gate)
- [Branch naming](#branch-naming)
- [Commit messages](#commit-messages)
- [Code comments (bilingual)](#code-comments-bilingual)
- [Pull request checklist](#pull-request-checklist)
- [Two things that bite everyone](#two-things-that-bite-everyone)
- [Where the docs live](#where-the-docs-live)

---

## Ways to contribute

| Kind | What to do first |
|------|------------------|
| **Bug report** | Open an issue with the reproduction steps, the SCAManager version or commit, and the relevant log lines. Redact tokens. |
| **Feature request** | Open an issue describing the problem before writing code. Large features are easier to land when the shape is agreed up front. |
| **Small fix** (typo, broken link, obviously wrong doc) | Send the PR directly, no issue needed. |
| **New static analyzer / language support** | Open an issue first. Analyzers register through a shared protocol and adding one touches the scoring path. |
| **Translation** | The UI, notifications, and AI review guides support English, Korean, and Japanese. See [`src/i18n/`](src/i18n/). |

---

## Local setup

Requires **Python 3.12+**, **Node.js** (for the Tailwind build), and **PostgreSQL** for anything beyond
the test suite. The test suite itself runs on in-memory SQLite and needs no database.

```bash
git clone https://github.com/xzawed/SCAManager.git
cd SCAManager

cp .env.example .env        # tests do not need real values in here

make install                # pip + npm in one step
make css-build              # REQUIRED — see below
python -m pip install pre-commit
python -m pre_commit install   # REQUIRED — installs both stages (pre-commit + commit-msg)
```

The last two steps are the ones people skip, and both fail quietly:

- **`make css-build`** — the Tailwind bundle at `src/static/css/dist/tailwind.css` is a build artifact and
  is gitignored. `base.html` links it unconditionally, so without this step every page serves a 404 for
  its stylesheet and the app looks unstyled rather than broken.
- **`pre-commit install` with both hook types** — every local guard in
  [`.pre-commit-config.yaml`](.pre-commit-config.yaml) (secret scanning, docs-number parity,
  architecture-tree sync, config-layer sync) runs *only* through pre-commit. `commit-msg` is a
  separate stage from `pre-commit`, so installing one does not install the other. Skip this and your
  commits still succeed — silently unguarded.

To run the app itself you need a `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`; everything
else has a default. See the *Environment Variables* section of [README.md](README.md) and
[`docs/reference/env-vars.md`](docs/reference/env-vars.md).

---

## Running tests

```bash
make test-fast    # unit tests, excludes the slow subprocess suite — what you want while iterating
make test         # everything
make test-slow    # the `slow` marker only — spawns real pylint/flake8/bandit/semgrep processes.
                  # tests/integration/ gets that marker automatically via its conftest.
make test-file f=tests/unit/scorer/test_calculator.py
make test-cov     # with coverage
```

Two conventions worth knowing:

- **Prefer a `make` target or an explicit path.** A bare `python -m pytest` used to collect the
  Playwright E2E suite and report hundreds of meaningless failures; `testpaths = tests` in
  [`pytest.ini`](pytest.ini) now prevents that, since `e2e/` sits outside `tests/`. Do not remove that
  setting.
- **Tests come first.** New behavior should arrive with the test that describes it. The suite is large
  (current counts live in [`docs/STATE.md`](docs/STATE.md)) precisely because regressions here are
  expensive to find in production.

E2E tests are Playwright-based and **local only** — they are not part of CI:

```bash
make install-playwright
make test-e2e            # headless
make test-e2e-headed     # with a visible browser
```

---

## Lint and the phase gate

```bash
py -3 scripts/pre_push_gate.py --full    # ← run this before pushing (guards + pylint + bandit + unit tests)
py -3 scripts/pre_push_gate.py           # ← guards only, when you just need the fast pass
```

`pre_push_gate.py` runs the guards CI actually enforces — the lists in that file
(`_INTEGRITY`, `_INTEGRITY_WITH_ARGS`, `_DIFF_SCOPED`) are the source of truth —
without depending on `make`. It prints, on every run, the axes it *cannot* see (CodeQL,
SonarCloud, Codecov, TruffleHog, pip-audit, lint-js, the Postgres job, integration tests), so a green
run is never mistaken for a green CI.

`--full` additionally runs pylint, `bandit -r src/` and `pytest tests/unit`. 🔴 The pylint floor is
**derived from the README badge**, exactly as CI does it (`pylint_floor()` in that file ↔
`ci.yml`) — do not write the number here; a literal drifts the moment the badge moves.
🔴 Note what neither form covers: **`tests/integration`**. If your change touches the pipeline,
the analyzers, or anything that shells out, run `make test-slow` (or `py -3 -m pytest tests/integration`)
as well — CI does.

> ⚠️ **`make gate` is not the same bar as CI**, and `make` may not exist on your machine at all
> (it does not on the primary dev PC). That target runs only the test suite,
> `pylint --fail-under=9.90 src/` and `bandit -r src/` — none of the guards above. Treat it as a
> convenience, never as evidence.

> ⚠️ **`make lint` is not a gate either.** It runs pylint, flake8, and bandit with `|| true` appended,
> so it prints findings and always exits `0`. It is useful for *reading* violations; it proves nothing.
> The only verifiable bar is the CI job result.

`flake8` is deliberately excluded from `make gate` — `src/` carries a handful of long-line violations
that would cost a cosmetic rewrite of a dozen files to clear. The meaningful subset (unused imports and
variables) is enforced by the `lint-changed-tests` CI job. Use `make lint` to see the full list.

---

## Branch naming

Everything goes through a branch and a pull request — including documentation-only changes.

| Prefix | Use for |
|--------|---------|
| `feat/` | New functionality |
| `fix/` | Bug fixes |
| `chore/` | Config, tooling, dependencies |
| `docs/` | Documentation only |

```bash
git checkout main && git pull
git checkout -b fix/telegram-otp-expiry
```

---

## Commit messages

Follow Conventional Commits: `type(scope): summary`.

```
fix(gate): bind auto-merge to the analyzed SHA instead of live head
docs(readme): correct the CLI Hook requirements
test(scorer): cover the no-AI ceiling at 89 points
```

Write the summary in the imperative mood and keep it under ~72 characters. Korean summaries are fine —
this project's history is bilingual.

**Never put a real token, key, or chat ID in a commit message.** A `commit-msg` hook blocks the Telegram
bot-token pattern specifically, and gitleaks scans both the diff and the message, but neither is
exhaustive. Use `<REDACTED>`.

---

## Code comments (bilingual)

New code comments are written **in Korean first, with the English on the very next line**:

```python
# 레이트 리밋 초과 시 재시도
# Retry on rate limit exceeded

# 같은 SHA가 이미 분석된 경우 건너뜀 (멱등성 보장)
# Skip if the same SHA was already analyzed (idempotency guard)
```

The reason is practical: the maintainer works in Korean and a growing share of contributors and AI
agents read the codebase in English. Keeping both in the source means neither has to guess.

If you are not comfortable writing Korean, **write the English line and say so in the PR** — a
maintainer will add the Korean. Do not machine-translate a comment you cannot verify.

Single-word standard tags (`# TODO`, `# FIXME`, `# type: ignore`) stay English-only. Existing files are
updated opportunistically: when you touch a file, bring the comments you edited into the bilingual form —
there is no requirement to convert a whole file you are only passing through.

**This is a convention, not an enforced gate.** A pre-commit hook used to block on it and was
deliberately disabled — it was the only style rule able to fail a commit, and the friction
was not worth it. The checker still exists if you want it:

```bash
python scripts/check_bilingual_comments.py
```

---

## Pull request checklist

Opening a PR fills in [the template](.github/PULL_REQUEST_TEMPLATE.md) automatically. Before you mark it
ready:

- [ ] `py -3 scripts/pre_push_gate.py --full` passes locally (13 CI-enforced guards + pylint + bandit + unit tests)
- [ ] For pipeline/analyzer changes: `py -3 -m pytest tests/integration` as well — neither gate form runs it
- [ ] New behavior has a test that fails without your change
- [ ] The PR body says **what a reviewer should verify by hand** — not just "tests pass". Anything
      visual, deploy-dependent, or involving a third-party service cannot be verified by the test suite.
- [ ] **UI changes** (`src/templates/**`, `src/static/**`): state that visual verification is outstanding
      and list the combinations — 4 themes (dark / light / pastel / catppuccin) × desktop and mobile.
      Static tests cannot catch a broken theme token.
- [ ] **New file under `src/`**: add it to the tree and, if it sits on a request path, to the data-flow
      section in [`docs/architecture.md`](docs/architecture.md). A pre-commit hook enforces the tree.
- [ ] **New environment variable**: document it in [`docs/reference/env-vars.md`](docs/reference/env-vars.md).
- [ ] **Changed test counts, coverage, or pylint score**: update [`docs/STATE.md`](docs/STATE.md) first —
      it is the single source of truth — then the README badges. A pre-commit hook compares them and will
      block the commit if they disagree.

Maintainers may push fix-up commits to your branch rather than round-tripping small review comments.

---

## Two things that bite everyone

**Adding an ORM column without a migration.** A new column on a model is not a schema change until
there is an Alembic revision for it. Without one, the code works locally against a freshly created
SQLite database and returns a 500 in production the moment it touches the real table.

```bash
make revision m="add merge_attempts.failure_reason"
make migrate
# then verify the round trip: alembic downgrade -1 && alembic upgrade head
```

Columns declared `nullable=False` need a `server_default`, otherwise the migration fails on any table
that already has rows.

**Changing a config field in one place.** A repository setting exists in five places — the SQLAlchemy
model, the dataclass, the API update body, the settings form, and the presets. Update fewer than all
five and the REST API will silently overwrite the field with `NULL` on the next save.

The automated guard covers **three of the five**:
[`scripts/check_config_5way_sync.py`](scripts/check_config_5way_sync.py) compares the three Python
layers by AST. The settings form and the presets are HTML and JavaScript, where field-name parsing is
too fragile to enforce, so **those two are a manual check** — grep the field name and confirm all five
before you push. (A separate test does catch the specific case of a form control that escapes the
`<form>` and silently stops being submitted.)

---

## Where the docs live

| I want to… | Read |
|------------|------|
| Understand the module layout and request flow | [`docs/architecture.md`](docs/architecture.md) |
| Understand how the score is computed | [`docs/reference/scoring.md`](docs/reference/scoring.md) |
| Look up an environment variable | [`docs/reference/env-vars.md`](docs/reference/env-vars.md) |
| See which languages each analyzer covers | [`docs/reference/language-coverage.md`](docs/reference/language-coverage.md) |
| Deploy or operate it | [`docs/runbooks/`](docs/runbooks/) |
| See current test counts and quality numbers | [`docs/STATE.md`](docs/STATE.md) |
| Find open work | [GitHub Issues](https://github.com/xzawed/SCAManager/issues) |

`CLAUDE.md` and `AGENTS.md` at the repository root are working agreements for the AI agents that
contribute to this project. You do not need to read them to contribute, but they explain why some
conventions here are stricter than usual.

---

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE), the same terms as the rest of the project.
