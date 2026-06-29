# 정합성 감사 Workflow 운영 가이드
# Integrity Audit Workflow Runbook

> 사이클 104/109 의 **수동 5+1 전수 감사**를 결정론적 `.claude/workflows/integrity-audit.mjs` Workflow 로
> 코드화한 read-only 감사. P0/P1/P2 정합성 결함을 재현 가능하게 발견·검증·리포트한다.

## 목적

수동 5+1 감사는 매번 에이전트 디스패치·관점 배정·중복 제거·검증을 손으로 했다 — 재현성·일관성이 사람에 의존했다.
이 워크플로우는 그 절차를 코드로 고정한다: **scope 팬아웃 → loop-until-dry 도메인 탐색 → 3-렌즈 adversarial verify
→ completeness critic → 구조화 리포트**. 동일 입력 → 동일 절차를 보장한다.

## 호출 3-레이어

| 레이어 | 호출법 | 용도 |
|--------|--------|------|
| **스킬** | `/integrity-audit [full\|diff\|area=<name>]` | 권장 — diff scouting + 리포트 작성 자동 ([.claude/skills/integrity-audit.md](../../.claude/skills/integrity-audit.md)) |
| **인라인** | `Workflow({ scriptPath: '<abs>/.claude/workflows/integrity-audit.mjs', args: {...} })` | 스킬 미인식 시 직접 호출 |
| **저장형 name** | ❌ 불가 | `.claude/workflows/` 는 `name` 자동 해소 안 됨 — `scriptPath` 절대경로 필수 (실측) |

## scope 모드

| scope | 도메인 | 비용 | 용도 |
|-------|--------|------|------|
| `area=<name>` | primary 1 + 인접 1 (예: gate → gate+pipeline) | 소 | 단일 영역 집중 점검·CI 게이트 |
| `diff` | 변경 파일이 닿는 도메인만 (매칭 0 시 full fallback) | 중 | PR/브랜치 변경 회귀 점검 |
| `full` | 8 도메인 전수 (pipeline/gate/security/api/db/ui/docs/tests) | 대 | 분기별 전수 감사 (**사용자 사전 승인**) |

> `area=<name>` 인접 맵: pipeline↔gate / security↔api / db→pipeline / ui→tests / docs→tests.

## 비용 가이드 (area < diff < full)

- 라운드: `loop-until-dry` — 2회 연속 신규 0 또는 `MAX_ROUNDS`(budget 설정 시 5 / 미설정 3) 또는 budget 잔량 < 60k 시 종료.
- 도메인당 라운드별 1 audit 에이전트 + 발견 결함당 3 렌즈(correctness/security/repro) verify 에이전트.
- verify 는 배치 4(= 12 에이전트/배치) 순차 — 고동시성 StructuredOutput 누락 회귀(full 33건 동시 검증 전면 붕괴) 방어.
- `full` 은 정책 8(≥5 에이전트)·16#5(토큰) 영역 — **매 실행 전 예상 비용 1줄 보고 + 사용자 명시 확인**.

## 리포트 해석

반환 `{ scope, rounds, confirmed[], unverified, unverified_findings[], roi }`:

- `confirmed` — 3 렌즈 중 **2/3 이상 real=true** 판정된 결함만. P0(운영 사고/보안)/P1(정합)/P2(품질).
- `roi.fp_blocked` — 검증 응답을 받았으나 다수결에서 reject 된 것 (= seen − confirmed − unverified). 적대적 검증의 가치 지표.
- 🔴 `unverified` — 검증 인프라(고동시성 StructuredOutput 누락 등)로 **다수결을 못 낸** 결함. false-negative 위험 →
  리포트에 별도 표 노출 + 재실행(`area=<domain>`) 또는 수동 grep 확인 권고.

## 거버넌스

- **read-only** — 워크플로우는 코드/문서를 수정하지 않는다. diff 변경파일 수집·리포트 파일 작성은 호출자(스킬/메인루프) 책임
  (Workflow 런타임은 git/파일시스템 접근 불가).
- fix 는 사용자가 **정책 7(PR 단위)/15(사전 사고)/18(Codex mutual)** 에 따라 결정 — 워크플로우 발견을 자동 수정 금지.
- file:line 인용은 정책 6(`grep -n` 실측) 강제 — verify repro 렌즈가 `citation_verified` 로 재확인.

## 검증 모델 (일반 TDD 와 다름)

이 산출물은 Workflow 전용 런타임(`agent`/`parallel`/`args`/`budget` 전역)에서만 실행된다 — pytest import 불가.
대신 **실행 기반 검증 + 무비용 dryRun 게이트**:

| 수단 | 비용 | 검증 대상 |
|------|------|----------|
| `args.dryRun=true` | ~0 (에이전트 0) | scope 해소·도메인 매핑 등 결정론 로직 |
| `scope=area=gate` | 소 | 오케스트레이션 plumbing·loop·completeness·verify end-to-end |
| `scope=full` 골든 | 대 | 사이클 109 수동 감사 재현율 (**사용자 사전 승인**) |

## 아키텍처 (B+C 결합)

scope 인식 팬아웃(C)으로 감싼 loop-until-dry 도메인 탐색(B) + 다관점 adversarial verify(B) + completeness critic(C)
+ `MAX_ROUNDS`·`budget` 비용 상한(C). 설계 상세: [docs/design/2026-06-05-integrity-audit-workflow-design.md](../design/2026-06-05-integrity-audit-workflow-design.md).

## 🔴 워크플로우 작성·운영 교훈 (동시성·회복력)

다중 에이전트 워크플로우(integrity-audit·retrospective·구조검토 등) 작성/실행 시 검증된 운영 제약:

- **무거운 Opus 에이전트 동시 실행 ≤ 3 (웨이브 분할 의무)** — 무거운 리뷰/감사 에이전트 15개 동시 실행 시 서버 버스트 rate-limit("not your usage limit")로 전멸한 사고(2026-06-25). `chunk(items, 3)` + 웨이브별 `await parallel` 로 분할. verify 등 경량 단계는 무관.
- **StructuredOutput placeholder 소실 위험** — 장시간(수 분)·고 tool-호출 에이전트가 schema 강제 최종 출력에서 placeholder(예: `"test summary"`)로 결과를 소실하는 사례(2026-06-29 구조검토 차원 5). 핵심 차원 결과가 placeholder 면 단일 Agent 재감사로 보완. finder/verify 는 `try { ... } catch { 재시도 }` 로 StructuredOutput flake 1회 재시도.
- **completeness/gap 라운드 try/catch 격리 (C10)** — 마지막 best-effort 라운드의 일시 API 오류가 이미 confirmed 결함·Report 를 무효화하지 않도록 try/catch 로 격리. integrity-audit.mjs + retrospective.mjs 동일 패턴. 회귀 가드: `tests/unit/scripts/test_retrospective_resilience.py`.
- **cross-vendor 필수 (정책 18)** — 단일 LLM 다중에이전트 sweep 도 P1 누락 가능. Codex(또는 타 vendor) 독립 감사로 교차 검증 — 2026-06-29 감사서 Codex 가 Claude 8-에이전트가 놓친 P1 2건(crypto invalid-key·migration fail-open) 발견.
