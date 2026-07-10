---
name: integrity-audit
description: 전체 정합성 감사 Workflow 실행 — read-only P0/P1/P2 리포트 생성 (다관점 verify + completeness critic)
---

`.claude/workflows/integrity-audit.mjs` 워크플로우를 실행하고 결과를 `docs/reports/` 리포트로 작성한다.
사이클 104/109 의 수동 5+1 전수 감사를 결정론적으로 코드화한 read-only 감사다 (코드/문서 수정 없음).

## 인자 해석

- `/integrity-audit` 또는 `/integrity-audit full` → `args: { scope: 'full' }`
  (8 도메인 전수, **토큰 다량 — 실행 전 예상 비용 1줄 보고 + 사용자 확인**)
- `/integrity-audit diff` → 먼저 `git diff --name-only main...HEAD` 로 변경 파일 수집
  → `args: { scope: 'diff', changedFiles: [...] }`
- `/integrity-audit area=<name>` → `args: { scope: 'area=<name>' }`
  (`<name>` ∈ pipeline / gate / security / api / db / ui / docs / tests — primary + 인접 1 도메인)

## 실행 절차

1. (diff 모드만) `git diff --name-only main...HEAD` 로 `changedFiles` 수집.
2. 워크플로우 호출 — **`scriptPath` 절대경로 필수** (빌트인이 아니라 `name` 해소 안 됨):
   `Workflow({ scriptPath: '<repo-abs>/.claude/workflows/integrity-audit.mjs', args: {...} })`
3. 반환 `{ scope, rounds, confirmed[], unverified, unverified_findings[], roi }` 를
   `docs/reports/YYYY-MM-DD-integrity-audit-<scope>.md` 로 작성 (아래 포맷).
4. 리포트 경로 + ROI 요약(P0/P1/P2 + fp_blocked + unverified)을 사용자에게 보고.
   **fix 는 사용자가 정책 7(PR 단위)/15(사전 사고)에 따라 결정 — 자동 수정 금지.**

> 🔴 `unverified > 0` 이면 검증 인프라(고동시성 StructuredOutput 누락 등)로 다수결을 못 낸 결함이다.
> false-negative 위험이므로 리포트에 별도 표로 노출하고 사용자에게 재실행/수동 확인을 권고한다.

## 리포트 포맷

```markdown
# 정합성 감사 리포트 — <scope> (YYYY-MM-DD)

| 항목 | 값 |
|------|-----|
| scope | <scope> |
| 라운드 | <rounds> |
| confirmed | <new> (P0 <p0> / P1 <p1> / P2 <p2>) |
| false-positive 차단 | <fp_blocked> |
| unverified (검증 실패) | <unverified> |

## 도메인별 confirmed 결함

| severity | file:line | 도메인 | claim |
|----------|-----------|--------|-------|
| P0 | path:line | domain | ... |

## ⚠️ unverified (다수결 미성립 — 재확인 필요)

| severity | file:line | 도메인 | title |
|----------|-----------|--------|-------|

## 🔍 사용자 검증 필요 (정책 2)
- P0 우선 검토 권장 — 운영 사고/보안 영향
- unverified 항목은 재실행(area=<domain>) 또는 수동 grep 확인
- fix 는 정책 7(PR 단위)/15(사전 사고)에 따라 진행
```

## 비용·거버넌스 주의

- `full` 은 8 도메인 × 다라운드(loop-until-dry, MAX_ROUNDS budget 시 5 / 미설정 3) = 다수 에이전트.
  정책 8(≥5 에이전트)·16#5(토큰) — 사용자 명시 호출 = 동의로 간주하되 **매 실행 전 예상 비용 1줄 보고**.
- 워크플로우는 read-only. 코드/문서 수정 없음. diff 변경파일 수집·리포트 파일 작성은 **호출자(이 스킬) 책임**
  (Workflow 런타임은 git/파일시스템 접근 불가).
- **스킬 미인식 시 인라인 대체**: `/integrity-audit` 가 스킬 목록에 안 뜨면 위 2단계 `Workflow({scriptPath, args})` 를 직접 호출하고 3~4단계를 수동 수행.

상세 운영 가이드: [docs/runbooks/integrity-audit.md](../../docs/runbooks/integrity-audit.md)
