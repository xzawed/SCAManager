# 보고서 인덱스

감사·회고·로드맵 보고서 목록. 카테고리별 분류.

> 실시간 상태는 [docs/STATE.md](../STATE.md) 가 단일 진실 소스입니다.
> 본 인덱스의 보고서들은 각 시점의 스냅샷입니다.

## 현재 상태 바로가기

| 항목 | 위치 |
|------|------|
| 2026-08-10 | [docs-system-audit](2026-08-10-docs-system-audit.md) | 문서 체계 감사 — **8 에이전트**·6 렌즈 전건 STRAINED. 🔴 **총량은 비용 문제가 아니다**(게이트 = 세션비용 0.48%, 리포 전체 통독도 2.6%) — 무리한 것은 집행 구조다. 확정 P0 6건 = pylint 배지 10.00 vs CI 9.99(집행자 0) · 예산 가드가 산문으로 충족되는 거짓 집행자 · `security.md` 가 `src/config.py` 에 미도달 · 6-step② vs 메모리 충돌 · claim-review 형식 도달범위<집행범위 · 실행형 계획 가드 4배치 중 2배치만 스캔 |
| 2026-08-13 | [retrospective](2026-08-13-retrospective.md) | 정책 8 5+1 회고 (범위 #1317~#1338, 22 PR) — **205 에이전트**·15.6M 토큰·3h16m. findings **182** · **verdict_coverage 1.00**(UNVERIFIED 0) · P0 8 / P1 83 / P2 81 · FP 차단 10 · SEVERITY_ADJUST **34%**. 🔴 **P0 3건이 이 세션 산출물이고 그중 2건을 라이브 재현했다**: (a) 정정 커밋 `e7159d8f` 가 이미 머지된 브랜치에 63분 뒤 얹혀 **고아**가 됐는데 인계 문서가 *"#1335 에 포함"* 으로 단언 — 자기보고가 살아있는 결함을 덮었다 (b) **아카이브 보존 가드 봉인 주장이 거짓** — 서사 100% 제거 + 지문·인용 채움으로 38건 전건 통과(Grok 이 준 특정 뮤테이션만 막았다). 🔴 규칙 파일 삭제가 `check_red_budget` 에서 **'개선'으로 채점**된다(무집행 🔴 −50). 비용 예측 4.6배 오차(재시도 승수 미계산) |
| 2026-08-12 | [docs-audit](2026-08-12-docs-audit.md) | 전 문서 항목별 채점 — **47 에이전트**·5.5M 토큰·Grok claim-review 3세션. 128건 채점(평균 61.6 · BROKEN 32) · 확정 P0 7 / P1 12 / P2 30 · 오탐 반증 21. 🔴 **감사의 분모가 틀렸다**(자진신고 279 vs 실측 205) — CRITICAL 23건 누락 후 갭 감사로 보완. 🔴 Grok 이 초판 설계를 **BROKEN** 판정(아카이브 정확성 면제 = 채점 회피 탈출구 · 집행<정확성 가중치 역전) · 결과를 **WEAKENED** 판정(P0 3건이 이미 #1331 에 수정·미머지). 처방 정본 = `runbooks/session-handoff-2026-08-12.md` |
| 2026-08-11 | [docs-scoring-report](2026-08-11-docs-scoring-report.md) | 문서 채점 + SDD·TDD 정리 계획 — **10 에이전트**·1.48M 토큰·검증 3라운드. 🔴 **2라운드에서 채점 체계 자체가 BROKEN** — 편집 불변성 없음(공백 커밋 1회로 처분 26건 소멸)·관측자 오염(감사 세션이 분모 안)·접근축 93%가 부수 등장. 그래서 **순위 기반 조치를 전면 철회**하고 조치 채점(AR)으로 대체. 문서 삭제·이동 **0건**, 12 PR 로 집행. 계획 정본 = `runbooks/docs-consolidation-plan.md` |
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
| 2026-07-23 | [comprehensive-review](2026-07-23-comprehensive-review.md) | **종합 코드+문서 검증** — 10 렌즈 다이나믹 워크플로우 339 에이전트·확정 64(P0 0·P1 11·P2 53)·FP 32. P1 전건 봉인(#1186~1194)·P2 21 처리(#1195~1201)·잔여 32 = backlog. Grok cross-verify top 3 REAL |

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
| 2026-07-22 | [retrospective](2026-07-22-retrospective.md) | 2026-07-19~22 4세션(#1114~#1170, **57 PR**) 누적 갭 회복 5+1 회고 — **93 에이전트**·확정 **65**(P0 **3**·P1 18·P2 44)·FP 8·verdict_coverage 1.0. **P0 = 회고 카덴스 자기위반 3회차**(57 PR·3.8x 임계·advisory 3세션 이월). 지배 테마 = **observer-lie 가 메타 층으로 이동**(카운터·아카이브·문서 freshness 가드가 "관측만·집행 없음"). 🔴 **이번 세션 자기 적발 2건**: #1170 문서-only 시정 + 살아있는 위반(`test_failover.py:304`) · SonarCloud "외부 장애" 조기 귀인. 세션5 회고(wf_317714e4·61확정) 미아카이브로 카운터 ~4배 오보 |
| 2026-07-24 | 🔴 **소실 — 복구 불가** | 세션8 에서 5+1 회고가 **실제로 수행**됐다(run `wf_1a8ad24b`·111 에이전트·확정 **80**[P0 0·P1 18·P2 62]·verdict_coverage 1.0·FP 10 — `docs/STATE.md`·`docs/cycle-history.md` 가 명시). 그러나 **보고서가 한 번도 작성되지 않았고**(`git log --all --diff-filter=A` 로 확인 — 삭제가 아니라 미생성), `~/.claude` 하위에 `wf_1a8ad24b` journal 도 남아 있지 않아 **2026-07-18 건과 달리 복구 원천이 없다**. 결과: 카덴스·스코프 기계가 직전 회고를 2026-07-22 로 오인 → "42 PR breach" 발화(실제 갭 ~20) → **2026-07-26 회고가 22 PR 을 중복 재검토**. 80 findings 의 분석 서사는 영구 소실. 미아카이브 **3회차**(:77·:80 에 이어) |
| 2026-07-26 | [retrospective](2026-07-26-retrospective.md) | #1175~#1218 + **본 세션 자기 산출물** 5+1 회고 — **197 에이전트**(0 error)·20.23M 토큰·확정 **161**(P0 **2**·P1 59·P2 100)·FP **12**·severity_adjust 53·verdict_coverage 1.0. 지배 주제 = **"옳은 일을 하면 빨개지는 가드" 의 쌍대 발견** — owed 원장이 42 PR 동안 0행이고 훅은 빈 원장을 green 으로 읽는다(**부채 미등재가 가장 싼 통과 경로**, P0-2). 🔴 **관측면이 자기 입력에 눈이 멂**(카덴스 기계의 입력인 보고서 파일이 인간 기억 의존 — 워크플로는 보고서를 쓰지 않는다). 2차 주제(형제 유추) **확산 확인** — 라이브 프로빙이 `#1208` `@` escape 가 **GitHub 에서 완전 no-op** 임을 반증. P0-1(credential 훅 복합명령 fail-open) = #1219 봉인 |
| 2026-07-31 | [retrospective](2026-07-31-retrospective.md) | #1221~#1247(22 PR) + **본 세션 자기 산출물** 5+1 회고 — **188 에이전트**(0 error)·16.9M 토큰·확정 **156**(P0 **8**·P1 72·P2 76)·FP **8**·severity_adjust 42·verdict_coverage 1.0. 지배 주제 = **지배 서사가 그 서사를 고친 PR 자신에게서 재생산** — `#1243`(훅 부활) 회귀 가드 0 · `#1244`(원자적 claim) **잠금 무동작**(`populate_existing` 부재 → 패자도 gate+notify **2회**) · `#1230`(정책 19 집행면) 면제 마커 미계량(seal PR 10건 중 **5건 면제 통과**). 🔴 신규 명명 = **"관측자가 자기 범위를 관측하지 않는다"**(`check_memory_refs` 죽은 경로로 영구 skip · B8 범위 비어도 "fail-open 0" 출력 · `check_docs_sync` 는 4지점 동시 오류를 원리적으로 못 봄). 병행 Grok claim-review(`019fb7fd`) = 배선 판정 substring **BROKEN**, 뮤테이션 12건 중 **11 GREEN** → #1248 로 7/7 RED 전환. 자기 적발 = 세션이 만든 worktree 가 **루트 grep 100% 인플레** |
| 2026-08-08 | [retrospective](2026-08-08-retrospective.md) | #1297~#1314(18 PR) + 세션17 자기 산출물 5+1 회고 — **11 에이전트**·verdict_coverage **1.0**. 🔴 **지배 주제 = 진단의 처방이 진단이 지목한 결함을 재생산했다** — 이 창이 만든 게이트 4개(P1~P4) 중 **3개가 같은 형태로 결함**(면제 마커 관용구는 복제하고 **하드닝은 복제하지 않음** → HTML 주석 은닉 면제 = R20 결함 1 의 3중 재발). 확정 P0 **5건** 전건 당일 봉인(`#1315`·`#1316`). 🔴 최대 수확 = **`6840` 은 사람의 오판독이 아니라 계기 오염**이었다 — 머지 충돌 중 `git ls-files` 가 stage 1/2/3 을 내어 parametrize 2곳에서 파일당 +4(`6824 + 4×4`), 그 값이 4지점 파생 전파 → 사본 일치로 `check_docs_sync` ✅ → main **12h49m red**. `#1308` 의 "오판독" 규명이 틀렸고, 그래서 처방이 전파 차단에 머물렀다. 🔴 **회고가 못 잡은 것을 Grok 이 잡았다**(`019fe026` — 1 BROKEN·2 WEAKENED): 이월 마커 봉인이 **merge commit 으로 머지하면 그대로 무력**(`allow_merge_commit`·`allow_rebase_merge` 둘 다 켜짐 실측)이고, 내 테스트는 `_git_text` 를 mock 해 **머지 토폴로지를 한 번도 실행하지 않았다**. 교훈 = *"게이트가 작동하는가"* 와 *"이 봉인을 어떻게 깨는가"* 는 **다른 질문**이고 후자만 이 결함을 찾았다. 원장 등재 = **R69~R73**. R48 판정 = 질문을 *"돌렸는가"* → *"본문 숫자가 기계값에서 파생됐는가"* 로 전환 권고 |
| 2026-08-06 | [retrospective](2026-08-06-retrospective.md) | #1273·#1276~#1293(19 PR) + **세션15·16 자기 산출물** 5+1 회고 — **190 에이전트**(0 error)·16.6M 토큰·2h48m·확정 **147**(P0 **7**·P1 58·P2 82)·verdict_coverage **1.0**. 🔴 **지배 주제 = 혼자서는 못 잡는다** — 확정 중 **3건이 이 세션의 산출물 자체**이고, 그중 하나는 *가드를 만든 그 커밋이 만든 결함*이다(`test_claude_md_behavior_rules.py` 가 정책 17 원칙 3 삭제를 못 잡음 — 뮤테이션 GREEN). 병행 Grok claim-review 4라운드가 **WEAKENED×2 · BROKEN×2** 를 냈고 그중 **가짜 분할 9건**("141개"가 splitter 출력이었다) · **꼬리 축 fail-open 3층** · **`--fix` 쓰기측 fail-open** · **축소가 행동 규칙 8건 삼킴** 이 전부 실측 적발이다. 확정 P0 = pre-commit 13 훅이 이 머신에 **전면 부재**(시크릿 훅 포함, 19 PR 내내 0회 실행·원장 미등재) · `claim-review-not-required` **자기발급 면제 11 PR 중 6건**(가드 트리거를 정책 트리거로 오인) · `retro_scope.py` 가 정책 8-(5) 절반만 구현(미머지 산출물 비가시, `retrospective.mjs` 는 호출조차 안 함) · origin/main CI **6연속 red**(수정본이 미머지 브랜치에만). 원장 등재 = backlog **R56~R62**. 근본원인 = **1회용 측정 도구가 낸 숫자를 검증 없이 사실로 발행**(10건 중 5건) → `AGENTS.md` **측정 규율** 축 신설 |
| 2026-08-04 | [retrospective](2026-08-04-retrospective.md) | #1250~#1272(23 PR) + **세션13·14 자기 산출물** 5+1 회고 — **162 에이전트**(0 error)·14.7M 토큰·2h53m·확정 **123**(P0 **1**·P1 60·P2 62)·FP **17**·severity_adjust 37·verdict_coverage 1.0. 🔴 **P0 후보 8건 중 7건이 cross-verify 에서 강등/기각**(P0→P1 6·FP 1) — 검증관이 실제로 반대편에 섰다. 지배 주제 = **새로 무장한 가드가 자기를 배신한다** — P1 60건 중 **24건이 세션13~14 가 만들거나 손댄 관측면**(심의 게이트 7·회고 워크플로 5·카덴스 원장 5·정책 19 집행면 2·pre_push_gate·훅 5), 결함 클래스 (6) *수정이 같은 결함을 재생산* 의 집중 발현. 확정 P0 = **심의 게이트가 응답 절단(`max_tokens=512`)을 '승인'으로 처리**(`doc_review_gate.py:373` — 파싱 실패 → approve → **stdout 0 무흔적 통과**. 심각도와 fail-open 확률이 정비례하고, 자기 테스트가 그 fail-open 을 정상으로 **고정**한다). 병행 Grok claim-review(`019fc81b`, 주장 트리거 단축 패스) = CLAIM-A **HOLDS**(로컬 재현) / CLAIM-B **BROKEN — 기전 오류**(Claude 재측정 확인: `6607`@3023·`6778`@3105 로 4000자 예산 **안**, 예산 밖은 pylint·커버리지뿐). Grok 메타 발견 = *"A·B 를 모순된 측정으로 취급하는 것 자체가 observer-lie"*. 자기 적발 = **회고 산출물을 커밋하는 중에 R36 이 라이브 재현**(3 에이전트 전건 호출 실패 → 경고 통과, 9회차) + **6-step ② 가 실제 회귀 1건 적발**(신규 보고서 미색인) |

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
