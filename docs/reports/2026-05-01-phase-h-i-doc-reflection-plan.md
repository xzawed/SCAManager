# Phase H+I 문서 반영 세부 계획서 (2026-05-01)

## 개요

Phase H+I 16 PR 머지 후 4개 에이전트 (`doc-consistency-reviewer`, `doc-quality-reviewer`, `general-purpose`, `doc-impact-analyzer`) 가 병렬 검증한 결과를 종합한 문서 반영 세부 계획서.

총 식별 항목 22개를 우선순위별로 분류 + 작업량 + 위험도 명시. 사용자 승인 후 단일 PR 또는 분할 PR 로 진행.

---

## 4-에이전트 종합 결과

| 에이전트 | 핵심 발견 |
|----|----|
| `doc-consistency-reviewer` | 정합성 위반 6건 (V1-V6) + 누락 갱신 2건 (M1-M2) |
| `doc-quality-reviewer` | 즉시 보완 5건 + 미래 위험 3건 |
| `general-purpose` | 갱신 필수 8건 + 권장 5건 |
| `doc-impact-analyzer` | CLAUDE.md 주의사항 5 카테고리 + 에이전트 정의 3건 + 행동 변경 위험 2건 |

**중복 제거 후 unique 항목 22개**.

---

## 우선순위 분류

### 🟡 A. 정합성 명확화 (회귀 위험 0, 단순 framing) — 1건

> **Round 3 보강**: 양쪽 검증 에이전트가 A1 = 🔴 즉시 수정 등급은 부적절 (회귀 위험 0) → 🟡 정합성으로 강등. A2 는 작업 0 → §검증 완료 섹션으로 분리.

| # | 항목 | 위치 | 작업 |
|---|----|----|----|
| A1 | "15 PR (Phase H+I)" 카운트 명확화 — 사용자 인식 "16 PR" 은 회고 PR 1건 포함 시 | CLAUDE.md L566, STATE.md L5/L9, 회고 도입부 | "15 PR (Phase H+I) + 회고 동기화 1 PR = 16 PR 머지" 1줄 명시 |

### ✅ 검증 완료 (작업 0)

- **active_db 잔존**: doc-impact-analyzer 가 false positive 식별 — PR-5B 에서 이미 정정 완료. CLAUDE.md L312 ("의도적으로 미노출") + STATE.md L97 (보안 결정 보존). grep 결과 0.

### 🟡 B. 정합성 갱신 (반드시 추가) — 7건

> **Round 3 보강**: B1 작업량 ~30줄 → ~45줄/45분으로 상향 (5 카테고리 × 평균 8줄 + 5xx 재시도 "신뢰 API 한정" 범위 제한 명시). E4 재분류 → B7 로 이동 (CLAUDE.md 본문 추가, docstring 아님).

| # | 항목 | 위치 | 작업량 |
|---|----|----|----|
| B1 | CLAUDE.md "주의사항" 섹션 신규 규약 5 카테고리 | CLAUDE.md `### 주의사항 카테고리별` | API/알림 / 보안 / DB / 테스트 / 파이프라인 5곳 추가 (~45줄, 45분). **5xx 재시도는 "신뢰 API (GitHub/Telegram/Anthropic/Railway) 한정" 범위 제한 필수** |
| B2 | CLAUDE.md "src/ 트리" — `find_by_full_name_with_owner` 명시 | CLAUDE.md `repositories/` 라인 | 1 줄 |
| B3 | STATE.md "주요 파일 역할" 표 — `find_by_full_name_with_owner` 명시 | STATE.md L42 부근 | 1 행 보강 |
| B4 | STATE.md 그룹 54 — alembic 0023/0024 + 인덱스명 3종 + C5/C6 처리 사유 명시 | STATE.md 그룹 54 PR 표 | 4-5 줄 보강 |
| B5 | STATE.md "잔여 과제" 섹션 — PR-3B-2 / PR-5A-2 항목 등재 | STATE.md L1024 부근 | 2 행 추가 |
| B6 | agents-index.md — Phase H+I 신규 함수/패턴 등재 + 갱신일 | docs/agents-index.md | 새 섹션 + 갱신일 |
| **B7** | **C7 cascade 일관성 매트릭스 (E4 재분류)** | CLAUDE.md "DB / 마이그레이션" 섹션 | 4개 child 모델 ondelete 정책 표 — docstring 아닌 본문 추가 |

### 🟢 C. 에이전트 정의 갱신 (학습 코드화) — 3건

| # | 항목 | 위치 | 작업 |
|---|----|----|----|
| C1 | `test-writer.md` — 신규 mock 패턴 4종 | `.claude/agents/test-writer.md` | asyncio.to_thread spy / asyncio.sleep patch / PARITY GUARD / HMAC scope 격리 |
| C2 | `pipeline-reviewer.md` — 신규 검토 항목 4종 | `.claude/agents/pipeline-reviewer.md` | async/sync 경계 / gather 패턴 / PARITY GUARD docstring / composite index 활용 |
| C3 | `doc-consistency-reviewer.md` — ORM-마이그레이션 sync 검증 | `.claude/agents/doc-consistency-reviewer.md` | `__table_args__` ↔ alembic 양방향 sync 추가 |

### 🔵 D. 운영 가이드 갱신 — 2건

| # | 항목 | 위치 | 작업 |
|---|----|----|----|
| D1 | `merge-retry.md` — Phase H+I 운영 영향 4건 | `docs/runbooks/merge-retry.md` | race-recovery / 인덱스 / cascade / GraphQL retry 영향 |
| D2 | `env-vars.md` — 신규 모듈 상수 (참고) | `docs/reference/env-vars.md` | TELEGRAM_RETRY_AFTER_MAX_SECONDS / _GRAPHQL_MAX_ATTEMPTS / _GRAPHQL_INITIAL_BACKOFF_SECONDS |

### 🟣 E. 도구 docstring 강화 — 3건

> **Round 3 보강**: E4 (cascade 매트릭스) 는 docstring 이 아닌 CLAUDE.md 본문 → B7 로 재분류. E2 는 양쪽 모듈 (engine.py + merge_retry_service.py) 동시 수정 = 2 파일.

| # | 항목 | 위치 | 작업 |
|---|----|----|----|
| E1 | `find_by_full_name_with_owner` docstring — 호출처 6곳 명시 | src/repositories/repository_repo.py | 마이그레이션 후보 grep 결과 인라인 |
| E2 | `_get_ci_status_safe` parity guard — patch 경로 마이그레이션 명시 (2 파일) | src/gate/engine.py + src/services/merge_retry_service.py | PR-5A-2 진행 시 patch 경로 변경 안내 |
| E3 | `_GRAPHQL_MAX_ATTEMPTS` — 다른 채널 재사용 힌트 | src/github_client/graphql.py | `src/shared/retry_helper.py` 통합 검토 힌트 |

### ⚪ F. 회고 본문 강화 — 2건

| # | 항목 | 위치 | 작업 |
|---|----|----|----|
| F1 | PR-5C functional bug 운영 영향 강조 | docs/reports/2026-05-01-phase-h-i-completion-retrospective.md | 본문 § 핵심 발견에 "이전 모든 semi-auto 콜백 401" 표시 보강 |
| F2 | C7 cascade 일관성 매트릭스 단일 출처 위치 명시 | 동일 회고 § 어려웠던 것 | E4 위치 (CLAUDE.md DB 섹션) 인용 |

### ⚫ G. 부수 발견 (Phase H+I 무관, 별도 PR 권장) — 3건

| # | 항목 | 사유 |
|---|----|----|
| G1 | `.claude/skills/test.md` Windows 경로 stale | Phase H+I 무관, 별도 chore PR |
| G2 | `.claude/skills/lint.md` 점수 환산 stale | 동일 |
| G3 | `.claude/skills/webhook-test.md` check_suite 누락 | Phase 12 후속, 별도 PR |

---

## 통합 작업량 추정

| 카테고리 | 항목 수 | 예상 시간 | src 변경 |
|----|----|----|----|
| 🔴 A 즉시 수정 | 2 | 5분 | 0줄 |
| 🟡 B 정합성 갱신 | 6 | 30분 | 0줄 (docs 만) |
| 🟢 C 에이전트 정의 | 3 | 20분 | 0줄 |
| 🔵 D 운영 가이드 | 2 | 25분 | 0줄 |
| 🟣 E 도구 docstring | 4 | 15분 | 4줄 (docstring 만) |
| ⚪ F 회고 강화 | 2 | 10분 | 0줄 |
| ⚫ G 부수 | 3 | 별도 PR | - |
| **합계 (A-F)** | **19** | **~2시간** | **~4줄** |

---

## PR 분할 전략

> **Round 3 결정**: 두 검증 에이전트 모두 Option 3 (2분할) 권장 — 정합성 (B/E4=B7) 과 에이전트 정의 (C) 의 회귀 검증 방식이 다르므로 분리.

### Option 3 — 2분할 PR (양쪽 에이전트 합의 — 채택)

**PR-α: 정합성 통합** (~50분, src 0줄)
- A1 (1건 — framing 정정)
- B1-B7 (7건 — 정합성 갱신, B7 = 재분류된 cascade 매트릭스)
- 검증: `make test-isolated` + grep 정합성

**PR-β: 가이드 + docstring + 에이전트** (~70분, src ~3줄)
- C1-C3 (3건 — 에이전트 정의)
- D1-D2 (2건 — 운영 가이드)
- E1-E3 (3건 — docstring 강화, src ~3줄)
- F1-F2 (2건 — 회고 강화)
- 검증: `make test-isolated` + 에이전트 호출 sanity check

**PR-γ (별도, 추후)**: G1-G3 (3건 — Phase H+I 무관 부수)

### 채택 이유
- 정합성 갱신 (B) 과 에이전트 정의 변경 (C) 의 회귀 검증 방식이 상이 (B=grep/diff, C=실제 에이전트 호출)
- PR-α 머지 직후 단일 진실 소스 즉시 확보 (PR-β 진행 중에도 일관)
- src 변경이 PR-β 에 한정 (PR-α 는 docs 만 → 회귀 위험 0)

---

## 위험 평가

> **Round 3 보강**: 검증 에이전트가 추가 위험 3건 식별 — 마지막 3행 추가.

| 위험 | 확률 | 영향 | 완화책 |
|----|----|----|----|
| docstring 변경이 다른 mock 패턴 깨뜨림 | 매우 낮음 | 낮음 | 변경 후 `make test-isolated` 검증 |
| CLAUDE.md "주의사항" 추가가 미래 PR 거부 유발 | 중간 | 중간 | 5xx 재시도는 "신뢰 API 한정" 으로 범위 제한 명시 (도구 분석가 식별) |
| agents-index.md 갱신이 다른 에이전트 호출 영향 | 매우 낮음 | 낮음 | grep 으로 호출 패턴 확인 |
| 회고 갱신이 머지된 회고와 충돌 | 0 | 0 | append-only 갱신 |
| **B1 5 카테고리 추가가 CLAUDE.md 토큰 예산 압박** | 낮음 | 중간 | 각 카테고리 최소화 (~8줄/카테고리), 중복 규약 통합 |
| **C1-C3 에이전트 정의 변경이 호출 결과 변동** | 낮음 | 낮음 | 변경 후 `Agent` 호출 1회 sanity check (PR-β 단계) |
| **E2 양쪽 모듈 (engine + merge_retry_service) 동시 수정 누락** | 매우 낮음 | 중간 | parity 회귀 가드 테스트 (PR-5A 의 8 tests) 자동 검증 |

---

## 실행 단계 제안

1. **이 계획서 머지** (현재 PR — 작업 근거 + 검증 결과 보존)
2. **사용자 승인 대기** — Option 1 vs Option 2 선택
3. **선택된 옵션 진행** — TDD 사이클 적용 (각 변경에 회귀 가드 검증)
4. **머지 후** — STATE.md / CLAUDE.md / 회고 메타 정보 갱신

---

## 사용자 결정 — 채택 완료 (2026-05-01)

| 결정 | 선택 |
|----|----|
| 진행 옵션 | **Option 3 (2분할)** |
| B1 텍스트 검토 시점 | 작업 진행 후 PR 단계에서 검토 |
| 부수 G 처리 | **PR-γ 로 별도 분리** (Phase H+I 무관) |

---

## 실행 상태

- ✅ Round 1: 4-에이전트 병렬 검증 완료
- ✅ Round 2: 본 계획서 작성 + 2-에이전트 보강 검증 완료
- 🚧 PR-α: 본 계획서 보강 + 정합성 통합 진행 중 (현재 PR)
- ⏳ PR-β: PR-α 머지 후 진행
- ⏳ PR-γ: 추후 별도
