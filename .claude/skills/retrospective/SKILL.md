---
name: retrospective
description: 5+1 다중 에이전트 회고 실행 (정책 8) — loop-until-dry + 전건 cross-verify
---

## 절차
1. 범위는 기계에서 얻는다 — **디스패치 직전** 실행, 손 조립 금지:

   ```bash
   py -3 scripts/retro_scope.py --json
   ```
   출력을 `context`/`scope` 에 그대로 넣는다.
2. `Workflow({ scriptPath: '<repo-abs>/.claude/workflows/retrospective.mjs', args: { scope, context, domains? } })` — 절대경로 필수. `area=<관점>` → `domains` ∈ process/code/docs/decision/tooling.
3. 반환 `{rounds, findings_total, verdict_coverage, confirmed[], unverified_findings[], scope_drift_during_run, roi}` → `docs/reports/YYYY-MM-DD-retrospective.md` (P0/P1/P2 + ROI 표). `verdict_coverage < 1.0` → 재실행/수동 확인.
4. fix 는 사용자 결정 — 자동 수정 금지.

## 규율
- 5+1(내부 self-verify)과 opus 적대 리뷰는 2-layer 독립 — 상호 생략 금지.
- cross-verify 생략은 1차 P0 ≥ 8 + 5 관점 모두 P0 ≥ 1 + 사용자 빠른 진행 신호 AND 시만.
- 직후 정책 9 자유 발언 4 섹션 + 회고 질문. 단일 작업일 dispatch ≥ 5회 = 사전 확인.
- 실행 전 예상 비용 1줄 보고.
