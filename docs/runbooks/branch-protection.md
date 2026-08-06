# 브랜치 보호 운영 (main)

> 🔴 **이 문서는 GitHub 설정의 기록이지 집행면이 아니다.** 리포 안의 어떤 테스트도
> 라이브 설정을 관측하지 않는다(사유는 아래 §관측의 한계). 설정을 바꾸면 **여기도 같이**
> 갱신해야 하고, 그 동기화는 사람이 한다.

## 현재 상태 (2026-08-06 실측)

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
| 10 | **`E2E (Playwright)`** | 🔴 **2026-08-06 승격 (backlog R64)** |

## R64 — e2e 승격 근거 (실측)

| 구간 | e2e job 성공률 |
|---|---|
| `#1294`(CSP 결함 + CI 의 CSS 빌드 누락) 이전 | **2 / 17** |
| 그 이후 | **16 / 16** |

빨강의 원인은 플레이크가 아니라 **원인이 밝혀진 두 결함**이었고, 그것이 닫힌 뒤로 한 번도
실패하지 않았다. `#1298` 이 공허화 3경로(전건 skip · 수집 범위 축소 · 통과 하한)를 닫아
"초록이 공허할 수 있다" 는 축도 함께 제거했다.

🔴 **정직 기준**: 16/16 은 **점추정**이다. 95% 신뢰 상한(rule of three)으로 플레이크율은
**≤ 17%** 이지 0% 가 아니다. `enforce_admins: true` 라 플레이크 1건이 전 리포 머지를
멈출 수 있다 — 그럴 때 아래 롤백을 쓴다.

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

## 🔴 이름이 곧 계약이다

required check 는 **(SHA, 이름)** 으로 식별된다. `ci.yml` 의 job `name:` 을 바꾸면
GitHub 이 기다리는 이름의 체크는 **영원히 보고되지 않고** 머지가 멈춘다 —
설정은 그대로인데 게이트만 조용히 의미를 잃는 형태다.

`tests/unit/scripts/test_required_check_names.py` 가 이 축(이름 drift)을 막는다.
job 이름을 바꿀 때는 **같은 PR 에서** 위 표와 그 테스트의 리터럴, 그리고 라이브 설정을
함께 갱신한다.

## 관측의 한계 (정직 기준)

🔴 **리포 안의 어떤 가드도 라이브 브랜치 보호를 보지 못한다.** GitHub 에서 항목을 빼도
CI 는 전건 초록이다. 관측하려면 `Administration: read` 토큰이 필요한데, 그것을 리포
시크릿에 두면 **같은 리포의 어떤 워크플로에서도 읽을 수 있어** containment 가 성립하지
않는다(Environment 스코프 + 브랜치 제한이 필요). 그래서 만들지 않았다 —
없는 관측을 있는 것처럼 보이게 하는 파일을 두는 것이 더 나쁘다.

## 알려진 상호작용 — auto-merge

`mergeable_state="blocked"`(required check 미충족)는 `merge_reasons.BRANCH_PROTECTION_BLOCKED`
로 매핑되고, 그 태그는 `_RETRIABLE_TAGS`(= `unstable_ci`, `unknown_state_timeout`)에
**없다** → 재시도 큐가 기다리지 못하는 **종결 실패**다.

즉 required check 가 아직 도는 동안 auto-merge 가 시도되면 그 PR 은 영구 포기된다.
🔴 이것은 R64 가 만든 것이 **아니다** — 브랜치 보호 자체(2026-08-01, R2-b, 사용자 승인)가
켜진 시점부터 있던 성질이고, 체크를 하나 더 넣으면 그 창이 길어질 뿐이다.
분류를 바꾸는 것(= `blocked` 를 retriable 로)은 auto-merge 동작 변경이라 **High tier**
(정책 15)로 별도 결정이 필요하다 — backlog 에 등재돼 있다.
