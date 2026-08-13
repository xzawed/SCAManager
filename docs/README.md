# SCAManager 문서 인덱스

> **이 파일이 `docs/` 진입점이다.** 모든 프로젝트 문서를 [Diátaxis](https://diataxis.fr/) 4 유형
> (tutorial / how-to / reference / explanation) 으로 분류한 지도다. 폴더명은 안정성(참조·훅 의존)을
> 위해 유지하고, 유형은 본 인덱스가 논리적으로 부여한다.

## 🧭 빠른 진입

| 목적 | 시작 문서 |
|------|----------|
| 프로젝트가 무엇인지 / 어떻게 쓰는지 | [README.md](../README.md) (English) · [README.ko.md](../README.ko.md) (한국어) |
| 에이전트(Claude) 작업 규칙 | [CLAUDE.md](../CLAUDE.md) |
| 시스템 구조 파악 | [architecture.md](architecture.md) — `src/` 트리 + 핵심 데이터 흐름 (단일 출처) |
| 최신 수치·상태 | [STATE.md](STATE.md) — 테스트·커버리지·등급 단일 출처 |
| **어떻게 수행하는가** (프로세스·플로우) | [process/](process/) — 가드 저술 · 주장 검증 · 문서 압축 · PR 수명 |
| **이렇게 틀렸었다** (실패 클래스) | [`.claude/traps.md`](../.claude/traps.md) — 실제로 밟은 함정 16종 |

---

## 📘 Reference — "무엇인가?" (사실 조회)

> 정확성·일관성·예측 가능한 구조가 핵심. 작업 중 찾아보는 사실 모음.

| 문서 | 내용 |
|------|------|
| [reference/env-vars.md](reference/env-vars.md) | 전체 환경변수 단일 출처 (kill-switch·SaaS·DB·모델 분기 포함) |
| [reference/scoring.md](reference/scoring.md) | 점수 배점·등급 임계·AI 스케일링 |
| [reference/language-coverage.md](reference/language-coverage.md) | AI 리뷰 49 언어 + 정적분석 25종 커버리지 |
| [STATE.md](STATE.md) | 현재 수치 단일 출처 (테스트·pylint·SonarCloud·커버리지) |
| [cycle-history.md](cycle-history.md) | 사이클 60~166 작업 이력 (최신순) |
| [agents-index.md](agents-index.md) | `.claude/agents`·`skills` 인덱스 |

## 🛠 How-to — "어떻게 하는가?" (작업 절차)

> 특정 작업을 끝내기 위한 레시피. 목표 지향.

| 문서 | 작업 |
|------|------|
| [process/README.md](process/README.md) | **흐름 진입점** — 어떤 작업에 어떤 흐름을 여는가 |
| [process/guard-authoring.md](process/guard-authoring.md) | 가드·테스트를 **새로 저술**할 때 (TDD → 뮤테이션 → 배선 → 한계 기술) |
| [process/claim-and-verify.md](process/claim-and-verify.md) | *"고쳤다 · 닫았다 · 0건이다"* 를 **말하기 직전** |
| [process/doc-compression.md](process/doc-compression.md) | 문서를 **압축·삭제·이동하기 직전** (소비자 grep → 이동 → 검증) |
| [process/pr-lifecycle.md](process/pr-lifecycle.md) | 커밋부터 머지까지 — 막히는 지점과 뚫는 법 |
| [runbooks/workflow.md](runbooks/workflow.md) | 작업 유형별 실행 순서 + 모바일 환경 보호 |
| [runbooks/new-machine-setup.md](runbooks/new-machine-setup.md) | 새 PC 셋업 — 리포가 실어 주지 않는 자산(`.env` 값·에이전트 메모리·MCP·`gh` scope) + 검증 |
| [runbooks/railway.md](runbooks/railway.md) | Railway 배포·운영 |
| [runbooks/db-migration.md](runbooks/db-migration.md) | DB 마이그레이션 절차 |
| [runbooks/merge-retry.md](runbooks/merge-retry.md) | CI-aware Auto Merge 재시도 운영 |
| [runbooks/operational-smoke-checks.md](runbooks/operational-smoke-checks.md) | 운영 endpoint smoke check (정책 13) |
| [runbooks/secret-prevention.md](runbooks/secret-prevention.md) | 시크릿 유출 방지 |
| [runbooks/branch-protection.md](runbooks/branch-protection.md) | main 브랜치 보호 — required check 정본 목록 + 승격/롤백 절차 + 관측의 한계 |
| [runbooks/self-analysis.md](runbooks/self-analysis.md) | 자기 분석 루프 방지 |
| [runbooks/static-assets.md](runbooks/static-assets.md) | 정적 자산(Tailwind 빌드) 관리 |
| [runbooks/phase2-data-readiness.md](runbooks/phase2-data-readiness.md) | Phase 2 데이터 준비 |
| [runbooks/integrity-audit.md](runbooks/integrity-audit.md) | 정합성 감사 워크플로우 운영 (`/integrity-audit`) |
| [runbooks/retrospective.md](runbooks/retrospective.md) | 5+1 회고 워크플로우 운영 (`/retrospective`) |
| [runbooks/retro-cadence-deferrals.md](runbooks/retro-cadence-deferrals.md) | 🔴 회고 카덴스 이월 원장 — breach 중 회고 미진입 시 승인 기록 의무 (정책 8 진화 (6)) |
| [runbooks/merge-verifier.md](runbooks/merge-verifier.md) | 2nd-LLM 머지 검증자 활성화 (운영 안전) |
| [runbooks/rls-role-separation.md](runbooks/rls-role-separation.md) | RLS 앱 role 분리 운영 (owner-bypass 차단) |
| [runbooks/ai-collaboration.md](runbooks/ai-collaboration.md) | 🔴 Claude ↔ Grok 협업 프로토콜 — **정책 19 단일 출처** (주장 트리거·A2 뮤테이션·소유 경계) |
| [runbooks/owed-verification.md](runbooks/owed-verification.md) | 🔴 미결 검증 원장 — SessionStart 훅이 매 세션 미회신 건을 경고 |
| [runbooks/cost-controls.md](runbooks/cost-controls.md) | AI 리뷰 비용 제어 (kill-switch·리포별 토글) 검증 절차 |
| [runbooks/docs-consolidation-status.md](runbooks/docs-consolidation-status.md) | 🔴 **문서·가드 정리 진행 상태 정본** — 착수 전 필독(12 PR 중 PR-1·2·3 완료, PR-4→PR-5 순서 강제) |
| [runbooks/docs-consolidation-plan.md](runbooks/docs-consolidation-plan.md) | 문서·가드 정리 계획 전문 (SPEC→RED→GREEN→GUARD 12 묶음) |
| [runbooks/doc-volume-reduction-plan.md](runbooks/doc-volume-reduction-plan.md) | 🟢 **결정 대기 제안서** — 기록성↔집행성 분리(backlog ✅ 47% · STATE 이력 46% 실측). 실행 0건 |
| [runbooks/session-handoff-2026-08-12.md](runbooks/session-handoff-2026-08-12.md) | 🔴 **세션 인계 — 다른 머신에서 이어받기**. main red 원인·PR #1331 대기·감사 결정 5건·미완 회고 |
| [runbooks/github-integration-guide.md](runbooks/github-integration-guide.md) | GitHub 연동 가이드 |
| [runbooks/onpremise-migration-guide.md](runbooks/onpremise-migration-guide.md) | 온프레미스 DB 전환 가이드 |
| [runbooks/operational-verification.md](runbooks/operational-verification.md) | 운영 검증 가이드 |
| [runbooks/external-quality-services.md](runbooks/external-quality-services.md) | 외부 품질 서비스(SonarCloud 등) 통합 |
| [runbooks/n8n-auto-fix.md](runbooks/n8n-auto-fix.md) | n8n auto-fix 통합 |

## 💡 Explanation — "왜 그런가?" (이해·배경)

> 설계 결정의 맥락과 근거. 학습·이해 지향.

| 문서 | 내용 |
|------|------|
| [architecture.md](architecture.md) | `src/` 트리 + 핵심 데이터 흐름 (Webhook → pipeline → notify → gate) — 구조 단일 출처 |
| [design/INDEX.md](design/INDEX.md) | 설계 문서 18건 인덱스 (시스템·인증·Gate·차트·UI 재설계·i18n·repo-automation 등 — 설계 시점 결정 기록) |

## 🎓 Tutorial — "처음부터 배우기" (학습)

> 입문자용 단계별 학습. 현재 별도 튜토리얼 문서는 없으며, 최초 설정·실행은 최상위
> [README.md](../README.md) "Quick Start" + [CLAUDE.md](../CLAUDE.md) "핵심 명령" 으로 갈음한다.

---

## 📁 보조 디렉토리

| 경로 | 용도 |
|------|------|
| [_archive/](_archive/) | 🔴 **과거 기록 단일 네임스페이스** (2026-08-13 통합) — `reports/`(회고·감사) · `plans/`(완료 계획, 구 `.claude/plans` + `superpowers/plans`) · `specs/` · `runbooks/`(구 `runbooks/_archive`). 히스토리 보존, 활성 참조 아님 |
| `reports/` | `/integrity-audit`·`/retrospective` 워크플로우 실행 시 생성되는 리포트 산출물 (활성) — 과거 회고 보존본은 `_archive/reports/` |
| `samples/` | 샘플 산출물 (tracked, 참조 빈도 낮음) |
| `superpowers/` | 🔴 **로컬 전용 working dir** (`.gitignore` 등재 · GitHub 미푸시) — 완료된 plan/spec 은 `_archive/superpowers/` 로 수동 이동 |

> **유지보수 원칙**: 새 문서 추가 시 본 인덱스의 해당 유형 표에 한 줄 등재. Diátaxis 유형 혼합
> (한 문서가 how-to + explanation 을 섞음) 은 지양 — 유형별 분리가 문서 명확성의 핵심이다.
