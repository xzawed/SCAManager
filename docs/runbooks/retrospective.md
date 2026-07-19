# 회고 워크플로우 운영 가이드 (retrospective.mjs)

> 정책 8 (5+1 다중 에이전트 회고)의 결정론적 코드화. 진입점 스킬 = [`/retrospective`](../../.claude/skills/retrospective.md),
> 실행 엔진 = [`.claude/workflows/retrospective.mjs`](../../.claude/workflows/retrospective.mjs) (PR-W W3 신설).
> peer = [`/integrity-audit`](integrity-audit.md) (정합성 감사). 두 워크플로우는 loop-until-dry 정본
> [`_lib/loop-until-dry.template.mjs`](../../.claude/workflows/_lib/loop-until-dry.template.mjs)을 인라인 공유
> (drift 가드: `tests/unit/scripts/test_workflow_loop_sync.py`).

## 목적
직전 세션/사이클을 5 관점(process·code·docs·decision·tooling)으로 회고 — loop-until-dry finder +
completeness critic + **cross-verify=finding 강제**(모든 finding 이 verdict 수신 → 단일 패스 회고의
"13건 중 8건만 검증" 한계 해소). read-only 분석 — 코드/문서 수정은 호출자/사용자 책임.

## 실행
워크플로우는 명명 레지스트리 미등록(빌트인 아님) → **`scriptPath` 절대경로 호출**:
```
Workflow({ scriptPath: '<repo-abs>/.claude/workflows/retrospective.mjs',
           args: { scope: 'session', context: '<머지 커밋·PR·범위>', domains?: [...] } })
```
- `scope`: 'session'(기본) — 직전 세션 전체.
- `context`: 머지 커밋 SHA·PR 번호·작업 범위 문자열 (finder/verify 프롬프트로 전달 — 충실할수록 정확).

> 🔴 **범위는 손으로 적지 말 것 — 착수 직전에 기계 산출한다 (2026-07-19 회고 P0-2)**
>
> ```bash
> python scripts/retro_scope.py          # 사람이 읽는 요약
> python scripts/retro_scope.py --json   # context 에 넣을 값
> ```
>
> **왜**: 정책 8 진화 (5)를 신설한 세션이 **첫 적용에서 자기 산출물 2건을 누락**했다.
> 범위를 손으로 `#1108~#1129` 라 적었고, 회고 착수 직전 머지된 `#1130`·`#1131` 이 빠졌다.
> 누락된 2건은 세션에서 **가장 마지막에 머지된 = 검증이 가장 덜 된** 산출물이다 —
> 정책이 막으려던 시나리오("가장 검증이 덜 된 코드가 회고를 피해간다")가 정책 신설 당일 발생했다.
>
> 🔴 이건 주의력 문제가 아니다. **범위를 적는 시점과 회고가 시작되는 시점이 다른 한 구조적으로
> 반복**된다. `retro_scope.py` 는 호출 시점의 `HEAD` 를 보므로 그 창을 없앤다.
> 경계 판정은 `check_retro_cadence.newest_retro` 를 **공유**한다 — 각자 구현하면 카운터와
> 회고 범위가 서로 다른 회고를 최신으로 골라 어긋난다(실제로 같은 날 회고 tie-break 버그가 있었다).
- `domains`(선택): 부분 회고 시 `['process','code',...]` (생략 = 5 관점 전체).
- `dryRun: true`: 에이전트 0 — 관점 resolve 만 확인하는 smoke.

## 반환 스키마
```
{ scope, rounds, findings_total, verdict_coverage,
  confirmed: [{domain, severity, adjusted_severity, title, file, line, claim, evidence, citation_verified, recommendation, verdict, reason}],
  unverified_findings: [{domain, severity, title}],
  roi: { fp_blocked, confirmed, severity_adjusted, p0, p1, p2 } }
```
- **verdict**: `CONFIRMED`(실제 결함/개선) · `FALSE_POSITIVE`(차단) · `SEVERITY_ADJUST`(adjusted_severity) · `UNVERIFIED`(재시도 3회 소진).
- 보고서 작성: `docs/_archive/reports/YYYY-MM-DD-retrospective.md` (ROI + verdict_coverage + 클러스터). **아카이브는 6-step 의무**(회고 P1 #39 = 미아카이브 반복 근본).

## verdict_coverage 해석
- `1.0` = 모든 finding 이 verdict 수신(목표). 단일 패스 13/8 한계 해소 입증.
- `< 1.0` = UNVERIFIED 존재(고동시성 StructuredOutput 누락 등) → 재실행 또는 수동 확인 권고. 보고서에 unverified 별도 표 노출.

## 비용 · 거버넌스
- 5 관점 × 다라운드(loop-until-dry, MAX_ROUNDS budget 시 5 / 미설정 3) + 전건 cross-verify = 다수 에이전트
  (2026-06-23 첫 실행 = 85 에이전트·~7.2M 토큰·3 라운드). **실행 전 예상 비용 1줄 보고**(정책 16#5).
- 5+1(내부 self-verify, 관점 다양성) ↔ `pipeline-reviewer`/opus whole-branch 적대 리뷰(리뷰 계층 다양성) = **2-layer 독립** — 한쪽으로 다른 쪽 생략 금지. (구 외부 LLM mutual = 정책 18, 2026-07-10 폐기.)
- cross-verify(6차) 생략 정량 기준(정책 8 진화): 1차 P0 ≥ 8 + 5 관점 모두 P0 ≥ 1 + 사용자 빠른 진행 신호 — **3 조건 AND** 시만.
- 회고 종합 직후 **자유 발언(정책 9, 4 섹션)** + **회고 질문(사용자 회신 의무)** 별도 수행(워크플로우 스키마 밖).
- **fix 는 사용자 결정**(정책 7 PR 단위 / 15 사전 사고) — 자동 수정 금지.

## 알려진 한계 (2026-06-23 첫 dogfooding → C10 일부 해소)
- ✅ **completeness 라운드 회복력**(C10): try/catch 격리 — API 일시 오류 시 gap 라운드만 건너뛰고 본체 회고·Report 는 보존(이전엔 전체 소실 위험). 단 gap 라운드 자체는 미수행(best-effort).
- ✅ **evidence·citation_verified 환류**(C10): 최종 confirmed 출력에 포함(보고서 추적성 복원, 이전엔 소실). adjusted_severity 도 명시 노출.
- ✅ **verdict_coverage < 1.0 자동 보강**(C10-d): UNVERIFIED finding 만 1회 bounded 재검증(고동시성 StructuredOutput flake 해소) — 토큰 비용 최소(소수 한정). 1회 후에도 UNVERIFIED 면 보고서 unverified 표 노출(현행).
- ⚠️ SEVERITY_ADJUST 시 adjusted_severity 미수신이면 count 가 원 severity 로 graceful fallback — 스키마 강제(if/then) 미적용(백로그 C10-c, 검증기 스키마 위험 회피).
- 자유 발언·회고 질문·cross-verify 생략 정량 표는 워크플로우 출력 밖 = 스킬/Claude 절차 의존.
- 회귀 가드: `tests/unit/scripts/test_retrospective_resilience.py` (try/catch + evidence 출력, 주석 false-pass 봉인). 추적: [`docs/_archive/reports/2026-06-23-retrospective.md`](../_archive/reports/2026-06-23-retrospective.md) §C10.
