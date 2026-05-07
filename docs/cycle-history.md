# SCAManager 사이클 작업 이력 (사이클 60~83 archive)

> CLAUDE.md tail entry 분리본 (사이클 85 정리 → 사이클 86 사이클 81 추가 → 사이클 87 사이클 82 추가 → 사이클 88 Phase A 사이클 83 추가). 사이클 60~83 historical entries.
> 사이클 84~88+ 직전 5 사이클은 CLAUDE.md tail 보존.
> 본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무.

## 목차

- [Phase F~Phase 12 (그룹 시대)](#phase-f-phase-12)
- [그룹 60+61 (2026-05-02 단일 작업일 23 PR)](#그룹-6061)
- [사이클 62 (2026-05-03)](#사이클-62)
- [사이클 63~64 (2026-05-04 Phase 3)](#사이클-6364)
- [사이클 65~67 (회고 P1 100% 처리)](#사이클-6567)
- [사이클 68~69 (회고 + 정합성 cleanup)](#사이클-6869)
- [사이클 70~72 (정책 15/16 신설 + 토큰 효율)](#사이클-7072)
- [사이클 73~74 (Phase 4 진입 + Phase 2 효율화)](#사이클-7374)
- [사이클 75~77 (5+1 cleanup + Tier B + Phase 옵션 표)](#사이클-7577)
- [사이클 78~80 (Phase 4 5 영역 분할 — Telegram + SaaS + 운영 모니터링)](#사이클-7880)
- [사이클 81 (모바일 Phase 1 MVP)](#사이클-81)
- [사이클 82 (Tier B 묶음 + NEW-P0-1)](#사이클-82)
- [사이클 83 (Tier B 11건 정책 진화 묶음)](#사이클-83)

---

## Phase F ~ Phase 12

- Tier1 정적분석 10종 + Observability (Sentry + Claude metrics + stage timing + MergeAttempt)
- AI 점수 피드백 루프 + Settings Minimal Mode + Onboarding 3단계 튜토리얼
- 5-렌즈 감사 95+ 통과
- Phase F Quick Win + F.1/F.3 완료
- Phase G 완료 (P1-5건 수정)
- Phase 9 자기 분석 루프 방지 완료
- Phase 10 Telegram 확장 완료 (cron + /stats·/connect 명령)
- ~~Phase 11 팀/멀티 리포 인사이트 완료 (author_trend + leaderboard + /insights 대시보드)~~ → **그룹 60+61 폐기 정정 (alembic 0025 + 5-way sync)**
- 툴링 안전장치 (testpaths + ORM-마이그레이션 완전성 검사 67개)
- Phase 12 CI-aware Auto Merge 재시도 완료 (merge_retry_queue + check_suite 웹훅 + 1분 cron)
- Settings UI/UX 리디자인 완료 (수신/발신 웹훅 분리 + 온보딩 배너) → Phase 2A Progressive 재설계 완료 (PR #152, #153)
- UI 감사 사이클 12 PR + 5-에이전트 정합성 cleanup 5 PR 완료
- Loop Guard Layer 3-b 화이트리스트 봇 한정 (PR #100)
- Tier 3 PR-A 완료 (PR #103)
- Phase 4 Critical 테스트 갭 5 PR 완료 (PR-T1~T5, +197 tests)
- Phase H+I 15 PR + 회고/문서 동기화 1 PR (12-에이전트 감사 Critical 10건 100% 처리)

## 그룹 60+61

**그룹 60+61 (2026-05-02 단일 작업일 23 PR) 완료** — Phase 1+2 Insight Dashboard 재설계 (`/dashboard` MVP-B 출시 + 폐기 4종 + Auto-merge KPI + feedback CTA + leaderboard 완전 폐기 alembic 0025) + 5-에이전트 회고 2회 (Phase 1 / Phase 1+2 통합) + 정책 11/12/13 신설 + 정책 2/3/7/11 진화/강화 + P0 OAuth 사고 + 사후 가드 (test_oauth_redirect_uri_smoke 4 + test_oauth_flow_smoke 10 + e2e/test_dashboard 14) + Hook fix (sys.executable → PATH python) + pre-existing 31 fail (단위 7 + 통합 24) 완전 해소 (autouse fixture 패턴) + Phase 3 SaaS 전환 토대 기획 (PR 6분할 안)

## 사이클 62

**사이클 62 (2026-05-03)** — cycle-61 v2 sync (#211) + e2e claude-dark 토큰 회귀 + WCAG 2.5.5 모바일 가드 7건 신설 (#212) + 5+1 에이전트 정합성 cleanup (P0 4 + P1 4 처리) + 정책 14 신설 (GitHub Security 탭 운영 체크 의무 + 첫 적용 사례 #325 fix)

## 사이클 63~64

- **사이클 63** — Phase 3 SaaS 토대 시작 (4/6 PR 머지 #218~#221) — caching 인프라 + insight_narrative service + 라우트/모드 토글 UI + 사용자 신호 default+localStorage. CI fix (pytest fixture lazy ORM import 트랩 → 모듈 최상단 이동)
- **사이클 64 (2026-05-04)** — Phase 3 100% 완료 — Supabase RLS 권한 모델 단일 PR (#223, 1008+ 사용자 명시 단일 결정) + Insight 회귀 가드 e2e 7 + integration 2 (#224) + 5+1 에이전트 회고 (P0 7건: 🔴 RLS 운영 활성화 미들웨어 부재 = 다음 사이클 첫 작업 의무)

## 사이클 65~67

**사이클 65~67 (2026-05-04)** — 회고 P1 100% 처리 종결 — 정합성 cleanup P0 12건 (#226 단위 80건 과대 정정 + Phase 3 누락 5건 + 정책 4건) + pre-existing 5 fail 4 사이클 누적 보류 종료 (#227 conftest setdefault → 직접 set, .env override 트랩) + RLS 운영 활성화 미들웨어 (#228 ASGI + contextvars + event listener LIFO 등록) + legacy NULL backfill 스크립트 (#229 author_login JOIN dry-run) + 잔여 5 P1 묶음 cleanup (#230 caching docstring + 정책 9/10 진화 + R0914 트리 + dialect helper 보류) — 단위 2041→2055

## 사이클 68~69

- **사이클 68 (2026-05-04)** — 4 사이클 종결 회고 (#232 5 에이전트 + cross-verify 생략 첫 사례 + 메모리 4건 신규/갱신) + 사이클 67 회고 P0 4건 정책 진화 묶음 (#233 정책 7 강화 단일 큰 PR + 정책 8 회고 패턴 3 분기 + 정책 2 진화 sync 실측 + 30초 체크리스트 강화) + 사이클 68 종료 sync (#234 4 사이클 종결 회고 + 정책 진화 누적 sync) — 카테고리 분류 별도 PR 보류 (High tier)
- **사이클 69 (2026-05-04 · #235)** — 5+1 깊은 정합성 cleanup — P0 12건 (Critical 5 + High 4 + Medium 3) + cross-verify general-purpose 2회 (1차 false-positive 1건 차단 + 2차 산식 정정 P0 3건 — STATE 헤더 42→45 / retro 합계 46→45 / "신규 2" 모호 제거)

## 사이클 70~72

- **사이클 70 (2026-05-04 · #236)** — 사용자 신규 규칙 2건 정책화 — 정책 15 신설 (코드 작업 전 사전 사고) + 정책 16 신설 (코드 단순화 default — 4 원칙)
- **사이클 71 (2026-05-04 · #237/#238/#240)** — 정책 16 default 적용 첫 사이클 — pure cleanup 5건 + 응집 헬퍼 3건 + gate legacy wrapper 단순화 (-90 LOC). PR 8 (asyncio.gather 병렬화) 영구 보류 (운영 위험). 후속 = Telegram Bot Token PR #227 commit message body 노출 사고 → git filter-branch --msg-filter rewrite + force push origin --all + stale branches 53/53 일괄 삭제
- **사이클 72 PR 1 (#241)** — 정책 16 5번째 원칙 추가 (토큰 비용 효율) + 명시 제외 영역 + 메모리 2건 신설
- **사이클 72 PR 2 (#242)** — Phase 1 옵션 🅓 (데이터 기반 단계 진행) Claude API 비용 모니터링 정확화 인프라 (g-G1 cache 비용 모델 + g-G2 메모리 카운터 + 신규 2 silent fallback WARNING + a-A 메모리/CLAUDE 정정 + e 결과 명시)

## 사이클 73~74

- **사이클 73 (2026-05-04 · #243)** — 사이클 70~72 종결 회고 + sync 페어 (5 에이전트 + cross-verify 생략 + 메모리 3 신설 + 4 강화) + Code Scanning 6건 dismiss API 자체 처리 (4 used_in_tests + 2 false_positive)
- **사이클 73 PR (#244)** — Phase 4 영역 진입 첫 작업 = Code/Secret Scanning F1+F2 + Copilot Autofix 5 + CI fix-up +14 (patch coverage 56.64%→80%+). 단위 2055→2099
- **사이클 74 진입 (#246)** — 사이클 73 종료 sync — Phase 2 후보 4 모두 진행 결정
- **사이클 74 PR-A (#247)** — Phase 2-A Anthropic API 호출당 효율화 묶음: 🅒 신규 1 = `_INSIGHT_SYSTEM_PROMPT` 1024 토큰 패딩 + 🅐 d-🅓 = Insight Haiku 모델 분기 (`claude_insight_model`) + 🅓 a-B = `build_review_blocks` 신규 helper (인프라만). 단위 2099→2105
- **사이클 74 PR-B (#248)** — Phase 2-B 🅑 DB 캐싱 1h TTL 단일 응집 PR: alembic 0028 + `InsightNarrativeCache` ORM (RLS user_id 직접 격리) + repo + service cache read/write + UI route `?refresh=1` + 🔄 Refresh + ⏱ generated_at. 신규 단위 +16 = 2105→2121

## 사이클 75~77

- **사이클 75 진입 (#249)** — 사이클 70~74 종결 회고 + sync 페어. 메모리 신설 3건 + 정정 (메모리 카운트 + 단위 카운트 + 정책 16 line:span)
- **사이클 75 첫 작업** — Railway 운영 alembic 0027 (`SecurityAlertProcessLog`) + 0028 (`InsightNarrativeCache`) 자동 적용 검증 완료 (Project Token + GraphQL deploymentLogs grep — 둘 다 SUCCESS, ERROR/Traceback 0건)
- **사이클 75 P1 묶음 (#250 — 옵션 🅓 단일 응집 PR)** — 정책 본문 진화 묶음 + 메모리 카테고리 분류: 정책 5 강화 (Phase 단계별 진행/종료 신호 분리 의무) + 정책 6 강화 (정책/메모리 본문 작성 시 line:span `grep -n` 실측 의무) + 정책 8 진화 (단일 관점 회고 정량 기준 적용 X + cross-verify ROI 정량 — 사이클당 평균 false-positive 차단 2~5건) + 정책 16 본문 보강 (4 단계 caching 활성화 사례 timeline) + 메모리 카테고리 분류 (≥ 20 임계 도달 — 5 카테고리: 환경 3 / TDD 5 / 협업 6 / 정책 4 / 기술 4 + deprecated 2) + 메모리 카운트 정정 (21→22)
- **사이클 76 (2026-05-04 · #251 추정 머지)** — 전체 문서 + 코드 5+1 다중 에이전트 정합성 cleanup: 1차 5 에이전트 (관점 1~5) P0 24건 + cross-verify general-purpose 6차 종합 = Tier A 8건 정정 (단위 카운트 2055→2122 3 위치 + 정책 7+14 line ref drift + 메모리 4→5 원칙 + STATE 헤더 + tail) + false-positive 차단 3건 (build_review_blocks 위치 / line ref 이미 갱신 / 메모리 :79,89 두 번호 보존) + 신규 발견 3건 (STATE 헤더 stale / CLAUDE.md tail 사이클 76 행 / scan-security 흐름 보강). **정책 8 진화 정량 기준 정합 — cross-verify ROI 양호** (false-positive 차단 3건 + 신규 발견 3건 = 평균 정합)
- **사이클 77 (2026-05-04 · #252)** — Tier B 메모리 line:span drift 정정 + Phase 진행 옵션 표: 사이클 76 회고 승인 후속 — Tier B 3건 즉시 정정 + Phase 2-C/D + Phase 4 후보 5종 옵션 표 작성. 사용자 결정 = Q1=🅐 + Q2=🅑 (5 사이클 분할) + Q3=전부다 (5 영역 모두 권장 ★ 채택) + Q4=NEW-P0-1 (Phase 2 진입 시 fix)

## 사이클 78~80

- **사이클 78 (2026-05-05)** — 영역 🅒 Telegram 본격화 (5 사이클 분할 첫 사이클): PR 1 (#253 머지) `feature_kill_switch` helper 모듈 신설 + 기존 2 사용처 마이그레이션 (NEW-P0-2 — Phase 4 5 영역 진입 의무 페어). PR 2/3/4 = 머지 대기 (사용자 영역)
- **사이클 79 (2026-05-05)** — 영역 🅐 SaaS Phase 1 read-only 종결: PR 1 (#254) alembic 0029 RLS 5 누락 테이블 보강 + PR 2 (#255) admin allow-list + require_admin Depends + `SAAS_MULTITENANT_DISABLED` kill-switch + PR 3a (#256) admin UI + REST API + saas_service (TemplateResponse 신 시그니처 fix-up + Copilot Autofix 3 commit 통합) + PR 3b (#257) `/dashboard?mode=usage` 본인 사용량 (user_id 직접 격리). **단위 2122 → 2178 (+56 회귀 가드 — RLS 6 + admin 11 + saas_service 7 + admin_endpoints 5 + dashboard_usage 9 + kill-switch 17 + telegram 봇 차단 7 등 누적)**
- **사이클 80 (2026-05-05)** — 영역 🅔 운영 모니터링 Phase 2 종결: PR 1 (#259) Sentry PII 스크러빙 강화 (4 → 10 헤더 + URL fragment 제거 + runbook `docs/runbooks/_archive/sentry-activation.md`) + PR 2 (#260) admin operations KPI 5 카드 (`/admin/operations` + `/api/admin/operations` — cache_hit_rate / api_cost / cache 토큰 분포 / merge success / pipeline_latency placeholder + `operations_service` 신설). **단위 2178 → 2214 (+36 회귀 가드 — observability 23 + operations 10 + admin operations 3)** · 옵션 🅒 (1주 baseline 보고서) = 사이클 81+ Sentry 활성화 1주 후 별도 진행 default (NEW-P0-3 정합) → **사이클 85 Sentry 통합 폐기로 NEW-P0-3 자동 폐기**

## 사이클 81

- **사이클 81 (모바일 Phase 1 MVP, 2026-05-05)** — PWA manifest + dashboard 모바일 KPI 우선순위 + settings 모바일 + form sweep (4 PR #262~#265). 통합 84→118 (+34 회귀 가드). `<details>` Progressive Disclosure = Phase 2 보류 (High tier).

## 사이클 82

- **사이클 82 (Tier B 묶음 + NEW-P0-1, 2026-05-05)** — alembic dialect 헬퍼 추출 (사용처 12) + 메모리 신설 2건 + Telegram 봇 차단 silent skip (NEW-P0-1) (#272/#274). 메모리 25→27.

## 사이클 83

- **사이클 83 (Tier B 11건 정책 진화 묶음, 2026-05-05)** — 정책 9 완화 + 정책 8 진화 (단일 작업일 ≥ 5 dispatch 사전 확인) + 정책 3 ⚠️ 마커 정량 기준 + 정책 1 진화 + 정책 5 cross-reference 강화 + 메모리 cross-reference (#279).
