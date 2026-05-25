# Auto-merge 실패 진단 + Phase F 로드맵 — 3-에이전트 분석 (2026-04-24)

> 일부 Repo 에서 PR auto-merge 가 실패하는 현상 보고 (2026-04-24 사용자 관찰).
> 3개 병렬 에이전트 (A: 현재 구현 분석 · B: GitHub 실패 시나리오 전문 · C: 재발
> 방지 로드맵) 독립 조사 후 종합.

---

## 📌 핵심 결론 (TL;DR)

1. **확정 원인 #1** (Agent B · P0): `mergeable_state == "unstable"` 이 현재 `_MERGEABLE_BLOCK` 에 없음 → BPR "Require status checks" 가 설정된 repo 에서 **CI 일부 실패** 상태에도 merge 시도 → GitHub 가 405 로 거부.
2. **가시성 공백** (Agent A): auto-merge 실패 이력이 **DB 에 기록되지 않음** (`GateDecision` 은 Approve/Reject 만). 어떤 repo 에서 얼마나 실패했는지 추적 불가.
3. **재시도 시간 부족** (Agent B · P1): unknown 상태 재시도가 3초 × 3회 = 9초만. 대규모 PR 이나 check suite 많은 repo 에서는 GitHub 의 mergeable 계산이 20초+ 걸릴 수 있음.
4. **권장 조치 부재** (Agent C): 실패 Telegram 알림에 사유는 있으나 "어떻게 해결하라" 가 없음.

---

## 📊 현재 auto-merge 구현 요약 (Agent A 기반)

| 항목 | 상태 | 위치 |
|------|------|------|
| 트리거 조건 | `config.auto_merge` AND `score >= merge_threshold` | `src/gate/engine.py::_run_auto_merge` |
| API 호출 | `PUT /repos/{o}/{r}/pulls/{n}/merge` (squash) | `src/gate/github_review.py::merge_pr` (line 65-116) |
| 사전 체크 | `_MERGEABLE_BLOCK = {"dirty", "blocked", "behind", "draft"}` | line 11-12 |
| unknown 재시도 | 3초 × 3회 (linear) | `_UNKNOWN_RETRY_LIMIT = 3`, `_UNKNOWN_RETRY_DELAY = 3.0` |
| HTTP 오류 분류 | 405/403/422/409 → 한국어 label | `_interpret_merge_error` |
| 실패 알림 | Telegram (text + score) | `_notify_merge_failure` |
| 실패 DB 기록 | **❌ 없음** | — |
| 권한 사전 검증 | **❌ 없음** | — |
| BPR 세부 조회 | **❌ 없음** | — |
| 반환값 | `tuple[bool, str | None]` | — |

**기존 테스트 커버리지** (test_engine.py + test_github_review.py): 12+ 시나리오.
**미커버**: unstable 상태 / BPR 상세 분화 / DB 실패 기록 / 권한 사전 검증.

---

## 🔍 실패 시나리오별 현재 대응 (Agent B 기반)

| 원인 | 빈도 | HTTP | 현재 대응 | 평가 |
|------|------|------|-----------|------|
| Branch Protection 미달 | **높음** | 405 | mergeable_state="blocked" 사전 감지 | ✅ 감지 OK, 사유 세분화 부족 |
| mergeable_state="dirty" (conflict) | 중간 | 405 | 사전 감지 | ✅ |
| mergeable_state="behind" | 중간 | 405 | 사전 감지 | ✅ |
| mergeable_state="draft" | 낮음 | 405 | 사전 감지 | ✅ |
| **mergeable_state="unstable"** | **높음** | **405** | **❌ 현재 merge 시도 후 실패** | **🔴 P0 버그** |
| mergeable_state="unknown" | 중간 | — | 재시도 3×3초 | ⚠️ 시간 부족 가능 |
| 권한 부족 (scope / collaborator) | 낮음 | 403 | 사후 감지 + Telegram | 🟡 문서화 부재 |
| PR 이미 merged / closed | 매우 낮음 | 405 | 사후 감지 | ✅ |
| HEAD SHA 변경 | 낮음 | 409 | 사후 감지 | ✅ |
| Validation failed | 낮음 | 422 | 사후 감지 | ✅ |
| GitHub Merge Queue 충돌 | Enterprise 전용 | 422/400 | 사후 감지 (원인 불명) | 🟡 |

---

## 🗺️ Phase F 로드맵 (Agent C 기반, Agent A/B 발견 통합)

### 설계 원칙
- **관측 먼저** — 측정 없이 개선 못 함 (F.1 을 절대 선행으로)
- **점진 개선** — 각 단계는 1세션으로 완결, 독립 배포 가능
- **후방 호환** — 기존 `merge_pr(...) -> tuple[bool, str]` 시그니처 보존, reason 을 enum 으로 승격하되 기존 문자열은 detail 로 포함

### 우선순위 및 단계

| Phase | 목표 | 선행 | 예상 테스트 | 세션 |
|-------|------|-----|-----------|------|
| **F.1** | 관측 — `MergeAttempt` ORM + `log_merge_attempt` + reason enum | 없음 | +8 | 1 |
| **F.2** | 사전 체크 보강 + unknown exponential backoff + **unstable 추가** | F.1 | +6 | 1 |
| **F.3** | 실패 알림 고도화 — reason → 권장조치 매핑 + Issue 자동 생성 옵션 | F.1 | +5 | 1 |
| **F.4** | 대시보드 "Auto-merge History" 탭 + 성공률 배지 | F.1 | +5 | 1 |
| **F.5** | Settings UI "BPR 호환성 체크" + 권한 dry-run | F.3 | +4 | 1 |

**총 예상**: 5 세션, +28 tests.

### Phase F.1 — 관측 기반 (최우선)

**파일 추가**:
- `src/models/merge_attempt.py` — `MergeAttempt` ORM
- `src/repositories/merge_attempt_repo.py` — CRUD + 집계
- `src/shared/merge_metrics.py` — `log_merge_attempt()` 헬퍼
- `src/gate/merge_reasons.py` — `MERGE_FAIL_*` 상수 enum-like
- `alembic/versions/0014_add_merge_attempts.py` — 마이그레이션

**ORM 스키마** (제안):
```python
class MergeAttempt(Base):
    id              # PK
    repo_id         # FK → repositories (indexed)
    analysis_id     # FK → analyses (indexed, nullable)
    pr_number       # int
    score           # int (at time of attempt)
    merge_method    # "squash" | "merge" | "rebase"
    status          # "success" | "failure" | "skipped"
    failure_reason  # MERGE_FAIL_* enum string (nullable)
    failure_detail  # 원본 GitHub 에러 메시지 (nullable)
    attempt_count   # unknown 재시도 시 몇 번째 시도
    duration_ms     # 시도 소요 시간
    created_at      # timezone-aware
```

**`failure_reason` enum (정규 태그)**:
```
branch_protection_blocked  # mergeable_state=blocked
dirty_conflict             # mergeable_state=dirty
behind_base                # mergeable_state=behind
draft_pr                   # mergeable_state=draft
unstable_ci                # mergeable_state=unstable (P0 신규)
unknown_state_timeout      # 재시도 후 unknown
permission_denied          # HTTP 403
not_mergeable              # HTTP 405
unprocessable              # HTTP 422
conflict_sha_changed       # HTTP 409
network_error              # httpx 네트워크 예외
unknown                    # 분류 불가
```

**리팩토링**: `merge_pr` 와 `_run_auto_merge` 가 tuple 대신 `MergeAttemptResult` dataclass 반환하게 변경 (reason_tag 필수). 기존 테스트는 `.ok` / `.reason_detail` 로 호환 접근.

### Phase F.2 — 사전 체크 보강 + unstable 추가 + exponential backoff

**핵심 변경**:
```python
# src/gate/github_review.py
_MERGEABLE_BLOCK = frozenset({
    "dirty", "blocked", "behind", "draft",
    "unstable",  # ← P0 추가 (BPR Required status checks 대응)
})

# unknown 재시도
_UNKNOWN_RETRY_DELAYS = [2.0, 4.0, 8.0]  # 최대 14초 (기존 9초)
# jitter ±10% 추가로 thundering herd 방지
```

**`draft` 의 reason 을 `draft_pr` 로 분리** — 현재 `_MERGEABLE_BLOCK` 묶여서 사유 구분 안 됨.

**`RepoConfig.merge_method` 컬럼 추가** — 기본 "squash", "merge"/"rebase" 옵션. 일부 repo 는 "Require linear history" 로 rebase 만 가능.

### Phase F.3 — 실패 알림 고도화

**새 모듈**: `src/gate/merge_failure_advisor.py`
```python
_ADVICE = {
    "branch_protection_blocked":
        "Required Reviewers 미달 또는 Status Check 미통과. "
        "GitHub Settings → Branches → Protection rules 확인.",
    "dirty_conflict":
        "PR 에 머지 충돌 발생. rebase 또는 수동 머지 필요.",
    "behind_base":
        "base branch 가 앞서 있음. PR 의 'Update branch' 버튼 또는 rebase.",
    "unstable_ci":
        "CI 일부 실패. GitHub Actions 확인 후 재실행 또는 status check 통과 필요.",
    "permission_denied":
        "GitHub Token 권한 부족. `repo` 스코프 (classic) 또는 "
        "`pull_requests: write` + `contents: write` (fine-grained) 필요.",
    # ...
}
```

**`_notify_merge_failure`** 메시지 포맷:
```
⚠️ Auto-merge 실패
  repo: owner/repo
  PR:   #123 (점수 88/100)
  사유: unstable_ci
  권장: CI 일부 실패. GitHub Actions 확인 후 재실행...
  링크: https://github.com/owner/repo/pull/123
```

**`RepoConfig.auto_merge_issue_on_failure`** 옵션 (기본 false):
- true 면 auto-merge 실패 시 GitHub Issue 자동 생성 (라벨 `auto-merge-failure`)
- 중복 방지: 최근 24시간 내 open issue 검색 후 skip

### Phase F.4 — 대시보드 Auto-merge History

**repo 상세 페이지 (`/repos/{name}`)** 에 새 섹션:
- 최근 20 건 `MergeAttempt` 테이블 (time · PR · score · status · reason · action)
- Overview (`/`) 의 repo 리스트에 auto-merge 성공률 배지 (7일 윈도우)
- reason 별 분포 도넛 차트 (`_build_merge_reason_distribution()`)

### Phase F.5 — Settings UI BPR 호환성 체크

**새 엔드포인트**: `GET /api/repos/{name}/bpr-check`
- `GET /repos/{owner}/{repo}/branches/{default}/protection` 호출
- 요약: Required Reviewers count / Required Status Checks list / Restrictions
- 현재 토큰으로 `PUT merge` 가 가능한지 dry-run (실패 시 사유)

**Settings UI**: `auto_merge` 토글 옆 "Check compatibility" 버튼 →
- ✅ 호환 가능 — 초록색
- ⚠️ 주의 — BPR 조건 + 현재 상태 표시
- ❌ 불가능 — 사유 + 해결 방법

auto_merge 저장 시 자동 호출 → 경고 배너.

---

## 🎯 Quick Win (Phase F 착수 전, 즉시 적용 가능)

Agent C 의 즉시 조치 제안 + Agent B 의 P0 발견 병합:

| # | 변경 | 예상 효과 | 소요 | 리스크 |
|---|------|----------|------|-------|
| **QW1** | `_MERGEABLE_BLOCK` 에 `"unstable"` 추가 | BPR "Require status checks" repo 실패율 감소 | 5분 | 낮음 |
| **QW2** | `_UNKNOWN_RETRY_DELAY/_LIMIT` 를 `settings` 로 외부화 (기본 3.0/3 유지) | 운영 중 튜닝 가능 | 30분 | 낮음 |
| **QW3** | `_notify_merge_failure` 본문에 `https://github.com/{repo}/pull/{n}` 링크 추가 | 사용자 즉시 접근 | 10분 | 없음 |
| **QW4** | `_run_auto_merge` 의 except 에 `RuntimeError` / `ValueError` 추가 | 알림 스킵 방지 | 10분 | 낮음 |
| **QW5** | `_interpret_merge_error` 의 label 을 `src/gate/merge_reasons.py` 상수로 추출 | F.1 준비 작업 (breaking change 없음) | 30분 | 없음 |

**Quick Win 5건 총 소요**: ~90분. Phase F.1 을 **이 상태에서 승인받아 착수** 하는 방식이 효율적.

---

## 📈 성공 지표

| 지표 | 현재 | Phase F 완료 목표 |
|------|------|-------------------|
| auto_merge 성공률 (7일 윈도우) | **측정 불가** | ≥ 85% |
| failure_reason 커버리지 | "unknown" 포함 | 100% 구체 enum |
| 실패 알림 SLA (Telegram) | 즉시 | < 5초 |
| GitHub Issue 생성 (옵션) | 없음 | < 30초 |
| 대시보드 조회 latency (p95) | N/A | < 200ms |
| `branch_protection_blocked` 재발률 (F.5 후) | N/A | -50% |

---

## 🚦 권장 승인 경로

**Option A — Quick Win 5건만 먼저**: 소요 90분, 배포 리스크 최소화. 관측 없이 `unstable` 추가만으로도 일부 repo 실패율 개선 가능.

**Option B — Phase F.1 (관측) 까지**: 소요 1세션. 이후 실제 실패율 데이터 수집 후 F.2~F.5 우선순위 재조정.

**Option C — Phase F 전체**: 5세션. 가장 완결된 해결.

**Claude 권장**: **Option B** (Quick Win + F.1 관측). 이유:
- Quick Win 으로 즉각적 개선 효과 (특히 P0 unstable 버그)
- F.1 로 실제 데이터 수집 → F.2~F.5 우선순위를 데이터 기반으로 결정 가능
- "계획 없이 F.5 BPR 체크부터" 같은 헛수고 방지
- 사용자 대기 시간 최소화 (1세션)

---

## 관련 문서

- [Phase E 서비스 전환 결정](2026-04-23-phase-e-service-pivot-decision.md) — Path A 채택
- [Phase E 완결 5-렌즈 감사](2026-04-23-phase-e-quality-audit-5lens.md) — 91/100
- [STATE.md](../STATE.md) — 전체 상태

## 감사 메타데이터

- **실행 일자**: 2026-04-24
- **대상 커밋**: `fecfba0` (5-렌즈 Minor 후속 직후)
- **참여 에이전트**: 3개 병렬 독립 (A: Explore · B: Explore · C: Plan)
- **합의 방식**: 독립 조사 후 편집자(Claude) 가 교차 검증 + 종합
