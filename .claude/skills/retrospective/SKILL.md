---
name: retrospective
description: 5+1 다중 에이전트 회고 실행 (정책 8) — loop-until-dry + 전건 cross-verify
---

## 절차
1. 범위는 기계에서 얻는다 — **디스패치 직전** 실행, 손 조립 금지:

   ```bash
   py -3 scripts/retro_scope.py --json
   ```
   출력을 `context` 로 넘긴다. `unmeasured` 가 남으면 그 축은 안 쟀다(`head-not-main` → `main` 에서).
   `records_expired_prs` = 세션 기록이 없을 수 있는 PR — 본문 · 커밋으로만 대조.
   `ok:false` 면 직전 회고 경계 SHA 를 주고 다시:
   `py -3 scripts/retro_scope.py --json --since <sha>`
   회고는 전용 워크트리(`git worktree add <경로> origin/main`)에서 돌린다 — 다른 세션 · 에이전트와 작업 트리를
   나누면 실측이 섞인다.
2. `Workflow({ scriptPath: '<repo-abs>/.claude/workflows/retrospective.mjs', args: { scope, context, domains? } })` — 절대경로 필수. `area=<관점>` → `domains` ∈ process/code/docs/decision/tooling.
3. 반환 `{rounds, findings_total, verdict_coverage, confirmed[], unverified_findings[], scope_drift_during_run, roi}` → `docs/reports/YYYY-MM-DD-retrospective.md` (P0/P1/P2 · ROI · `false_positives` 표). 첫 표에 분석 종료 `head`(main SHA)를 적는다. `verdict_coverage < 1.0` → 재실행/수동 확인. ROI 표에 1단계 출력의 `claim_review`(창의 claim-review 반증률)를 옮긴다 — `null` 이면 «안 쟀다».
4. 확정 목록은 `[WBS]` Issue 하나로 등재한다. fix 는 사용자 결정(자동 수정 금지).
   - 처리 순서는 사용자가 정한다 — «문서 · 절차는 맨 뒤» 같은 부류 정렬을 기본으로 두지 않는다(그 정렬이 절차 묶음을
     한 번도 닫지 못했다). 다음 할 일은 Issue 머리의 «다음» 줄이 갖는다 — 메모리에만 두지 않는다.
   - 결정 질문은 권장안을 먼저 원장에 적고 묻는다. «권장안대로» 같은 포괄 답은 그때 원장에 적힌 권장안에만 적용하고,
     답은 원문 그대로 항목의 결정 줄에 남긴다(민감한 결정은 «내용은 작성자 메모» 로만).
   - P0 를 «채널»(명령 · 도구의 꼴)로 확정한 날, 그 채널을 막는 임시 deny(훅 한 줄)를 원장 첫 결정 질문으로 올린다 —
     권장안 = 본 수정보다 먼저 넣는다. 본 수정이 올 때까지 그 채널이 열려 있지 않게 한다.
   - 항목을 닫기 전 · 회고 착수 전, 머지된 PR 본문의 «원장 … P#-##» 참조와 체크 상태를 대조한다 — 해소를 적은 PR 이
     있는데 미체크면 체크하고, 체크인데 해소 PR 이 없으면 근거를 적는다.

## 규율
- 5+1(내부 self-verify)과 opus 적대 리뷰는 2-layer 독립 — 상호 생략 금지.
- cross-verify 생략은 1차 P0 ≥ 8 + 5 관점 모두 P0 ≥ 1 + 사용자 빠른 진행 신호 AND 시만.
- 단일 작업일 dispatch ≥ 5회 = 사전 확인.
- 실행 전 예상 비용 1줄 보고.
