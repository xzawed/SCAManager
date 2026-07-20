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
| 최신 작업 이력 | [STATE.md — 사이클 헤더 참조](../STATE.md) |
| **사용자 협업 정책** | [collaboration-retrospective.md](2026-05-01-collaboration-retrospective.md) (다음 세션 default) |

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
| 2026-06-03 | [wbs-codebase-audit](2026-06-03-wbs-codebase-audit.md) | WBS 코드베이스 감사 — 238파일 23.8K LOC 평가, 확정 22건 (P0 1 거버넌스 통제 / P1 2 / P2 19) |
| 2026-07-17 | [grok-full-review](2026-07-17-grok-full-review.md) | **Grok 8차원 발견 + Claude 46 에이전트 적대 검증** — Grok P0 4·P1 30 → 확정 **P0 0 · P1 4**(SHA 결속·워커 내구성·NULL-owner IDOR·SMTP 587), 반증 3. 은닉/악성 코드 CLEAN |

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
| 2026-05-01 | [collaboration-retrospective](2026-05-01-collaboration-retrospective.md) | 사용자 ↔ Claude 협업 회고 — 25 PR 시리즈 후 신뢰 모델 평가 + 사용자 합의 정책 5건 (옵션 장단점 명시 / PR 검증 미완료 섹션 / 자율 판단 보고 / 단언+가드 묶음 / 사이클 종료 신호) — **다음 세션 default 정책** |
| 2026-05-02 | [oauth-redirect-uri-incident](2026-05-02-oauth-redirect-uri-incident.md) | P0 사고 회고 — GitHub OAuth App redirect_uri 불일치로 인한 운영 정지 + 재발 방지 정책 신설 |
| 2026-05-02 | [phase1-retrospective](2026-05-02-phase1-retrospective.md) | Phase 1 회고 — Insight Dashboard 재설계 5 PR (MVP-B): /insights 폐기 + /dashboard 출시 + 정책 진화 4건 |
| 2026-05-02 | [phase1-2-retrospective](2026-05-02-phase1-2-retrospective.md) | Phase 1+2 회고 — 12 PR 머지 (대시보드 KPI 5종 + CTA banner): pre-existing fail 해소 + 정책 신설 4건 |
| 2026-05-04 | [phase3-end-multi-agent-retrospective](2026-05-04-phase3-end-multi-agent-retrospective.md) | Phase 3 종결 5+1 에이전트 회고 — RLS 운영 활성화 + Insight 회귀 가드 + P0 7건 (RLS 미들웨어 부재 등) |
| 2026-05-04 | [cycle-64-67-end-multi-agent-retrospective](2026-05-04-cycle-64-67-end-multi-agent-retrospective.md) | 사이클 64~67 4 사이클 종결 회고 — cross-verify 생략 첫 사례 + 메모리 4건 신규/갱신 + 정책 P0 4건 진화 |
| 2026-05-04 | [cycle-70-72-end-multi-agent-retrospective](2026-05-04-cycle-70-72-end-multi-agent-retrospective.md) | 사이클 70~72 종결 회고 — 정책 15/16 신설 적용 첫 사이클 + Telegram secret 사고 + 토큰 비용 효율 5번째 원칙 추가 |
| 2026-05-04 | [cycle-70-74-end-multi-agent-retrospective](2026-05-04-cycle-70-74-end-multi-agent-retrospective.md) | 사이클 70~74 종결 회고 — Phase 2-A/B (Anthropic 효율화 + DB 캐싱) 머지 + Phase 4 영역 진입 첫 작업 + 메모리 카테고리 분류 임계 도달 |
| 2026-05-04 | [cycle-76-full-consistency-cleanup-retrospective](2026-05-04-cycle-76-full-consistency-cleanup-retrospective.md) | 사이클 76 전체 문서+코드 5+1 정합성 cleanup — Tier A 8건 정정 + false-positive 차단 3건 + 신규 발견 3건 (정책 8 진화 정량 기준 정합) |
| 2026-05-05 | [cycle-78-81-end-multi-agent-retrospective](2026-05-05-cycle-78-81-end-multi-agent-retrospective.md) | 사이클 78~81 4 사이클 종결 회고 (영역 4종 진입 머지 — 🅒/🅐/🅔/🅑) — 5+1 다중 에이전트 P0 18 → cross-verify 통합 13 + Tier A 4 정정 + Tier B 2 메모리 신설 + TestClient lifespan 트랩 메모리 등재 (3중복) + alembic dialect 헬퍼 정책 16 위반 정정 권장 |
| 2026-05-05 | [cycle-78-82-end-multi-agent-retrospective](2026-05-05-cycle-78-82-end-multi-agent-retrospective.md) | 사이클 78~82 5 사이클 종결 회고 (사용자 명시 "전체 문서 정리 + 다중 에이전트 깊게 + 자유 발언") — 5+1 default 진행 (관점 1~5 + cross-verify 6차) → Tier A 4 즉시 정정 (env-vars.md 4 환경변수 + CLAUDE.md L1060 dialect helper stale + sync 체크리스트 강화 + STATE L117 header) + Tier B 11 (High 3 사용자 결정 의무 — 정책 9/3/1 진화 + Medium/Low 8) + cross-verify ROI 양호 (false-positive 차단 2 + 신규 발견 3) + 각 에이전트 5건 + 오케스트레이터 회고 + 자유 발언 (회고 질문 7건 사용자 회신 의무) |
| 2026-05-05 | [i18n-3language-support-detailed-plan](2026-05-05-i18n-3language-support-detailed-plan.md) | **다국어 (영어/한국어/일본어) 지원 도입 세부 기획안** (사용자 명시 "긴급 + 5번 정도 검수 + 세부 기획안") — 5+1 다중 에이전트 (관점 1 인프라 + 관점 2 대시보드/UI + 관점 3 코드리뷰 + 관점 4 알림 채널 9 + 관점 5 테스트/운영) + cross-verify 6차 + 본인 5 라운드 검수 + 18 PR 분할 (Phase 1~5, 12100 LOC, 3~5주) + 사용자 결정 8건 (Q1 Jinja2+Babel / Q2 18 PR / Q3 DB 컬럼 3 / Q4 검수 / Q5 Phase 진행 / Q6 kill-switch / Q7 caching / Q8 일본어 우선순위) + 위험 평가 P0 2 + P1 6 + P2 2 + 번역 비용 ~$4 |
| 2026-05-05 | [i18n-phase1-pr1-pre-review](2026-05-05-i18n-phase1-pr1-pre-review.md) | **Phase 1 PR-1 사전 검토 종합** (3 에이전트 병렬 — 관점 A 라이브러리/Middleware + 관점 B DB 마이그레이션/ORM + 관점 C 환경변수/kill-switch) — 통합 LOC ~1,495 (정책 7 강화 임계 영역 — 사용자 사전 확인 의무) + 신규 발견 정합 10건 + 위험 평가 P0 1 + P1 3 + P2 2 + Q9 신규 결정 (PR-1 분할 — Claude 권장 ★ = 🅑 3 PR 분할) + 본 사이클 진행 default = 사전 검토 종합 push만 (코드 작성 X — 사용자 명시 신호 의무) |
| 2026-05-06 | [cycle-84-i18n-18pr-end-multi-agent-retrospective](2026-05-06-cycle-84-i18n-18pr-end-multi-agent-retrospective.md) | 사이클 84 회고 — 다국어 i18n 18 PR 종결 (영어/한국어/일본어), 5+1 다중 에이전트 검증 |
| 2026-05-06 | [cycle-85-end-multi-agent-retrospective](2026-05-06-cycle-85-end-multi-agent-retrospective.md) | 사이클 85 회고 — Sentry 통합 제거 + GitHub branch 정리 + CLAUDE.md 정합 (2 PR) |
| 2026-05-06 | [cycle-86-end-multi-agent-retrospective](2026-05-06-cycle-86-end-multi-agent-retrospective.md) | 사이클 86 회고 — 정책 진화 추출 + Dependabot 8 PR + pylint 회복 (11 PR, CI timeout 대응) |
| 2026-05-07 | [cycle-89-91-end-multi-agent-retrospective](2026-05-07-cycle-89-91-end-multi-agent-retrospective.md) | 사이클 89~91 회고 — fixture/i18n/flake8 통합 수정 + slow test mock (4 PR) |
| 2026-06-03 | [cycle-156-157-retrospective](2026-06-03-cycle-156-157-retrospective.md) | 사이클 156/157 회고 — Theme B SSRF 회귀가드 봉인 (4채널), 5+1 다중 에이전트 재검증 |
| 2026-06-11 | [cycle-166-859-retrospective](2026-06-11-cycle-166-859-retrospective.md) | 사이클 166~#859 회고 — Task9 백로그·RLS Phase 2~4·2nd-LLM 머지 검증자(#859) 종결, 5+1+cross-verify (P0 1·P1 8·P2 다수) |
| 2026-06-16 | [session-retrospective](2026-06-16-session-retrospective.md) | 2026-06-16 Railway follow-up 세션(#906~#910 + RLS Phase 4 step 0) 5+1 회고 — P0 0·P1 1·P2 10·FP 0, Option A follow-up #912~#914 (CodeQL #518·codex 도구 codify·architecture 6-step ⑥) |
| 2026-06-23 | [retrospective](2026-06-23-retrospective.md) | 잔여작업 세션(#973~#975) 회고 — retrospective.mjs 첫 dogfooding, 55 confirmed(P1 2·P2 53)·FP 14·verdict_coverage 1.0, C10 회복력 갭 식별 |
| 2026-07-03 | [retrospective](2026-07-03-retrospective.md) | 2026-06-25~07-03 4세션(#989~#1023) 누적 갭 회복 5+1 회고 — 66 confirmed(P0 1·P1 12·P2 53)·FP 6·verdict_coverage 1.0, 8 클러스터(회고 카덴스·self-inflicted CodeQL·가격 parity 가드·grep 전수·docs drift·supply-chain 렌즈) |
| 2026-07-18 | [retrospective](2026-07-18-retrospective.md) | 2026-07-08~18 5~6세션(#1032~#1077) 누적 갭 회복 5+1 회고 — 87 에이전트·61 confirmed(P0 **3**·P1 15·P2 43)·FP 6·verdict_coverage 1.0. **P0 = 회고 카덴스 트리거(#1028) 첫 측정창 자기위반**(~46 PR 무회고·~3x 임계·문서-only 시정 실패→기계화 필요). 테마: CodeQL turn-0 가드 진공·Hook false-green·dead-code 배선·비대칭 가드·owed 운영검증·docs drift |
| 2026-07-18 | [scoped-retrospective](2026-07-18-scoped-retrospective.md) | 🔴 **복구본** — 세션2 remediation 15 PR 범위 한정 5+1 회고(`wf_40082e43-d00`). 186 에이전트·확정 **147**(P0 2·P1 55·P2 90)·FP 16·미페어링 7. **보고서가 아카이브되지 않아 소실**됐던 것을 2026-07-20 워크플로 journal 에서 복구 (P0·P1 집계가 STATE 기록과 정확히 일치해 교차 확인). 두 회고가 각각 P1 로 이 소실을 지목했다(`2026-07-19-retrospective.md` P1-3·P1-47) |
| 2026-07-19 | [retrospective](2026-07-19-retrospective.md) | 2026-07-19 세션2(#1078~#1101, 22 PR) 5+1 회고 — 164 에이전트·확정 135(P0 **11**·P1 66·P2 58)·FP 7·verdict_coverage 1.0. **"가드의 가드" = YES** — 직전 세션 신규 가드 4종이 전부 결함(뮤테이션 실증). 자초 CodeQL 원인 **반전**(게이트 부재가 아니라 note 임계값 미설정 — PR 시점 이미 탐지) |
| 2026-07-19 | [retrospective-2](2026-07-19-retrospective-2.md) | 🔴 **회고를 수행한 세션 자신의 산출물**(#1102~#1107)을 범위로 한 2차 회고 — 168 에이전트·확정 134(P0 **8**·P1 51·P2 75)·FP 13·verdict_coverage 1.0. **P0 8건 중 4건이 `#1104` 를 정면 반박**(4 에이전트 독립 도달 + 재현 실증 — "2계층 봉인" 선언이 거짓, exc_info·uvicorn 축이 열려 있었음 → `#1109` 로 완결). → 정책 8 진화 (5) **회고 범위에 세션 자신의 산출물 포함** default 신설의 근거 |

---

## 로드맵·결정

| 날짜 | 문서 | 핵심 |
|------|------|------|
| 2026-04-23 | [remaining-roadmap-3agent](2026-04-23-remaining-roadmap-3agent.md) | 잔여 과제 3-에이전트 논의 |
| 2026-04-23 | [phase-e-service-pivot-decision](2026-04-23-phase-e-service-pivot-decision.md) | Phase E — Path A(서비스화) 전환 결정 |
| 2026-04-24 | [auto-merge-failure-analysis-3agent](2026-04-24-auto-merge-failure-analysis-3agent.md) | Auto-merge 실패 진단 + Phase F 로드맵 |
| 2026-05-01 | [phase-h-i-doc-reflection-plan](2026-05-01-phase-h-i-doc-reflection-plan.md) | Phase H+I 문서 반영 세부 계획 — 4 에이전트 검증 22항목 우선순위 분류 (위험도·작업량 명시) |
| 2026-05-05 | [i18n-18pr-closure-baseline](2026-05-05-i18n-18pr-closure-baseline.md) | 사이클 84 i18n 18 PR 종결 baseline — Phase 1~5 18/18 완료 (1800+ LOC), 회귀가드 12건 |
| 2026-05-11 | [doc-cleanup-plan](2026-05-11-doc-cleanup-plan.md) | 문서 정비 계획 — CLAUDE.md/AGENTS.md 감사 P0 5/P1 10/P2 5건 식별 (5+1 다중 에이전트) |

---

## 기타

| 날짜 | 문서 | 핵심 |
|------|------|------|
| 2026-05-18 | [perf-2026-05-18-2314](perf-2026-05-18-2314.md) | 성능 리포트 — 로컬 E2E 서버 8개 페이지 측정 (TTFB/FCP/LCP/DCL), 전부 통과 |
| — | (artifacts/ 정리) | 2026-04-27 PR #87 에서 19개 보조 파일 일괄 삭제 — 디렉토리 폐기 |
