# Tier 3 — GitHub Native Auto-Merge 통합 설계

> 작성일: 2026-04-27
> 상태: **계획안 (Draft) — 사용자 승인 후 구현 PR 진행**
> 선행 의존: PR #100 (Loop Guard 화이트리스트 봇 한정) 머지 완료

---

## 1. 배경 및 문제 의식

### 1.1 현재 구조

SCAManager 는 PR 분석 후 점수가 `merge_threshold` 이상이면 직접 머지를 수행한다. CI 가 진행 중(`mergeable_state=unstable/unknown`)이면 `merge_retry_queue` 에 큐잉하고 1분 cron + `check_suite.completed` 웹훅으로 재시도한다.

```
분석 완료
  → score ≥ threshold
  → merge_pr() 호출
      ├─ 성공: 머지 완료
      ├─ unstable/unknown: merge_retry_queue 큐잉 → 재시도 (최대 30회, 24h)
      └─ 영구 실패: failure_reason 태그 기록 + Issue 생성 (Phase F.3)
```

관련 파일:
- `src/services/merge_retry_service.py` (~250 줄) — 재시도 워커
- `src/models/merge_retry.py` (~80 줄) — claim 패턴 ORM
- `src/repositories/merge_retry_repo.py` (~120 줄) — DB 접근
- `src/gate/retry_policy.py` (~150 줄) — 순수 함수: parse_reason_tag, should_retry, compute_next_retry_at
- `src/api/internal_cron.py` 일부 — 1분 cron 엔드포인트
- 관련 테스트 ~15 파일

### 1.2 문제점

| # | 항목 | 영향 |
|---|------|------|
| 1 | **유지보수 부담** | 큐 관리·재시도 정책·stale claim 회수·메트릭이 모두 우리 코드 |
| 2 | **CI 변경 시 cron 빈도 조정 필요** | 5분 → 1분 으로 단축한 이력 (`c99329e`) — 트레이드오프 매 회 의사결정 |
| 3 | **재배포 중 진행 중 큐 작업 유실 위험** | claim 후 5분 stale 정책으로 완화하지만 완전 보장 안 됨 |
| 4 | **GitHub 가 더 잘 하는 일을 우리가 함** | `enablePullRequestAutoMerge` 가 정확히 같은 의미론 제공 |

### 1.3 목표

GitHub 네이티브 `enablePullRequestAutoMerge` GraphQL mutation 을 채택해:
- 머지 대기/재시도/CI-aware 의 책임을 GitHub 에 위임
- `merge_retry_service.py` 폐기 → 코드 ~600 줄 감소
- `MergeAttempt` 관측 + `failure_reason` 태깅 + 실패 Issue 생성 (Phase F.3) 은 유지

---

## 2. GitHub 네이티브 Auto-Merge 동작 사양 (조사 결과)

### 2.1 활성화 흐름

```
1. PR 가 base 브랜치로 fast-forward 가능
2. 리포 Settings → "Allow auto-merge" 토글 ON (전제 조건)
3. GraphQL: enablePullRequestAutoMerge(input: {
     pullRequestId: <Node ID>,
     mergeMethod: SQUASH,
     expectedHeadOid: <PR head SHA>  // force-push 보호
   })
4. GitHub 가 모든 required check 통과 + 충돌 없음 시점에 자동 머지
5. 결과 webhook: pull_request.closed (merged=true)
```

### 2.2 자동 비활성화 조건

GitHub 가 auto-merge 를 자동으로 OFF 하는 시나리오:
- Required check fail
- 머지 충돌 발생
- 사용자가 force-push (`expectedHeadOid` 불일치)
- PR 작성자에게 GitHub 가 알림 발송

### 2.3 권한

- OAuth User Token: `repo` 스코프 충분 (현재 SCAManager 가 사용 중)
- GitHub App: Fine-grained `pull_requests: write` + `contents: write`
- 리포 settings 의 "Allow auto-merge" 가 OFF 면 mutation 이 422 반환

### 2.4 actor / mergedBy

- `mergedBy` 필드: auto-merge 를 활성화한 사용자 (= 우리 OAuth 토큰 owner = 리포 owner)
- 머지 commit 의 author/committer: PR head commit 의 원본 정보 유지

---

## 3. 새 머지 흐름

```
분석 완료
  → score ≥ threshold
  → enablePullRequestAutoMerge GraphQL 호출 (squash 메서드)
      ├─ 성공: GitHub 가 알아서 머지 (CI 대기 자동)
      │   → MergeAttempt 로깅 (status="auto_merge_enabled", expected_sha)
      │   → 머지 완료 시 pull_request.closed webhook 수신
      │       → MergeAttempt 업데이트 (status="merged")
      │
      ├─ 422 "Auto-merge not allowed": 리포 settings 미활성화
      │   → MergeAttempt failure_reason="auto_merge_disabled_in_repo_settings"
      │   → Issue 생성 (Phase F.3 advice 적용 — "Settings → Allow auto-merge ON")
      │   → 폴백: 즉시 merge_pr() 시도 (현재 동작 유지)
      │
      ├─ 422 "Required SHA mismatch": force-push 발생
      │   → MergeAttempt failure_reason="force_pushed"
      │   → 새 SHA 도착 시 webhook 으로 자동 재분석 → 새 enable 호출
      │
      └─ 4xx/5xx 기타: failure_reason="enable_api_error"
          → 폴백: merge_pr() 시도

머지 후 webhook:
  pull_request.closed (merged=true) 수신
  → MergeAttempt 행 lookup (PR number) → status 업데이트

머지 비활성화 webhook:
  pull_request.auto_merge_disabled 수신
  → MergeAttempt failure_reason 기록 + Issue 생성 (조건부)
```

---

## 4. 변경 면적

### 4.1 신규 코드

| 파일 | 줄 | 역할 |
|------|----|------|
| `src/github_client/graphql.py` | ~80 | GraphQL POST 래퍼 (httpx.AsyncClient 재사용) + `enable_auto_merge()` mutation |
| `src/gate/native_automerge.py` | ~120 | enable 호출 + 422 분류 + 폴백 로직 + MergeAttempt 로깅 |
| `tests/unit/github_client/test_graphql.py` | ~100 | mutation 직렬화·응답 파싱 테스트 |
| `tests/unit/gate/test_native_automerge.py` | ~250 | 각 422 시나리오·폴백·MergeAttempt 통합 테스트 |

### 4.2 수정 코드

| 파일 | 변경 |
|------|------|
| `src/gate/engine.py::_run_auto_merge` | `merge_pr()` 직접 호출 → `native_automerge.enable_or_fallback()` 호출로 교체 |
| `src/webhook/providers/github.py` | `pull_request.auto_merge_disabled` action 핸들러 추가 |
| `src/models/merge_attempt.py` | `failure_reason` enum 에 `auto_merge_disabled_in_repo_settings`, `force_pushed`, `enable_api_error` 추가 |
| `src/gate/merge_failure_advisor.py` | 신규 reason 별 advice 텍스트 추가 |
| `src/notifier/merge_failure_issue.py` | 신규 reason 처리 (dedup key 동일) |

### 4.3 폐기 후보 (다음 PR 또는 같은 PR 후반부)

| 파일 | 폐기 이유 |
|------|-----------|
| `src/services/merge_retry_service.py` | GitHub 네이티브가 동일 역할 수행 |
| `src/repositories/merge_retry_repo.py` | 큐 자체가 사라짐 |
| `src/models/merge_retry.py` | 동일 |
| `src/gate/retry_policy.py` | 동일 |
| `src/api/internal_cron.py` 의 retry 엔드포인트 | 동일 |
| `tests/unit/services/test_merge_retry_service.py` 등 | 동일 |
| `railway.toml` 의 1분 retry cron | 제거 |
| **합계 ~600 줄 감소** | |

> ⚠️ 폐기는 새 흐름이 production 에서 1주일 이상 안정 동작 검증 후 별도 cleanup PR.

### 4.4 마이그레이션

ORM 변경:
- `MergeAttempt.failure_reason` 에 새 태그 3개 추가 (CHECK constraint 없으면 마이그레이션 불필요, 단 ENUM 타입이면 Alembic op 필요 — 확인 필요)

데이터:
- 기존 `merge_retry_queue` 행은 cleanup PR 시점에 archive 또는 truncate

---

## 5. 단계별 진행 (3-PR 분할)

### PR-A: 네이티브 enable 인프라 (~600 줄 + 테스트)

- `github_client/graphql.py` + `gate/native_automerge.py` 신규
- `_run_auto_merge` 가 새 함수 호출하도록 교체 — **단, 폴백 로직으로 기존 `merge_pr()` 도 유지** (안전망)
- `pull_request.auto_merge_disabled` 웹훅 핸들러 추가
- MergeAttempt 신규 reason 태그 + advisor 텍스트
- **`merge_retry_service.py` 는 그대로 작동** — 폴백 경로가 여전히 큐잉 가능

### PR-B: 1주일 dogfooding 검증 후 큐 폐기 (~600 줄 감소)

- `merge_retry_service.py` 및 관련 모듈 삭제
- 1분 cron 엔드포인트 제거
- railway.toml cronJobs 정리
- `merge_retry_queue` 테이블 truncate (선택: drop 마이그레이션)

### PR-C (선택): "Allow auto-merge" 자동 활성화 안내

- Settings UI 에 "리포의 Allow auto-merge 가 활성화되어 있는지" 체크 표시
- 미활성화 시 사용자에게 한 번 안내 — Issue 생성 또는 banner

---

## 6. 위험 분석 및 완화

| 위험 | 발생 가능성 | 영향 | 완화 |
|------|-----------|------|------|
| 리포 settings "Allow auto-merge" OFF | 중 | 머지 안 됨 | 422 분기 → Issue 생성 + 폴백 로직 |
| Required check 정의 없는 리포에서 즉시 머지 | 저 | 검증 없이 머지될 위험 | SCAManager 자체가 분석 통과한 상태에서만 enable 호출하므로 점수 기반 검증은 보장됨 |
| GitHub 측 native auto-merge 장애 | 매우 저 | 머지 지연 | 폴백 경로로 직접 merge_pr() 시도 — PR-A 의 안전망 |
| `expectedHeadOid` 불일치 (force-push) | 저 | 머지 자동 disable | 새 SHA 도착 시 자동 재분석 → 새 enable 호출 (자연 복구) |
| MergeAttempt 로깅 시점 변화 | 중 | 메트릭 의미 변동 | "auto_merge_enabled" status 신규 — 기존 "merged" 와 분리 집계 |

---

## 7. 관측성 / 메트릭

### 7.1 새 status 값

`MergeAttempt.status`:
- `auto_merge_enabled` (신규): enable mutation 성공, 머지 대기 중
- `merged` (기존): 실제 머지 commit 발생
- `failed` (기존): enable 422 + 폴백도 실패

### 7.2 분포 추적

대시보드 또는 cron 에서:
- enable → merged 까지 평균 latency (CI 대기 시간 = 우리 책임 아님)
- enable → disabled (force-push 등) 비율
- 폴백 발동률 (네이티브 422 → 직접 머지로 회복)

### 7.3 stage_metrics 통합

`stage_timer("native_automerge_enable", trigger_source="gate")` 등으로 각 단계 latency 측정.

---

## 8. 결정 지점 — 사용자 승인 필요

이 계획서가 채택되면 **PR-A 부터 구현 시작** 합니다. 다음 결정이 필요합니다:

1. **머지 메서드**: `SQUASH` 가 기본값인가? 리포별로 다르게 설정 가능해야 하는가?
2. **폴백 정책**: 422 발생 시 항상 `merge_pr()` 시도? 아니면 Issue 만 생성하고 사용자 결정?
3. **Repo settings 사전 검사**: enable 시도 전에 "Allow auto-merge" 토글 상태를 GraphQL `repository.autoMergeAllowed` 로 미리 확인할까? (한 번의 추가 API 호출 비용)
4. **MergeAttempt status 변경 마이그레이션**: 기존 행의 의미 그대로 유지? PR-B 시점에 기존 행을 별도 archive 테이블로?
5. **PR-A 구현 시기**: 즉시 진행 vs 다른 작업 우선순위?

---

## 9. 비-목표 (Out of Scope)

- GitHub App 으로 인증 모델 전환 (별도 Tier — 멀티 테넌트 확장 시점)
- Check Runs 출력 채널 채택 (별도 Tier — Tier 3 와 독립)
- Branch Protection 자동 설정 (사용자가 직접 구성)
- 머지 충돌 자동 해소 (GitHub 가 알림만, 우리는 처리 안 함)

---

## 10. 참고

- [GitHub Docs — Automatically merging a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
- [GraphQL Mutation `enablePullRequestAutoMerge`](https://docs.github.com/en/graphql/reference/mutations#enablepullrequestautomerge)
- 사고 회고: PR #98/#100 (Loop Guard 사고 → Tier 분석 → Tier 3 도출)
- 선행 PR: #93 (BPR 미설정 큐잉), #97 (BPR base ref 동적), #100 (Loop Guard 봇 한정)

> **Audit roundtrip test 3** (2026-04-29) — 3회 반복 성공률 측정.

