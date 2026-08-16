# 브랜치 보호 운영 (main)

> **이 문서는 GitHub 설정의 기록이지 집행면이 아니다.** 리포 안의 어떤 테스트도
> 라이브 설정을 관측하지 않는다(사유는 아래 §관측의 한계). 설정을 바꾸면 **여기도 같이**
> 갱신해야 하고, 그 동기화는 사람이 한다.

## 허용 머지 방식 — 3종 전부 유지

`gh api repos/xzawed/SCAManager` 실측: `allow_squash_merge` · `allow_merge_commit` ·
`allow_rebase_merge` **전부 true**. `squash_merge_commit_message` = `COMMIT_MESSAGES`.

> **커밋 메시지를 판정 입력으로 쓰는 모든 가드는 세 방식 전부에서 동작해야 한다.**
> tip 하나(`git log -1`)가 아니라 **범위**로 읽는다 — merge commit / rebase 는 tip 에
> 마커가 없다.

정본: `scripts/check_test_count_sync.py` 의 `before..after` 범위 조회.
회귀: `tests/unit/scripts/test_deferral_marker_survives_merge.py`.

## 현재 상태

- `enforce_admins`: **true** — 관리자도 우회 불가
- `required_pull_request_reviews`: **없음** (사람 리뷰 요구 없음)
- `strict`: **false** (base 최신화 강제 안 함)
- `required_status_checks.checks`: **10종** (전부 `app_id: 15368` = GitHub Actions)

| # | context | 비고 |
|---|---|---|
| 1 | `Repo integrity guards (stdlib backstop)` | |
| 2 | `pip-audit (SCA — 의존성 취약점 게이트)` | |
| 3 | `pytest + Codecov + SonarCloud` | |
| 4 | `Static analysis gate (pylint + bandit on src/)` | |
| 5 | `TruffleHog secret scan` | |
| 6 | `Lint changed test files (F401/F841 — C1)` | |
| 7 | `lint-js 공허화 차단 (검사 범위 비면 fail)` | |
| 8 | `PG-only tests (SKIP LOCKED + migration round-trip)` | |
| 9 | `Analyze (python)` | CodeQL |
| 10 | **`E2E (Playwright)`** | required. `enforce_admins: true` 이라 플레이크 1건이 전 리포 머지를 멈춘다 — 그때 아래 롤백을 쓴다. |

이름 불변 가드: `tests/unit/scripts/test_required_check_names.py` (`ci.yml` job `name:` ↔ 위 표).
라이브 GitHub 목록은 이 테스트가 **보지 않는다**.

## 승격·롤백 절차

두 작업 모두 **하위 리소스 PATCH** 를 쓴다. `PUT .../protection` 은 보호 설정 **전체를
덮어쓰므로**, 일부만 보내면 `enforce_admins` 등 나머지가 소실된다.

```bash
# 0) 현재 상태 보존 (반드시 먼저)
gh api repos/xzawed/SCAManager/branches/main/protection/required_status_checks \
  > rsc.before.json

# 1) 승격 — before 의 checks 배열에 항목을 추가한 페이로드를 만든다(app_id 보존 필수)
#    {"strict": false, "checks": [ ...기존..., {"context": "<이름>", "app_id": 15368} ]}
gh api -X PATCH repos/xzawed/SCAManager/branches/main/protection/required_status_checks \
  --input rsc.promote.json

# 2) 롤백 — 0) 에서 받은 파일의 strict/checks 를 그대로 되돌린다
gh api -X PATCH repos/xzawed/SCAManager/branches/main/protection/required_status_checks \
  --input rsc.rollback.json

# 3) 확인
gh api repos/xzawed/SCAManager/branches/main/protection \
  --jq '{checks:(.required_status_checks.contexts|length), admins:.enforce_admins.enabled}'
```

## 체크가 인프라 사유로 실패했을 때

required 체크는 **코드와 무관한 이유로도** 빨개진다(러너 할당 실패 등 `Set up job` /
`Checkout`). `enforce_admins: true` 라 그 순간 머지는 물리적으로 막힌다.

**대응 순서** (롤백은 마지막 수단이다):

1. 실패 step 이 `Set up job` · `Checkout` 등 **인프라 단계**인지 확인한다.
   `gh api repos/xzawed/SCAManager/actions/jobs/<job_id> --jq '.steps[]|select(.conclusion=="failure")'`
2. **워크플로 run 이 아직 진행 중이면 재실행이 거부된다**(`This workflow is already running`).
   나머지 job 이 끝날 때까지 기다린 뒤 `gh run rerun <run_id> --failed` 로 실패 job 만 돌린다.
3. 재실행도 같은 단계에서 실패하면 그때 §승격·롤백 절차의 롤백을 검토한다.

**`--no-verify`·admin 우회는 선택지가 아니다** — `enforce_admins: true` 는 그러라고 켠 것이다.

## 이름이 곧 계약이다

required check 는 **(SHA, 이름)** 으로 식별된다. `ci.yml` 의 job `name:` 을 바꾸면
GitHub 이 기다리는 이름의 체크는 **영원히 보고되지 않고** 머지가 멈춘다 —
설정은 그대로인데 게이트만 조용히 의미를 잃는 형태다.

`tests/unit/scripts/test_required_check_names.py` 가 이 축(이름 drift)을 막는다.
job 이름을 바꿀 때는 **같은 PR 에서** 위 표와 그 테스트의 리터럴, 그리고 라이브 설정을
함께 갱신한다.

## 관측의 한계

**리포 안의 어떤 가드도 라이브 브랜치 보호를 보지 못한다.** GitHub 에서 항목을 빼도
CI 는 전건 초록이다. 관측하려면 `Administration: read` 토큰이 필요한데, 그것을 리포
시크릿에 두면 **같은 리포의 어떤 워크플로에서도 읽을 수 있어** containment 가 성립하지
않는다(Environment 스코프 + 브랜치 제한이 필요). 그래서 만들지 않았다 —
없는 관측을 있는 것처럼 보이게 하는 파일을 두는 것이 더 나쁘다.

## 알려진 상호작용 — auto-merge

`mergeable_state="blocked"`(required check 미충족 또는 규칙상 충족 불가)는
`merge_reasons.BRANCH_PROTECTION_BLOCKED` 로 매핑된다. 이 태그는 `_RETRIABLE_TAGS` 에
**있다** — 집합은 `UNSTABLE_CI` · `UNKNOWN_STATE_TIMEOUT` · `BRANCH_PROTECTION_BLOCKED`
(`src/gate/merge_reasons.py` 의 `_RETRIABLE_TAGS`).

재시도 여부는 `retry_policy.should_retry(tag, ci_status)` 가 정한다.
`BRANCH_PROTECTION_BLOCKED` 는 **`ci_status == "running"` 일 때만** 큐에 넣는다.

- required check 가 아직 도는 중이면 재시도 큐가 기다린다.
- CI 가 끝났는데도 (`passed` / `failed` / `unknown`) 여전히 blocked 면 종결한다
  — 리뷰 미승인처럼 기다려도 풀리지 않는 경우다. 이 태그는 `UNSTABLE_CI` 와 달리
  `passed` 를 재시도하지 않는다.

가드: `tests/unit/gate/test_retry_policy.py` ·
`tests/unit/gate/test_merge_reasons.py` (`test_branch_protection_blocked_is_retriable`).
