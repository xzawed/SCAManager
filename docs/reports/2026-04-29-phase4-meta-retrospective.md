# Phase 4 메타 회고 — 작업 사이클 + 문서 정리 다각도 점검 (2026-04-29)

## 개요

Phase 4 Critical 테스트 갭 5 PR + NPE fix + 1차 문서 동기화가 모두 머지된 직후, 사용자 요청으로 **3-에이전트 다각도 교차 검증**을 수행해 누락된 문서 갱신 9건을 식별·수정한 작업의 메타 회고.

이 회고는 [Phase 4 1차 회고](2026-04-29-phase4-test-coverage-retrospective.md) 의 후속편이며, **"작업이 머지된 후의 문서 정리 주기"** 자체에 대한 학습을 정리한다.

---

## 수행 작업 (오늘 하루, 2026-04-29)

| 단계 | PR / 작업 | 결과 |
|----|----|----|
| 1 | PR #116 (PR-T1) — analyzer/tools + ai_review_errors + scorer_edges (+106) | 머지 |
| 2 | PR #117 (PR-T2) — engine/pipeline guards (+26) | 머지 |
| 3 | PR #118 (PR-T3) — merge_retry_service helpers (+16) | 머지 |
| 4 | PR #119 (PR-T4) — Tier 3 PR-A 시나리오 (+24) | 머지 |
| 5 | PR #120 (PR-T5) — E2E 통합 (+25) | 머지 |
| 6 | PR #122 — 1차 문서 동기화 (STATE/README/CLAUDE 수치) | 머지 |
| 7 | PR #123 — 회고 작성 + INDEX 갱신 | 머지 |
| 8 | PR #124 — `_loop_guard_check` head_commit=None NPE 방어 | 머지 |
| 9 | PR #125 — NPE fix 결과 STATE/회고 반영 | 머지 |
| 10 | **이 PR — 3-에이전트 교차 검증으로 식별한 누락 9건 + 메타 회고** | 진행 |

---

## 3-에이전트 교차 검증으로 발견된 누락 (이 PR 에서 일괄 처리)

| 에이전트 | 식별한 갭 | 수정 위치 |
|----|----|----|
| `doc-consistency-reviewer` | STATE.md 산수 갭 (1864→2036+172 vs 최종 1931, 차감 105건 미설명) | STATE.md 합계 표 아래 누적 산수 주의 박스 추가 |
| `doc-consistency-reviewer` | README 배지 1999 → 단위 1931 + 통합 72 = 2003 와 불일치 | README/README.ko 배지를 `1931_unit_+_72_integration` 으로 분리 표기 |
| `doc-consistency-reviewer` | CLAUDE.md "주의사항/파이프라인" 섹션에 head_commit=None 방어 규약 미추가 | CLAUDE.md 파이프라인 섹션 🔴 규약 추가 (PR #124 출처 명시) |
| `doc-consistency-reviewer` | STATE.md "주요 파일 역할" 표에 `src/webhook/loop_guard.py` 누락 | 표에 한 줄 추가 |
| `doc-consistency-reviewer` | `docs/guides/operational-verification.md:99` 매우 오래된 1074 stale | 동적 참조(STATE.md 헤더) 로 변경 |
| `doc-quality-reviewer` | PR-B3 평가 기준이 "신뢰성이 충분하면" 같은 모호한 표현 | STATE.md 그룹 53 § 잔여 후속에 정량 기준 4종 + 측정 SQL 쿼리 추가 |
| `general-purpose` | `.claude/agents/pipeline-reviewer.md:24` 점수 배점 stale (코드30+보안20+테스트10+커밋20+방향20) → 실제는 25+20+15+25+15 | 배점 + 등급 임계값 + constants.py 출처 명시로 갱신 |
| `general-purpose` | `.claude/agents/test-writer.md` 테스트 파일 명명 (`tests/test_<모듈>.py`) 가 Phase 4 의 `tests/unit/<영역>/` 계층과 불일치 + Phase 4 학습 mock 패턴 누락 | 명명 규칙 갱신 + Mock 전략 (settings 직접 patch / AsyncMock / 모듈 캐시 격리 / SQLite StaticPool) 4종 추가 |
| `general-purpose` | `docs/agents-index.md` 에 신규 에이전트 3종 미등재 + `merge_retry_service` 폐기 평가 미언급 | 에이전트 표에 doc 3종 추가, 신규 모듈 표에 PR-B3 폐기 평가 표기 |

---

## 잘 된 것

### 다각도 병렬 검증 패턴 — 단일 에이전트 대비 누락 발견율 ↑

3-에이전트 (`doc-consistency-reviewer` + `doc-quality-reviewer` + `general-purpose`) 를 병렬 디스패치한 결과:
- consistency-reviewer: 수치 정합성 + 트리 누락 5건
- quality-reviewer: 미래 결정 모호성 (PR-B3 정량 기준 부재) 1건 + 회고 일반화 부족 등
- general-purpose: 다른 에이전트가 보지 않는 `.claude/agents/` 와 `.claude/skills/` 영역 4건

**핵심**: 단일 에이전트가 봤다면 **`.claude/agents/pipeline-reviewer.md` 의 점수 배점 stale (Critical) 을 놓쳤을 가능성이 높다**. 미래 리뷰가 잘못된 기준 (코드 30점) 으로 판정해 합계 100점이 안 되는 PR 을 통과시킬 수 있는 사고 직전 갭이었다.

**교훈**: 큰 사이클 (5+ PR) 종료 후에는 반드시 다각도 검증 1회 — 한 명의 시각으로는 사각지대가 발생.

### NPE fix 가 회고에서 식별 → 별도 PR 분리 → 회고 갱신 사이클이 깔끔했다

PR-T5 (E2E 통합) 작성 중 발견한 `head_commit=None` NPE 를 즉시 수정하지 않고:
1. 테스트는 우회 (빈 dict 사용)
2. 1차 회고 §발견된 잔여 결함에 명시
3. 별도 PR #124 로 TDD (Red → Green) 사이클로 fix
4. PR #125 로 회고/STATE 갱신

**교훈**: 작업 중 발견한 부수적 결함은 같은 PR 에 묶지 말고 회고에 기록 → 별도 PR 로 분리. 머지 후 회고를 다시 갱신 (PR #125 패턴) 하면 stale 표기 방지.

### CLAUDE.md "완료 시 필수 5-step" 이 누락 방지에 효과적이었다

매 PR 마다 ① 커밋 → ② PR 생성 → ③ push → ④ STATE.md 갱신 → ⑤ CLAUDE.md 동기화 — 9개 PR 시리즈 전반에 걸쳐 이 체크리스트를 반복 적용. 그러나:
- 5-step 은 **수치** 갱신을 강제하지만, **stale 참조 sweep** 까지는 강제하지 않는다.
- 이 메타 회고에서 발견된 9건 중 6건이 "다른 문서에서 같은 사실을 언급하는데 갱신 누락" 패턴 → **5-step 만으로 부족함**.

**개선 제안**: 5-step 에 ⑥ "관련 문서 grep sweep" 추가 — 큰 사이클 (3+ PR) 종료 시 적용.

---

## 어려웠던 것

### `pipeline-reviewer.md` 점수 배점 stale 이 오랫동안 발견되지 않은 이유

- 점수 체계가 Phase E 또는 그 이전에 변경됐는데 (`src/constants.py` 의 `CODE_QUALITY_MAX=25`, `AI_REVIEW_MAX=25` 등), 에이전트 정의 파일은 그대로 남아있었다.
- `pipeline-reviewer` 에이전트는 자주 호출되지 않으므로 (파이프라인 변경 시에만), 잘못된 배점으로 리뷰가 수행됐어도 결과가 사용자에게 노출될 기회가 적었다.
- CLAUDE.md "src/ 트리" 와 "주의사항" 은 갱신했지만 `.claude/agents/` 내부는 제외 → 시야 사각지대.

**교훈**: `.claude/agents/` 와 `.claude/skills/` 도 정기 검증 대상 (분기 1회 또는 큰 Phase 완료 시).

### "+197 vs 1931" 산수 갭 — 회고와 STATE 두 군데에 다른 설명이 있었다

회고는 "다른 PR 정리분 차감 +67" 으로 일반 표기, STATE 는 "+197" 만 표기. 미래 Claude 가 baseline 으로 1864/1931/2036 중 어느 것을 잡아야 할지 혼란.

**해결**: STATE.md 합계 표 아래에 단일 출처 (1931) + 차감 사유 + +197 의 의미 (신규 추가 카운트) 명시.

### PR-B3 평가 기준 정량화 부재가 가장 위험한 발견이었다

`doc-quality-reviewer` 가 식별: "신뢰성이 충분하면" 같은 모호 표현은 미래 Claude 가 **표면적 판단으로 ~500줄 코드를 성급히 제거** 할 수 있는 위험. 1주일 후 평가 시점에 기준이 없으면 잘못된 결정 위험.

**해결**: 4개 정량 기준 (도달률 ≥ 95%, 평균 latency ≤ 30분, disabled_externally ≤ 5건/주, REST 폴백 ≤ 10%) + 측정 SQL 쿼리 + 합격선을 STATE.md 그룹 53 § 잔여 후속에 추가.

---

## 다음 단계

### PR-B3 평가 (~2026-05-06)

이 회고에서 추가한 정량 기준 4종을 사용. 평가는 다음 SQL 결과를 토대로:

```sql
-- 도달률
SELECT 100.0 * COUNT(*) FILTER (WHERE state='actually_merged')
  / NULLIF(COUNT(*) FILTER (WHERE state IN ('actually_merged','enabled_pending_merge','disabled_externally')), 0)
  AS reach_pct
FROM merge_attempts
WHERE enabled_at > NOW() - INTERVAL '7 days';

-- 평균 latency (분)
SELECT AVG(EXTRACT(EPOCH FROM (merged_at - enabled_at)) / 60.0)
  AS avg_latency_minutes
FROM merge_attempts
WHERE state='actually_merged' AND enabled_at > NOW() - INTERVAL '7 days';

-- disabled_externally / REST 폴백 비율
SELECT
  COUNT(*) FILTER (WHERE state='disabled_externally') AS disabled_count,
  COUNT(*) FILTER (WHERE state='direct_merged') AS rest_fallback_count,
  COUNT(*) AS total_count
FROM merge_attempts
WHERE enabled_at > NOW() - INTERVAL '7 days';
```

### 메타 회고 패턴을 다른 사이클에도 적용

이번에 정착시킨 "큰 사이클 종료 → 3-에이전트 병렬 검증 → 누락 일괄 수정 → 메타 회고" 패턴은 다음 대형 작업 (예: PR-B3 또는 새 Phase) 에서도 동일하게 사용. 사이클당 누락 검출 5-10건 예상.

---

## 수치 요약

| 영역 | Phase 4 시작 | 메타 회고 종료 | 증감 |
|------|----|----|----|
| 단위 테스트 | 1864 | **1931** | +67 (신규 +172, 정리분 -105) |
| 통합 테스트 | 47 | **72** | +25 |
| E2E | 53 | 53 | 0 |
| pylint | 10.00 | 10.00 | 0 |
| bandit HIGH | 0 | 0 | 0 |
| SonarCloud QG | OK | OK | OK 10연속 |
| src/ 결함 fix | - | 1건 (head_commit=None NPE) | - |
| 누락 문서 갱신 (메타 회고) | - | **9건** | - |

---

## 회고 요약

**Phase 4 본 작업 (5 PR + NPE fix + 1차 문서 동기화) 은 무사고 완료**.
**그 후 3-에이전트 다각도 검증으로 누락 9건을 추가 발견 — 한 시각만으로는 부족**.
**가장 위험했던 것은 `pipeline-reviewer.md` 점수 배점 stale (Critical) — 미래 리뷰 사고 직전 차단**.
**미래 Claude 를 위해 PR-B3 정량 평가 기준 + measurement SQL 명시 — 평가 시 합격선 기반 결정 가능**.

다음 액션: PR-B3 평가 시점 (~2026-05-06) 까지 대기 + 메타 회고 패턴을 다음 사이클에도 적용.
