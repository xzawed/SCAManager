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

---

## 📘 Reference — "무엇인가?" (사실 조회)

> 정확성·일관성·예측 가능한 구조가 핵심. 작업 중 찾아보는 사실 모음.

| 문서 | 내용 |
|------|------|
| [reference/env-vars.md](reference/env-vars.md) | 전체 환경변수 단일 출처 (kill-switch·SaaS·DB·모델 분기 포함) |
| [reference/scoring.md](reference/scoring.md) | 점수 배점·등급 임계·AI 스케일링 |
| [reference/language-coverage.md](reference/language-coverage.md) | AI 리뷰 49 언어 + 정적분석 25종 커버리지 |
| [STATE.md](STATE.md) | 현재 수치 단일 출처 (테스트·pylint·SonarCloud·커버리지) |
| [cycle-history.md](cycle-history.md) | 사이클 60~159 작업 이력 (최신순) |
| [agents-index.md](agents-index.md) | `.claude/agents`·`skills` 인덱스 |

## 🛠 How-to — "어떻게 하는가?" (작업 절차)

> 특정 작업을 끝내기 위한 레시피. 목표 지향.

| 문서 | 작업 |
|------|------|
| [runbooks/workflow.md](runbooks/workflow.md) | 작업 유형별 실행 순서 + 모바일 환경 보호 |
| [runbooks/railway.md](runbooks/railway.md) | Railway 배포·운영 |
| [runbooks/db-migration.md](runbooks/db-migration.md) | DB 마이그레이션 절차 |
| [runbooks/merge-retry.md](runbooks/merge-retry.md) | CI-aware Auto Merge 재시도 운영 |
| [runbooks/operational-smoke-checks.md](runbooks/operational-smoke-checks.md) | 운영 endpoint smoke check (정책 13) |
| [runbooks/secret-prevention.md](runbooks/secret-prevention.md) | 시크릿 유출 방지 |
| [runbooks/self-analysis.md](runbooks/self-analysis.md) | 자기 분석 루프 방지 |
| [runbooks/static-assets.md](runbooks/static-assets.md) | 정적 자산(Tailwind 빌드) 관리 |
| [runbooks/phase2-data-readiness.md](runbooks/phase2-data-readiness.md) | Phase 2 데이터 준비 |
| [guides/github-integration-guide.md](guides/github-integration-guide.md) | GitHub 연동 가이드 |
| [guides/onpremise-migration-guide.md](guides/onpremise-migration-guide.md) | 온프레미스 DB 전환 가이드 |
| [guides/operational-verification.md](guides/operational-verification.md) | 운영 검증 가이드 |
| [integrations/external-quality-services.md](integrations/external-quality-services.md) | 외부 품질 서비스(SonarCloud 등) 통합 |
| [integrations/n8n-auto-fix.md](integrations/n8n-auto-fix.md) | n8n auto-fix 통합 |

## 💡 Explanation — "왜 그런가?" (이해·배경)

> 설계 결정의 맥락과 근거. 학습·이해 지향.

| 문서 | 내용 |
|------|------|
| [architecture.md](architecture.md) | `src/` 트리 + 핵심 데이터 흐름 (Webhook → pipeline → notify → gate) — 구조 단일 출처 |
| [design/INDEX.md](design/INDEX.md) | 설계 문서 16건 인덱스 (시스템·인증·Gate·차트·UI 재설계·i18n 등 — 설계 시점 결정 기록) |

## 🎓 Tutorial — "처음부터 배우기" (학습)

> 입문자용 단계별 학습. 현재 별도 튜토리얼 문서는 없으며, 최초 설정·실행은 최상위
> [README.md](../README.md) "Quick Start" + [CLAUDE.md](../CLAUDE.md) "핵심 명령" 으로 갈음한다.

---

## 📁 보조 디렉토리

| 경로 | 용도 |
|------|------|
| [_archive/](_archive/) | 회고 보고서·폐기 계획·과거 산출물 아카이브 (히스토리 보존, 활성 참조 아님) |
| `samples/` · `superpowers/` | 샘플·플랜 산출물 (참조 빈도 낮음) |

> **유지보수 원칙**: 새 문서 추가 시 본 인덱스의 해당 유형 표에 한 줄 등재. Diátaxis 유형 혼합
> (한 문서가 how-to + explanation 을 섞음) 은 지양 — 유형별 분리가 문서 명확성의 핵심이다.
