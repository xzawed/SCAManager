# SCAManager 문서 인덱스

> **이 파일이 `docs/` 진입점이다.** 모든 프로젝트 문서를 [Diátaxis](https://diataxis.fr/) 4 유형
> (tutorial / how-to / reference / explanation) 으로 분류한 지도다. 폴더명은 안정성(참조·훅 의존)을
> 위해 유지하고, 유형은 본 인덱스가 논리적으로 부여한다.

> **독자는 사람이다 — 이것은 설계이지 결함이 아니다.** 이 파일은 어떤 자동 로드 경로에도 없다
> (SessionStart 훅 · `doc_review_gate` 컨텍스트 · `.claude/rules` 의 `paths:` 매칭 전부 밖).
> 68개 문서 중 유일하다. 대상은 **GitHub 에서 `docs/` 디렉토리를 열어 본 사람**이고,
> 그 자리에서 렌더되는 것이 이 파일의 용도 전부다.
> 에이전트(Claude)의 진입점은 여기가 아니라 [`CLAUDE.md`](../CLAUDE.md) §탐색이다 — 그쪽은 매 세션 로드된다.
> Human-facing index for the GitHub directory view; agents enter through CLAUDE.md instead.

## 🧭 빠른 진입

| 목적 | 시작 문서 |
|------|----------|
| 프로젝트가 무엇인지 / 어떻게 쓰는지 | [README.md](../README.md) (English) · [README.ko.md](../README.ko.md) (한국어) |
| 에이전트(Claude) 작업 규칙 | [CLAUDE.md](../CLAUDE.md) |
| 시스템 구조 파악 | [architecture.md](architecture.md) — `src/` 트리 + 핵심 데이터 흐름 (단일 출처) |
| 최신 수치·상태 | [STATE.md](STATE.md) — 테스트·커버리지·등급 단일 출처 |
| **어떻게 수행하는가** (프로세스·플로우) | [process/](process/) — 가드 저술 · 주장 검증 · 문서 압축 · PR 수명 |
| **이렇게 틀렸었다** (실패 클래스) | [`.claude/traps.md`](../.claude/traps.md) — 실제로 밟은 함정 (계열 A~E) |

---

## 📘 Reference — "무엇인가?" (사실 조회)

> 정확성·일관성·예측 가능한 구조가 핵심. 작업 중 찾아보는 사실 모음.

| 문서 | 내용 |
|------|------|
| [reference/env-vars.md](reference/env-vars.md) | 전체 환경변수 단일 출처 (kill-switch·SaaS·DB·모델 분기 포함) |
| [reference/scoring.md](reference/scoring.md) | 점수 배점·등급 임계·AI 스케일링 |
| [STATE.md](STATE.md) | 현재 수치 단일 출처 (테스트·pylint·SonarCloud·커버리지) |
| [agents-index.md](agents-index.md) | `.claude/agents`·`skills` 인덱스 |

## 🛠 How-to — "어떻게 하는가?" (작업 절차)

> 특정 작업을 끝내기 위한 레시피. 목표 지향.

| 문서 | 작업 |
|------|------|
| [process/claim-and-verify.md](process/claim-and-verify.md) | *"고쳤다 · 닫았다 · 0건이다"* 를 **말하기 직전** |
| [runbooks/workflow.md](runbooks/workflow.md) | 작업 유형별 실행 순서 + 모바일 환경 보호 |
| [runbooks/new-machine-setup.md](runbooks/new-machine-setup.md) | 새 PC 셋업 — 리포가 실어 주지 않는 자산(`.env` 값·에이전트 메모리·MCP·`gh` scope) + 검증 |
| [runbooks/railway.md](runbooks/railway.md) | Railway 배포·운영 |
| [runbooks/operational-smoke-checks.md](runbooks/operational-smoke-checks.md) | 운영 endpoint smoke check (정책 13) |
| [runbooks/secret-prevention.md](runbooks/secret-prevention.md) | 시크릿 유출 방지 |
| [runbooks/branch-protection.md](runbooks/branch-protection.md) | main 브랜치 보호 — required check 정본 목록 + 승격/롤백 절차 + 관측의 한계 |
| [runbooks/retrospective.md](runbooks/retrospective.md) | 5+1 회고 워크플로우 운영 (`/retrospective`) |
| [runbooks/rls-role-separation.md](runbooks/rls-role-separation.md) | RLS 앱 role 분리 운영 (owner-bypass 차단) |
| [runbooks/ai-collaboration.md](runbooks/ai-collaboration.md) | 🔴 Claude ↔ Grok 협업 프로토콜 — **정책 19 단일 출처** (주장 트리거·A2 뮤테이션·소유 경계) |
| [runbooks/cost-controls.md](runbooks/cost-controls.md) | AI 리뷰 비용 제어 (kill-switch·리포별 토글) 검증 절차 |
| [runbooks/github-integration-guide.md](runbooks/github-integration-guide.md) | GitHub 연동 가이드 |
| [runbooks/onpremise-migration-guide.md](runbooks/onpremise-migration-guide.md) | 온프레미스 DB 전환 가이드 |
| [runbooks/n8n-auto-fix.md](runbooks/n8n-auto-fix.md) | n8n auto-fix 통합 |

## 💡 Explanation — "왜 그런가?" (이해·배경)

> 설계 결정의 맥락과 근거. 학습·이해 지향.

| 문서 | 내용 |
|------|------|
| [architecture.md](architecture.md) | `src/` 트리 + 핵심 데이터 흐름 (Webhook → pipeline → notify → gate) — 구조 단일 출처 |

## 🎓 Tutorial — "처음부터 배우기" (학습)

> 입문자용 단계별 학습. 현재 별도 튜토리얼 문서는 없으며, 최초 설정·실행은 최상위
> [README.md](../README.md) "Quick Start" + [CLAUDE.md](../CLAUDE.md) "핵심 명령" 으로 갈음한다.

---

## 📁 보조 디렉토리

| 경로 | 용도 |
|------|------|
| `reports/` | `/integrity-audit`·`/retrospective` 워크플로우가 **지금** 쓰는 산출 착지 |
| `samples/` | 샘플 산출물 (tracked, 참조 빈도 낮음) |

> **유지보수 원칙**: 새 문서 추가 시 본 인덱스의 해당 유형 표에 한 줄 등재. Diátaxis 유형 혼합
> (한 문서가 how-to + explanation 을 섞음) 은 지양 — 유형별 분리가 문서 명확성의 핵심이다.
