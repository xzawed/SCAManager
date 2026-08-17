# 브랜치 보호(main)

🔴 가드는 라이브 설정을 못 본다 — 바꾸면 같은 PR 에서 이 파일 갱신.

`enforce_admins: true` · 리뷰 불요 · `strict: false` · squash/merge/rebase 3종 → 커밋 가드는 `before..after` 범위. required 10종(전부 `app_id: 15368`):

```
Repo integrity guards (stdlib backstop)
pip-audit (SCA — 의존성 취약점 게이트)
pytest + Codecov + SonarCloud
Static analysis gate (pylint + bandit on src/)
TruffleHog secret scan
Lint changed test files (F401/F841 — C1)
lint-js 공허화 차단 (검사 범위 비면 fail)
PG-only tests (SKIP LOCKED + migration round-trip)
Analyze (python) # CodeQL
E2E (Playwright)
```

**이름 변경 = 4곳** — (SHA,이름) 식별 — 어긋나면 영원히 pending: `ci.yml` job `name:` · 위 목록 · `test_required_check_names.py` `_REQUIRED_JOB_NAMES` · 라이브 설정.

**승격·롤백** — `PUT .../protection` = 전체 덮어쓰기(`enforce_admins` 소실) → 하위 리소스만 PATCH. `P=repos/xzawed/SCAManager/branches/main/protection/required_status_checks` → `gh api $P > before.json` → `gh api -X PATCH $P --input next.json`.

**red** — 인프라(`Set up job`·`Checkout`) 실패면 run 종료 후 `gh run rerun <run_id> --failed`(진행 중 거부), 재발 = 롤백. `--no-verify`·admin 우회 금지.

**auto-merge** — `mergeable_state=blocked` → `BRANCH_PROTECTION_BLOCKED`(`merge_reasons._RETRIABLE_TAGS`), 재시도 = `ci_status=="running"`(`retry_policy`).
