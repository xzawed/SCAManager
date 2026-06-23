---
name: retrospective
description: 5+1 다중 에이전트 회고 실행 (정책 8) — retrospective.mjs 워크플로우 loop-until-dry + 전건 cross-verify, 회고 보고서 작성
---

`.claude/workflows/retrospective.mjs` 워크플로우를 실행하고 결과를 회고 보고서로 작성한다.
정책 8 (5+1 다중 에이전트 회고)의 결정론적 코드화 — 5 관점 finder loop-until-dry +
completeness critic + **cross-verify=finding 강제**(모든 finding 이 verdict 수신, 단일 패스 13/8 한계 해소).

## 인자 해석
- `/retrospective` → 직전 세션 전체 회고. `args: { scope: 'session', context: '<머지 커밋·PR·범위>' }`
- `/retrospective area=<관점>` → 특정 관점만. `args: { domains: [...] }` (∈ process / code / docs / decision / tooling)
- `context` 에 머지 커밋 SHA·PR 번호·작업 범위 주입 (finder/verify 프롬프트로 전달).

## 실행 절차
1. 세션 컨텍스트 수집: `git log --oneline <baseline>..HEAD` + 머지 PR 목록 → `context` 문자열.
2. 워크플로우 호출 — **`scriptPath` 절대경로 필수** (빌트인 아님 → `name` 해소 안 됨):
   `Workflow({ scriptPath: '<repo-abs>/.claude/workflows/retrospective.mjs', args: { scope, context, domains? } })`
3. 반환 `{ scope, rounds, findings_total, verdict_coverage, confirmed[], unverified_findings[], roi }` 를
   `docs/_archive/reports/YYYY-MM-DD-retrospective.md` 로 작성 (P0/P1/P2 + ROI + verdict_coverage 표).
4. ROI(P0/P1/P2 + fp_blocked + severity_adjusted) + verdict_coverage 보고.
   **fix 는 사용자 결정(정책 7 PR 단위 / 15 사전 사고 / 18 Codex mutual) — 자동 수정 금지.**

> 🔴 `verdict_coverage < 1.0` = 일부 finding 이 verdict 미수신(UNVERIFIED). 단일 패스 회고의 13/8
> 한계 재발 신호 — 재실행 또는 수동 확인 권고 (리포트에 unverified 별도 표 노출).

## 정책 8 / 거버넌스
- 5+1 = **내부 self-verify**(관점 다양성). 외부 LLM mutual(정책 18)과 **2-layer 독립** — 한쪽으로 다른 쪽 생략 금지.
- cross-verify(6차) 생략 정량 기준(정책 8 진화): 1차 P0 합계 ≥ 8 + 5 관점 모두 P0 ≥ 1 + 사용자 빠른 진행 신호 — **3 조건 AND 시만** 생략 OK.
- 회고 종합 보고 직후 **자유 발언(정책 9, 4 섹션)** + **회고 질문(사용자 회신 의무)** 별도 수행.
- 단일 작업일 5+1 dispatch ≥ 5회 = 사용자 사전 확인(정책 8 진화).

## 비용
- 5 관점 × 다라운드(loop-until-dry, MAX_ROUNDS budget 시 5 / 미설정 3) + 전건 cross-verify = 다수 에이전트.
  **실행 전 예상 비용 1줄 보고**(정책 16#5).
- **스킬 미인식 시 인라인 대체**: 위 2단계 `Workflow({scriptPath, args})` 직접 호출 + 3~4단계 수동 수행.

> 연계: `.claude/workflows/retrospective.mjs`(PR-W W3) 가 실행 엔진, 본 스킬이 진입점. loop-until-dry 정본 =
> `.claude/workflows/_lib/loop-until-dry.template.mjs` (drift 가드: `tests/unit/scripts/test_workflow_loop_sync.py`).
