# 브랜치 보호 운영 (main)

리포 가드는 라이브 설정을 보지 못한다 — 설정을 바꾸면 같은 PR 에서 이 파일도 갱신한다.

## 현재 계약

`enforce_admins: true` · 리뷰 요구 없음 · `strict: false` · squash/merge/rebase 3종 허용 → 커밋 메시지 가드는 `before..after` 범위로 읽는다(`scripts/check_test_count_sync.py`).

required status checks 10종(전부 `app_id: 15368`):

1. `Repo integrity guards (stdlib backstop)`
2. `pip-audit (SCA — 의존성 취약점 게이트)`
3. `pytest + Codecov + SonarCloud`
4. `Static analysis gate (pylint + bandit on src/)`
5. `TruffleHog secret scan`
6. `Lint changed test files (F401/F841 — C1)`
7. `lint-js 공허화 차단 (검사 범위 비면 fail)`
8. `PG-only tests (SKIP LOCKED + migration round-trip)`
9. `Analyze (python)`(CodeQL)
10. `E2E (Playwright)`

## job 이름을 바꿀 때

required check 는 (SHA, 이름)으로 식별된다 — 이름이 어긋난 체크는 영원히 pending 이고 머지가 멈춘다. 같은 PR 에서 넷을 고친다.

1. `ci.yml` 의 job `name:`
2. 위 목록
3. `tests/unit/scripts/test_required_check_names.py` 의 `_REQUIRED_JOB_NAMES`
4. 라이브 설정

## 승격·롤백

`PUT .../protection` 은 전체를 덮어써 `enforce_admins` 를 지운다. 하위 리소스 PATCH 만 쓴다.

```bash
R=repos/xzawed/SCAManager/branches/main/protection
gh api $R/required_status_checks > rsc.before.json   # 보존
# checks 편집 — app_id 보존: {"context":"<이름>","app_id":15368}
gh api -X PATCH $R/required_status_checks --input rsc.next.json
gh api $R --jq '.required_status_checks.contexts'
# 롤백 = rsc.before.json 의 strict/checks 로 다시 PATCH
```

## 체크가 인프라 사유로 빨갈 때

1. 실패 step 이 `Set up job`·`Checkout` 등 인프라 단계인지 본다(`gh api .../actions/jobs/<id> --jq '.steps[]|select(.conclusion=="failure")'`).
2. run 진행 중이면 재실행이 거부된다 — 끝난 뒤 `gh run rerun <run_id> --failed`
3. 또 같으면 롤백을 검토한다. `--no-verify`·admin 우회는 쓰지 않는다.

## auto-merge 상호작용

`mergeable_state="blocked"` → `BRANCH_PROTECTION_BLOCKED`(`merge_reasons._RETRIABLE_TAGS`). 재시도는 `retry_policy.should_retry` 가 `ci_status == "running"` 일 때만, 종료 후 blocked 면 종결.
