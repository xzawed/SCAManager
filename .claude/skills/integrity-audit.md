---
name: integrity-audit
description: 정합성 감사 워크플로 실행 — read-only P0/P1/P2 리포트 생성
---

read-only — 코드/문서 수정 없음.

## 인자
- `[full]` → `{ scope: 'full' }` (8 도메인 전수 — 실행 전 비용 1줄 보고)
- `diff` → `git diff --name-only main...HEAD` 수집 후 `{ scope: 'diff', changedFiles: [...] }`
- `area=<name>` → `{ scope: 'area=<name>' }` · name ∈ pipeline|gate|security|api|db|ui|docs|tests

## 절차
1. `Workflow({ scriptPath: '<repo-abs>/.claude/workflows/integrity-audit.mjs', args })` — 절대경로 필수.
   `changedFiles` 수집은 호출자 몫(런타임에 git·파일시스템 접근 없음).
2. 반환 `{ scope, rounds, confirmed[], unverified, unverified_findings[], roi }` 를
   `docs/reports/YYYY-MM-DD-integrity-audit-<scope>.md` 로 쓴다 — 요약표 · confirmed/unverified 표(severity·file:line·도메인·claim) · §🔍 사용자 검증 필요(정책 2).
3. 리포트 경로 + ROI 보고. fix 는 사용자가 정책 7/15 로 결정 — 자동 수정 금지.

`unverified > 0` = 다수결 미성립 → 재실행(`area=<domain>`) 권고. 스킬 미인식 시 1단계를 직접 호출하고 2~3을 수동 수행한다.
