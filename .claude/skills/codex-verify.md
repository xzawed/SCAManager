---
name: codex-verify
description: 정책 18 push 전 Codex mutual 검증 표준 흐름 — 브랜치 diff → codex-rescue ground-truth → OK 후 push / Codex 다운 시 자체검증 분기
---

로컬 commit 후 **push 전** Codex 상호 검증(정책 18)을 결정론화한다.
양방향 대칭: Claude 작업(로컬 commit) → Codex 검증 → **OK 후 push**. push 전 단독 완료 금지.

## 실행 절차
1. **로컬 commit 완료 확인** — 아직 `git push` 금지 (정책 18 §1·§2).
2. **codex-rescue 에이전트 디스패치** — ground-truth 프롬프트 작성:
   - **self-contained**: diff 인라인 금지(길이 한도) → `git -C <repo-abs> show <sha>` / `cat` 직접 지시.
   - 검증 항목 명시: 동작 불변 / 로직 정확성 / 회귀 없음 / 카운트·docs 정합.
   - **"추측 금지 — 실제 git/grep/pytest 명령으로 확인"** 강제.
   - 출력 강제: `VERDICT: OK|NG` + NG 시 file:line 근거 + (**설계방향 NG vs 단일정답 버그** 구분).
3. **OK 회신 → push**. NG 회신 → 정책 18 §3 **2-tier**:
   - (a) 설계방향·트레이드오프 동반 NG → 자율 수정 금지 → 사유 분석 + 수정 plan 옵션 표(정책 1) + 사용자 confirm.
   - (b) 단일 정답 버그/회귀 NG(객관 정답 1개·트레이드오프 없음) → 동일 PR 즉시 수정 후 재검증, 옵션 표 면제.
   - 판별 애매 시 (a) 보수 처리. **NG 회기 ≤ 3회** — 4회차 = 사용자 직접 결정 escalation.
4. 응답에 **"🔍 Codex 검증 의뢰 (push 전)" 1줄** + 결과 명시. push 후 PR 본문 `## 🔍 Codex 검증 의뢰 (push 전, 정책 18)` 섹션 기록.

## Codex 다운 감지 시 분기 (정책 18 예외)
`codex exec` 가 샌드박스/spawn 오류(spawn_agent 400 · python 차단 등)로 검증 불가 시:
- **사용자 사전 승인** 후 Claude 다중 수단 자체검증으로 대체:
  pylint + flake8 + TDD RED→GREEN + 라이브 실측(curl / dryRun) + python re·grep 실측.
- PR 본문에 "Codex 다운 → 정책 18 예외(자체검증)" + 대체 증거 명시.
- **부분 차단**(Codex 가 정적은 OK, 실행은 차단) 시: 검증된 항목 OK + 미검증 항목은 Claude 로컬 실증으로 보완 명시(NG 아님).

## 주의
- **push 전 OK 의무**: OK 회신 받기 전 `git push` 금지. 누락 시 다음 응답 회복(정책 1 진화 회귀 가드 페어).
- mutual **면제 영역**: 사용자 "생략 OK" 명시 · read-only 보고 · 메모리 grep · 사용자 직접 결정 영역.
- 5+1(정책 8 내부 self-verify) ↔ mutual(외부 LLM) = **2-layer 독립** — "Codex OK 받았으니 5+1 6차 생략" 오해 금지.
- 참고: `feedback-codex-post-validation-mandatory`(push 후 의뢰 안티패턴) · 정책 18 상세 `.claude/policies/active.md#정책-18`.
