# 보고서 인덱스

감사·회고·로드맵 보고서 목록. 카테고리별 분류.

> 실시간 상태는 [docs/STATE.md](../STATE.md) 가 단일 진실 소스입니다.
> 본 인덱스의 보고서들은 각 시점의 스냅샷입니다.

## 현재 상태 바로가기

| 항목 | 위치 |
|------|------|
| 단위 테스트 수·커버리지·pylint | [STATE.md 헤더](../STATE.md) |
| 아키텍처·작업 규칙·주의사항 | [CLAUDE.md](../../CLAUDE.md) |
| README 배지 | [README.md L21-25](../../README.md) |
| 최신 작업 이력 | [STATE.md 그룹 54](../STATE.md) |

---

## 품질 감사 (다중 에이전트)

| 날짜 | 문서 | 핵심 |
|------|------|------|
| 2026-04-09 | [code-quality-report-2026-04-09](code-quality-report-2026-04-09.md) | 초기(Phase 0) 품질 강화 보고서 |
| 2026-04-19 | [code-quality-audit](2026-04-19-code-quality-audit.md) | 초기 품질 감사 |
| 2026-04-21 | [quality-audit-round5](2026-04-21-quality-audit-round5.md) | 5라운드 다중 에이전트 합의 점수 |
| 2026-04-22 | [quality-audit-6lens](2026-04-22-quality-audit-6lens.md) | 6렌즈 품질 감사 |
| 2026-04-23 | [phase-e-quality-audit-5lens](2026-04-23-phase-e-quality-audit-5lens.md) | Phase E 완결 시점 5-렌즈 감사 (91/100 A) |
| 2026-04-23 | [sonarcloud-baseline](2026-04-23-sonarcloud-baseline.md) | SonarCloud 1차 분석 + 청산 계획 |
| 2026-04-23 | [structure-audit-3agent](2026-04-23-structure-audit-3agent.md) | 프로젝트 구조 3-에이전트 감사 |
| 2026-04-24 | [comprehensive-audit](2026-04-24-comprehensive-audit.md) | 14 에이전트 × 3 Round 전면 감사 (P1 7건, G Phase 착수) |
| 2026-04-30 | [12agent-comprehensive-audit](2026-04-30-12agent-comprehensive-audit.md) | 12 에이전트 × 2 Round 종합 감사 (Critical 10건, Phase H+I 6 PR / 36h 로드맵) |
| 2026-04-25 | [static-analysis-baseline](2026-04-25-static-analysis-baseline.md) | G.6 병렬화 Go/No-Go 기준선 |
| 2026-04-26 | 3-에이전트 교차 감사 (PR #73) | 문서 불일치 9건 수정 — STATE.md 그룹 44 참조 |

---

## 회고 (문제 → 원인 → 교훈)

| 날짜 | 문서 | 핵심 |
|------|------|------|
| 2026-04-19 | [multilang-expansion-retrospective](2026-04-19-multilang-expansion-retrospective.md) | 다언어 코드리뷰·정적분석 확장 회고 (Phase 0~C) |
| 2026-04-23 | [railway-rubocop-prism-retrospective](2026-04-23-railway-rubocop-prism-retrospective.md) | Railway 빌드 실패 — rubocop/prism transitive 의존성 트랩 |
| 2026-04-26 | [doc-review-gate-retrospective](2026-04-26-doc-review-gate-retrospective.md) | 문서 심의 게이트 설계 결정 회고 |
| 2026-04-26 | [quality-audit-and-tooling-retrospective](2026-04-26-quality-audit-and-tooling-retrospective.md) | 3-에이전트 교차 감사 + 500 에러 진단 + 툴링 안전장치 |
| 2026-04-27 | [phase12-docs-overhaul-retrospective](2026-04-27-phase12-docs-overhaul-retrospective.md) | Phase 12 완료 + 문서 정비 — 병렬 에이전트 브랜치 충돌 교훈 |
| 2026-04-29 | [phase4-test-coverage-retrospective](2026-04-29-phase4-test-coverage-retrospective.md) | Phase 4 Critical 테스트 갭 5 PR 회고 — +197 tests, src/ 변경 0, Quality Gate 5연속 OK |
| 2026-04-29 | [phase4-meta-retrospective](2026-04-29-phase4-meta-retrospective.md) | Phase 4 메타 회고 — 3-에이전트 병렬 검증으로 누락 9건 발견·수정 + PR-B3 정량 평가 기준 추가 |
| 2026-05-01 | [phase-h-i-completion-retrospective](2026-05-01-phase-h-i-completion-retrospective.md) | Phase H+I 15 PR 완료 회고 — 12-에이전트 감사 Critical 10건 100% 처리, 외부 의존성 추가 0, Functional bug 1건 발견 (Telegram HMAC) |
| 2026-05-01 | [ui-audit-cycle-retrospective](2026-05-01-ui-audit-cycle-retrospective.md) | UI 감사 사이클 (그룹 55~57) 회고 — 4-에이전트 화면 감사 65건 → Step A~E 분할 → 5-에이전트 정합성 cleanup 4 PR + 메타 sync PR-D1~D5 모델 + 환각 토큰 발견 패턴 + claude-dark 테마 토큰 매트릭스 |

---

## 로드맵·결정

| 날짜 | 문서 | 핵심 |
|------|------|------|
| 2026-04-23 | [remaining-roadmap-3agent](2026-04-23-remaining-roadmap-3agent.md) | 잔여 과제 3-에이전트 논의 |
| 2026-04-23 | [phase-e-service-pivot-decision](2026-04-23-phase-e-service-pivot-decision.md) | Phase E — Path A(서비스화) 전환 결정 |
| 2026-04-24 | [auto-merge-failure-analysis-3agent](2026-04-24-auto-merge-failure-analysis-3agent.md) | Auto-merge 실패 진단 + Phase F 로드맵 |

---

## 기타

| 날짜 | 문서 | 핵심 |
|------|------|------|
| — | (artifacts/ 정리) | 2026-04-27 PR #87 에서 19개 보조 파일 일괄 삭제 — 디렉토리 폐기 |
