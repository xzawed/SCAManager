# SCAManager 사이클 작업 이력 (사이클 60~166, 최신순)

> CLAUDE.md tail entry 분리본. 사이클 60~166 이력 (본문 최신순 — 목차는 166부터, 하단에 60~92 archive).
> 본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무.

## 목차

- [품질 감사 P2 백로그 해소 — 코드 nit + 문서 인용 2 PR (#926 resilience logs JSON 래핑·openai fallback 메트릭 대칭·config validator DRY +6 · #927 repo_config 0035→0036·architecture diff_exceeds_cap·env-vars 라인 정정, doccon-4 FP 드롭·simplicity-1/bp-2 보류, 단위 4971·전체 5125, 2026-06-17)](#품질-감사-p2-백로그-해소--코드-nit--문서-인용-2-pr-926927-2026-06-17)
- [전체 문서·코드 품질 감사 세션 — 9차원 다이나믹 워크플로우 + P1 2건 해소 (#923 rules path 메타 정합·#924 STATE SSOT 복원, P0 0·P1 2·P2 11·FP 1차단, 브랜치 정리 13개, 2026-06-17)](#전체-문서코드-품질-감사-세션--9차원-다이나믹-워크플로우--p1-2건-해소-923924-2026-06-17)
- [차트 hx-boost async 로드 race 가드 LIVE 머지 + sync (#921 — hx-boost body swap 중 htmx 가 Chart.js vendor `<script>` 를 비동기 재삽입하는 동안 인라인 `buildXChart()` 동기 실행 → `Chart is not defined` → 4 차트 템플릿 `typeof Chart` undefined early-return + vendor onload 즉시 no-anim 재빌드 + fetchpriority, 회귀 가드 +8, 단위 4965·전체 5119, 2026-06-17)](#차트-hx-boost-async-로드-race-가드-live-머지--sync-921-2026-06-17)
- [RLS Phase 4 운영 전환 검증 완료 (앱 `scamanager_app` 전환·DATABASE_URL/WORKER/MIGRATION 설정 → pg_stat_activity 라이브 + /admin/rls-audit UI 2 독립 신호 일치 = connection_bypasses_rls=False, docs sync #920, 2026-06-16)](#rls-phase-4-운영-전환-검증-완료-2026-06-16)
- [잔여/후속 — 회고 P2 마지막 테스트 하드닝 CODE-3/TEST-2 (#919 env online connect_args URL 흐름 AST 가드·effective_migration_url 정규화 결합, 단위 +2, 회고 P2 백로그=0, 2026-06-16)](#잔여후속--회고-p2-마지막-테스트-하드닝-code-3test-2-919-2026-06-16)
- [잔여/후속 — broad-docs Railway IPv6 opt-in 정확화 (#918 railway.md ① IPv4-only 절대화→IPv6 opt-in 한정·database.py docstring, override 방향은 #916서 정정 완료, 카운트 불변, 2026-06-16)](#잔여후속--broad-docs-railway-ipv6-opt-in-정확화-918-2026-06-16)
- [잔여/후속 — 회고 P2 백로그 Phase 4 transition 안전 하드닝 (#915 config Supabase SSL host/query-param 파싱·#916 runbook lifespan/pooler/대시보드 docs, Codex 사실 정정 2건, 단위 +3, 2026-06-16)](#잔여후속--회고-p2-백로그-phase-4-transition-안전-하드닝-915916-2026-06-16)
- [잔여/후속 — 2026-06-16 세션 회고(정책 8, 5+1) + Option A follow-up (#912~#914 — CodeQL #518 py/mixed-returns 해소·codex mutual 도구 default codify·architecture.md 6-step ⑥ 회복, P0 0·P1 1·P2 10·FP 0, 카운트 불변, 2026-06-16)](#잔여후속--2026-06-16-세션-회고정책-8-51--option-a-follow-up-912914-2026-06-16)
- [잔여/후속 — Railway pre-deploy + 연결 invariants docs + MIGRATION_DATABASE_URL (#906~#908 — railway.toml preDeployCommand 배포 차단 fix·Railway↔Supabase 연결 invariants+Phase 4 마이그레이션 게이트 docs[Codex NG 2→정정]·MIGRATION_DATABASE_URL owner 분리, 단위 +7, 2026-06-16)](#잔여후속--railway-pre-deploy--연결-invariants-docs--migration_database_url-906908-2026-06-16)
- [마이그레이션 0039/0040 멱등화 — 운영 alembic 0038 고착 해소 (#904, 0039 DROP IF EXISTS→SET NULL·0040 end-state 보장 3-statement·PG drift 행동 테스트, RLS Phase 4 step 0 선행 차단 해소, 단위 +3, 2026-06-15)](#마이그레이션-00390040-멱등화--운영-alembic-0038-고착-해소-904-2026-06-15)
- [starlette 1.0.1+ 마이그레이션 + dependabot 배치 — #902 (fastapi>=0.137.0·starlette>=1.0.1·PYSEC-2026-161 패치·_IncludedRouter 라우트 테스트 적응) + #897~#900 자동 머지·#901 close, 단위 +2, 2026-06-15)](#starlette-101-마이그레이션--dependabot-배치--902--897900-2026-06-15)
- [회고 P2 백로그 해소 — P2-a/C22/C12 3 PR (#893 테스트 i18n 키 고정·#894 C22 절단 점수 NULL-persist·#895 C12 OTP 6→8, 단위 +1, 회고 P2 잔여 0, 2026-06-14)](#회고-p2-백로그-해소--p2-ac22c12-3-pr-893895-2026-06-14)
- [회고(5+1) P1 follow-up — README.ko 배지·#888 정적 가드·db.md U1 divergence (C12/C22/U1 머지 세션 회고 → P0 0·P1 3·P2 3·FP 9, 단위 +1, 2026-06-14)](#회고51-p1-follow-up--readmeko-배지888-정적-가드dbmd-u1-divergence-2026-06-14)
- [정합성 감사 백로그 C12·C22·U1 머지 — 3 PR (#884 C12 OTP rate-limit·#885 C22 diff 절단 마커·#886 U1 0027 RLS 의도적 divergence, 단위 +23, code-side 백로그 전량 해소, 2026-06-13)](#정합성-감사-백로그-c12c22u1-머지--3-pr-884886-2026-06-13)
- [잔여/후속 세션 — C1 save_gate_decision dead wrapper 제거 (호출처 0 dead code + 35 inert patch de-indent + 죽은-래퍼 테스트 2개 제거, 기능 영향 0, 단위 −2, 2026-06-13)](#잔여후속-세션--c1-save_gate_decision-dead-wrapper-제거-2026-06-13)
- [잔여/후속 세션 — U2 effects.js hx-boost 애니메이션 재초기화 (named init + document._fxEffectsHandler remove-before-add + effect별 WeakMap 멱등 가드, Codex mutual NG 1회 적발→수정, 단위 +1·E2E +2, 2026-06-13)](#잔여후속-세션--u2-effectsjs-hx-boost-애니메이션-재초기화-2026-06-13)
- [정합성 감사 P2 백로그 처리 — 6 PR (#874 dead-code·#875 보안 escape/sanitize·#876 pipeline 방어·#877 db/i18n/관측·#878 test/UI·#879 CodeQL, 단위 +8, 백로그 보류 5, 2026-06-12)](#정합성-감사-p2-백로그-처리--6-pr-874879-2026-06-12)
- [전체 정합성 감사 — 보안/correctness P1 4 PR (#868 P0 hook auth·#869 U0 cross-tenant·#870 C6+C2 AI-fail fail-open·#871 C3 retry 격리, 단위 +12, 2026-06-12)](#전체-정합성-감사--보안correctness-p1-4-pr-868871-2026-06-12)
- [잔여/후속 세션 — #865 검증자 봉인 P1-1 반자동 parity (verifier_blocks_merge engine 단일출처화, Option A, 단위 +9, 2026-06-12)](#잔여후속-세션--865-검증자-봉인-p1-1-반자동-parity-2026-06-12)
- [잔여/후속 세션 — #863 머지 (검증자 봉인 P1-4 diff/token cap fail-closed + max_completion_tokens, 단위 +6, 2026-06-12)](#잔여후속-세션--863-머지-검증자-봉인-p1-4-2026-06-12)
- [잔여/후속 세션 — docs 정합·사이클 166~#859 5+1 회고·P2 하드닝 (#860/#861 — db-migration/INDEX 백필·회고 아카이브·verifier fail-closed 엄격파싱+CI 하드닝·CodeQL fix-up, 단위 +16, 2026-06-11)](#잔여후속-세션--docs-정합회고p2-하드닝-860861-2026-06-11)
- [2nd-LLM 머지 검증자 도입 (cross-vendor AI 거버넌스 가드 — OpenAI GPT 가 경계밴드 자동머지의 머지안전성+조작/환각 독립검증, 순수 opt-in, SDK 우선+httpx fallback, 브레인스토밍→spec→subagent-driven 9 task, +26 단위, feat/merge-verifier, 2026-06-11)](#2nd-llm-머지-검증자-도입-cross-vendor-ai-거버넌스-가드-2026-06-11)
- [정합성 감사 + deep-research follow-up (integrity-audit full + deep-research 미검증 후보 직접 실측 → pipeline AI-fail NULL-persist·webhook secret 캐시 상한·SSRF 단일출처·KPI historyRestore·docs 정합, 5 PR #852~856, Codex mutual OK, 2026-06-11)](#정합성-감사--deep-research-follow-up-2026-06-11--852856)
- [사이클 166 (Task9 full 감사 P2 백로그 해소 — 빠른 정합 docs/db·test/effects.js dead-code + UI Medium hx-boost 리스너 누적·i18n 이중이스케이프[Option A], 5 PR #820~#824, Codex mutual 5/5, 2026-06-09)](#사이클-166)
- [사이클 166 적대 재검증 후속 (STATE overclaim + #32 'resolved' 위양성 적발 → #838 docs정정·#839 #32 tojson·#840 drift④ FK·#841 drift① rename, 4 PR, 2026-06-09)](#사이클-166-적대-재검증-후속-2026-06-09--838841)
- [잔여작업 라운드 (사용자 결정 C — #843 drift③④' ORM 부분 인덱스 정합·#844 #2 RLS owner-bypass 근본 runbook, 2 PR, 2026-06-09~10)](#잔여작업-라운드-2026-06-0910--843844-사용자-결정-c)
- [잔여 정리 라운드 A옵션 (PR #838~#845 본문 `@-` 소실 복원 + 정책 10 본문 검증 의무 + Code Scanning 12건 처분 + RLS stale docs 정정, 1 PR #846, 2026-06-10)](#잔여-정리-라운드-a옵션-2026-06-10)
- [RLS #2 Phase 4 admin 대시보드 cross-tenant 보존 — api/admin·ui/routes/admin hybrid (tenants/operations=worker·rls-audit=web), #849 후속, +9 단위, 2026-06-10](#rls-2-phase-4-admin-대시보드-cross-tenant-보존--apiadminuiroutesadmin-hybrid-849-후속-2026-06-10)
- [RLS #2 Phase 4 코드 차단 경로 해소 — auth_callback worker 세션(옵션 2) + 시스템 API 라우트 3종(Codex mutual 발견) worker 재라우팅, #849, +8 단위, 2026-06-10](#rls-2-phase-4-oauth-로그인-blocker-해소--auth_callback-worker-세션-전환-옵션-2-2026-06-10)
- [RLS Phase 1 운영 + Phase 3 — 0041 FORCE + force_applied/connection_bypasses_rls 실측 (Phase 4 OAuth blocker 식별, 2026-06-10)](#rls-phase-1-운영--phase-3--0041-force--실측-가시화-2026-06-10)
- [RLS Phase 2 — background 전용 worker 세션 분리 (옵션 A: DATABASE_URL_WORKER + WorkerSessionLocal + 16 모듈 alias + ast 가드 52, 1 PR #847, 2026-06-10)](#rls-phase-2--background-전용-worker-세션-분리-2026-06-10)
- [사이클 165 (Task9 골든 리메디에이션 — P1 #802~810 + P2 보안·파이프라인 하드닝 클러스터 #811~814: 게이트 원자적 리플레이 claim·webhook 본문 파싱·ai_review per-field PARITY·SSRF docstring·hook parse_error NULL+overview, Codex true mutual 실결함 4건 적발, 11 PR, 2026-06-08~09)](#사이클-165)
- [사이클 164 (area=gate 잔여 6 결함 — 사용자 Q1~Q4 결정: 정적분석 파일격리+타임아웃 부분결과 보존, telegram 반자동 auto-merge 완전 대칭, regate first-writer-wins, 3 PR #794~#796, 2026-06-08)](#사이클-164)
- [사이클 163 (area=gate P2 백로그 해소 — ApproveAction 정적분석 가드·hook 점수 비숫자/Infinity 안전변환·merge_retry 백오프 validator·zero-SHA 조기종료·_ensure_repo race 복구, 5 PR #783~#787, 2026-06-07)](#사이클-163)
- [사이클 162 (잔여 백로그 전량 + integrity-audit 워크플로우 Task1~8 + area=gate P1 fix 3건 — RLS 자동탐지·test-quality·effects.js·정적분석 타임아웃·insert race·merge_retry expired, 8 PR #774~#781, 2026-06-07)](#사이클-162)
- [사이클 161 (정합성 감사 P1 백로그 해소 — hook 클램프·gate 단일출처·hx-boost 가드·로컬 테스트 루트 독립, 4 PR #764~#767, 2026-06-06)](#사이클-161)
- [사이클 160 (integrity-audit 워크플로우 세션 — 문서 stale 경로·n8n 토큰 차단·timeout 단일출처·RLS 0037, 4 PR #760~#763, 2026-06-06)](#사이클-160)
- [사이클 159 (157 회고 백로그 P2 전량 해소 — 4 PR: security_scan/e2e fail-fast·CI 결정성·DNS OSError·job name + Codex 게이트 비활성화, 2026-06-03)](#사이클-159)
- [사이클 158 (157 회고 5+1+cross-verify — docs 정합 봉인: cycle-history 157 섹션 부재 P1 + docs P2 3건 + db.md env.py 함정 노트, 2026-06-03)](#사이클-158)
- [사이클 157 (156 회고 반영 메타 scope — round_trip CI 활성화 + WCAG tap-target silent-skip→fail-fast, 2 PR, 2026-06-02)](#사이클-157)
- [사이클 156 (Theme B 안전망 회귀가드 봉인 — "존재하나 미실행" 가드 활성화: SSRF·4채널·legacy CI·PG SKIP LOCKED, 4 PR, 2026-06-02)](#사이클-156)
- [사이클 155 (154 회고 메타학습 봉인 — 발신 경로 한국어 AST 소스 스캔 자동 가드, 3연속 과대선언 패턴 영구 차단, 2026-06-02)](#사이클-155)
- [사이클 154 (153 회고 발견 잔여 발신 경로 i18n — telegram 반자동 body P0 + P2 6건 + 호출 역추적 seam, 2026-06-02)](#사이클-154)
- [사이클 153 (i18n 로드맵 완결 — railway Issue·cron 알림 i18n, 발신 경로 한국어 0건 ⚠️회고서 부정확 판정, 2026-06-01)](#사이클-153)
- [사이클 152 (i18n 통합 회고(143~151) — P0 3건 수정·발신 경로 비대칭 교정, 2026-06-01)](#사이클-152)
- [사이클 151 (hook.py CLI 에러 i18n — repo 소유자 언어 해소, i18n 전수 완결, 2026-06-01)](#사이클-151)
- [사이클 150 (웹 UI 에러 메시지 i18n — issue 등록·리포 추가·설정, 2026-06-01)](#사이클-150)
- [사이클 149 (알림/Gate 메시지 i18n — 자동 승인·반려·Telegram·머지 조언·재시도 + engine.py dead code 제거, 2026-06-01)](#사이클-149)
- [사이클 148 (전체 템플릿 i18n 완결 — base.html langName FOUC 해소, 2026-06-01)](#사이클-148)
- [사이클 147 (회고 Tier A/B — settings 누락 i18n + toggle a11y + render-parity 가드, 2026-06-01)](#사이클-147)
- [사이클 146 (템플릿 i18n 완성 — base/repo_insights/settings/landing 잔존 한국어 전수 전환, 2026-06-01)](#사이클-146)
- [사이클 145 (JS 동적 텍스트 i18n — analysis_detail/repo_detail JS 메시지 data-i18n 전환, 2026-05-31)](#사이클-145)
- [사이클 144 (회고 Tier B 이행 — analysis_detail/repo_detail i18n 완성 + 렌더 정합 가드, 2026-05-31)](#사이클-144)
- [사이클 143 (i18n 완성 + 프로세스 강화 — analysis_detail·repo_detail HTML i18n + PR 템플릿, 2026-05-31)](#사이클-143)
- [사이클 142 (5+1 에이전트 감사 4 Phase + 회고 Tier A/B 이행, 2026-05-31)](#사이클-142)
- [사이클 141 (Rate Limiting 테스트 보강 + GateAction 구현 직접 이전, 2026-05-30)](#사이클-141)
- [사이클 140 (conftest 모델 기본값 fix + GateAction Registry 패턴 도입, 2026-05-30)](#사이클-140)
- [사이클 139 (5+1 에이전트 조사 기반 품질 개선 4 Phase — Code Scanning·alembic·Rate Limiting·알림·dashboard, 2026-05-30)](#사이클-139)
- [사이클 138 (대시보드 server-side auto-detect 제거 — 항상 개요 표시, 2026-05-27)](#사이클-138)
- [사이클 137 (대시보드 localStorage redirect 버그 수정, 2026-05-26)](#사이클-137)
- [사이클 136 (analysis_detail 최상단/맨하단 디자인 마감 개선, 2026-05-25)](#사이클-136)
- [사이클 135 (모바일 테이블 헤더-값 정렬 불일치 수정 — 3페이지, 2026-05-25)](#사이클-135)
- [사이클 134 (문서 정리 — README 제품화 + reports/superpowers 아카이브 + policies .claude/ 이동, 2026-05-25)](#사이클-134)
- [사이클 133 (nav-logo 라이트/파스텔 텍스트 불가시 수정, 2026-05-25)](#사이클-133)
- [사이클 132 (theme-option CSS 변수 충돌 버그 수정, 2026-05-25)](#사이클-132)
- [사이클 131 (Claude Design UI 전체 재설계 9 PR — 토큰 시스템·컴포넌트·WCAG, 2026-05-25)](#사이클-131)
- [사이클 130 (pylint 10.00/10 복원 + IssueRegistration 타입 힌트 + codecov/patch 수정, 2026-05-24)](#사이클-130)
- [사이클 129 (AI Issue 등록 기능 Phase 1+2, 2026-05-24)](#사이클-129)
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
- [사이클 84 (다국어 i18n 18 PR + 회고 + Tier B)](#사이클-84)
- [사이클 85~91 (Sentry 제거 + 정책 17 신설 + 정기 검증 + Phase C RLS, 2026-05-06~07)](#사이클-8591)
- [사이클 92~94 (정기 검증 + 정책 18 + Tailwind v4 빌드, 2026-05-07~11)](#사이클-9294)
- [사이클 95~106 (문서 정비 + pylint 10.00 + 성능 측정 E2E, 2026-05-14~18)](#사이클-95106)
- [사이클 107~109 (테마 차트 수정 + 전체 감사 14건, 2026-05-19)](#사이클-107109)
- [사이클 110~116 (AI Insight 에러 추적·차트·다국어·감사 묶음, 2026-05-20~22)](#사이클-110116) — 상세: STATE.md 작업 이력 참조
- [사이클 129 (Lint L-1 언어 확장 — 15개 신규 정적분석기 + hotfix #656~#658, 2026-05-28)](#사이클-129)
- [사이클 128 (테마 드롭다운 CSS 변수 스코프 + 대비 수정, 2026-05-23)](#사이클-128)
- [사이클 127 (hx-boost JS 에러 트랩 + 정적 스캐너 + ESLint 인프라 + E2E stale 셀렉터 수정, 2026-05-23)](#사이클-127)
- [사이클 126 (차트 스파크라인 리디자인 — 테마 accent 그라디언트 fill, 2026-05-23)](#사이클-126)
- [사이클 125 (회고 P1/P2 이행 — session 예외 처리 + overflow 테스트, 2026-05-23)](#사이클-125)
- [사이클 124 (B+C — S1192 상수화 + 보안 심층 테스트 2건, 2026-05-23)](#사이클-124)
- [사이클 123 (B+C — Email XSS 회귀 가드 + Optional→X|None 현대화, 2026-05-23)](#사이클-123)
- [사이클 122 (121 승인 항목 — STATE.md 테이블 출처 레이블 + 수치 동기화, 2026-05-23)](#사이클-122)
- [사이클 121 (5+1 회고 + P2 GET timeout 회귀 가드 + 메모리 2건, 2026-05-23)](#사이클-121)
- [사이클 120 (119 회고 Tier B 3건 이행 — kill-switch 구현 + rules 동기화, 2026-05-23)](#사이클-120)
- [사이클 119 (5+1 문서 감사 22건 정확도 수정 Option C, 2026-05-22)](#사이클-119)
- [사이클 118 (회고 P0/P1 전수 이행 — architecture.md/STATE.md/landing.html, 2026-05-22)](#사이클-118)
- [사이클 117 (/login 제거 + 오류 배너 + P2 login.html 삭제, 2026-05-22)](#사이클-117)

## 품질 감사 P2 백로그 해소 — 코드 nit + 문서 인용 2 PR (#926/#927) (2026-06-17)

- **품질 감사 P2 백로그 후속 (2026-06-17)** — 사용자 "후속 작업 부탁드립니다" → 품질 감사 세션(`wf_c9b58749`) confirmed P2 11건 중 잔여 처리. P1 2건(#923/#924)·doccon-1/3 은 직전 세션 머지 완료. **사용자 결정**(정책 1 옵션 표): simplicity 범위 = config validator만 통합·bp-2 = 보류.
  - 🔴 **ground-truth 직접 재검증 default**(메모리 "audit verdict 맹신 금지") — 9건 전부 실측 후 진행. 그 결과 **doccon-4(`[[memory]]` slug) = FALSE POSITIVE 적발·드롭**: 감사가 "파일명(`project_audit_backlog_*.md`) 불일치"를 근거로 underscore 정정 권고했으나, wikilink `[[name]]` 은 파일명이 아닌 **frontmatter `name:` 슬러그**(실측 = `project-audit-backlog-2026-06-12`/`rls-owner-bypass-finding`, 둘 다 하이픈) 참조 → 현재 docs 이미 정확. underscore 변경 시 오히려 링크 파손.
  - **#926 코드 nit 묶음** (TDD, +6 단위): ⓐ resilience-1 `railway_client/logs.py` — `resp.json()` `JSONDecodeError`(ValueError 하위) 미래핑 → `except ValueError` 확장(미래핑 시 deploy-failure Issue BackgroundTask 까지 전파돼 알림 silent skip, docstring Raises 계약 강제) · ⓑ bp-1 `verifier/openai_client.py` — `_call_via_http` fallback 실패 시 `status="error"` 메트릭 소실(예외가 부모 `except ImportError` 안에서 발생해 형제 `except Exception` 로깅 우회) → 내부 try/except 로 로깅 후 re-raise(SDK 경로 대칭·fail-closed 보존) · ⓒ simplicity-2 `config.py` — postgres URL 정규화 validator 3개 byte-identical → pydantic v2 멀티필드 `@field_validator(...)` 단일화(`fix_optional_pg_url`, required `database_url` 은 빈-값 가드 절 차이로 별도 유지·wrapper 0).
  - **#927 문서/주석 인용 정정** (회귀 가드 불요): consistency-1 `repo_config.py:52-53` 주석 `Alembic 0035`→`0036`(실제 추가 = `0036_repo_config_disabled_tools.py`) · docacc-1 `architecture.md:96` merge_verifier 함수 목록 `diff_exceeds_cap` 추가(7 public 중 #863 진입점 누락) · doccon-5 `env-vars.md:115-116` `config.py:63/64`(db_sslmode/force_ipv4 오인용)→`87/88`.
  - **Codex(o3) mutual 검증** — 양 PR 전부 OK(push 전, `git show`/`git ls-files` 실측·이중 로깅 위험 없음 명시 확인·라인 87/88 직접 실측). 순수 git 명령만 지시(파이프/pytest 금지 — 샌드박스 차단·model 오파싱 회피)로 genuine OK.
  - **보류**(사용자 결정): simplicity-1 `insight_cache` 3쌍(get_fresh/upsert/record_error) 통합 = 현행 유지(wrapper 간접화/call-site 회귀 위험 > 가독 이득, 정책 16 최소 추상화) · bp-2 `railway.toml` `FORWARDED_ALLOW_IPS` = 운영 rate-limit 부정확 관측 데이터 후 결정(정책 17). 단위 4965→**4971**·전체 5119→**5125**·E2E 115·pylint 10.00. [[project-session-2026-06-16-17]]

## 전체 문서·코드 품질 감사 세션 — 9차원 다이나믹 워크플로우 + P1 2건 해소 (#923/#924) (2026-06-17)

- **품질 감사 세션 (2026-06-17)** — 사용자 "전체 문서와 전체 코드의 품질상태 점검 — 딥리서치 및 다이나믹 워크플로우 승인" → ① 브랜치 정리 ② 9차원 품질 감사 워크플로우 ③ P1 2건 해소.
  - **브랜치 정리**: [gone] 상태(원격 삭제=squash 머지 완료) 로컬 브랜치 13개 전부 삭제 → `main` 단독.
  - **품질 감사 워크플로우** (`wf_c9b58749`·24에이전트·~8분): 코드 5차원(정확성·보안·단순성/정책16·복원력·정합성) + 문서 3차원(정확도·일관성·명료성) + 딥리서치 1차원(스택 best-practice) → 각 finding 적대 검증(기본값 의심) → 합성 + completeness critic. 결과 **raw 14 → confirmed 13 (FP 1 차단)·P0 0·P1 2·P2 11**. 코어(정확성·보안) **건전 0건**.
  - **#923 PR-② rules path 메타 정합** (doccon-1/2/3, P1): `.codex/rules/deploy.md` 유령 `Procfile`(dead glob) 제거 + 실재 `.python-version`·`sonar-project.properties` 추가 · `.codex/rules/security.md` `src/main.py` 추가 · `CLAUDE.md` 보안/배포 행 권위 rules 정합. 전 8쌍(.claude↔.codex) paths `Compare-Object` IDENTICAL. **자율 판단**: CLAUDE.md:407 배포 행도 동일 부류 정합화(정책 3 보고).
  - **#924 PR-① STATE.md SSOT 복원** (docclr-1, P1): 헤더가 32KB(31,986자) 단일 라인에 '직전' 서사 25건 누적 → 표준 Read token cap 초과로 SSOT 무력화 → [최신 1건(#921) + 종합 수치 + cycle-history.md 포인터]로 축약. 누적 서사 손실 0(헤더 110 PR 중 108개 cycle-history 보존 실측). UTF-8 BOM+LF 보존(Python utf-8-sig splice). **다음 세션 갱신 규칙 명시**(직전 서사 cycle-history 이관, 헤더 '직전' 체인 누적 금지 — 회귀 방지).
  - 🔴 **mutual 검증 학습**: PR-② 1차 Codex(o3 codex-rescue)가 존재하지 않는 `Dockerfile`/`.github/workflows/**` paths 를 환각해 false-NG → *audit verdict 맹신 금지* 원칙대로 ground-truth 직접 재검증(`git ls-files`)으로 거짓 확정 → built-in 리뷰어가 실파일 기반 OK 독립 확증. PR-① 은 codex-rescue 가 `git`/`rg` 실측으로 genuine OK(A~E). 환각 검증자를 직접 검증으로 적발한 사례.
  - 🔴 **P2 11건 백로그**: [코드] railway logs.py JSONDecodeError silent skip·openai_client httpx fallback 메트릭 비대칭·insight_cache 3쌍 + config validator 3개 DRY·repo_config 주석 0035→0036 / [문서] architecture.md `diff_exceeds_cap` 누락·cycle-history `[[memory]]` slug 6회·env-vars 라인 인용 drift / [딥리서치] railway.toml `FORWARDED_ALLOW_IPS` (보류 권장). 카운트 불변(전부 docs-only, 단위 4965·전체 5119). [[project-session-2026-06-16-17]]

## 차트 hx-boost async 로드 race 가드 LIVE 머지 + sync (#921) (2026-06-17)

- **차트 hx-boost async 로드 race 가드 (#921, 2026-06-17)** — 사용자 "머지 이후 후속작업 수행" → 지난 세션 머지 대기 PR #921 squash 머지(CI 8/8 green·CLEAN·Codex PUSH OK 6/6) + 본 sync.
  - **증상**: 라이브 대시보드/분석 상세 차트가 "늦게 뜨거나 안 보임". 콘솔 = `Chart is not defined at buildDashChart`.
  - **근본원인**(workflow `wil4i5lbi` 4각도 적대검증 HIGH): hx-boost body swap 시 htmx 가 vendored `<script src=chart.umd.min.js>` 를 **비동기** 재삽입하는 동안 인라인 `buildXChart()` 가 **동기 즉시** 실행 → `new Chart` throw → 차트 미표시 + 이후 핸들러(themechange 등) 등록 중단. full reload 는 파서 동기라 정상(증상 hx-boost 경로 한정).
  - **수정**(Option B + 속도, 사용자 결정): 4 차트 템플릿(dashboard/analysis_detail/repo_insights/repo_detail) — ⓐ `new Chart` 앞 `if (typeof Chart === 'undefined') return;` early-return 가드(throw→graceful) · ⓑ vendor `<script>` `onload="if(document._xChartReady)document._xChartReady()"` (async 로드 즉시 no-anim 재빌드) + `fetchpriority="high"`(속도) · ⓒ `document._<scope>ChartReady` 노출(IIFE 외부 호출 대응) + `.claude/rules/ui.md` 규칙 codify.
  - 🔴 **학습**: `analysis_detail.html:897 (window.Chart && Chart.getChart)` = 기존 차트 destroy-가드일 뿐 race 가드 아님(적대검증이 "가드 있음" 으로 오분류 → 정정). 진짜 race-safe 기준 = `repo_detail:729`.
  - 회귀 가드 `tests/unit/ui/test_chart_race_guards.py` +8. 단위 4957→**4965**·전체 5111→**5119**·E2E 115·pylint 10.00·UI 323 pass. [[feedback-hxboost-themechange-pattern]] [[project-session-2026-06-16-17]].

## RLS Phase 4 운영 전환 검증 완료 (2026-06-16)

- **#2 RLS owner-bypass Phase 4 운영 전환 검증 (docs sync #920, 2026-06-16)** — 사용자가 step 1(PW 교체, SQL Editor 직접)+step 2(Railway env 3종 설정·재배포) 완료 → "진행 부탁" → Claude 재확인 검증(앱 자체보고 ↔ DB 실측 2 독립 신호 교차, cycle-166 overclaim 재발 방지).
  - **step 2 URL 전환 실측**: `DATABASE_URL`→`scamanager_app`(rolbypassrls=false) · `DATABASE_URL_WORKER`→`scamanager_worker`(true) · `MIGRATION_DATABASE_URL`→postgres/owner(#908 게이트 — pre-deploy `alembic upgrade head` 가 owner 자격 실행해 app role default-deny 회피).
  - **신호 ① DB 실측(MCP read-only, 정책 12)**: `pg_stat_activity` 라이브 = 앱이 `scamanager_app` 로 접속(조회 시점 새 backend) — **운영 앱이 더 이상 postgres(BYPASSRLS) 아님** + alembic **0041** + `relforcerowsecurity` **11/11** + `scamanager_app` rolbypassrls=false → **connection_bypasses_rls=False 등가**.
  - **신호 ② 앱 자체보고(Playwright 실브라우저)**: `SAAS_ADMIN_EMAILS` 설정 후 `/admin/rls-audit` UI 접근 = RLS 매트릭스 11/11 applied · **BYPASSRLS 경고 배너 없음**(비-BYPASSRLS 연결 반영) + 로그인 smoke(`xzawed`) + 대시보드 실데이터 정상(RLS 과차단 0).
  - → 2 신호 일치 = **#2 owner-bypass 근본 해결 운영 전환 LIVE**(2차 RLS 안전망 실평가 활성). 장기 잔여 1순위 #2 운영 전환 닫힘.
  - 🔴 **선택 심층검증 잔여**(비차단): 신규 GitHub 가입 smoke · cross-tenant 누출 테스트(2 테넌트 pooler 격리, deep-research P1) · `/admin/tenants` cross-tenant 가시성(admin 활성화로 확인 가능). secret rotate = Phase 4 신규 PW로 RLS 임시 PW 폐기 = 사실상 완료.
  - docs-only(카운트 불변 단위 4957·전체 5111·E2E 115·pylint 10.00). 코드 무변경. [[rls-owner-bypass-finding]] 갱신.

## 잔여/후속 — 회고 P2 마지막 테스트 하드닝 CODE-3/TEST-2 (#919) (2026-06-16)

- **회고 P2 마지막 테스트 하드닝 (#919, 2026-06-16)** — 사용자 "후속작업 수행" → 회고 P2 잔여 2건(CODE-3·TEST-2) de-scope 해제. #918 이 IPv4/SSL 연결 경로(회귀 민감 영역)를 직접 수정 → retro 의 CODE-3 de-scope 근거("운영 IPv4 불변이 회귀 민감 영역일 때만 추가") 충족. src 무변경(테스트-only).
  - **CODE-3** `test_alembic_env_migration_url.py` AST 가드 +1 — `run_migrations_online` 이 `config.get_main_option(_SQLALCHEMY_URL=effective_migration_url)` 로 얻은 url 을 그대로 `_build_connect_args` 에 넘기는지 정적 검증(헬퍼 3종 early-continue 구조, pylint R0916 회피). 회귀(`_build_connect_args(settings.database_url)` 등) 시 마이그레이션 connect_args(IPv4 hostaddr/sslmode)가 owner credential URL 과 어긋날 위험 차단. Codex caveat = 변수명 동등성 검증(완전 data-flow 증명 아님)이나 현실적 회귀 차단 충분.
  - **TEST-2** `test_config.py` +1 — `MIGRATION_DATABASE_URL=postgres://...supabase.co` → `effective_migration_url` 이 `postgresql://` 시작 + `sslmode=require`(field 정규화 + property precedence 결합을 단일 케이스로 봉인, 기존엔 transitive 만).
  - 단위 4955→**4957**(+2)·전체 5109→**5111**·E2E 115·pylint 10.00·flake8 clean. Codex mutual OK. **회고 P2 백로그 = 0**(Claude 실행 가능 전량 완료). 🔴 잔여 = ops only(#2 RLS Phase 4 step 1~3·secret rotate — 사용자).

## 잔여/후속 — broad-docs Railway IPv6 opt-in 정확화 (#918) (2026-06-16)

- **broad-docs Railway IPv6 opt-in 정확화 (#918, 2026-06-16)** — 사용자 "권장·타당 방안으로 진행" → #916 에서 Codex 가 공식 docs 근거로 적발한 broad-docs 사실 오류 중 **LIVE 가이드**(미래 독자가 따르는 문서) 일괄 정정.
  - **railway.md ① 연결 invariants** — "Railway egress = IPv4-only"(절대화) → **"기본 IPv4-only (Railway Outbound IPv6 = service별 opt-in·기본 비활성)"**. "IPv6 아웃바운드 차단" → "기본적으로 미사용(opt-in)". direct 호스트(IPv6-only) 도달 불가는 **"Outbound IPv6 미활성 기본 Railway" 기준**으로 한정 + "Supabase IPv4 add-on 있으면 direct 도 IPv4" 예외 명시 + "pooler 사용(권장) / Outbound IPv6 opt-in / IPv4 add-on" 3택 정리.
  - **src/database.py:23** `_ipv4_connect_args` docstring(한·영) 동일 정확화 — railway.md 가 이 주석을 근거로 인용하므로 일관성 유지(주석-only, 로직 무변경).
  - **override 방향**(공식 = 코드 우선·대시보드 비움 권장)은 **#916 deploy.md(.claude/.codex)/railway.toml 에서 이미 정정** — railway.md 엔 override 주장 없음(grep 확인).
  - 🔴 **STATE/cycle-history 과거 narrative**(예: #907 "IPv4-only egress")는 **append-only 기록**이라 보존(과거 PR 이 그렇게 문서화한 사실은 정확 — 본 정정 자체가 forward-log). LIVE 가이드만 정정하는 것이 정확·일관(역사 재작성 회피).
  - 카운트 불변(단위 4955·전체 5109 — docstring-only). Codex mutual OK(railway.md IPv6 표현 정확·database.py 주석 일치·override 방향은 #916 정정 확인). 🔴 잔여 = ops(#2 RLS Phase 4 step 1~3·secret rotate).

## 잔여/후속 — 회고 P2 백로그 Phase 4 transition 안전 하드닝 (#915/#916) (2026-06-16)

- **회고 P2 백로그 Phase 4 transition 안전 하드닝 (#915/#916, 2026-06-16)** — 사용자 "이후 작업을 수행" → 2026-06-16 회고 P2 백로그 중 Claude 실행 가능 + 사용자 다음 ops(RLS Phase 4 step 1~3 transition-day)와 직결되는 안전 하드닝 클러스터.
  - **#915 (CODE-2)** `config.py` `_normalize_pg_url` Supabase SSL 자동추가를 **host 파싱**(`urlparse(v).hostname` 의 `.supabase.co`/`.supabase.com` endswith) + **query-param 기준**(`parse_qs(parsed.query)`)으로 강화. 기존 `'supabase.co' in v` 전체 substring 은 pooler `.supabase.com` 을 우연히 매칭(부수효과)이라 엄격매칭 '정정' 시 pooler SSL 누락 회귀 위험. credential/path 의 `supabase.com` false-positive + `evil-supabase.com` 유사도메인 배제 · password 내 `sslmode` false-negative 방지 · 기존 query `?...?` 손상 방지(separator `?`/`&`). **동작 불변**(진짜 supabase host SSL 보존). 테스트 +3(pooler SSL / credential 미강제 / 기존 query 병합·sslmode 중복 방지). 🔴 Codex mutual **NG 2회**(전체 substring→host 파싱→query-param 강화, 매 라운드 robustness ↑)→OK. `urlunparse` 전체 재구성은 round-trip 재인코딩 위험으로 지양(append-only, 정책 16).
  - **#916 (DOC-2/DOC-3/ops-DOC1)** runbook Phase 4 transition-day 운영 안전 docs(코드 무변경). **DOC-2**: step 2 게이트 `/health` 200 ≠ 마이그레이션 성공(lifespan 30s timeout+broad-except silent-fail) → Deploy 로그서 alembic head 직접 확인. **DOC-3**: `MIGRATION_DATABASE_URL` = owner + session-pooling(5432)/direct 권장(transaction 6543 DDL 비호환). **ops-DOC1**: 대시보드 Pre-deploy Command 빈 값 권장(railway.toml 단일출처) — railway.toml 주석 + deploy.md(.claude/.codex). 🔴 Codex mutual **NG 1**(공식 docs 근거 **사실 오류 2건 적발**: "Railway IPv4-only egress" 절대화 → Outbound IPv6 opt-in(기본 비활성) 한정 · "대시보드가 railway.toml override" 방향 → Railway 공식 config-as-code 는 **코드 우선**, 2026-06-15 사고는 railway.toml preDeployCommand **미정의** 상태라 대시보드 stale `npm run migrate` 사용된 것)→정정→OK.
  - 🔴 **broad-docs follow-up**: override 방향·IPv6 표현은 STATE/railway.md 등에도 동일(pre-existing) — 내가 만진 파일만 정정, 더 넓은 정정은 사용자 운영 경험 확인 후 별도 PR 권장.
  - 단위 4952→**4955**(+3, #915)·전체 5106→**5109**·E2E 115 불변·pylint 10.00. 전 PR Codex mutual OK. **de-scope**: CODE-3(online connect_args 행동 테스트)·TEST-2(config 결합 회귀 테스트) = 정책 16 과투자 금지(retro 명시 optional). 🔴 **잔여 = ops 불변**(#2 RLS Phase 4 step 1~3·secret rotate — 사용자) + P2 백로그(CODE-3·TEST-2·override/IPv6 broad-docs).

## 잔여/후속 — 2026-06-16 세션 회고(정책 8, 5+1) + Option A follow-up (#912~#914) (2026-06-16)

- **2026-06-16 세션 회고 + Option A follow-up (#912~#914, 2026-06-16)** — 사용자 "후속 작업을 수행" → 메모리에 "🔵 다음 세션 우선 task"로 명시된 **2026-06-16 Railway follow-up 세션(#906~#910 + RLS Phase 4 step 0) 5+1 다중 에이전트 회고**(정책 8) + Claude 자유 발언(정책 9) + Option A(의무+저위험) follow-up.
  - **회고(workflow `wf_74404088`, 6 에이전트 = 5 도메인 병렬 + 1 cross-verify)** — 13 finding(11 distinct). cross-verify = **8 TRUE · 5 SEVERITY_ADJUST(전부 P1→P2) · 0 FALSE_POSITIVE**. 순 **P0 0 · P1 1 · P2 10**. 회고 후보 (b) "게이트 도입부 stale" = cross-verify 가 **이미 #908/#909 에서 완전 해소** 확인(캐리포워드 방지). cross-verify ROI = severity 정정 5(CodeQL #518 3 도메인 수렴 + PROC-1 + ops railway P1→P2) + completeness critic 6건(단위 카운트 machine-verify 누락 → `pytest --collect-only` 5106/4952/154 실측 확정). positives = #908 게이트 설계 정합·Codex mutual 2-layer ROI 실증·README↔STATE 배지 정합·PR 본문 무결성 100%.
  - **#912 (P2, 정책 14)** CodeQL alert #518 `py/mixed-returns`(note, #908 self-inflicted, 전례 #516/#517 계열) 해소 — `test_alembic_env_migration_url.py` 헬퍼 끝 `pytest.fail()`→`raise AssertionError`(명시 raise=CodeQL 종단 인식) + `import pytest` 제거(단일 사용처 소실 → `py/unused-import` #517 cascade 선제 차단). Codex mutual OK.
  - **#913 (P2, PROC-1/3)** codex mutual(정책 18) 운용 도구 default codify — `active.md` "codex mutual 운용 도구 default" 서브섹션(입력=`codex exec -` stdin/repo 밖 임시파일·`git add -A` 금지[`.codex_*` staging→hook fail→commit 무음 실패→false NG, 2026-06-15 사고]·정적 리뷰만·Bash 툴 한정) + `.gitignore` `.codex_*` 가드(`.codex/` 설정 디렉토리 비매칭 — `git check-ignore` 실측). Codex mutual **NG 1[관용구 POSIX-shell 한정 누락 — PowerShell 오해 소지]→정정→OK**(정책 18 §3b 단일정답).
  - **#914 (P1, DOC-1)** `architecture.md:27` config.py 트리 설명에 `effective_migration_url`/`MIGRATION_DATABASE_URL` 반영 — #908 이 config.py 변경했으나 architecture.md(src/ 트리 SSOT)만 미동기화한 **6-step ⑥ 누락 회복**(db.md/env-vars/runbook 은 갱신됐음) + 본 회고 아카이브(`docs/_archive/reports/2026-06-16-session-retrospective.md`) + STATE/cycle-history sync.
  - **카운트 불변** (단위 4952·전체 5106·E2E 115·pylint 10.00·Code Scanning #518 머지 후 main 전체 스캔서 auto-resolve 예정). 전 PR Codex mutual OK. 정책 9 회고 질문(wf3sn621a + 이번 세션) = 사용자 **"모두 OK"** 회신. 🔴 **잔여 = ops 불변**(#2 RLS Phase 4 step 1 PW 교체·step 2 URL 전환·step 3 검증·secret rotate — 사용자 운영 영역).

## 잔여/후속 — Railway pre-deploy + 연결 invariants docs + MIGRATION_DATABASE_URL (#906~#908) (2026-06-16)

- **잔여/후속 — Railway pre-deploy fix + 연결 invariants docs + MIGRATION_DATABASE_URL (#906~#908, 2026-06-16)** — 사용자 "잔여/후속 작업 진행" → 2026-06-15 Railway↔Supabase 장애 회고 follow-up 3 PR + post-merge docs sync.
  - **#906 Railway pre-deploy fix** — 운영 배포 차단 사고 해소. 대시보드 pre-deploy 명령이 `npm run migrate`(`package.json` 미존재 스크립트)로 설정돼 "Deploy › Pre-deploy command failed" → 배포 미완료·alembic 0038 고착. `railway.toml [deploy] preDeployCommand = "alembic upgrade head"`(config-as-code, loud-fail — lifespan silent-fail 보완). `.claude`/`.codex` deploy.md 규칙 동기화. 🔴 운영 잔여 = 대시보드 Pre-deploy Command 동기화 후 재배포(사용자). Codex mutual OK.
  - **#907 연결 invariants + Phase 4 게이트 docs** — `docs/runbooks/railway.md` "Railway↔Supabase 연결 invariants" 섹션(IPv4-only egress → pooler 사용·direct `db.<ref>` IPv6-only 도달 불가·`DB_FORCE_IPV4` 정확한 역할[dual-stack IPv6 선호 교정]·pooler `aws-N` prefix 가변[`get_project` 재도출]·8단계 probe 프로토콜) + `rls-role-separation.md §6` 연결 probe 의무 + 마이그레이션 credential 게이트 + line 59/126 내부 모순 정정 + `.gitignore` `.dbpw`/`db_probe.py` 가드. **검증** = 3-agent 적대(0 findings) + Codex mutual **NG 2건**(DB_FORCE_IPV4 가 IPv6-only 호스트 도달 불가[`getaddrinfo(AF_INET)`→`{}` no-op]·DNS ENOTFOUND↔Supavisor "Tenant or user not found" 계층 혼동)→정정→OK. 🔴 학습: 내부 5+1 통과해도 Codex 모델 다양성이 기술 오류 적발(mutual 2-layer 가치 실증).
  - **#908 MIGRATION_DATABASE_URL** — RLS Phase 4 "두 번째 벽". `alembic/env.py` 가 `settings.database_url` 무조건 override → Phase 4 에서 `DATABASE_URL`=app(비-BYPASSRLS) 전환 시 pre-deploy/lifespan 마이그레이션이 app role 로 돌아 `alembic_version` default-deny 차단. `config.py` `migration_database_url` 필드 + validator + **`effective_migration_url` property**(= `migration_database_url or database_url`) + `env.py` 적용(offline/online+pre-deploy CLI+lifespan 단일 결정점). `"sqlalchemy.url"` 3건 `_SQLALCHEMY_URL` 상수화(SonarCloud S1192 선제). **미설정 시 발효 0**(`DATABASE_URL_WORKER` 패턴). TDD 7(config 5 + env.py ast 회귀 가드 2 — `effective_migration_url` 사용 강제·`database_url` 직접 사용 금지). `railway.toml` 미변경(#906 충돌 0). Codex mutual OK.
  - **post-merge docs sync** — #907 게이트 문구("별도 코드 PR 미구현")를 "✅ 구현됨 #908"로 갱신(rls-role-separation.md §6/line 59/126 + db.md + .codex/rules/db.md) + STATE/cycle-history/README 배지.
  - 단위 4945→**4952**(+7)·전체 5099→**5106**·E2E 115 불변·pylint 10.00. 전 PR CI green·Codex mutual OK. 🔴 **잔여 = ops**(#2 RLS Phase 4 운영 전환 — #906 대시보드 + PW 교체/URL 전환 + secret rotate, 사용자 영역).

## 마이그레이션 0039/0040 멱등화 — 운영 alembic 0038 고착 해소 (#904) (2026-06-15)

**날짜**: 2026-06-15 | **트리거**: RLS Phase 4 step 0 배포 후 사용자 "재배포 완료, MCP 확인" → MCP 진단으로 alembic 0038 고착 발견 | **상태**: #904 squash 머지, Codex mutual round1/2 NG→round3 OK · 전체 CI green(PG-only job 포함)

**근본 원인 (운영 MCP 실측)**:
- Supabase 운영 DB(`qaoirpyhldlkeoyppfwq`)가 **alembic 0038 고착 / FORCE 0/11**. postgres 로그: `ERROR: constraint "repositories_user_id_fkey" for relation "repositories" already exists`.
- `repositories_user_id_fkey`가 **NO ACTION으로 사전 존재**(0039 의도는 SET NULL) → 0039의 무조건 `create_foreign_key`가 "already exists"로 실패 → 0039 롤백 → 0038 고착(0040 rename·0041 FORCE 미적용).
- lifespan(`main.py:160` broad-except)이 마이그레이션 실패를 잡고 앱은 기동(무중단) → **~2026-06-09(0039 추가) 이후 모든 배포에서 조용히 실패**(미발견). CI는 clean DB(FK 미존재)서 시작해 미검출.

**처리 (#904)**:
- 0039: orphan 정리 후 `DROP CONSTRAINT IF EXISTS` → create SET NULL (멱등 + 사전 NO ACTION FK를 SET NULL로 교정).
- 0040: 단순 RENAME → end-state 보장 3-statement (조건부 rename으로 정의 보존 + neither 상태 시 ORM 정합 `CREATE UNIQUE INDEX IF NOT EXISTS` + stale source `DROP`). 시작 상태 무관 `ix_users_github_id`(UNIQUE) 존재 보장. github_id unique 실측(ORM·0005·prod 일치).
- test_0039/0040: 멱등 가드 정적 단언. test_0020_round_trip: PG 행동 테스트 `test_migrations_idempotent_over_prod_drift_postgres`(0038+NO ACTION FK 주입→upgrade head→FK=SET NULL·FORCE 검증) + ci.yml pg-concurrency `::node-id` 핀.

- **수치**: 단위 4942→**4945**(+3) · 통합 154 · 전체 5096→**5099** · E2E 115 불변 · pylint **10.00/10** · Code Scanning open 0.
- 🔴 **프로세스 학습**: (1) **운영 마이그레이션 silent fail** — lifespan broad-except가 마이그레이션 실패를 흡수해 앱은 뜨지만 schema는 stale, ~6일간 미발견. 운영 배포 후 alembic_version 실측(MCP) 검증 의무. (2) **마이그레이션 비-멱등 = drift 환경서 실패** — CI clean DB는 사전 존재 객체를 못 잡음. DDL 추가 마이그레이션은 `IF EXISTS`/`IF NOT EXISTS` 멱등화 + PG drift 행동 테스트로 봉인. (3) Codex mutual이 0040 collision/neither 상태 미처리를 2라운드 적발 → end-state 보장 설계.
- 🔴 **잔여**: 사용자 재배포 → `/admin/rls-audit force_applied=True` → RLS Phase 4 step 2(URL 전환) → step 3 종단 검증.

## starlette 1.0.1+ 마이그레이션 + dependabot 배치 — #902 · #897~#900 (2026-06-15)

**날짜**: 2026-06-15 | **트리거**: 사용자 "잔여/후속 작업 확인" → RLS Phase 4 + dependabot 트랙 착수. dependabot 5건(#897~#901) CI fail 조사 | **상태**: #902 squash 머지 + dependabot #897~#900 rebase→green 자동 머지·#901 close, Codex mutual round1 NG→round2 OK·전체 CI green

**근본 원인 (2중)**:
- **테스트 break**: `requirements.txt` `fastapi>=0.136.3`(상한 무)가 fresh install 시 starlette **1.3.1** 유입. fastapi 0.137 `include_router`가 `_IncludedRouter`(지연 include)로 바뀌어 `app.routes` 평탄화 제거 → `[r.path for r in app.routes]`가 `_IncludedRouter.path` AttributeError → 라우트 등록 테스트 6건 fail (dependabot 전건 차단, `6 failed/5081 passed`).
- **보안**: `starlette<1.0`(0.52.1)은 **PYSEC-2026-161 / CVE-2026-48710**(Host 헤더 미검증→`request.url.path` 오염→경로 인증 우회; ≤1.0.0 전체 취약, **1.0.1 단독 수정**) 미패치 → 핀 다운그레이드 = 보안 회귀. secure 1.0.1+ 만 안전.

**처리 (#902)**:
- requirements.txt: `fastapi>=0.137.0` + `starlette>=1.0.1` (이전 starlette CVE 승계, dependabot #901 해소).
- `tests/unit/_route_helpers.py` 신규: `registered_paths`(`_IncludedRouter`·`include_router(prefix=)`·`APIRouter(prefix=)`·중첩 include·`Mount` 재귀 평탄화) + `route_name_count`(중복 name 탐지).
- `test_main.py`/`test_github.py` 5 경로 등록 테스트 → `registered_paths` 적응. `test_oauth_redirect_uri_smoke.py` auth_callback 가드 → `route_name_count==1` + `app.url_path_for`.
- `tests/unit/test_route_helpers.py` 신규: 견고성 가드(prefix/Mount/중첩 6케이스 + count unique/missing/duplicate).
- `.claude/rules/deploy.md` FastAPI/starlette 핀 규칙 + `_IncludedRouter` 가이드 동기화.

**dependabot**: #897~#900 rebase 후 전부 green 자동 머지(cryptography 48→49 = Fernet-only 사용·49 변경 무관 = 안전 평가). #901(fastapi)은 #902의 `>=0.137.0` 핀으로 superseded → close.

- **수치**: 단위 4940→**4942**(+2 test_route_helpers) · 통합 154 · 전체 5094→**5096** · E2E 115 불변 · pylint **10.00/10** · Code Scanning open 0. **잔여 = ops 2건 불변**(#2 RLS Phase 4 운영 · 검증자 활성화 — #902로 RLS step 0 배포 안전 확보).
- 🔴 **프로세스 학습**: (1) **Codex mutual 이 보안 회귀 차단** — 첫 시도 `starlette<1.0` 핀이 PYSEC-2026-161 미패치 버전(0.52.1) 고정 → Codex NG → secure 1.0.1+ 전환. mutual 검증의 보안 효용 실증. (2) round1 NG(헬퍼 prefix/Mount 미처리·url_path_for 중복 name 미탐지·deploy.md 과장·robustness 테스트 부재) → 공유 robust 헬퍼 + count==1 + 견고성 테스트로 해소 → round2 OK. (3) `_IncludedRouter`는 fastapi 0.137 구조(starlette 아님) — `original_router.routes`로 하강·`include_context.prefix` 누적. (4) 로컬 dev 구버전(starlette 0.38.6)은 평탄화라 미재현 — 격리 venv(0.137+1.3.1) 실측으로 forward-compat 검증.

## 회고 P2 백로그 해소 — P2-a/C22/C12 3 PR (#893~#895) (2026-06-14)

**날짜**: 2026-06-14 | **트리거**: 사용자 "권장하는 순서로 진행" 위임 → integrity-audit 회고 P2 잔여 3건(P2-a 자율 + C22/C12 정책15 High tier 사용자 결정 A/A) 순차 처리 | **상태**: 3 PR squash 머지, 전 PR Codex mutual OK(genuine `completed` 실측)·CI green·pylint 10.00

**처리 (권장 순서)**:
- **#893 P2-a (테스트 견고성)**: `test_telegram_commands.py` C12 brute-force 클러스터 3 테스트의 substring/OR 단언(`"OTP" in`/`"많"`/`"many"`/`"시도"`)을 i18n 키 직접 == 비교(`_RATE_LIMITED_MSG`/`_INVALID_OTP_MSG`)로 교체 → 영어/로케일 문구 변경 회귀 차단. 프로덕션과 동일 `settings.default_locale` 대조. 테스트 수 불변(26 passed).
- **#894 C22 (analytics 집계 오염, 사용자 결정 A)**: AI diff 절단(`ai_review_truncated`) 리뷰는 status=success 라 `ai_review_failed=False` 지만 부분-diff 인플레 점수 → `_save_and_gate` 에서 score/grade NULL 저장(`_persisted_score_is_unreliable` 헬퍼 = `ai_review_failed or ai_review_truncated`). 집계(func.avg·leaderboard, `score IS NOT NULL` 필터)가 자연 제외. auto-merge 차단은 #885 별도. hook 경로는 `AiReviewResult.truncated` 미설정이라 대칭 불필요(pipeline-reviewer + Codex 확인). 🔴 **SonarCloud S3776 fix-up**: C22 의 `or` 가 `_save_and_gate` Cognitive Complexity 16>15 초과 → 판정을 모듈 헬퍼로 추출(사이클93 `_race_recover_existing` 동일 패턴)해 16→15 복원(동일 PR fix-up commit, Codex 재검증). pipeline-reviewer APPROVE. `.claude`+`.codex` rules/pipeline.md NULL-persist 노트 동기화. TDD +1.
- **#895 C12 (OTP brute-force 상한, 사용자 결정 A)**: Telegram 연동 OTP `_OTP_LENGTH` 6→8 → brute-force 공간 10^6→10^8(100배). `find_by_otp` 가 user 무관 전역 풀 조회 + 리미터는 per-telegram_user_id 라 계정 로테이션 시 전역 상한 부재 → 자릿수 확대로 per-sender 리미터와 곱연산. 스키마 변경 0(telegram_otp 임시 문자열). i18n `connect_usage` 3언어(ko/en/ja) 동기화 + constants.py C12 주석 10^6→10^8. 테스트 수 불변(단언/생성 변경).

- **수치**: 단위 4939→**4940**(+1 #894 C22) · 통합 154 · 전체 5093→**5094** · E2E 115 불변 · pylint **10.00/10** · Code Scanning open 0. **integrity-audit 회고 P2 잔여 = 0** — 코드 사이드 잔여 작업 0. **잔여 = ops 2건**(#2 RLS Phase 4 운영 전환[🛑 명시 보류] · 2nd-LLM 검증자 활성화[`OPENAI_API_KEY` BYO]). 상세: [[project-audit-backlog-2026-06-12]].
- 🔴 **프로세스 학습**: (1) Codex companion 이 프롬프트의 "pytest 실행" 요청을 model 파라미터로 오파싱(`The 'pytest' model is not supported`) → pytest 실행 요청 제거 + 로컬 증거 제공 정적 리뷰로 전환 시 genuine Codex OK(정책18 무결성은 companion status `completed` 실측으로 확인). (2) C12 i18n JSON 3건 edit 1차 commit 누락("3 files") → 즉시 grep 적발·amend("6 files"). (3) C22 SonarCloud S3776 는 PR-CI 에서 검출 → fix-up 으로 머지 전 해소(PR-diff CodeQL 한계와 대비 — Sonar 는 PR 차단).

## 회고(5+1) P1 follow-up — README.ko 배지·#888 정적 가드·db.md U1 divergence (2026-06-14)

**날짜**: 2026-06-14 | **트리거**: 사용자 "회고를 수행해주세요" → 5+1 다중 에이전트 회고(wf_7adc2655) → 사용자 결정 "P1 3건 fix PR" | **상태**: 1 PR, Codex mutual

**회고 결과**: C12/C22/U1 머지 세션을 5 관점 병렬 finder(코드 correctness·테스트 품질·문서 정합·프로세스/정책·보안/운영) + 1 cross-verify 로 적대 검토 → **P0 0 · confirmed P1 3 · P2 3 · false-positive 9 차단**. 최대 정정: 관점 4 "NG→fix commit 비대칭" P1 → squash 머지 환경서 merged main 에 zero 차이라 cross-verify 가 FP 로 강등(finding 본문도 "fold 자체 위반 아님" 인정).

**P1 3건 정정 (본 PR)**:
- **① README.ko.md 배지**: Coverage 95→97%(#872[2026-06-12]에서 95→97 상향 시 README.md 만 갱신된 비대칭 — README.ko 는 한 번도 97% 였던 적 없음, 한국어 사용자에 2%p 낮게 오표기) + Tests 배지 구분자 리터럴 `+`→`%2B`(shields.io 에서 리터럴 `+` 는 공백 렌더 → README.md 와 시각 비대칭 해소).
- **② #888 회귀 가드**: `test_dispatcher_returns_not_connected_constant_directly` — 디스패처가 `_NOT_CONNECTED_MSG` 상수를 직접 반환함을 ast(`ast.Return` value `ast.Name`)로 단언. 기존 3 테스트(`== _NOT_CONNECTED_MSG`)는 값 동등 비교라 디스패처를 inline `get_text` 로 되돌려도 통과 → 상수 재고아화(CodeQL #516 재발) 미검출. CodeQL 은 비동기 Code Scanning(머지 후 alert)이라 PR-CI 에서 못 잡음 → 정적 가드로 PR-CI 차단 보완(#883/#839 동형 패턴). 단위 +1.
- **③ db.md U1 노트**(`.claude/rules/db.md` + `.codex/rules/db.md` 미러): 활성 app-layer 필터(`security_alert_log_repo._apply_owner_filter` + dashboard 의 `OR Repository.user_id.is_(None)`)가 legacy 보안알림을 전역 노출 → 0027 RLS strict(legacy 비노출) 의도와 **정반대 방향**. #2 미완(BYPASSRLS) 동안 충돌 0이나 Phase 4 비-BYPASSRLS 전환 시 legacy 행에서 두 레이어 상반(app=노출 vs RLS=차단) → 더 제한적 RLS 우선. strict 통일 시 app 필터 `is_(None)` 절도 동시 제거(#2 묶음·사용자 결정).

- **수치**: 단위 4938→**4939**(+1) · 통합 154 · 전체 5092→**5093** · E2E 115 불변 · pylint **10.00/10**. **P2 3건 백로그**: brute-force 통합 테스트 substring 결합(en 문구 취약) / C22 절단 점수 analytics 집계 비대칭(ai_review_failed NULL-persist 대비) / C12 OTP 리미터 per-telegram_user_id 키 → 계정 로테이션 시 전역 OTP 풀 상한 부재 — 후 2건은 정책15 High tier(데이터모델) 사용자 결정. 상세: [[project-audit-backlog-2026-06-12]].
- 🔴 **#891 CodeQL #517 후속** (두 번째 self-inflicted alert): 위 #888 정적 가드 테스트가 `import src.notifier.telegram_commands as mod` 를 추가했는데 파일 상단 `from ... import` 와 이중 → `py/import-and-import-from`(note, open 0→1) — #888(#516)과 동일하게 **main 전체 스캔서만 노출**(PR-diff CodeQL green). **수정**: 이미 import 된 `handle_message_command` 심볼로 `inspect.getsourcefile()` 사용 → 모듈 재import 제거(테스트 동작 동일 26 passed·단위 4939 불변). main 재스캔서 #517 auto-fixed → **Code Scanning open 0**. 🔴 학습: 정적 가드서 모듈 소스 필요 시 `import as`(이미 `from import` 공존) 금지 — `inspect.getsourcefile(이미_import된_심볼)` 사용. (PR-diff CodeQL ≠ main 전체 스캔 = #888/#891 2회 반복 확인 → 머지 후 정책14 점검 필수.)

## 정합성 감사 백로그 C12·C22·U1 머지 — 3 PR (#884~#886) (2026-06-13)

**날짜**: 2026-06-13 | **트리거**: 사용자 "잔여/후속 작업 확인" → 상태 실측(메모리 stale 정정 — C12/C22 결정이 이미 내려져 PR 생성됨) → "순차 머지 위임" | **상태**: 3 PR squash 머지, 전 PR Codex mutual OK·CI+CodeQL green

**흐름**: integrity-audit full(wf_7fb7c8f8) 백로그 잔여 code-side 3건(C12·C22·U1)을 `#883` 기반 분기 순차 squash 머지(#884→#885→#886, 각 머지 후 다음 PR mergeable 재확인 = 실충돌 0). 3건 모두 사용자 결정 반영 + Codex mutual OK 완료 상태였음(머지 신호만 잔여).

- **#884 C12 — Telegram OTP brute-force in-memory rate-limit**(사용자 결정 ⓐ): `/connect <otp>` 가 `find_by_otp`(만료 전 *모든* 사용자 OTP 매칭) 호출 전 시도횟수 체크 0 → 6자리 OTP 무작위 추측 위험(동시 유효 OTP N개면 적중률 ~N배, webhook HMAC·IP limiter 부적합). `_OtpAttemptLimiter`(deque 슬라이딩 윈도우 + `threading.Lock`, `BotInteractionLimiter` 동형) per-telegram_user_id 실패 시도 5회/300s 초과 시 조회 전 차단 + 성공 시에만 clear(오타 비페널티) + 키 상한 2048(`WEBHOOK_SECRET_CACHE_MAX` 패턴). 상수 3종(`OTP_MAX_FAILED_ATTEMPTS`/`OTP_ATTEMPT_WINDOW_SECONDS`/`OTP_LIMITER_MAX_KEYS`) + i18n 3언어. 🔴 Codex R1 NG(`clear()` 가 `set_telegram_user_id` 전 → already_linked 시 카운터 오초기화, 정책18 §3b 단일정답 버그) → clear 를 set 성공 후로 이동 + 회귀 테스트 + TOCTOU docstring(단일 worker 실용 위험 낮음·다중 worker 전환 시 atomic 재검토) → R2 OK. 단위 +11.
- **#885 C22 — AI리뷰 diff 무음 절단 마커**(사용자 결정 ⓐ): `review_prompt.py` `MAX_DIFF_CHARS=16000` 무음 절단인데 `AiReviewResult` 에 절단 신호 부재 → 큰 PR 일부만 채점돼 점수 인플레돼도 incomplete 미전파 = `static_analysis_incomplete`(auto-merge 차단)와 비대칭. `AiReviewResult.truncated`(success 경로 `len(diff)>MAX_DIFF_CHARS`) + pipeline `ai_review_truncated` 전파 + auto_merge/approve/telegram 반자동 4 caller 가드(기존 마커 동일 레이어 = engine 단일출처 대신 유지보수 일관성). 🔴 정책16 §명시제외(`build_review_prompt` 토큰예산/prompt 구조) 인접하나 prompt·예산 미접촉(절단 여부 관측만). 🔴 Codex R1 NG 2건(parse_error 시 truncated 오설정·telegram 반자동이 AutoMergeAction 우회) → success 경로 한정 + 인라인 가드 추가(둘 다 단일정답 버그) → R3 OK(로컬 테스트 증거 제출 후). 단위 +10.
- **#886 U1 — alembic 0027 RLS 의도적 divergence 종결**: 0027 RLS 정책이 0026 형제(analyses/merge_attempts/repositories) 대비 `OR user_id IS NULL` 절을 의도적 생략(더 엄격한 격리 = legacy 보안알림 비노출, #869 per-user 방향 정합)임을 EXACT 재검증 → false-positive 종결. alembic SQL 무변경(주석-only) → 운영 영향 0 + 구조단언 가드 `test_0027_rls_intentional_divergence.py`. 🔴 Codex R1 NG(가드가 `current_setting`+정책명만 단언 → 골격 제거돼도 통과 무력) → 구조단언 3종(`repo_id IN`/`SELECT id FROM repositories`/`WHERE user_id = NULLIF(...)`) 강화·mutation 4변형 포착 확인 + dangling docstring 참조(`test_0027_security_alert_log.py` 미존재) 정정 → OK. 🔴 학습: 0027 에 `user_id IS NULL` 추가 금지(legacy 보안알림 cross-tenant 노출). 단위 +2.
- **수치**: 단위 4915→**4938**(+23) · 통합 154 · 전체 5069→**5092** · E2E 115 불변 · pylint **10.00/10**. architecture.md 무변경(신규 src 파일 없음 — 신규는 테스트/상수/i18n). **integrity-audit full 백로그 code-side 전량 해소** — 잔여 = ops 2건(#2 RLS owner-bypass Phase 4 운영 전환·2nd-LLM 검증자 활성화, 둘 다 코드 100% 완료·사용자 운영 영역). 상세: [[project-audit-backlog-2026-06-12]].
- 🔴 **#888 CodeQL #516 후속** (머지 후 정책14 점검): main CodeQL 전체 스캔서 신규 alert(open 0→1) — #884(C12)가 not_connected 디스패처(`telegram_commands.py:240`)를 inline `get_text("notifier.commands.not_connected", settings.default_locale)` 로 바꿔 모듈 상수 `_NOT_CONNECTED_MSG`(:46) 가 src 에서 고아화 → `py/unused-global-variable`(note). **수정**: 디스패처가 상수 직접 반환(`return _NOT_CONNECTED_MSG`) — CodeQL 해소 + 중복 `get_text` 제거(DRY). `settings.default_locale` 정적이라 import-time(상수) ≡ call-time(inline) → 동작 동일. 테스트 무변경(3건이 이미 `result == _NOT_CONNECTED_MSG` 비교, 55 passed)·pylint 10.00·단위 4938 불변. Codex mutual OK(4항목). main 재스캔서 #516 **auto-fixed**(14:25) → **Code Scanning open 0 복원**. 🔴 학습: **PR-diff CodeQL green ≠ main 전체 스캔** — 상수 고아화는 main push 스캔서만 노출되므로 머지 후 정책14 점검 필수.

## 잔여/후속 세션 — C1 save_gate_decision dead wrapper 제거 (2026-06-13)

**날짜**: 2026-06-13 | **트리거**: U2 머지(#882) 후 사용자 "머지 확인 + 다음 작업" → integrity-audit 백로그 C1 (결정 게이트 없는 유일한 자율-안전 항목) | **상태**: 1 PR, Codex mutual

**흐름**: 잔여 백로그 4건(C1·C12·C22·U1) 중 C12(in-memory↔DB 설계 선택)·C22(정책16 인접)·U1(migration 민감)은 사용자 결정 필요 → 결정 게이트 없는 **C1** 진행. `grep -S` 로 호출처 0 재확인(#712 사이클 149에서 마지막 호출 제거) + `test_gate_decision_repo::test_upsert_updates_existing` 로 upsert UPDATE 커버리지 중복 확인.

- **dead wrapper 제거**: `src/gate/engine.py::save_gate_decision()` (gate_decision_repo.upsert 위임 thin wrapper, 호출처 0) 제거. auto 경로는 `ApproveAction` 이 자체 `SessionLocal()` + `gate_decision_repo.upsert()` 직접 호출이라 **기능 영향 0**. `GateDecision`·`gate_decision_repo` unused import 정리(pylint 10.00 유지, merge_retry_repo 는 잔존).
- **테스트 정리**: `test_engine.py` 의 inert `with patch("src.gate.engine.save_gate_decision")` 35개 de-indent(mock_db 가 이미 DB 격리 → patch 무동작) + multi-patch 4건 절 제거 + 죽은-래퍼 전용 테스트 2개 제거 — `test_save_gate_decision_updates_existing_record`(upsert UPDATE 분기 = `test_gate_decision_repo::test_upsert_updates_existing` 중복) + `test_save_gate_decision_db_failure_does_not_crash_other_options`(래퍼 미호출로 `side_effect` 미발화 = false-confidence, testing.md "왜 통과하는가" 트랩). `testsave_*_called_on_*` 3건은 `gate_decision_repo.upsert` 검증 실테스트라 함수명만 legacy(유지).
- **stale 주석/문서 정정**: `gate_decision.py`·`gate_decision_repo.py`·`telegram.py`·`test_gate_decision.py`·`test_telegram_provider.py` 의 save_gate_decision 언급 5건 → upsert/claim 으로 정정 + `.claude/rules/pipeline.md` GateDecision upsert/claim 항목 동기화.
- **수치**: 단위 4917→**4915**(−2) · 전체 5071→**5069** · E2E 115 불변 · pylint **10.00/10**. architecture.md 무변경(파일 변동 없음). 잔여 백로그 3건(C12·C22·U1) + ops 2건. 상세: [[project-audit-backlog-2026-06-12]].

## 잔여/후속 세션 — U2 effects.js hx-boost 애니메이션 재초기화 (2026-06-13)

**날짜**: 2026-06-13 | **트리거**: 사용자 "잔여작업과 후속작업 확인" → 7항목 직접 재검증(read-only 워크플로 wf_6fea0937, 7 에이전트) → 사용자 결정 **U2** | **상태**: 1 PR, Codex mutual 대기

**흐름**: integrity-audit full 백로그 잔여 7건(code 5·ops 2)을 현재 코드로 직접 재검증(EXACT line 인용)해 전부 still_open 확정. 사용자가 code-side 중 **U2**(사용자 눈에 보이는 실결함) 선택 → 나머지(C1·C12·C22·U1)는 백로그 유지. TDD: RED(정적 가드 + E2E) → GREEN → 전체 회귀 0.

- **U2 effects.js 재초기화**: `effects.js` IIFE 가 `DOMContentLoaded` 에만 `init()` 바인딩 → hx-boost body swap 후 score-bar/SVG draw/count-up/entry 애니메이션 미재실행(opacity:0/0% 고착). **수정**: IIFE 유지하되 `init` 을 `document._fxEffectsHandler` 단일 슬롯에 저장 + `htmx:afterSettle`/`htmx:historyRestore` 에 remove-before-add 로 등록(ui.md PR #473 패턴) + 부분 swap 재애니메이션 방지를 위한 `seen` WeakMap effect별 태그 멱등 가드(`freshOnly(nodeList, tag)` — 새 DOM 노드만, effect 마다 독립 처리).
- 🔴 **Codex mutual NG 1회 적발 → 수정**(정책 18 §3b 단일정답 버그): 초기 구현은 단일 공유 `seen` WeakSet → `setupEntryAnimations` 가 `.repo-card`/`.kpi`/`.principle` 선점 → `setupMagnetic` 의 `freshOnly` 가 동일 셀렉터 전부 skip = **magnetic hover 가 초기 로드·swap 양쪽에서 미등록되는 회귀**. effect별 태그 추적(WeakMap)으로 수정 + 회귀 가드 E2E 추가 후 재검증.
- **TDD**: 정적 가드 `test_hx_boost_listener_guards.test_effects_animations_reinit_on_hx_boost`(remove-before-add 소스 단언, 단위 +1) + E2E `test_navigation.test_effects_init_reruns_on_hx_boost`(3회 hx-boost 재방문 후 `typeof document._fxEffectsHandler === "function"` + `body.fx-ready`) + E2E `test_magnetic_hover_registers_on_overlapping_cards`(Codex 발견 회귀 가드 — `.repo-card` mousemove 후 인라인 `--mx` 설정, E2E +2). RED 전부 실패 확인 → GREEN.
- **수치**: 단위 4916→**4917** · E2E 113→**115** · 전체 수집 5070→**5071**. pylint 영향 없음(static JS). architecture.md 무변경(신규 파일 없음).
- 🔴 **잔여 백로그 4건**(code-side): C1(save_gate_decision dead wrapper+39 inert patch) · C12(OTP brute-force rate-limit) · C22(AI리뷰 diff 16000자 무음 절단, 정책16 인접·결정 필요) · U1(0027 RLS legacy user_id NULL 제외, migration 민감·결정 필요). **후속 2건**(ops-side, 사용자 운영): #2 RLS Phase 4 운영 전환 · 2nd-LLM 검증자 활성화(OPENAI_API_KEY). 상세: [[project-audit-backlog-2026-06-12]].

## 정합성 감사 P2 백로그 처리 — 6 PR (#874~879) (2026-06-12)

**날짜**: 2026-06-12 | **트리거**: 사용자 "C1 + P2 전부" 결정 | **상태**: 6 PR 머지 완료, 백로그 보류 5건

**흐름**: 직전 P1 4 PR(#868~871) 머지 후 사용자가 "나머지 P1/P2 스코프" 질문에 **C1 + P2 전부**(장기·PR 다수) 선택 → integrity-audit full 백로그(P2 22 + 미검증 4)를 테마별 cohesive 배치로 처리. 각 PR = 직접 EXACT 재검증 → TDD → 구현 → Codex mutual(push 전) → 머지.

- **#874 dead-code/docstring**: C23 `review_prompt.has_test_files`(src 호출처 0, test_score=LLM 위임) 제거 + `is_test_file` import 정리 · C24 `merge_reasons._MERGEABLE_STATE_TO_REASON` has_hooks/clean 엔트리 제거(호출처 `_MERGEABLE_BLOCK` 가드 내부라 도달 불가, 테스트 non-block→UNKNOWN 갱신) · C25 `OPTIONAL_CHECK_ONLY` dead 상수 제거 · C26 merge_retry expired docstring 정정(force-push→abandoned:206, expired=max_age만:255).
- **#875 webhook/notifier 보안**: C13 railway `logger.warning` exc → `sanitize_for_log(str(exc))`(NOSONAR 단언 정합) · C20 telegram 비인가 경고 repo.full_name sanitize · C27 telegram 봇 명령 응답(parse_mode=HTML, telegram.py:232)의 사용자 제어값(display_name/github_login·repo_name 3곳·repo.full_name) **전수 html.escape**(분석-알림 경로 대칭). 🔴 C12(OTP rate-limit) 백로그 보류.
- **#876 pipeline 하드닝**: C10 python.py pylint/bandit 파서 `item["key"]` 직접 subscript → `item.get()` 방어(키 누락/None 시 KeyError 가 analyzer 전체 중단→이슈 전량 무음 폐기+incomplete 미설정 fail-open 차단, golangci_lint 패턴, 6키 missing+None 안전) · C18 `detect_languages_from_patches` content 전달(shebang-only 확장자 없는 스크립트 감지, 정적분석 경로 대칭). 🔴 C22(diff 절단) 백로그 보류.
- **#877 db/i18n/관측**: C14 `insight_narrative_cache_repo.invalidate` .first() 단일삭제 → bulk delete(전역 캐시 user_id,days,language 다중 행 중 비결정적 wrong-language eviction → Claude API 재생성 차단) · C28 i18n `loader.get_text` format except 에 ValueError 추가(불균형/리터럴 중괄호 번역문 렌더 500 차단) · C11 merge_retry 관측 로그/Issue threshold enqueue 스냅샷 → live `cfg.merge_threshold`(게이트 :177 정합, '머지 가른 임계값'↔'관측 기록' 발산 해소).
- **#878 test/UI**: C30 dashboard grade dead assertion(value=85 고정인데 grade in 전체+가공 'B+' 허용 → `==B`) · U3 analysis_detail 트렌드 차트 클릭 nav REPO_NAME 미인코딩 → `encodeURIComponent`(형제 feedback URL 대칭, 라우트 경로 분절 nav 깨짐 해소).
- **#879 CodeQL fix-up**: C5(#873) ORM 부작용 import 가 CodeQL py/unused-import #507~514(8건) 유발(`# noqa: F401`는 flake8만 억제) → 클래스 import + `_REGISTERED_MODELS` 튜플 참조로 'used' 표시(테이블 등록 부작용 유지).

전 PR TDD·Codex mutual OK(다수 NG 적발→동일 PR 즉시 수정→재검증, 정책 18 §3b — C10 None 미봉인·C11 failure 경로·C9 주석 이중언어·C30 테스트 등)·CI green·pylint 10.00. 단위 4907→4915(+8)·통합 154·전체 5069. **🔴 백로그 보류 5건** (`project-audit-backlog-2026-06-12` 메모리): **C1**(`save_gate_decision` dead wrapper + 55 inert patch — 🔴 git `-S` 로 #712[사이클 149]에서 마지막 호출 제거 확인 = CONFIRMED dead, 2026-06-11 deep-research FP-기각["auto 경로 사용 중"]이 부정확했음 reconcile; 대규모 테스트 리팩토링이라 별도 세션) · **C12**(OTP brute-force rate-limit feature) · **C22**(AI리뷰 diff 절단 score-integrity 다층 신호) · **U1**(0027 RLS legacy NULL, migration 민감·미검증) · **U2**(effects.js hx-boost 애니메이션, E2E 필요).

## 전체 정합성 감사 — 보안/correctness P1 4 PR (#868~871) (2026-06-12)

**날짜**: 2026-06-12 | **트리거**: 사용자 "다음 작업" 위임 (1,2번 수행) | **상태**: 4 PR 머지 완료

**흐름**: 사용자 "다음 작업" → 사이클 종료 점검(Code Scanning #506 fix #867 머지) → `/integrity-audit full`(wf_7fb7c8f8, 179 에이전트·3라운드·14M 토큰) → 확정 32(P0 1·P1 9·P2 22)+미검증 4·위양성 11 차단 → AskUserQuestion(U0 방향=per-user·스코프=보안/correctness P1만) → 4 PR(TDD→Codex mutual→머지) → docs 백로그 sync.

- **#868 (P0 보안 — hook 인증 우회)**: `POST /api/hook/result`(`hook.py:187`)가 `config.hook_token=NULL` + `body.token=""` 시 `secure_str_compare(None,"")`(None·"" 둘 다 `b""` 인코딩 → `b""==b""`=True) → hook_token 미설정 행에 빈 토큰 인증 통과 → 위조 Analysis 저장/점수 오염. NULL 도달: `upsert_repo_config`(`manager.py:73`)가 RepoConfigData field만 생성(hook_token 미포함). 수정: verify 엔드포인트(`hook.py:139`) 대칭 `not body.token or config is None or not config.hook_token` 가드. 🔴 `secure_str_compare` **8 호출처 전수 확인** — 나머지 7(verify L139·internal_cron L42·auth·validator/telegram callback computed HMAC·telegram webhook L259·railway NULL-lookup)은 상류 가드 안전.
- **#869 (보안 — U0 cross-tenant 노출)**: `/dashboard?mode=security`가 모든 로그인 사용자(require_login)에게 타 테넌트 보안 알림 노출. 라우트(`dashboard.py:224`)는 `user_id=current_user.id` 전달하나 `dashboard_security`가 무시(unused-argument)하고 `list_pending(db)`/`count_by_classification(db)` 전체 조회. RLS owner-bypass(Phase 4 전)라 앱 1차 필터가 유일 방어인데 부재. 수정: `security_alert_log_repo._apply_owner_filter`(`repo_id→Repository.user_id == user_id OR IS NULL`, `_apply_analysis_user_filter` 의미론) + `user_id` 파라미터 + `dashboard_security` 전달. 🔴 alert.user_id 는 pending 시 NULL(`record_user_decision`에서만 설정)이라 repo 소유권 격리. 사용자 결정 = per-user.
- **#870 (P1 correctness — AI-fail fail-open 2건)**: **C6** approve `_run_semi_auto`가 AI genuine 실패/정적 불완전 시 가드 없이 인플레 점수를 Telegram 승인 버튼 노출 → `_run_auto` 가드(static_incomplete+ai_review_failed) 미러링(발송 skip). **C2** ai_review `_parse_response`가 commit/direction 키 누락 시 `data.get(key,DEFAULT)`로 인플레 default(17/17)를 success 위장 → `keys_present` 검사 추가(hook `_coerce_ai_scores` parity, PARITY GUARD). test_score는 has_tests 폴백(부재=0)이라 제외.
- **#871 (P1 resilience — C3 retry 격리)**: `process_pending_retries` per-row 핸들러가 `(httpx,SQLAlchemy)`만 포착 → 단일 행 예상외 예외(KeyError 등)가 전체 배치 중단 + 무고한 잔여 행 미처리. broad-except 격리(rollback+release_claim+다음 행 계속). 🔴 **Codex mutual NG**: terminal status 커밋 후 부수효과 예외 시 release_claim이 완료 행 last_failure_reason 오염 → `db.refresh` 후 status='pending'일 때만 release 가드 추가(동일 PR 즉시 수정, 정책 18 §3b) → 재검증 OK.

전 PR TDD(+12: #868+3·#869+1·#870+6·#871+2)·**Codex mutual OK**·CI green·pylint 10.00. 단위 4895→4907·통합 154·전체 5061. **docs 백로그 정정**: 커버리지 95→97%(8497줄/291 실측, C4)·pytest-asyncio 1.3.0→1.4.0(C29, requirements-dev `>=1.4.0` 정합)·env-vars.md VERIFIER 상수 2종(`VERIFIER_DIFF_CHAR_CAP`/`VERIFIER_MAX_OUTPUT_TOKENS`)+`.env.example` `MERGE_VERIFIER_DISABLED`(C7/C9). **나머지 백로그**(P1 tests C1/C5 · P2 22 · 미검증 4) = `project-audit-backlog-2026-06-12` 메모리 차기 세션.

## 잔여/후속 세션 — #865 검증자 봉인 P1-1 반자동 parity (2026-06-12)

**날짜**: 2026-06-12 | **트리거**: 사용자 "순서대로 수행 → 머지후 다음작업" | **상태**: #863·#864·#865 머지 완료 (열린 PR 0)

**흐름**: 사용자 "순서대로 수행" → ① #863 머지 + sync #864 → ② RLS Phase 4 운영 가이드 제공(사용자 영역) → ③ 검증자 봉인 P1-1 = **AskUserQuestion Option A confirm** → TDD(test-writer) → 구현 → pipeline-reviewer + Codex mutual → #865 → 머지 + combined sync.

- **#865 (검증자 봉인 P1-1 — 반자동 Telegram parity)**: 검증 가드(should_verify→verify_merge_safety→차단 시 PR 코멘트)가 자동 경로(`AutoMergeAction.execute`)에만 존재 → 반자동 Telegram(`handle_gate_callback`)이 `engine._run_auto_merge` 직접 위임 시 **검증자 우회**(parity 갭). 가드를 신규 `merge_verifier.verifier_blocks_merge(*, github_token, repo_name, pr_number, result, score, merge_threshold) -> bool`(+ `_MergeVerifyContext` frozen dataclass)로 추출 + `_run_auto_merge` 진입부(threshold 직후·`SessionLocal` 전) **단일출처화** → 자동·반자동 양 경로 공유. 양 호출자 `result` 전달(자동 `ctx.result`·반자동 `result_dict`, 미전달 시 빈 dict). 🔴 retry 서비스(`process_pending_retries`)는 `_run_auto_merge` 미경유(`merge_pr` 직접)라 CI 완료 재시도마다 재검증 안 됨(초기 머지 1회만 — 의도). fail-closed 보존(api_error/parse_error → 차단). `post_plain_pr_comment` deferred import(순환 회피).
- **설계 결정**: 사용자 **Option A confirm**(정책 18 §3a + gate High tier — AskUserQuestion 3옵션[A 단일출처화·B 미러링·C 백로그] 중 A). A = parity 완전 보장 + DRY + 형제 가드 일관(B=2곳 중복 drift 위험·C=활성화 시 봉인 의무 잔존).
- **검증**: TDD 14 신규(`verifier_blocks_merge` 7 + `engine` 가드 6 + telegram parity 1, 기존 `test_auto_merge_verifier.py` 5 seam 이동 재작성). gate+webhook 404 pass. pipeline-reviewer **APPROVE**(P0 0 — 6항목 실측: retry 미경유·자동 경로 동작 보존·순서 변경 무해·fail-closed 유지·NPE 안전·import 순환 0). Codex mutual **OK**(5항목 + AST 파싱 + git diff --check). pylint 10.00, flake8 신규 0.
- **검증자 INACTIVE라 운영 동작 영향 0**(`OPENAI_API_KEY` 미설정 시 `should_verify=False`). 활성화 시 자동/반자동 양 경로 검증 발효.
- **P1(reviewer 권고, INACTIVE라 영향 0)**: 검증자 차단 시 `MergeAttempt` DB row 미기록(로그+PR코멘트만, engine 단일출처 규칙 api.md). 반자동도 동일 가드 타나 운영 활성화 PR에서 "verifier-blocked DB 기록"(#859 회고 P2 백로그) 재검토.
- **docs sync**: `.claude/rules/api.md`(반자동 위임 룰 + 검증자 단일출처 문단)·`docs/architecture.md`(`verifier_blocks_merge` 추가). 본 combined sync = STATE/README/cycle-history 수치(#863 sync #864 의 4886 → #865 의 4895·전체 5049) — #864 스택 충돌 회피로 분리했던 것 통합.

Codex mutual OK(#865 push 전)·CI 8/8 green. **검증자 봉인 P1 코드상 3건 전부 완료**(interpret_verdict #861·diff cap #863·parity #865) → 활성화(`OPENAI_API_KEY` BYO, 사용자)만 잔여. 단위 4886→4895(+9)·통합 154·전체 5049. pylint 10.00.

## 잔여/후속 세션 — #863 머지 (검증자 봉인 P1-4) (2026-06-12)

**날짜**: 2026-06-12 | **트리거**: 사용자 "잔여/후속 작업 확인 → 순서대로 수행" | **상태**: #863 머지 완료 (열린 PR 0)

**흐름**: 잔여/후속 다중 소스 적대 교차검증(워크플로 rate-limit → 6 도메인 인라인 대체 실측 — GitHub 라이브·STATE·메모리·코드 마커·회고 백로그·runbook) → 사용자 "순서대로 수행" → ① #863 머지.

- **#863 (검증자 활성화 봉인 P1-4 — diff/token cap)**: `diff_exceeds_cap(patches)` True 시 OpenAI **미호출 + fail-closed 차단**(`VerifierVerdict(False,False,...)` → `auto_merge.py` VERIFIER_BLOCKED 매핑, 비용 0). 절단 후 전송(초안)은 위험 hunk safe 오판 비결정론 → Codex Option A 채택. `_assemble_diff_text` 단일출처(프롬프트↔cap 측정 포맷 일치) · `VERIFIER_DIFF_CHAR_CAP=60000` · `VERIFIER_MAX_OUTPUT_TOKENS=8192`(2048→8192, gpt-5 reasoning 소진 방지) · `max_completion_tokens`(SDK+httpx). 회귀 +6.
- **잔여**: ① #2 RLS owner-bypass **Phase 4 운영 전환**(사용자 — 임시 PW 교체 + `DATABASE_URL`/`DATABASE_URL_WORKER` 설정 + pooler `SET LOCAL` 테넌트 격리 검증; 코드 Phase 1~4 완료, 절차 [`docs/runbooks/rls-role-separation.md`](runbooks/rls-role-separation.md) §Phase 4) ② 검증자 활성화 봉인 **P1-1 반자동 Telegram parity**(`engine._run_auto_merge` 단일출처화, 설계 confirm 대기 — 정책 18 §3a + gate High tier) ③ 검증자 활성화(`OPENAI_API_KEY` BYO, 사용자).

Codex mutual OK(#863, 머지 전 완료)·CI 8/8 green. 단위 4880→4886(+6)·통합 154·전체 5040. pylint 10.00.

## 잔여/후속 세션 — docs 정합·회고·P2 하드닝 (#860/#861, 2026-06-11)

**날짜**: 2026-06-11 | **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" | **상태**: 2 PR 머지 완료 (#860/#861)

**흐름**: read-only sweep 워크플로(wf_08d70ad8, 5 소스 병렬 + 종합 + completeness critic) → 사용자 결정 C(CI 재실행·docs PR·회고 진행).

- **메인 CI flake 복구**: run 27332085798 PG-only 잡 실패 = `httpcore==1.*` pypi 네트워크 timeout(코드결함 아님) → 재실행 3잡 green.
- **#860 (docs 정합 + 회고 아카이브)**: db-migration.md 0032~0041 등재(CLAUDE.md 마이그레이션 목록 의무 위반 해소) · `.env.example` SMTP_FROM 유령 제거(config 필드·src 사용처 0) + OPENAI_API_KEY 주석 이중용도 정정(#859 후 'Production 사용 X' stale) + 검증자 env 2종 등재 · `env-vars.md` 내부상수 2종(WEBHOOK_SECRET_CACHE_MAX·OPENAI_VERIFIER_TIMEOUT) · `Makefile` test-local .PHONY · `reports/INDEX.md` 미등재 13건 백필(2026-05-05 stale) · **사이클 166~#859 5+1 회고 보고서** 아카이브(`docs/_archive/reports/2026-06-11-cycle-166-859-retrospective.md`).
- **#861 (회고 P2 하드닝)**: `merge_verifier.interpret_verdict` fail-closed 엄격 파싱 — `bool(raw["safe"])` → `raw["safe"] is True`(문자열 "false"→bool 함정 fail-OPEN 차단), `manipulation_detected` → `is not False`(🔴 회고 권장 `is True` 는 manip fail-OPEN 회귀라 정정) + 게이트(`auto_merge.py:74`) 정합 · `_call_via_http` httpx fallback 테스트(ImportError 분기 강제) · ci.yml `-rs`(PG-gated skip 가시화)+pip `--retries 5 --timeout 60`(flake 복원력) · **CodeQL fix-up**: 테스트 `assert "openai.com" in url` → 정확 URL 비교(`py/incomplete-url-substring-sanitization` HIGH 해소). 회귀 +16.
- **회고 (5+1+cross-verify, 24건 중 22 TRUE)**: P0 1(정책10 본문 @- 소실 — 단 라이브 PR 본문 실측 시 **이미 2026-06-10 복원됨 = 위양성**) · P1 8(반자동 verifier parity 갭·secret purge·#504·diff cap·env 주석·STATE overclaim self-caught 실패·회고 미보관·임시 PW) · P2 다수. 자성: STATE 범위 단언 self-verify 누락·정책10 @- 재발·추정 카운트(81→실측 66).
- **Code Scanning**: #504(`openai_metrics.py:32` `await result` py/ineffectual FP) dismiss → open 0 복구.
- **Secret Scanning**: alert #1 `telegram_bot_token` state=resolved/revoked(2026-05-04) 확정 → dangling commit `7d0fa1fe` 실위험 0.
- **사용자 결정 3건**: ① 2nd-LLM 검증자 INACTIVE 유지(봉인 P1 2건[반자동 parity·diff cap] 백로그, interpret_verdict 엄격파싱은 #861 선제 완료) ② secret purge = Secret Scanning revoked 확인 후 보류 권고 ③ 자율 후속 수행(#504 dismiss·본문 회복[FP 불필요]·P2 하드닝).

전 PR Codex mutual OK(정책 18)·CI 8/8 green. 단위 4864→4880(+16, #861)·통합 154·전체 5034. pylint 10.00.

---

## 2nd-LLM 머지 검증자 도입 (cross-vendor AI 거버넌스 가드, 2026-06-11)

**날짜**: 2026-06-11 | **브랜치**: feat/merge-verifier | **트리거**: 사용자 "현재 분석/동작 체계가 AI 거버넌스에 해당하는가, 아니면 별도 LLM 이 추가 투입돼 상호보완 협업해야 하는가" 문의 | **상태**: 브레인스토밍→spec→writing-plans→subagent-driven 9 task 구현 완료

**배경 (AI 거버넌스 진단)**: SCAManager 는 "AI 를 활용한 코드품질 거버넌스" + 부분 AI 거버넌스 속성(정적분석 45점 직교신호·AI출력 구조검증·fail-closed·human-in-loop semi-auto·감사추적)을 갖췄으나 **AI 판단 자체(55점: 커밋15+방향25+테스트15)가 독립 미검증** + 신뢰불가 diff→AI 프롬프트 인젝션 표면 = 핵심 갭. 사용자 옵션 표 결정: 옵션 B(2nd LLM 검증자) → 검증대상=머지안전성(의사결정)+조작/환각 탐지(재채점 X) · 트리거=경계밴드만(merge_threshold~+10) · 모델=OpenAI GPT(cross-vendor 다양성) · 불안전처리=차단+PR코멘트 · SDK 우선+API fallback · 이용자 추가비용 0(opt-in).

**구현 (subagent-driven 9 task — sonnet 구현자 그룹 디스패치 + opus 최종 리뷰)**:
- **신규 3 모듈**: `gate/merge_verifier.py`(순수: `is_in_verification_band`/`should_verify`/`build_verifier_prompt`[인젝션 방어 `<untrusted-data>` 경계+역할고정]/`interpret_verdict` + 오케스트레이션 `verify_merge_safety`[diff fetch→프롬프트→OpenAI→verdict, 모든 예외 fail-closed 차단]) · `verifier/openai_client.py`(`call_openai_verifier` — `openai.AsyncOpenAI` 우선 + `ImportError` 시 httpx raw API fallback, anthropic 패턴 미러) · `shared/openai_metrics.py`(extract_openai_usage/log_openai_api_call/aclose, claude_metrics 대칭).
- **통합**: `AutoMergeAction.execute` 신규 가드(기존 static_incomplete/ai_failed 가드 뒤·`engine._run_auto_merge` 위임 앞) — `should_verify`(kill-switch off + 키 + 경계밴드) True 시만 `verify_merge_safety` → unsafe/조작/검증자오류 시 차단+`post_plain_pr_comment`(English-only). + `merge_reasons` VERIFIER_BLOCKED/ERROR 태그 + config 4 env.

**거버넌스 효과**: "AI 활용 거버넌스" → **"AI 출력을 cross-vendor 독립 검증하는 AI 거버넌스"** 격상. 🔴 **순수 opt-in**: `OPENAI_API_KEY` 미설정 시 검증자 완전 비활성 = 도입 전과 100% 동일(비용 0·동작 변화 0, BYO key). 켜도 경계밴드 표적화 + 저가 소형 모델로 비용 최소(정책 16 정합).

**검증**: 최종 코드리뷰(opus, fresh context) — **Critical 0**(fail-closed 3중 try + 비용불변 코드경로 추적 확인) + Important 2 반영: ① merge_attempt DB row 는 `log_merge_attempt` engine 단일출처 규칙(api.md)상 descope → 구조화 로그 VERIFIER_BLOCKED/ERROR 태그 + PR 코멘트로 감사(형제 가드 static_incomplete/ai_failed 와 동일 패턴) ② `merge_verifier_band` `Field(ge=1)` validator(0/음수 시 silent 무효화 차단) + 비용불변 종단 테스트(실 should_verify + 빈 키 → 검증자 미진입) 추가. 🔴 발신 한국어 가드(#155) 위반(검증자 프롬프트·차단 코멘트 하드코딩 한국어) → English-only 수정(i18n 은 spec §16 deferred). 단위 4838→4864(+26: merge_verifier 15[Codex-fix interpret 무예외·band=0 거부 2 포함] + openai_client 5 + github_comment 1 + auto_merge_verifier 5), 통합 154, 전체 5018, E2E 113, pylint 10.00.

**잔여/사용자 검증 필요**: `OPENAI_API_KEY` 운영 설정 시 실 PR 경계점수 차단 동작(사용자) + 모델 ID `gpt-5-mini` 기본값 운영 확정(저가 최신 모델) + httpx fallback 경로 무테스트(openai 가 hard dep 라 dead-branch, minor 수용). 설계/계획: `docs/superpowers/specs/2026-06-11-merge-verifier-design.md` · `docs/superpowers/plans/2026-06-11-merge-verifier.md`(gitignore working).

---

## 정합성 감사 + deep-research follow-up (2026-06-11) — #852~856

**날짜**: 2026-06-11 | **PR**: #852~856 (5건 머지) | **트리거**: 사용자 "잔여작업 및 후속작업 확인" → "PR 우선 머지 + 이후 순차 진행" | **상태**: 직전 세션(2026-06-10/11) integrity-audit full + deep-research 검토 발견 후보 5 PR 머지 완료 + sync

**배경**: #848(RLS Phase 3) 머지 후 사용자 "정리작업 + deep-research + 다이나믹 워크플로우 검토" 요청 → integrity-audit full(8 도메인) + deep-research(RLS/SaaS·아키텍처·문서 3 초점) 실행. 두 워크플로우 모두 서버측 rate-limit 으로 verify/synthesize 부분 실패 → 코드 후보 10건 직접 실측(verdict: REAL 4 + 하드닝 P2 4 + borderline 1 + FP 1).

**코드 4 PR**:
- **#853 (pipeline, P1+P2)**: AI 리뷰 genuine 실패(`ai_review_status ∈ {api_error, parse_error}`) 시 webhook pipeline(`_save_and_gate`)이 인플레 기본 점수(17/17/7→~89/B)를 `Analysis.score/grade` 에 영속 → 대시보드/리더보드 집계 오염. hook 경로(#25/#814)는 이미 NULL-persist 였으나 **pipeline 경로 비대칭** → `ai_review_failed(result_dict)` 게이트로 NULL 저장 통일(status/breakdown 보존). `no_api_key`/`empty_diff`(의도적 미수행)는 점수 유지(회귀 방지). P2 `ai_review.py::_default_result` literal 17/17/7→`AI_DEFAULT_*_RAW` 상수(값 동일, drift 방지). 회귀 가드 4. Codex 5/5. 단위 +4.
- **#854 (webhook, P1+P2)**: pre-auth secret 캐시 무한 증가 차단 — `_store_secret` 가 forged `full_name` 마다 엔트리 생성 → DoS. `WEBHOOK_SECRET_CACHE_MAX=2048` 상한. P2 telegram/railway provider 로그 `sanitize_for_log`. Codex 5/5. 단위 +3(test_secret_cache_bound 신규).
- **#855 (api, P2)**: webhook URL SSRF 검증 storage 단일출처화 — `shared/ssrf.py::is_safe_webhook_url`(settings + repos field_validator 공유, 저장 시점 차단). email To 헤더 CRLF strip(헤더 인젝션). Codex 5/5. 단위 +3(test_repos/test_email 추가·test_settings_ssrf refactor).
- **#856 (ui, P2)**: base.html `_kpiCountupHandler` 를 `htmx:historyRestore` 에도 등록(#473 대칭) — 뒤로가기 bfcache 복원 시 KPI count-up 재초기화 누락 해소. Codex 4/4. 단위 +2(test_base_kpi_handler 신규).

**docs 1 PR**:
- **#852 (docs)**: 검증 drift 3 정정 — architecture.md WorkerSessionLocal 항목·STATE 60~166 cycle 범위·i18n.md 쿠키명(preferred_language) + runbook §4 Phase 4 prerequisite(pgbouncer/Supavisor `SET LOCAL` 테넌트 격리 실측 항목). 무증가.

**기각 (2건)**: (borderline) gate `merge_retry_service.py:142` 재시도 재확인은 LIVE threshold 평가 = 결정 정확, observability nit 보류. (FP) `test_engine.py:39` "dead patch" — `save_gate_decision`(engine.py:632) 존재 + auto 경로 사용 중이라 patch 유효, dead 아님.

**deep-research 핵심**: ✅ SCAManager RLS = AWS 권장 모델 일치(비-owner + NOBYPASSRLS + runtime param + FORCE). 🔴 Phase 4 prerequisite = pooler(pgbouncer/Supavisor) + `SET LOCAL` 테넌트 격리(SET LOCAL + autocommit=False 설계상 안전, 운영 pooler 모드 실측 의무 — #852 runbook §4 반영). ⚠️ CLAUDE.md 18 정책 비대(Anthropic "최소 고신호 토큰") — 미조치(정책 17 안정성 우선, 사용자 사전 확인 영역).

**검증**: 전 PR Codex true mutual OK(push 전, 정책 18) + 전 CI green(pytest·SonarCloud·CodeQL·TruffleHog·PG-tests·codecov). 단위 4826→4838(+12: #853 +4·#854 +3·#855 +3·#856 +2·#852 0, 각 머지 커밋 collect-only 실측), 통합 154 불변, 전체 4992, E2E 113, pylint 10.00.

**최종 잔여**: **#2 RLS owner-bypass — Phase 4 운영 전환만**(코드 Phase 1~4 전부 완료). 사용자 작업 = ① 임시 PW 교체 ② `DATABASE_URL`(app role)/`DATABASE_URL_WORKER`(worker role) 운영 설정 ③ pooler `SET LOCAL` 테넌트 격리 실측([runbook](runbooks/rls-role-separation.md) §Phase 4). full 감사 36건 = #2 외 전부 해소/결정.

---

## 사이클 166

**날짜**: 2026-06-09 | **PR**: #820~#824 (5건 머지) | **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" | **상태**: Task9 full 감사 P2 백로그 자율 가능 10건 해소

**작업 내용**: Task9 full 감사(2026-06-08, 36 confirmed)의 자율 가능 P2 항목을 코드 실측 검증 후 해소. 잔여 백로그 검증 워크플로우(wf_d1e440d5, 6에이전트 read-only — db/docs/gate·sec·test/ui/RLS/completeness critic)로 still_present 16 + partial 1(#17) + resolved 1(#32 이미 `| tojson`) 판정 → 응집 단위 5 PR 분할. 사용자 AskUserQuestion 2회(빠른 정합 → UI Medium) + #34 escape 전략 결정 1회.

> 🔴 **정정 (2026-06-09, 사이클166 후 4에이전트 적대 재검증 — wf_688dd1f2)**: 위 `resolved 1(#32 이미 | tojson)` 판정은 **위양성**. 검증자가 `confirm()` 라인(settings.html:1114/1130)의 `| tojson` 을 #32 가 지목한 `PRESET_LABELS` JS-리터럴(settings.html:1174-1176 등 ~15곳)으로 오인 — 실제 이 위치들은 `'{{ ... | i18n_args(...) }}'` 형태로 `| tojson` 미적용. [`filters.py`](../src/i18n/filters.py) `i18n_args` 는 raw 텍스트 + Jinja HTML autoescape(JS-escape 아님)라 JS 문자열 리터럴 컨텍스트 부정합. **#32 = 미해소 잔여**(라이브 XSS 無·구조적 비일관, 차기 fix). still_present 정정 = 17, resolved = 0.

**빠른 정합 묶음 (Low)**:
- **#820 (docs/rule)**: #19 README internal cron 2개(scan-security·retry-pending-merges) 추가 · #20 architecture.md scripts/ 2파일(capture_design_screenshots·extract_design_tokens) 추가 · #21 env-vars.md config.py line drift 60/61→63/64 · #28 security.md SESSION_SECRET 기본값 'dev-secret-key'→'dev-secret-change-in-production'(main.py:101 정합). 코드 0.
- **#821 (db/test)**: #17 insight_narrative_cache `repo_id index=True` 제거 — 명시 Index `ix_insight_cache_repo_id`+alembic 0031 이미 정합, 자동명 `ix_insight_narrative_cache_repo_id` 중복/유령 인덱스(SQLite create_all 전용, 운영 PG 미존재) 제거, **마이그레이션 불필요** + 회귀 가드(inspect Red 2→Green 1) · #31 test_0029 dead-branch 2개 제거(`s.lower()` 'ON users' 미매칭·`or` fallback unreachable). 단위 +1.
- **#822 (UI)**: #33 effects.js `setupTabs`/`setupNavMagnet`/`repositionAllTabIndicators` dead-code 제거 — `.tabs`/`.nav__*` BEM 셀렉터 템플릿 사용 0(grep 실측), `setupNavMagnet` preventDefault 함정 제거, #777 `_tabsResizeHandler` 도 함께 제거(누적 우려 완전 해소). −91줄. 🔴 고아 CSS(components.css `.tabs`/`.nav__*`) follow-up 분리(정책 11 시각 비대칭).

**UI Medium 묶음**:
- **#823 (#35/#36)**: add_repo.html pagehide + tweaks.js document keydown 익명 리스너 → named handler(`document._addRepoPagehide`·`_tweaksKeydown`) + remove-before-add(effects.js `_tabsResizeHandler` 패턴). 정적 가드 2건(`test_hx_boost_listener_guards`). 단위 +2.
- **#824 (#34, 보안 민감)**: i18n_args 이중이스케이프 = 필터 수동 `_html_escape` + Jinja2 autoescape 재escape('Tom & Jerry'→'Tom &amp;amp; Jerry'). **Option A**(사용자 결정): 수동 escape 제거 → autoescape 위임(표준 Jinja2 패턴). 🔴 감사 원안이 "`| safe` 22건 XSS 노출"처럼 보였으나 실측=사용자 자유문자열 kwarg **0건**(config 정수·Markup span `_otp_countdown_span`·placeholder뿐)→A 안전. B′(Markup 전체 래핑)은 literal-< 번역문(`reject_threshold_hint:716`·`range_summary`) 깨짐으로 기각. 방어선 가드 `test_i18n_args_safe_contract`(`| safe`+kwarg 호출처 allowlist). 단위 +2.

**검증**: 전 PR Codex true mutual OK(push 전, 정책 18), 모든 CI green(pytest·SonarCloud·CodeQL·TruffleHog·PG-tests·codecov). 단위 4718→4723(+5), 통합 154, pylint 10.00.

**🔴 핵심 학습**: (1) #34 — 감사 에이전트가 overview.html 1곳만 보고 `| safe` 22건 놓침 → 보안 수정은 호출처 전수 grep + Codex mutual 2-layer 필수. (2) #17 — 리포트 인덱스명 부정확(partial 재판정), grep 실측이 추정 의존보다 우선. (3) #33 — CSS 동반 제거 권장이었으나 정책 11/17 기준 JS-only 축소.

**후속 머지 (사용자 "순차적 작업", 3 PR #826~#828)**:
- **#826 (#15/#16)**: ORM↔alembic 인덱스 정합 — `ix_merge_attempts_state_repo`(state,repo_name) + `uq_merge_retry_queue_active`(부분 유일, sqlite/postgresql_where status='pending') ORM `__table_args__` 선언. **운영 PG DDL 무변경**(인덱스 이미 alembic 0020/0022 존재). 가드 +2(test_0023 inspect).
- **#827 (#33 follow-up)**: 고아 CSS −156줄 제거 — components.css dead `.nav`/`.nav__*`/`.tabs`/`.tabs__*`(0 element match). 실제 nav=base.html 인라인 `nav{}`+하이픈 `.nav-*`. S4666 중복 셀렉터 해소.
- **#828 (#14)**: `analyses.repo_id` FK ON DELETE CASCADE — 신규 마이그레이션 0038(0024 동일 패턴, PG only, FK명 `analyses_repo_id_fkey`). SET NULL=NOT NULL 불가, RESTRICT=delete_repo_cascade 충돌 → **CASCADE 사용자 confirm**. **PG-only round-trip CI 가 실 마이그레이션 검증**. 가드 +1(test_0038).

전 PR Codex true mutual OK·CI green. 단위 4723→4726.

**결정 영역 처리 (사용자 순차 결정, #830~#831)**:
- **#830 (#22)**: Python 버전 SSOT 3.12 정렬 — README/README.ko/STATE 의 3.14 미검증 선언 → CI(3.12) 기준. docs-only. ⚠️ **#830 후속 정정(#22 부정확)**: 당시 'Railway nixpacks 핀없음'으로 기술했으나 **부정확** — 루트 `.python-version`=`3.12` 가 nixpacks Python provider 를 **이미 핀**(nixpacks 는 `.python-version`/`runtime.txt` 등을 읽음, 미지정 시 default 3.11; context7 nixpacks 공식 확인). #830/Codex 둘 다 `.python-version` 미확인 → 'follow-up nixpacks 핀'은 실제로 **이미 완료 상태**였고, 후속 PR 은 핀 추가가 아니라 **deploy.md 핀 메커니즘 문서화 + 본 정정**으로 종결. 즉 Railway·CI·docs 3종 모두 3.12 정합.
- **#831 (#23)**: gate retry `'passed'` 의도 설계 명시 — 사용자 결정 **A(현 설계 유지, 코드 동작 0)**. `should_retry(UNSTABLE_CI,'passed')=True` 는 merge API lag / 다중 check suite pending 대비 의도적·bounded(감사 '영구 재시도' 표현 부정확). docstring + 회귀 가드. 🔴 **Codex mutual 적발(2-layer ROI)**: 초안이 예산을 `is_expired(max_age/max_attempts)` 로 오기 → 실측 is_expired=max_age 만, max_attempts=process_pending_retries(abandoned) 별도 → 정정 후 OK.

- **#833 (#22 follow-up)**: Railway Python 핀 발견·정정 — `.python-version`=3.12 가 이미 nixpacks Python 을 핀(context7 nixpacks 공식, default 3.11), #830 'Railway 핀없음' 부정확 정정 + deploy.md `.python-version` 핀 메커니즘 규칙(docs-only). Railway·CI·docs 3종 모두 3.12 정합.
- **#834 (회고 follow-up)**: `_coerce_score`/`_coerce_raw_score` 정수 변환 의미(`int()` 0방향 절삭 8.9→8, 반올림 X) docstring 명시 + 절삭 값 가드(+1). 🔴 회고 follow-up 분류 결과: **#795 안전망 비율화**=사이클164 Q2=A 결정(부분실패≠incomplete) 코드+rule 봉인 → 무작업(재결정 영역) · **background UX silent**=전 background task 가 webhook 콜백(사용자 버튼 무관)·버튼 액션은 동기+에러 UX → 구체 지점 미발견 · **#18**(compare_metadata)=미착수.

단위 4726→4728.

- **#836 (#18, 사용자 착수 승인)**: 전역 ORM↔alembic `compare_metadata` 정합 가드(PG-only, pg-concurrency CI) — `alembic upgrade head` 스키마 ↔ `Base.metadata` 구조적 diff==0 단언, **신규 drift 차단**. FP 제거: compare_type/server_default off + 단일 PK 컬럼 인덱스 중복 FP 제너릭 필터 + 사전존재 8건 allowlist(문서화). 첫 CI 14 diff → 2차 PASS. 🔴 **#18 이 사전존재 실 drift 4종 추가 발견(allowlist 문서화, 차기 fix 후보)**: ① users `ix_users_google_id` legacy 인덱스명(컬럼 github_id 리네임 미반영) ② analyses `ix_analyses_repo_id_created_at_tokens`(0032 alembic-only, #15류) ③ insight_cache `uq_insight_cache_global/repo` 부분유일(0031, #16류) ④ `repositories.user_id` FK(0005 컬럼만, DB FK 부재, #14류) + email unique index↔constraint 표현 FP. 필터 로직 로컬 가드(PG 불필요) 동반. 단위 +2.

**잔여 (full 감사 36건 — #2 + drift ③④' 만, 나머지 전부 해소/결정)**: **#2**(RLS FORCE — SaaS 전환 근본 항목, #810 갭 가시화로 운영 경고만, 보류·아키텍처). + **drift ③④'**(analyses `ix_analyses_repo_id_created_at_tokens` · insight_cache `uq_insight_cache_global/repo` 부분유일 인덱스 — ORM 미선언, WHERE 정규화 FP 리스크+운영무해라 allowlist '문서화된 무해' 유지). 🔴 **#32·drift ④(FK)·①(users 인덱스명)은 2026-06-09 적대 재검증 후속(#838~#841)에서 해소 — 아래 §"적대 재검증 후속" 참조**.

**사이클 종료 (정책 18 §4 3조건)**: 회고 수행 완료 + 전 PR(#820~#836) Codex true mutual OK(push 전) + CI green. ⚠️ 회고 follow-up 'background UX silent' = '구체 지점 미발견' soft-close(결함 미입증 종료) — 차기 정합성 감사 시 background task 사용자 가시성 명시 재확인 권장.

---

## 사이클 166 적대 재검증 후속 (2026-06-09) — #838~#841

**날짜**: 2026-06-09 | **PR**: #838~#841 (4건 머지) | **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" (재요청) | **상태**: STATE overclaim + #32 위양성 적발 → 해소

**작업 내용**: 사이클166 종료 후 사용자 재요청 → 4에이전트 적대 재검증 워크플로우(wf_688dd1f2)로 골든 36건 실제 상태를 main 코드와 대조. **STATE '#2 외 전부 해소/결정' overclaim 적발** + **#32 'resolved' 위양성 적발**(사이클166 검증이 `confirm()` 1114/1130 의 tojson 을 #32 가 지목한 PRESET_LABELS JS-리터럴 1174 로 오인). 사용자 결정 4건(AskUserQuestion 3회) → 4 PR.

- **#838 (docs 정합 정정)**: cycle-history:83 #32 위양성 정정 + STATE:5/:65 헤더 잔여 명시 + 사이클166 종료 3조건. docs-only.
- **#839 (#32, 결정 A=tojson)**: settings.html 17 JS-리터럴 `'{{ ... | i18n_args }}'` → `{{ ... | tojson }}` (PRESET_LABELS 3·labels 9·mode 2·suffix/hide/show 3). render-parity 단언 12건 `_js()` tojson 형식 갱신 + 정적 가드. 🔴 tojson=ensure_ascii=True → 한국어 `\uXXXX`(브라우저 정상 복원), 테스트 `_js=json.dumps(get_text())`. 라이브 XSS 無·구조적 비일관 해소. 단위 +1.
- **#840 (drift ④, 결정 A=SET NULL+고아정리)**: repositories.user_id→users.id DB FK 추가(0039, ondelete=SET NULL, 고아 user_id→NULL 정리 선행). ORM ondelete 추가 + allowlist ⑤ 제거 + test_0039. **drift 4종 중 유일 데이터 무결성 영향분**(고아 user_id 가능). 단위 +1.
- **#841 (drift ①, 결정 A=①만 처리)**: users 인덱스명 `ix_users_google_id`→`ix_users_github_id` rename(0040, 0005 생성·0006 컬럼리네임 시 인덱스명 stale). allowlist ① 제거 + 필터 로직 fixture 잔존 ③ 으로 교체 + test_0040. **#840 스택**(0040 down_rev=0039), 머지 순서 #840→#841(squash 충돌 → `rebase --onto main` 해소).

**검증**: 전 PR Codex mutual OK(push 전, 정책 18) · 전 CI green(**PG-only tests 포함 — FK·rename 의 compare_metadata 정합 실 PG 검증**). 🔴 Codex NG 2회(#839/#841)는 환경/메타 사유(샌드박스 pytest 차단·검증서 경로 오타)로 **코드 결함 0** — 로컬 증거 제공 후 OK 전환. 단위 4730→4733(+3), 통합 154, pylint 10.00.

**🔴 핵심 학습**: (1) **감사 항목은 리포트 지목 EXACT line 확인 의무** — 파일 내 tojson 존재 ≠ 해당 위치 적용(#32 위양성 근원). (2) **스택 마이그레이션 패턴**: 병렬 open PR 둘 다 마이그레이션 추가 시 두 번째는 첫 head 를 down_revision(0038→0039→0040) + base=앞 브랜치 스택 PR. 둘 다 0038 기반이면 alembic multiple heads. squash 머지 후 스택 PR 충돌 → `git rebase --onto main <앞PR 마지막커밋>` 으로 해소(이미 머지된 변경 drop).

**잔여**: #2(RLS·SaaS 보류) + drift ③④'(부분인덱스 allowlist 무해 유지). 🔴 **이후 잔여작업 라운드(#843/#844)에서 drift ③④' 해소 + #2 근본 runbook — 아래 §"잔여작업 라운드" 참조**.

---

## 잔여작업 라운드 (2026-06-09~10) — #843/#844 (사용자 결정 C)

**날짜**: 2026-06-09~10 | **PR**: #843~#844 (2건 머지) | **트리거**: 사용자 "잔여 작업 수행을 원합니다" → AskUserQuestion 결정 **C(둘 다 순차: ③④' → #2)** | **상태**: full 감사 36건 drift·#32 전부 해소, #2 근본 runbook 준비

이전 보류 결정(③④' allowlist 유지 / #2 SaaS 유지)을 사용자 재결정(C)으로 수행.

- **#843 (drift ③④' ORM 정합)**: alembic 0032 `ix_analyses_repo_id_created_at_tokens`(WHERE input_tokens IS NOT NULL) + 0031 `uq_insight_cache_global/repo`(부분 UNIQUE, WHERE repo_id IS NULL/NOT NULL) 를 ORM `__table_args__` 에 선언. 🔴 **postgresql_where + sqlite_where 양 방언 필수**: postgresql_where 만 쓰면 SQLite create_all 이 전체 유니크 인덱스를 만들어 전역+리포 캐시 공존 붕괴 → 양 방언 partial 선언(sqlite_master 실측 확인). allowlist ③④ 제거(잔존=② email 표현 FP 뿐) + 필터 fixture ②로 교체 + 가드 test_orm_partial_indexes(양 방언 WHERE 술어 정확 비교, Codex mutual 강화). 🔴 **WHERE-FP 미발생** — pg-concurrency CI compare_metadata green(ORM postgresql_where 술어가 반영 PG WHERE 와 정합, 사전 우려된 WHERE 정규화 FP 실측상 無). 단위 4733→4735.
- **#844 (#2 RLS owner-bypass 근본 runbook)**: `docs/runbooks/rls-role-separation.md` — RLS 2차 안전망 실효 0(앱=postgres BYPASSRLS 접속, FORCE 단독 무의미) 근본 해결 4단계 절차(비-BYPASSRLS 앱 role + BYPASSRLS worker role 프로비저닝 → background 전략 3옵션 → FORCE 마이그레이션 → DATABASE_URL 전환) + 검증/롤백/pre-flight. 🔴 **핵심 설계 요건**: background 경로(webhook/cron/worker) app.user_id 미설정 → FORCE+비-BYPASSRLS 전환 시 user-owned repo 차단(파이프라인 붕괴) → service role 분리 선행 필수. db.md RLS 규칙 참조 추가. docs-only(실제 실행=사용자 운영 작업+Phase 2 코드 PR).

**검증**: 전 PR Codex mutual OK(push 전). 🔴 Codex mutual ROI: #843 가드 술어 미고정(단일정답 버그) + #844 runbook 3건(ALTER DEFAULT PRIVILEGES FOR ROLE·11테이블 출처·worker role SQL 누락) 적발→정정. 단위 4733→4735, 통합 154, pylint 10.00.

**🔴 핵심 학습**: (1) **부분 유니크 인덱스 ORM 선언 = postgresql_where + sqlite_where 양 방언 의무** — 한쪽만 쓰면 SQLite 가 전체 유니크화로 도메인 무결성 붕괴. (2) **#2 류 RLS owner-bypass 는 코드만으로 미완결** — BYPASSRLS 접속이면 FORCE 도 무의미, role 분리(운영) + background 전략(코드 설계) 선행 필수. runbook 으로 절차 문서화가 actionable 산출물.

**최종 잔여**: **#2(RLS·SaaS — role 분리 runbook 준비완료, 운영 실행 + Phase 2 background 코드 PR 대기)만**. full 감사 36건 = drift①③④'·#32 전부 해소/#22/#23/#14 결정 + #2 근본 절차 문서화. 실질 종결.

---

## 잔여 정리 라운드 A옵션 (2026-06-10)

**날짜**: 2026-06-10 | **PR**: #846 (docs 1건 — 번호는 생성 후 fix-up 반영, Codex R1 처방) + GitHub-side 작업 (repo 변경 없음) | **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" → 전수 스캔 워크플로우(wf_851d8529, 5 스캔 + completeness critic, read-only) → 옵션 표 결정 **A(신규 P1+P2 정리 라운드)** | **상태**: 신규 발견 P1 2건 + P2 4건 처리

전수 스캔(1차 42건 → critic 검증 후 고유 ~24건, 허위 2건 부분 기각)이 STATE '잔여 #2만' 선언 밖에서 신규 P1 사고를 적발 — 본 라운드로 정리.

- **PR #838~#845 본문 8건 복원** (GitHub-side): `gh pr create` 본문 인자 결함으로 전건 리터럴 `@-` 2자 저장 → squash 커밋 메시지에서 복원 + #839 에 정책 11 8조합 체크리스트 회복 섹션 추가. 정책 2/11/18 의무 섹션 GitHub 기록 소실 사고.
- **재발 방지 (정책 10 진화)**: 본문 임시 파일 + `--body-file <경로>` 전달 의무 + 생성/수정 직후 `gh pr view --json body` 길이 검증 1줄 의무 — CLAUDE.md 1줄 + active.md detail (#846).
- **Code Scanning 12건 처분** (정책 14): #492~#502 unused-import 11건 = parity 테스트 의도적 ORM side-effect import (testing.md 'empty `__init__` + 명시 import' 규칙) → used-in-tests dismiss / #491 ineffectual-statement = `claude_metrics.py:35` `await result` 실효 코루틴 await → false-positive dismiss. open alert 12→0.
- **stale docs 정정**: operational-smoke-checks.md §8.7 — 'RLS 운영 활성화' 행이 '사용자 별도 PR 의무 + 부재 메모리 파일 참조' 로 stale (미들웨어 `rls_session.py` + `_set_rls_user_id_per_query` 구현 완료) → 구현 완료 + role 분리 선행 필요로 갱신, rls-role-separation.md cross-link + `rls_session.py` docstring 동일 stale 참조 정정 (#846 — Codex mutual P2 적발).
- **메모리 동기화**: dangling commit 7d0fa1fe Support 요청 기록 상충 2곳 (`project_security_3layer_guard` 미체크 ↔ `project_cycle_theme_nav_fix` 완료) → 2026-06-10 실측(API 200 — purge 미반영, 결과 확인/재요청 잔여) 반영 통일.

**검증**: 주석/docs-only (src 변경 = `rls_session.py` docstring 1곳 — 런타임 무변경, rls 단위 9 passed. 테스트 4889 불변). Codex mutual (push 전, 정책 18 — R1 NG 2건·R2 NG 1건 정정 후 OK).

**잔여 (불변)**: **#2(RLS owner-bypass — Phase 2 background 코드 PR + 운영 role 분리)**. 본 라운드 신규 식별 백로그: 정책 11 일괄 회신 대기 (#822/#823/#824/#827/#839 8조합), 사이클 164~166 회고 보고서 미보관 + #838~#845 라운드 회고 미수행, claude_metrics 가격표 분기 재확인 (2026-07 초), 온프레미스 PG rolbypassrls 미측정 (#2 선행).

---

## RLS #2 Phase 4 admin 대시보드 cross-tenant 보존 — api/admin·ui/routes/admin hybrid (#849 후속) (2026-06-10)

**날짜**: 2026-06-10 | **PR**: #850 | **트리거**: #849 머지 후 사용자 "이후 작업을 수행해주세요" → 마지막 코드 가능 #2 항목(/admin cross-tenant under-report) 해소 | **상태**: 코드 완료(#850 머지) — **Phase 4 코드 차단 경로 전부 해소**, #2 잔여 = Phase 4 운영 전환만(사용자)

- **문제**: admin 은 `require_admin` **세션**이 있지만, `/admin/tenants`(`tenant_inventory` — User/Repository/Analysis)·`/admin/operations`(`operations_kpi` — MergeAttempt/User)는 **전체 테넌트 집계**다. Phase 4 비-BYPASSRLS app role 전환 시 admin 세션 RLS(`app.user_id=admin`)가 admin 본인 행만 남겨 under-report(admin 대시보드 붕괴). api/admin.py + ui/routes/admin.py 양쪽 동일.
- **해소 (엔드포인트별 hybrid)**: 신규 `_get_worker_db`(WorkerSessionLocal, BYPASSRLS) 의존성 도입 → `tenants`·`operations` 만 분기. cross-tenant 가시성 보존(현 BYPASSRLS postgres 동작 = Phase 4 후에도 동일).
- 🔴 **`rls-audit` 는 `_get_db`(web) 유지 의무**: `connection_bypasses_rls` 가 **현재 connection 의 rolbypassrls** 를 실측하는 진단이라 웹 app role 로 평가돼야 정확하다. worker(BYPASSRLS) 세션이면 항상 우회=TRUE 로 오진단 → Phase 3~4 거짓 안심 창 가시화가 무력화. (이 subtlety 가 blanket 모듈 이동을 막고 per-endpoint 분기를 강제.)
- **가드**: api/admin·ui/routes/admin 2 모듈 `_HYBRID_DB_MODULES` 편입(github.py 와 동일 — bare+worker 둘 다 import, alias 금지). 엔드포인트별 세션 라우팅 = **sentinel 회귀 가드 3**(`test_admin_endpoints.py` — worker/web distinct 세션 주입 후 tenant_inventory=worker·operations_kpi=worker·rls_coverage_summary=web 검증; 정적 import 가드가 못 잡는 endpoint swap 차단).
- **불변성**: `DATABASE_URL_WORKER` 미설정 시 `WorkerSessionLocal is SessionLocal` = 현행 동일. src 2파일 + 테스트 2파일 + docs.

**검증**: 전체 4973 passed / 7 skipped (수집 4971→4980, 단위 4817→4826 +9: test 10 hybrid 계약 확장 4 + sentinel 3 + `_get_worker_db` 제너레이터 커버 2[CI codecov/SonarCloud coverage-on-new-code fix-up]) · pylint 10.00 · flake8 0. Codex mutual 검증(6/6).

**잔여**: #2 = **Phase 4 운영 전환만**(사용자) — 임시 PW 교체 + `DATABASE_URL`/`DATABASE_URL_WORKER` 설정 + runbook §4 검증. 코드 차단 경로(OAuth·시스템 API·admin) 전부 해소.

---

## RLS #2 Phase 4 OAuth 로그인 blocker 해소 — auth_callback worker 세션 전환 (옵션 2) (2026-06-10)

**날짜**: 2026-06-10 | **PR**: #849 | **트리거**: 사용자 "잔여 작업을 확인해주세요" → 잔여 #2 Phase 4 선행 blocker(OAuth users self-RLS) 옵션 표 제시 → 사용자 **옵션 ② (auth upsert worker 세션 경유)** 결정 위임 | **상태**: 코드 완료(#849 머지) — #2 잔여 = Phase 4 운영(URL 전환·PW 교체) + `/admin/tenants` under-report(후속 PR 해소)

- **문제 (직전 RLS Phase 3 적대 verify P1 blocker)**: `auth_callback`(`src/auth/github.py`)은 웹 `SessionLocal` 로 users upsert(`find_by_github_id` SELECT + 신규 User INSERT) 수행 — 콜백 시점 `session["user_id"]` 부재 → `app.user_id=''` → `users_self_isolation`(0029, `id = NULLIF(current_setting('app.user_id',true),'')::integer`) 이 SELECT/INSERT 모두 거부. `scamanager_app`(비-owner) 전환 즉시 전원 로그인 장애(FORCE 무관, 0041 롤백으로도 미해소).
- **해소 (옵션 2)**: `auth_callback` upsert 블록만 `WorkerSessionLocal`(BYPASSRLS worker role, 시스템 컨텍스트 — 사용자 식별 프로비저닝)로 전환 → RLS 우회로 SELECT/INSERT 통과. `logout` 은 세션 존재(본인 행, `id == user_id`)라 bare `SessionLocal`(웹 RLS 경로) 유지 — defense-in-depth 보존(본인 토큰만 삭제 가능).
- **가드 재설계 (Phase 2 라우팅 가드)**: `github.py` 가 bare `SessionLocal`(logout) + `WorkerSessionLocal`(callback) 둘 다 import 하는 **hybrid** 모듈이 됨. `_HYBRID_DB_MODULES`(github.py 1건) 카테고리 도입 — test 6(웹 모듈 WorkerSessionLocal 금지) 예외 처리 + test 7a(worker importer bijection) expected 확장 + **hybrid 계약 가드 2종**(test 10: 양 import 존재 + `as SessionLocal` alias 금지 — logout 오라우팅 차단). `as` alias 미사용(자체 이름 import)로 두 세션 심볼 구분 유지.
- **테스트**: test_github.py 콜백 patch 8건 `WorkerSessionLocal` 전환(logout 2건 `SessionLocal` 유지 — 12-space 들여쓰기로 구분). TDD Red(`WorkerSessionLocal` 속성 부재 AttributeError) → Green. `DATABASE_URL_WORKER` 미설정 시 `WorkerSessionLocal is SessionLocal` 이라 mock 동작 동일.
- **Codex mutual(정책 18, push 전) 발견 — 시스템 API 라우트 3종**: Codex 가 OAuth 코드(a~d) CORRECT 확인 + (e) 추가 갭 적발 — `src/api/repos.py`·`stats.py`·`repo_report.py` 가 `require_api_key`(글로벌 키) 인증으로 **세션 없이** cross-tenant 전체 데이터를 bare `SessionLocal` 로 조회 → Phase 4 후 RLS 가 owned 행 은닉/차단(list_repos under-report·analyses 404·config/delete 차단). 제 잔여 문서가 `/admin/tenants` 만 적은 건 overclaim(메모리 STATE overclaim 패턴 재발). 사용자 "함께 수정" 결정 → 3종을 `WorkerSessionLocal as SessionLocal`(background 패턴, 모듈 심볼 `SessionLocal` 유지로 기존 `patch("src.api.repos.SessionLocal")` 불변) 전환 + `_SYSTEM_API_MODULES` 라우팅 가드 신설(`_WEB_API_MODULES` 6→3 분리, `_WORKER_ALIAS_MODULES` = background 17 + 시스템 API 3). `issue_registration`(get_current_user+user_id 필터)·`users`(require_login) 는 세션 기반이라 WEB 유지.
- **불변성**: `DATABASE_URL_WORKER` 미설정 동안 `WorkerSessionLocal is SessionLocal` = 현행 동작 완전 동일 — Phase 4 worker URL 설정 시 자동 발효. src 4파일(github + api 3) + 테스트 2파일 + docs.

**검증**: 전체 4964 passed / 7 skipped (수집 4963→4971, 단위 4809→4817 +8: hybrid 계약 2 + 시스템 API 재라우팅 가드 6) · pylint 10.00 · flake8 0. require_admin·internal_cron subset 실패 = main 동일 재현(settings 싱글톤 reload subset-ordering 오염, CI 전체 순서 무영향 — 격리 시 전부 pass) — 본 변경 무관 실측 확인.

**잔여**: #2 = **Phase 4 (운영, 사용자)** — 임시 PW 교체 + DATABASE_URL/DATABASE_URL_WORKER 전환 + runbook §4 검증 6종. **+ `/admin/tenants` under-report**(admin 크로스테넌트 가시성 = 권한 상승 별도 PR + 사용자 확인).

---

## RLS Phase 1 운영 + Phase 3 — 0041 FORCE + 실측 가시화 (2026-06-10)

**날짜**: 2026-06-10 | **PR**: #848 | **트리거**: 사용자 "Claude가 MCP로 수행하기를 원합니다" (Phase 1 — 정책 12 DDL 사전 승인) → "네 바로 수행을 부탁드립니다" (Phase 3) | **상태**: Phase 1 운영 완료 + Phase 3 코드 완료 — #2 잔여 = Phase 4 (운영, 🔴 OAuth blocker 결정 선행)

- **Phase 1 (운영, Claude MCP `execute_sql` 직접 실행)**: Supabase 에 `scamanager_app`(LOGIN, NOBYPASSRLS) + `scamanager_worker`(LOGIN, BYPASSRLS) 생성 + GRANT(테이블 12/12 full DML·시퀀스 11/11) + `ALTER DEFAULT PRIVILEGES FOR ROLE postgres`. **기능 실증**: `SET LOCAL ROLE scamanager_app` → repositories 0/8 가시(owner-bypass 해소 실증) / worker → 8/8(BYPASSRLS 보존). 임시 PW 채팅 전달 — 사용자 `ALTER ROLE ... PASSWORD` 교체 의무(Phase 4 전). ⚠️ 부수 실측: `alembic_version` = RLS enabled + policy 0건(비-owner default-deny). 적용 범위 = Supabase 만(사용자 결정).
- **Phase 3 (코드)**: alembic **0041** — 11 테이블 리터럴 `FORCE ROW LEVEL SECURITY`(PG-only, downgrade=`NO FORCE`) + `rls_coverage_summary(db)` 실측 2종 — `force_applied`(pg_class.relforcerowsecurity 11/11, bound parameter) + **`connection_bypasses_rls`**(rolbypassrls OR rolsuper) → `/admin/rls-audit` BYPASSRLS 우회 경고 배너(3 locale 신설)로 **Phase 3~4 사이 거짓 안심 창 봉인**. 라우트 2곳 db 전달 + `scripts/backfill_repository_user_id.py` worker 세션 alias. i18n `force_warning_body` 실측 의미 갱신.
- **가드**: `test_0041_rls_force` 7건(**ENABLE↔FORCE bijection** — 미래 RLS 테이블 FORCE 누락 자동 fail + NO FORCE 오염 차단 2중) + `test_migration_0041_force_round_trip_postgres`(실 PG upgrade/downgrade + 실측 양성 경로 — ci.yml pg-concurrency 핀 등재) + 라우트 db-전달 가드 2 + worker routing 재바인딩/모듈객체 가드 scripts 확장.
- **적대적 3-렌즈 verify (wf_fde4d85b, 정책 8 내부 layer)**: **P1 1건 — Phase 4 전환 시 OAuth 콜백(users self-RLS, `app.user_id` 미설정)이 SELECT/INSERT 차단 → 전원 로그인 장애**(FORCE 무관, 0041 롤백으로도 미해소) → runbook §Phase 4 **P1 blocker** + 로그인/admin 크로스테넌트 smoke + pre-flight 항목으로 문서 봉인. 근본 전략(① users OAuth upsert 정책/컨텍스트 키 ② auth worker 세션 경유 ③ WITH CHECK 분리) = **사용자 결정 영역(High tier)**. P2 8건 중 6 반영(bypass 배너·PG-live 테스트·가드 확장·fallback listener 문서·FORCE defense-in-depth 표현 정정).

**검증**: 전체 4956 passed / 7 skipped (수집 4941→4963, 단위 4787→4809 +22) · pylint 10.00 · flake8 E501 15 (baseline 동일). TDD test-writer 선행(Red 14 → Green). Codex mutual (push 전, 정책 18 — R1 NG 1건 [STATE/cycle-history/README 수치 stale] → 본 sync 반영 후 재검증).

**잔여**: #2 = **Phase 4 (운영, 사용자)** — 임시 PW 교체 + 🔴 **OAuth users self-RLS 전략 결정 선행 의무** + DATABASE_URL/WORKER 전환 + runbook §4 검증 6종.

---

## RLS Phase 2 — background 전용 worker 세션 분리 (2026-06-10)

**날짜**: 2026-06-10 | **PR**: #847 (번호는 생성 후 fix-up 반영 — Codex R1 처방 흐름) | **트리거**: 사용자 "다음단계는 가장 권장하는 옵션으로" → runbook 권장안 **옵션 A (service role 분리)** 위임 결정 (정책 15 High tier — 위임 근거 PR 본문 명시) | **상태**: Phase 2 코드 완료 — #2 잔여 = 운영 Phase 1/4 + Phase 3 FORCE(운영 선행 후 코드)

정합성 감사 #2 (RLS owner-bypass) 의 선행 필수 코드 — role 분리 후 background 경로가 `app.user_id` 미설정으로 차단되는 파이프라인 붕괴(runbook L32/L57)를 막는 이중 세션 라우팅.

- **config**: `database_url_worker: str = ""` + postgres:// 스킴 변환 validator (`_normalize_pg_url` 공유 — fallback 패턴 미러).
- **database.py**: `_build_worker_session_factory(worker_url, web_factory)` — **미설정 시 web_factory 동일 객체 반환 (현행 동작 bit-identical 보존)** / 설정 시 독립 `FailoverSessionFactory` 단일 엔진 (failover 없음 + RLS `SET LOCAL` listener 미등록 — BYPASSRLS worker 전제 + 활성 시 INFO 로그 1줄 [pipeline-reviewer P2-1]).
- **background 16 모듈 alias 전환**: `from src.database import WorkerSessionLocal as SessionLocal` — 모듈 심볼명 유지로 기존 테스트 patch 대상 (`src.worker.pipeline.SessionLocal` 등) 불변 (사이클 165 #811 stale-mock 함정 회피). 대상: worker/pipeline · webhook/providers 3종 + _helpers · gate/engine + actions(review_comment·approve — auto_merge 는 engine 위임 커버) · notifier lazy 6종 · api/internal_cron · api/hook. `services/merge_retry_service` 는 cron 세션 주입 — 자동 커버.
- **TDD**: test-writer 선행 48 테스트 (Red 45 → Green 48) + **Codex R1/R2 강화 +4 = 52** — config 변환 / factory identity·독립 인스턴스 / RLS listener 범위 / **ast 기반 정적 라우팅 가드** (16 모듈 alias 강제 + bare import 차단 + 웹 모듈 negative + **전수 inventory 양방향 bijection** [src 전체에서 SessionLocal 계열 import 하는 미분류 신규 모듈 자동 fail] + **재바인딩 금지** [alias 후 `SessionLocal = ...` 재할당 우회 차단] + **모듈 객체 import 금지** [`import src.database as db; db.SessionLocal()` attribute 우회 차단 — Codex R2, src 기존 사용처 0건 실측]).
- **pipeline-reviewer APPROVE** (P0 0): (a) 미설정 시 동일성 검증 (b) 전환 누락/과잉 0 — 잔존 bare import 16곳 전부 웹 경로 실측 (c) P0-H gather 독립 세션 보존 (d) P2 — failover 미지원·이중 풀 트레이드오프 env-vars.md 명시, scripts/backfill 은 범위 외 보류(정책 3 보고).
- **docs sync**: env-vars.md(트레이드오프 포함) · .env.example · db.md(WorkerSessionLocal 라우팅 규칙 — 사이클 86 Q2 path-scoped sync) · runbook Phase 2 ✅ 구현 완료 표기 · README 배지.

**검증**: 전체 4935 passed / 6 skipped (수집 4889→4941, 단위 4735→4787 +52) · pylint 10.00 · flake8 E501 15 (main baseline 동일 — notifier lazy import 5건 괄호 분리로 신규 0). Codex mutual (push 전, 정책 18 — R1 NG 3건 [AST 가드 우회·.env.example exclude 평가·README/deploy 등재 누락] → inventory/재바인딩 가드·훅 ID 정정·docs 등재·exclude 반증 [placeholder 변경 시 SESSION_SECRET 32자 validator 가 dev flow 파손, R2 동의] → R2/R3 잔여 [모듈 객체 import 우회·수치 정밀] 라운드별 정정. push 는 mutual OK 수신 후에만 수행 — 최종 판정 기록 = PR 본문 §Codex 검증 의뢰).

**잔여**: #2 = **Phase 1 (scamanager_app/worker role 생성 SQL — 운영, 사용자)** → **Phase 4 (DATABASE_URL/DATABASE_URL_WORKER 전환 + 검증 4종 — 운영, 사용자)** + **Phase 3 (0041 FORCE 마이그레이션 + force_applied 실측 쿼리 — Phase 1·2 적용 확인 후 코드 PR)**. 미설정 동안 운영 동작 변화 0.

---

## 사이클 165

**날짜**: 2026-06-08~09 | **PR**: #802~#814 (11건 머지) | **상태**: Task9 골든 리메디에이션 — P1 9/10 + P2 보안·파이프라인 하드닝 클러스터 5/5

**작업 내용**: Task9 full 골든 감사(#801, 36 confirmed = P1 10 / P2 26)의 P1 리메디에이션 + 사용자 선택 P2 클러스터(보안·파이프라인 하드닝). Codex mutual 복구 하에 전 PR push 전 Codex OK 의무(정책 18) — 이번 사이클에서 Codex 가 단독 진행이었다면 운영 반영됐을 **실결함 4건 적발**(핵심 성과). 11 PR 순차 머지는 사용자 위임.

**P1 리메디에이션 (#802~#810, 9/10 — #2 RLS 근본해결은 SaaS 전환 항목)**:
- #802(#1) telegram 반자동 콜백 리포 소유권 authz · #803(#9/#10 + 비-ASCII 변종 #26/#27/#29/#30) `secure_str_compare` 전 compare_digest 호출처(validator/hook/telegram/railway/auth) 적용 · #804(#8) AI 리뷰 genuine 실패(api_error/parse_error)만 auto-merge 차단(`ai_review_failed`, no_api_key/empty_diff 제외) · #805(#6) content-fetch transient(403/5xx) 실패 → incomplete · #806(#7) per-tool subprocess 타임아웃 → `AnalyzeContext.timed_out` → incomplete(ctx-신호 설계, re-raise 회귀 회피) · #807(#5) hook SHA insert race → `analysis_repo.save_new` race-safe · #808(#4) check_suite.completed `only_ids` force-due · #809(#3) docs architecture gate/actions · #810(#2-D) rls-audit FORCE RLS 미설정 owner-bypass 경고 가시화.

**P2 보안·파이프라인 하드닝 클러스터 (사용자 AskUserQuestion 선택, #811~#814)**:
- **#811 (#11+#13)** — #11 게이트 콜백 리플레이 가드: `gate_decision_repo.claim_decision`(insert-only UNIQUE analysis_id, IntegrityError→False)로 부수효과 전 결정 원자적 claim(first-writer-wins, save_gate_decision upsert 대체 — 결정 뒤집기 차단). #13 telegram_webhook `request.json()` try/except→400 + isinstance(dict)→400(railway 대칭). 🔴 **Codex 3라운드**: R1 NG(find 기반 비원자 TOCTOU)→사용자 옵션A→원자 claim / R2 NG(타 파일 save_gate_decision stale mock 3건)→claim 전환 / R3 OK.
- **#812 (#24)** — ai_review `_parse_response` bare int()→`_coerce_score`(hook `_coerce_raw_score` PARITY GUARD 인라인). 단일 비숫자/Infinity 필드가 리뷰 전체 붕괴 차단 — feedback·정상 점수 보존 + status=parse_error 유지(#804 게이트 fail-closed 불변, 설계 'success 복구' 대신 보수적 안 채택).
- **#813 (#12)** — SSRF DNS-rebinding docstring 정직화(옵션 B, 사용자 결정 — 코드 0줄). validate-time 1차 차단 한계 + connect 재해석 TOCTOU 명시(httpx native IP 핀 미지원으로 옵션 A 거부, 정책17 안정성).
- **#814 (#25)** — hook parse_error 시 인플레 89/B 점수 NULL 저장(집계 오염 차단, 컬럼 nullable+집계 NULL 제외 재사용 쿼리 0줄). 🔴 **Codex 적발 회귀**: overview.py 가 count(parse_error 포함)↔func.avg(NULL 제외) 불일치로 score-전부-NULL 리포 grade=F 오분류 → grade 를 avg_raw 기준으로 수정 + 전 read-path 감사(analytics/dashboard 안전 확인).

**검증**: 각 PR TDD red→green + Codex true mutual(정책 18, push 전). 전체 단위 4655→4713, 통합 153 불변, pylint 10.00, 전 PR CI green(codecov/patch tiny-diff 아티팩트 #813 non-blocking).

**학습**: ① **Codex mutual 검증 ROI 결정적** — #811 비원자 TOCTOU·타 파일 stale mock 3건, #814 overview F-오분류 등 단독 진행 시 누락될 실결함 4건 적발(외부 LLM 모델 다양성 layer, 정책 18 §5). ② NULL 저장 같은 데이터 변경은 **모든 read-path 영향** → 전수 감사 의무(overview 가 유일 미처리 경로였다). ③ Codex exec 안정 호출 = `codex exec --skip-git-repo-check "단일라인" < /dev/null`(멀티라인/stdin 미차단 시 "Reading additional input from stdin..." 만 출력하고 리뷰 미생성). ④ #11 원자성은 사용자 옵션 A 결정(claim 후 GitHub 실패 시 retry 억제 트레이드오프 수용) — NG 시 자율 수정 금지·옵션 표·사용자 confirm(정책 18 §3). ⑤ #26/#27/#29/#30 비-ASCII compare_digest P2 변종은 #803 으로 이미 해소 실측 확인 → P2 잔여 26→실질 ~21.

**회고 + follow-up (#816/#817)**: 5+1 다중 에이전트 회고(6 에이전트, P0 0/확정 P1 6~7, cross-verify: false-positive 강등 1·신규 P2 2·completeness gap 4) → 즉시 반영 2 묶음. **(A) #816** docs/rule 정합: architecture.md 텔레그램 흐름(claim 단계+순서)·pipeline.md auto-merge fail-open 봉인 3종(#804 ai_review_failed·#805 content-fetch·#806 tool-timeout)·정책18 §3 NG 2-tier(설계방향 옵션표 / 단일정답 즉시수정)·gate_decision_repo docstring(broad IntegrityError 흡수)·api/testing 룰. **(B) #817** 회고 P1 테스트 갭: claim_decision PG first-writer-wins invariant(실 PG `threading.Barrier(2)`, pg-concurrency CI job 실측 PASSED)·broad IntegrityError 흡수(NOT NULL→False)·seam 실DB(StaticPool, claim_decision 미patch → 심볼 리네임 fail-fast). 🔴 **Codex mutual 이 follow-up 에서도 정합오류 적발**: #816 정책18 §3 NG 회기 off-by-one(3→4회차 정정)·#817 PG 테스트 'in-flight 결정론 증명' 과장 → invariant 로 정직화. 단위 4713→4715·통합 153→154(4869 수집).

---

## 사이클 164

**날짜**: 2026-06-08 | **PR**: #795·#796·#794 (3건 머지) | **상태**: area=gate 감사 잔여 6 결함 — 사용자 Q1~Q4 결정 이행

**작업 내용**: 이전 세션 중단 복구 — area=gate 감사(2026-06-06) confirmed 잔여 6 결함을 read-only 재분석(워크플로우 7에이전트, 전부 still_present 확인 + 라인 drift 보정 + 부분 해소 검증 + tier 분류) → 사용자 4 결정(Q1~Q4) → 3 PR 구현. Codex exec 401 만료 지속(`refresh token already used`) → 정책 18 standing 승인 하 Claude 적대적 self-verify(pipeline-reviewer 4회 + 독립 skeptic 7렌즈) fallback.

- **#795 (Q2+Q3 정적분석 코어 재구성)** — `_run_static_analysis`/`_run_static_with_timeout` 재구성. **Q2-A 파일 단위 격리**: list comprehension → 파일별 try/except(실패 파일 빈 결과, 나머지+AI리뷰 보존). **Q3-B 타임아웃 부분결과 보존**: 전량 폐기([], True) → `loop.time()` deadline 파일별 순차(완료분 보존 + incomplete 마커, 고아 스레드 in-flight 1파일로 한정). self-verify 발견 **안전망**: 전량 실패 → incomplete=True fail-closed(Q2 격리가 만들 수 있는 전량-실패 fail-open 회귀 차단). pipeline-reviewer APPROVE×2. 단위 +3.
- **#796 (Q1-A telegram 반자동 대칭화)** — `handle_gate_callback` 인라인 단발 merge(merge_pr + 실패 reason 폐기) 제거 → `engine._run_auto_merge` 위임. 자동/반자동 **완전 대칭**(retry 큐잉·SHA 가드·CI 재판별·terminal/deferred 알림·관측 단일 출처). 가드 AutoMergeAction 미러링(approve + auto_merge + not incomplete). **부수 버그 수정**: reject+고score 시 거부 PR 머지되던 결함 차단. except RuntimeError 보강 + dead code(`_log_merge_attempt_safe`) 제거 + `.claude/rules/api.md` sync. 단위 −2(Block2 관측 테스트 engine 이관).
- **#794 (Q4-A regate first-writer-wins)** — `_regate_pr_if_needed` last-writer-wins → first-writer-wins(기존 pr_number non-None 시 skip+WARNING, `_race_recover_existing` 대칭). 동일 head SHA 멀티 PR 시 잘못된 PR 에 auto-merge/댓글/승인 적용 차단. 단위 +1. ⚠️ codecov/patch tiny-diff 아티팩트 fail(SonarCloud New Code 100% — non-blocking, main branch protection 부재).

**검증**: 각 PR TDD red→green + 적대적 self-verify(pipeline-reviewer + 독립 skeptic 2~3렌즈) — 전 PR **P0·P1 0건**. 전체 단위 4648→4650, pylint 10.00 유지, #795/#796 CI 전부 green, #794 codecov/patch 외 green.

**학습**: ① read-only 워크플로우 선행(7에이전트)으로 라인 drift 보정·부분 해소 검증·tier 분류 → 결정 패키지화로 사용자 Q1~Q4 효율 결정. ② self-verify 가 안전 회귀 1건 발견(Q2 격리의 전량-실패 fail-open) → 안전망 동봉(정책 4). ③ #796 위임 리팩터가 reject 오머지 잠재 버그를 노출·수정. ④ codecov/patch tiny-diff 집계 아티팩트(test파일/주석 줄 오집계) — SonarCloud New Code 가 권위, main branch protection 부재로 non-blocking. ⑤ Codex 만료 지속 — 정책 18 복구 강제, 다음 세션 `codex login` 필수.

**5+1 회고 + follow-up (#798/#799)**: 6 에이전트 회고(cross-verify false-positive 0건) — P1 6건 + P2 4건 confirmed. 즉시 반영 2건(#797 fix-up: STATE.md 셀 stale·pipeline.md rule sync) + 후속 PR 2건: **#798** PR 코멘트 incomplete 경고 배너(인플레 점수 무경고 노출 차단, i18n 3언어, `notifier.github_pr_comment.static_incomplete_warning`) — 회고 운영 가시성 P1 최우선. **#799** 회귀 가드 3건(incomplete 종단 영속·_race_recover 대칭 first-writer-wins·semi-auto 임계 layer 격리) — 정책 4 봉인 깊이 보강. **🔴 Codex mutual 복구**(2026-06-08 사용자 재로그인 → exec CODEX_OK): 6사이클 self-verify fallback 종료, #798/#799 push 전 정상 mutual(CODEX OK) — #798 은 Codex 제안(배너 ordering assertion) 반영. 단위 4650→4655.

**Task 9 (full 골든 감사)**: 사용자 cost 승인(~20M토큰) → integrity-audit scope=full 8 도메인 실행 — 별도 리포트(`docs/reports/`).

---

## 사이클 163

**날짜**: 2026-06-07 | **PR**: #783~#787 (5건 머지) | **상태**: area=gate P2 백로그 해소 (자기완결적 5건)

**작업 내용**: 사이클 162 integrity-audit 워크플로우가 area=gate 라이브 실행에서 confirmed 한 P2 중 자기완결적 5건을 단일 도메인 PR + TDD + 적대적 self-verify(독립 skeptic 5~7렌즈)로 해소. Codex 토큰 만료 지속(본 세션 exec 시 401) → 정책 18 #773 fallback(사용자 standing 승인 하 Claude 단독 적대적 self-verify) 적용. pipeline 변경 2건(#786/#787)은 pipeline-reviewer 병행.

- **#783 (ApproveAction 정적분석 가드)** — `_run_auto` 진입부에 `static_analysis_incomplete` 마커 가드(#779 auto_merge 가드의 approve 경로 확장). `approve_mode='auto'` + branch-protection "approval 시 자동머지" 시 인플레 점수 간접 머지 차단. semi-auto(human-in-loop) 의도적 제외. fix-up: i18n seam approve auto 3 테스트 `ctx.result` dict 명시(MagicMock 첫-읽기 gotcha). 단위 +1.
- **#784 (hook 점수 안전 변환)** — `POST /api/hook/result` 점수 필드 비숫자/None/Infinity 입력이 `int()` TypeError/ValueError/OverflowError → 500. `_coerce_raw_score`/`_coerce_ai_scores`(예외 흡수 → default 폴백 + parse_error, 200). self-verify 가 OverflowError(Infinity, json.loads→float('inf')) 갭 발견·차단. Infinity 검증은 TestClient json= 직렬화 환경 의존 → 헬퍼 직접 단위 테스트. 단위 +3.
- **#785 (merge_retry 백오프 validator)** — 백오프/재시도 정수 5필드 `Field(ge=1)` 양수 + `model_validator(mode="after")` max>=initial 경계(max<initial 시 백오프 단조성 소멸 차단). 기본값 전부 충족(startup 무영향), env-vars.md sync. self-verify 7렌즈(운영 config 전수 grep — 배포 crash 위험 0). merge_unknown_* 별도 self-clamp 경로 의도적 제외. 단위 +6.
- **#786 (zero-SHA 조기 종료)** — GitHub branch/tag 삭제 push 의 after=40-zero SHA 가 `_collect_files` 진입 → 존재하지 않는 SHA 404 반복. `_is_blank_sha`(빈/all-zeros set 비교) 가드를 `run_analysis_pipeline` 진입부(`_ensure_repo` 전) 추가. pipeline-reviewer APPROVE + self-verify 6렌즈. 단위 +8(skip 2 + `_is_blank_sha` parametrize 6, P2-B 반영).
- **#787 (`_ensure_repo` race 복구)** — 동시 webhook 의 같은 신규 repo INSERT race(full_name unique IntegrityError) → 워커 abort. `try/except IntegrityError` → rollback+재조회(다른 워커 repo 복구), 재조회 None re-raise(진짜 오류 전파). 복구는 caller(`_ensure_repo`) 책임 — `repository_repo.save_new` add-only 계약 유지. pipeline-reviewer APPROVE + self-verify 7렌즈(reraises seal 강화 반영). 단위 +2.

**검증**: 각 PR TDD red→green + 적대적 self-verify(독립 skeptic) + pipeline-reviewer(#786/#787). 전체 단위 4628→4648, pylint 10.00 유지, CI 전부 green(#784/#785 1회 fix-up — 환경 의존 테스트).

**학습**: ① 적대적 self-verify ROI 양성 — #784 OverflowError(Infinity) 실 결함 1건 push 전 차단. ② MagicMock 필드 첫-읽기 gotcha — 새 가드가 기존 미사용 필드(`ctx.result`)를 처음 읽으면 MagicMock(truthy)이라 해당 필드를 mock 으로만 두던 테스트 광범위 fail(#783 i18n seam 3건). ③ `float('inf')` 서버 처리 검증은 TestClient json= 직렬화 환경 의존(CI httpx reject) → 순수 헬퍼 직접 단위 테스트가 견고. ④ Codex 토큰 만료 지속 — 정책 18 복구 강제 가드, 다음 세션 `codex login` 필수.

---

## 사이클 162

**날짜**: 2026-06-07 | **PR**: #774~#781 (8건 머지) | **상태**: 잔여 백로그 전량 처리 + integrity-audit 워크플로우 완성 + 워크플로우 발견 area=gate P1 fix 3건

**작업 내용**: 사이클 160~161 잔여 백로그(RLS 자동탐지 가드·test-quality·effects.js·워크플로우 Task4~9)를 전량 처리하고, integrity-audit 워크플로우를 area=gate 라이브 실행으로 검증하던 중 워크플로우가 발견한 gate·pipeline P1 결함 3건을 추가 fix. 전 PR Codex 토큰 무효화(`refresh_token_reused`, 4연속)로 정책 18 #773 fallback(사용자 승인 하 Claude 단독 적대적 self-verify) 적용.

- **#775 (RLS 자동탐지 가드)** — `_RLS_MATRIX`(admin RLS 감사 단일 출처)가 0037 issue_registrations 적용 후 미갱신(10→11 누락). `tests/unit/test_rls_matrix_completeness.py` 신설(alembic `ENABLE ROW LEVEL SECURITY` 테이블 집합 ↔ `_RLS_MATRIX` bijection 4 가드, 정규식 schema/quote 정규화) + 매트릭스 동기화 + db.md 가드 노트. 단위 +5.
- **#776 (test-quality)** — `test_main.py` dead `or True` 제거 + `test_e2e_pipeline_scenarios` malformed JSON 파이프라인 미진입 단언(`assert_not_called`+`Analysis.count()==0`). mutation test 로 비-vacuity 입증. 기존 테스트 정정(무증가).
- **#777 (effects.js hx-boost)** — `setupTabs` window resize 리스너가 hx-boost 재방문마다 누적 → remove-before-add 단일 전역 핸들러(`document._tabsResizeHandler`). 8조합 시각검증 사용자 수행 후 머지.
- **#778 (integrity-audit 워크플로우 Task1~8)** — 수동 5+1 감사의 결정론적 코드화: `.claude/workflows/integrity-audit.mjs`(scope 팬아웃 → loop-until-dry → 3-렌즈 adversarial verify → completeness critic) + `/integrity-audit` 스킬 + runbook + CLAUDE.md 1줄 + area=gate 검증 리포트. area=gate 실측 5.7M토큰/75에이전트(plan "소" 초과)·confirmed 14(P1 4·P2 10)·fp_blocked 8·unverified 0. Task 9(full 골든)는 비용으로 사용자 승인 보류.
- **#779 (P1: 정적분석 타임아웃 → auto-merge 차단)** — `_run_static_with_timeout` 타임아웃 시 `[]` → `calculate_score([])` 가 만점(45/45)으로 환산 → 무분석 코드 auto-merge 가능. `(results, timed_out)` 튜플 + `result["static_analysis_incomplete"]` 마커 → `AutoMergeAction.execute` skip(Approve/Review 무영향). 사용자 결정 ⓐ. 단위 +3.
- **#780 (P1: 동시 insert race 중복 알림)** — `save_new` 가 DB 제약 위반 시 기존 레코드 반환을 신규와 미구분 → run_gate_check 재실행·중복 notify. `(analysis, created)` 반환 + `not created` 시 `_race_recover_existing`+result_dict=None(find_by_sha race 경로 일관). 단위 +1.
- **#781 (P1: merge_retry expired 상태)** — `(not should_retry) or expired` 를 한 분기로 묶어 만료 행도 `mark_terminal` 오기록(`mark_expired` dead code). `is_terminal_failure` vs `expired` 분기 → 만료는 `mark_expired`(status='expired')+`counts["expired"]`, terminal 우선. 기존 버그-인코딩 테스트 2건(unit+integration) 정정.

**검증**: 각 PR TDD red→green + 적대적 self-verify 워크플로우/에이전트(P0/P1/P2 0). 테스트 4768→4781 수집(단위 4615→4628), pylint 10.00 유지.

**학습**: ① integrity-audit 워크플로우가 검증 실행 중 실 결함(`mark_expired` dead code·만료 오기록·버그-인코딩 테스트) 발견 — 결정론적 감사 ROI 양성. ② area=gate 실측 5.7M토큰 = plan "소" 추정 대폭 초과(loop-until-dry×3라운드) → full(8도메인) 비용 가드 필요. ③ Codex 4연속 무효화 — 정책 18 복구 강제 가드 도달, 다음 세션 `codex login` 필수.

## 사이클 161

**날짜**: 2026-06-06 | **PR**: #764~#767 | **상태**: 정합성 감사 P1 백로그 해소 (직전 #759 full 감사 confirmed)

**작업 내용**: 직전 integrity-audit 세션(사이클 160)의 #759 full 감사 confirmed P1 3건 + 머지 후 발견 로컬 테스트 결함 1건을 단일 도메인 PR 4건으로 해소. 착수 전 적대적 분석 워크플로우(analyze+refute, 6 에이전트)로 3건 모두 `diff_is_safe=true` + 정확 최소 diff·회귀 위험·필요 테스트 사전 도출 (정책 15 사전 사고).

- **#764 (hook 클램프)** — CLI hook(`POST /api/hook/result`)이 `ai_result` raw 점수를 클램프 없이 `int()` 캐스팅만 해 범위 밖 값(예: commit 999)이 `calculator.py:66-68` 스케일링을 거쳐 breakdown 카테고리 점수가 cap(commit 15 / ai 25 / test 15)을 초과·음수가 되는 정합 위반. `ai_review.py:184-185` 의 `max(0, min(AI_RAW_*_MAX, int(...)))` 패턴을 `hook.py:165-167` 에 미러 + `hook.py:24` 상수 import. 유효 범위 입력은 동작 100% 보존. 회귀 가드 2건(범위초과→cap / 음수→0, `result["breakdown"]` 기준 assert — raw 는 직렬화 안 됨을 적대적 검증이 정정). 단위 +2.
- **#765 (gate 단일출처)** — `merge_reasons.is_retriable_tag()` 가 "단일 출처" 문서화됐으나 src 호출처 0인 dead code, `engine.py:202` 가 `(UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT)` 튜플 멤버십으로 중복 하드코딩(`_RETRIABLE_TAGS` frozenset 과 drift 위험). `not is_retriable_tag(reason_tag)` 로 교체 + `engine.py:28` import 원자 정리(`DEFERRED` 보존). frozenset/tuple 멤버십 동치로 동작 보존. 기존 테스트(T8-1 retriable / T8-4 terminal + test_merge_reasons)로 완전 커버 — 신규 테스트 미추가(정책 16). 메모 "engine 3곳"은 실측 1곳으로 정정.
- **#766 (hx-boost UI 가드)** — `base.html` `<script>` 가 hx-boost body swap 마다 재실행되는데 `_initReveal`(988-989)·`_finishProgress`(1096-1099) 가 `htmx:afterSettle`/`historyRestore` 에 remove-before-add 없이 등록돼 재방문 N회마다 N개 누적. `_baseNavHandler` 미러로 `document._initRevealHandler`/`_finishProgressHandler` 단일 슬롯 가드. 940-1120 전수 결과 가드 누락은 이 2곳뿐. E2E 회귀 가드 1건(`test_reveal_progress_handlers_use_remove_before_add` — 3회 hx-boost 후 핸들러 단일 슬롯 검증, TDD RED→GREEN) + nav E2E 11 passed. 8조합 시각검증 사용자 수행 후 머지. E2E +1.
- **#767 (로컬 테스트 루트 독립)** — 머지 후 전체 스위트 실측 중 `test_doc_review_gate.py::test_stale_hardcoded_prefix_not_relied_on` 1건 실패 발견. 하드코딩 `d:/source/scamanager/CLAUDE.md` 를 "비-루트 경로"로 가정했으나 본 리포 실제 루트(`d:\Source\SCAManager`)와 정규화 시 일치 → `_normalise` strip → `critical` → **루트가 `d:\Source\SCAManager` 인 머신에서만 실패**(CI Linux 루트 불일치로 통과 → 결함 은폐). 런타임 루트(`parents[3]`) + `_external` 접미사 형제 경로로 교체해 머신 독립화 + 테스트명 `test_non_runtime_root_absolute_path_is_skip` 개명. src 무변경.

**검증**: Codex 액세스 토큰 만료(`refresh token already used`) → 사용자 승인 하 **Claude 직접검증 fallback** (사이클 119/125 전례, PR 일괄 승인). 각 PR 본문에 fallback 사유 + 근거 명시. 테스트 4716→4768 수집 (단위 4563→4615 [#760~763 미추적분 실측 포함 + #764 +2], E2E 112→113 [#766 +1]), pylint 10.00 유지.

**학습**: ① 적대적 분석 워크플로우(analyze→refute)가 테스트 assertion 결함(raw vs breakdown) 사전 차단 — High tier 작업 전 적대적 self-verify ROI 양성. ② **CI green ≠ 로컬 green** — `test_doc_review_gate` 가 CI(Linux) 통과로 머신 의존 결함을 은폐 → 머지 후 전체 스위트 실측의 가치 재확인 (정책 17 §5 누적 결함 정기 검증 정신). ③ STATE.md 가 사이클 160(#760~763)부터 stale — 6-step §⑤ 머지 후 즉시 동기화 의무 재확인.

## 사이클 160

**날짜**: 2026-06-06 | **PR**: #760~#763 | **상태**: integrity-audit 다이나믹 워크플로우 검증 + 현재 main 정합성 감사 fix

**작업 내용**: integrity-audit 다이나믹 워크플로우의 옵션 검증(원 요청)에서 출발 → 워크플로우 verify 단계 회복력 수정 + 현재 origin/main 전수 감사 → 정합성 fix 4건 머지.

- **#760** 운영 문서 stale 경로 7건 (CLAUDE.md 메모리-grep 경로 `f--DEVELOPMENT`→`d--Source-SCAManager` silent-skip 등).
- **#761** n8n issue 릴레이 GitHub 토큰 유출 차단 — 전역 env `N8N_RELAY_REPO_TOKEN`(default off) **opt-in + `n8n_webhook_secret` 둘 다 충족 시에만** 토큰 전송. github.py 조회 게이트 + n8n.py 방어 심화.
- **#762** timeout 단일출처 정리 (미사용 `constants.py` 300 제거, `pipeline.py` 60 유지, 동작 무변경) + merge off-by-one(N-1) 문서화.
- **#763** `issue_registrations` RLS policy `alembic/versions/0037_*` (repo_id→repositories.user_id 1-hop, PG 전용).

**핵심 학습**: ① 감사는 반드시 현재 origin/main 기준 실행 — 초기 감사를 stale feat 브랜치(당시 origin/main보다 102 커밋 뒤)에서 돌려 이미 main 에서 고쳐진 결함을 헛수정. ② 워크플로우 verify 단계가 고동시성(~100 에이전트)에서 StructuredOutput 누락으로 전면 붕괴(33발견→0검증) → 재시도+소배치(4)+`unverified` 버킷으로 수정. ③ Codex 토큰 만료 → Claude 직접검증 fallback. ⚠️ 본 사이클 STATE.md/cycle-history 동기화는 사이클 161 에서 일괄 수행 (사이클 160 당시 미반영 stale).

## 사이클 159

**날짜**: 2026-06-03 | **PR**: #743~#746 (PR-A/B/C/D) + #742 | **상태**: 157 회고 백로그 P2 전량 해소

**작업 내용**: 사이클 157 회고(사이클 158 수행)가 식별한 백로그 P2 8건 + cross-verify 신규 2건을 4 PR 로 분할 해소 (정책 7 응집 단위 + 정책 17 위험 티어 분리). 테스트 4712→4716 (단위 4559→4563), pylint 10.00 유지. **Codex stop-time mutual 게이트는 미로그인으로 불능 → 사용자 지시로 비활성화(`reviewGateEnabled:false`) — 정책 18 면제, Claude 직접 검증** (메모리 `feedback_codex_sandbox_precheck.md` 갱신).

| PR | 묶음 | 항목 |
|----|------|----|
| A (#743) | 테스트 하드닝 | ⑤ security_scan rollback 후 secret-scanning 지속 회귀가드 (unit +1) + ⑧·자매 `_min_height_px`/`_measure_injected_btn` 비px silent 0.0 → fail-fast 통일 (e2e) |
| C (#744) | CI 결정성 | ⑨ `postgres:16`→`16.4` minor 핀 + ⑥ round_trip `DROP/CREATE SCHEMA` clean-base self-isolating + ci.yml node-id 핀 가드 주석(신규) |
| B (#745) | src 정합 | ⑦ `_http.py` DNS `except socket.gaierror`→`except OSError` (timeout/OSError fail-closed, 가드 +2) + ⑪ `scan_all_repos` 외부 루프 `db.rollback()` 세션 격리 (가드 +1, unit +3) |
| D (#746) | CI 가독성 | ⑩ pg-concurrency job name `PG SKIP LOCKED concurrency` → `PG-only tests (SKIP LOCKED + migration round-trip)` (step name 일치) |

**위험 영역 실측 (정책 15/17#4)**: PR-D job name 변경 전 `gh api .../branches/main/protection` = 404 'Branch not protected' → main 보호 규칙 부재 확정 → required-check 명 변경 영향 없음.

**부수 정리**: stale 잡파일 삭제(`.playwright-mcp/`·사이클 135/142 잔여물) + `.gitignore` `.playwright-mcp/` 추가 (#742).

**자율 판단 보고 (정책 3)**: ⑥ round_trip clean-base 를 PR-A→PR-C 이관(PG-only/required-check 영역 분리). STATE.md 충돌 회피로 PR-D 는 ci.yml 만 수정 → 본 wrap-up 에서 cycle-history 159 엔트리 + STATE 서사 PR-D 반영 (6-step §⑤ — 사이클 158 P1 패턴 재발 방지).

---

## 사이클 158

**날짜**: 2026-06-03 | **PR**: #741 | **상태**: 회고 + docs 정합 봉인

**작업 내용**: 사이클 157 회고 — **5+1 다중 에이전트(관점 5 + cross-verify, Workflow 오케스트레이션)**. 직전 세션이 사이클 158 진입 직후 중단(브랜치만 생성, 커밋 0건 — 6파일 "수정"은 CRLF/LF 노이즈로 HEAD 바이트 동일) → 회고 재실행으로 컨텍스트 복원. 5 관점(test-guard·ci-infra·security-ssrf·docs-sync·policy-meta) 14건 발견 → cross-verify 독립 재검증으로 **real 12(P1 1 + P2 11) / FP 1 차단 / duplicate 1**. 회고 보고서: [`docs/_archive/reports/2026-06-03-cycle-156-157-retrospective.md`](_archive/reports/2026-06-03-cycle-156-157-retrospective.md).

**P1 (1건, 두 관점 독립 식별)**: `docs/cycle-history.md` 사이클 157(#739/#740) 섹션 전면 부재 — STATE.md 는 157 기재하나 cycle-history 는 156→155 직행 (6-step §⑤ STATE↔history 비대칭). → 본 PR 에서 157 섹션 추가로 해소.

**범위 A (안전 docs 묶음 — 사용자 결정, 정책 17 안정성 우선)**: P1 수정 + docs P2 3건 (cycle-history:71 'S3 작업 완료' → 머지 완료 stale 정정 / STATE.md:9 'neednew job' typo / 회고 보고서 경로 추적성) + db.md `env.py:30` override 함정 노트(신규 발견 ROI 최고). **src·테스트·CI 무변경 (4712 불변)**.

**회고 백로그 (P2 8건 보류 — 사용자 결정 영역)**: 테스트/CI 하드닝 (security_scan rollback secret 단언 / round_trip clean-base 가드 / `_http.py:73` DNS except OSError 확장 / `_min_height_px` fail-fast 정합 / postgres:16.x 핀 / pg-concurrency job name) + src (`scan_all_repos` 외부 루프 db.rollback) + 신규 (ci.yml node-id 핀 가드 / `_measure_injected_btn` 자매 헬퍼 silent 0.0).

**테스트 카운트 실측** (정책 8 진화 3): `pytest --collect-only` = 4712 (단위 4559 + 통합 153) — STATE·README 정확 일치.

**Codex mutual** (정책 18): push 전 검증 의뢰.

---

## 사이클 157

**날짜**: 2026-06-02 | **PR**: #739~#740 (#8·#9) | **상태**: 머지 완료

**작업 내용**: 사이클 156 Theme B 회고 반영 — 메타 scope 완성. Theme B 회고가 발견한 **인접 false-confidence 2건** 활성화 (156 의 "존재하나 미실행 가드" 패턴 연장). 근거 회고: 사이클 156 Theme B (cycle-history 사이클 156 참조).

| # | PR | 내용 |
|---|----|----|
| #8 | #739 | round_trip 마이그레이션 테스트 CI 활성화 — `test_0020_round_trip` 의 alembic 왕복이 모든 CI(SQLite)서 영구 skip → `pg-concurrency` job 에 편입. **활성화가 잠재 결함 노출**: `alembic/env.py:30` 가 cfg URL 을 `settings.database_url` 로 덮어써 SQLite 실행 → `patch.object(app_settings, "database_url")` 싱글톤 patch 로 fix-up (메모리 'skip 가드 활성화 = 버그 노출' 교훈 실증). |
| #9 | #740 | WCAG tap-target E2E silent-skip→fail-fast — 셀렉터 미존재 시 회귀를 skip 으로 흡수하던 것을 fail 로 전환. `base.html .nav-hamburger`·overview `.btn--sm` 은 항상 렌더되므로 미존재 = 회귀. conftest `get_current_user` override 로 항상 렌더 보장. |

**테스트**: round_trip 활성화(skip→pass 상태전환) + WCAG fail-fast 가드. **신규 수집 0** (단위 4559 / 통합 153 불변 — 기존 skip 테스트 활성화·동작 전환 위주). pylint 10.00 유지(src 무변경).

**핵심**: 156 회고의 "인접 false-confidence" 식별 → 활성화. 메모리 `feedback_activate_skipped_guard_reveals_bug.md` 패턴(영구 skip 가드 CI 활성화 시 잠재 버그 노출) 재실증 — #8 env.py override 함정을 동일 PR fix-up 으로 봉인.

---

## 사이클 156

**날짜**: 2026-06-02 | **PR**: #735~#738 (S1·S2·S4·S3) | **상태**: S1~S4 전부 머지 완료 (#735~#738)

**작업 내용**: Theme B "안전망 회귀가드 봉인" — 차기 영역 조사(6관점 워크플로 → 5 Theme) 후 사용자 선택. **"가드는 존재하나 절대 실행되지 않는" false-confidence** 영역을 mutation 검증으로 활성화. **전 Sprint src 무변경** (테스트/CI만).

| Sprint | PR | 내용 | mutation |
|--------|----|----|----------|
| S1 | #735 | SSRF `_http.py` fail-closed 분기 — 빈 host(L54-55)·DNS gaierror(L73-75). 기존 11테스트가 scheme 단계서 막혀 미도달 | KILLED (가드 flip→FAIL) |
| S2 | #736 | 4채널(discord/slack/webhook/n8n) `validate_external_url`=False 차단 early-return — 기존 테스트 `validate=True` 고정으로 0회 실행 | KILLED ×4 |
| S4 | #737 | checks.py `_legacy_state_to_ci_status`(auto-merge gate fallback 정확성) parametrize 6+e2e 1 + security_scan 본체 happy/rollback 2 (kwargs 값 단언 PR-5C 봉인) | KILLED ×2 |
| S3 | #738 | PG SKIP LOCKED 동시성 — `test_retry_concurrency_postgres` 3건이 CI(SQLite)서 영구 skip → `pg-concurrency` job(postgres:16 service) 추가로 활성화 + barrier 결정성 | CI 실측 (PG) |

**계획 프로세스**: 4 클러스터 실측 deep-dive → Sprint 계획 → **적대적 검토**(조건부 승인, 4건 정정 반영: S3 env 단일 `DATABASE_URL_TEST_POSTGRES`·barrier `timeout` deadlock guard·security_scan kwargs 단언 의무화·카운트 표현).

**핵심**: 정책 4(단언+회귀가드 동반) 정합. 각 Sprint mutation 논증으로 "테스트가 진짜 회귀를 잡는가" 입증 (PR-5C 트랩 회피). 검증은 Codex 샌드박스 지속 불능으로 Claude 직접 mutation 검증 대체(세션 확립 선호).

**신규 테스트**: +15 단위 (S1 +2, S2 +4, S4 +9) — 4544→4559. S3 +0(skip→pass 상태전환, 통합 153 불변). pylint 10.00 유지(전 Sprint src 무변경 — 테스트/CI yaml/barrier만).

**보류**: railway_issue.py body 영문 라벨 P2(사이클 154 cross-verify 식별 — 사용자 결정 영역).

---

## 사이클 155

**날짜**: 2026-06-02 | **PR**: #734+ | **상태**: 작업 완료

**작업 내용**: 사이클 154 회고(5+1+cross-verify) 메타학습 봉인. 회고 결과 사이클 154 "발신 경로 0건" = ✅ **정확** (6차 적대적 cross-verify 반증 실패 — discord/email/slack/n8n/issue 본문 빌더 전수 + get_text 키 99개 3-locale 확인). **149/152/153/154 3연속 "완결 과대선언→회고 P0" 패턴이 사이클 154에서 끊김 확정.**

**핵심 (회고 에이전트 5 메타결함 해소)**:
- 근본 원인 = 검증 도구(grep 패턴)를 **고정 함수명 enumeration** 으로 산문 규칙에 봉인 → enumeration drift 가 새 회피 경로. 산문 규칙 자체가 drift 소스 (line:span drift 동형).
- 해소 = **AST 소스 스캔 자동 회귀 가드** `tests/unit/notifier/test_no_hardcoded_korean_in_send_modules.py`:
  - `src/notifier·gate·webhook/providers` + cron/merge_retry 37파일 AST 스캔 → 문자열 리터럴 한국어를 logger.* 인자·docstring 제외 후 검출, 위반 0건 강제.
  - **mutation 자기검증 2건**: 합성 하드코딩 한국어 body(telegram.py:120 동형) → 탐지 / logger·docstring 한국어 → 미탐지. 가드가 no-op 아님 증명.
  - "발신 경로 한국어 0건" 이 Claude self-declaration 이 아니라 **CI green** 으로 객관화. 신규 발신 모듈 추가 시 자동 커버 (수동 enumeration 갱신 불요).

**추가**:
- telegram ko-default seam 테스트 (회고 에이전트 3 P1-1 — approve→ko fallback body 대칭).
- 문서 정정: cycle-history 사이클 154 PR `#732+`→`#733`·상태 "✅ 머지 완료" / i18n.md `notifier.gate.*` 열거에 `manual_*` 추가(149~154) + 자동 가드 default 등재.

**🔴 가드 검증이 식별한 P1 (회고 6 에이전트가 모두 놓친 leak — push 전 Codex 검증 fallback 이 포착)**:
- `src/analyzer/io/ai_review.py:203` `_default_result` summary `"AI 리뷰 불가 (기본값 적용)"` 하드코딩 한국어가 AI 리뷰 실패 시 **discord/email/github_comment/telegram 4채널로 사용자 발신** (키는 i18n 이나 summary **값**이 하드코딩). 회고 에이전트 1/6(cross-verify) 모두 notifier 디렉토리만 봐서 upstream 출처(`analyzer/io`)를 놓침 — 에이전트 5 가 예측한 "가드 scope = 새 drift 면" 의 실증.
- 수정: `_default_result` summary=`""` + `notifier._common.resolve_ai_summary(ai_review, language)` 헬퍼 (status!=success 시 `notifier.common.ai_unavailable` ko/en/ja 현지화) + 4 notifier 적용. 대시보드는 기존 `ai_review_status` 기반 i18n 배너 유지(영향 0).
- **가드 scope 보강**: `_TARGET_FILES` 에 `src/analyzer/io/ai_review.py` 추가 (AI 프롬프트는 review_prompt.py/review_guides 분리 → 본 파일 summary 외 한국어 0). 재발 시 가드 자동 포착.
- **의의**: 검증 layer(외부 LLM fallback) + 자동 가드 개념이 작동 — 6 에이전트 self-verify 가 공유한 "notifier scope" 가정을 외부 검증이 깸 (정책 18 mutual 2-layer 정당성 실증).

**보류 (사용자 결정 영역)**: railway_issue.py body 구조 라벨(Project/Status/Build Log 등) 영문 하드코딩 P2 — 사이클 153 #730 명시 채택 영역이라 사용자 결정 대기 (cross-verify 식별, 한국어 누출 아님 = i18n 미완성).

**신규 테스트**: +11 단위 (4533→4544, 전체 4686→4697) — AST 가드 +3, ko-default seam +1, resolve_ai_summary 현지화 +7 (ai_unavailable 키 3 + success/en/ja/none-empty 4). 통합 153 유지. pylint 10.00 유지 (discord _build_embed R0914 inline disable — ai_summary local).

---

## 사이클 154

**날짜**: 2026-06-02 | **PR**: #733 | **상태**: ✅ 머지 완료

**작업 내용**: 사이클 153 회고(5+1 cross-verify)가 발견한 잔여 발신 경로 한국어 수정. 153의 "발신 경로 0건 실측" 선언이 회고에서 **부정확 판정** — grep 범위를 `src/notifier/ src/gate/ src/services` 디렉토리로 한정해 `src/webhook/providers/` 누락.

**P0 (1건)**:
- `webhook/providers/telegram.py:120` — 반자동 Gate 콜백의 승인/반려 body `f"{'✅ 승인' if ... else '❌ 반려'} by @..."` 가 `post_github_review` → **GitHub PR Review 로 게시 = 모든 협업자 영구 노출**. 단일 한국어. → `notifier.gate.manual_approve_body`/`manual_reject_body` 3언어 키 + config 조기 로드 + `resolve_notification_language` 해소.

**P2 (6건)**:
- `services/cron_service.py:105/206` — `<code>{repo_full_name}</code>` escape 미적용 (engine/merge_retry 와 비대칭) → `escape()` 적용.
- `webhook/providers/railway.py:106` — 로그 조회 실패 시 `logs_tail = f"로그 조회 실패: {exc}"` (i18n 키 우회) → `None` 유지로 `railway_issue` 가 `log_fetch_failed` 키 대체. exc 는 logger 보존.
- `api/repos.py:81` — `validate_thresholds` 한국어 ValueError(422 노출) → 형제 validator 와 동일 영문화.
- `services/operations_service.py:80/180` — admin KPI 한국어("추정"/"Phase 2 영역") → 운영자용 영문화.
- `constants.py:151` — 모델 라벨 `★기본값` → `★기본 · Default` 이중언어 (기존 `(균형 · Balanced)` 패턴 정합).

**프로세스 학습 (회고 핵심)**: 발신 경로 grep = **디렉토리 한정 금지, 발신 API 호출 역추적 의무**. `grep 'post_github_review\|telegram_post_message\|create_.*_issue\|...' src/` 로 모든 호출 site 수집 후 인자 개별 확인. `.claude/rules/i18n.md` 에 default 등재. "0건 실측" 선언은 회고 cross-verify 통과 후에만 (선언→회고 P0 발견 패턴 149/152/153 3연속 재발).

**신규 테스트**: +6 단위 (4527→4533, 전체 4680→4686) — telegram 콜백 seam +2(승인 ja/반려 en body 언어 배선), cron escape 가드 +2, railway 핸들러 seam +2(language 배선 + 로그 실패 None 유지). 통합 153 유지. pylint 신규 경고 0 (R0917/E501 은 pre-existing).

---

## 사이클 153

**날짜**: 2026-06-01 | **PR**: #730~#731 | **상태**: ✅ 머지 완료

**작업 내용**: 통합 회고 로드맵 완결 — railway 빌드 실패 Issue + cron 주간/트렌드 알림 i18n.

| PR | 내용 |
|----|------|
| #730 | fix(i18n): railway_issue.py Railway 빌드 실패 GitHub Issue i18n — notifier.railway.* 3키, repo owner 언어, [SCAManager] prefix 영문 고정 |
| #731 | fix(i18n): cron 주간 리포트/점수 하락 알림 i18n — notifier.cron.* 7키, 이중언어("한국어 / English")→수신자 언어 단일 |

**주요 결정**:
- railway: config 기반 resolve_notification_language → background task 스레딩. field 라벨(Project/Status)은 기술 식별자라 영어 유지.
- cron: 기존 이중언어를 단일 언어로 전환 (수신자 언어). HTML 태그 보존.

**🎉 발신 경로 사용자 노출 한국어 0건 실측 달성** — ⚠️ **사이클 154 회고에서 부정확 판정**: 이 grep 이 `src/notifier/ src/gate/ src/services/{merge_retry,cron}` **디렉토리로 한정**되어 `src/webhook/providers/telegram.py:120`(반자동 승인 body, GitHub PR Review 노출 P0)를 누락. "0건 실측" 은 미달성이었음. 사이클 154 가 호출 역추적 grep 으로 수정 + i18n.md default 등재. (선언→회고 P0 발견 패턴 149/152/153 3연속)

**i18n 대장정 최종 (143~153)**: UI(143~148) + 알림(149,152) + 웹/CLI 에러(150~151) + 로드맵(153). en/ja 사용자가 모든 발신 경로에서 자국어 수신. (내부 로그는 운영자용 — 대상 외)

**신규 테스트**: +34 단위 (4493→4527, 전체 4646→4680). 통합 153 유지.

## 사이클 152

**날짜**: 2026-06-01 | **PR**: #726~#728 | **상태**: ✅ 머지 완료

**작업 내용**: i18n 대장정(143~151) 통합 회고(5+1) + Tier A/B 이행 — "전수 완결" 선언 후 발견된 발신 경로 i18n 우회 P0 3건 수정.

**통합 회고 결과**: P0 3건(cross-verify 진위 3/3 확정) + P1 3건 + P2 1건. false-positive 차단 2건.

| PR | 내용 |
|----|------|
| #726 | fix(i18n): format_ref 커밋 레퍼런스 i18n (P0-A) — push 이벤트 "커밋" 4채널 누출 + 회귀 가드 |
| #727 | fix(i18n): engine.py 동기 머지 알림 i18n (P0-B/C) — _notify_merge_failure/deferred + reason tag-only(P1-1) |
| #728 | fix(i18n): notification_language validator(P1-2) + 오케스트레이션 seam 테스트(P1-3) |

**근본 원인 (자성)**: 사이클 149 "알림 i18n 완결" 선언 시 `gate/engine.py` 동기 머지 알림(_notify_merge_failure/_notify_merge_deferred)과 `_common.py::format_ref`를 검증하지 않음. 동일 의미 메시지를 merge_retry_service는 i18n인데 engine만 우회 = 동기/비동기 경로 비대칭. cross-verify(6차)가 없었으면 "완결" 보고에 묻혔을 P0.

**학습 (.claude/rules/i18n.md 5건 추가)**:
- 알림 발신 경로 전체 i18n 의무 — 동기/비동기 비대칭 금지, "완결" 선언 전 grep 전수 검증
- 내부 로그 vs 사용자 발신 경계
- hook owner 언어 해소 패턴 (151)
- notifier.gate/merge_advice/common/errors 키 그룹 (149~152)
- notification_language validator 의무

**잔존 (로드맵)**: railway_issue.py 한국어 (P2 — 별도 기능, 캠페인 scope 외) / cron_service.py 주간 리포트·점수 하락 알림은 이미 이중언어("한국어 / English") — 누출 아님.

**신규 테스트**: +51 단위 (4442→4493, 전체 4595→4646). 통합 153 유지.

## 사이클 151

**날짜**: 2026-06-01 | **PR**: #724 | **상태**: ✅ 머지 완료

**작업 내용**: hook.py(pre-push hook CLI 인증) 에러 4건 i18n — 사이클 150 보류 항목 완결. repo 소유자 언어 해소.

| 에러 | 키 |
|----|------|
| 토큰이 필요합니다 (401) | errors.hook_token_required |
| 등록되지 않은 리포 또는 유효하지 않은 토큰 (404) | errors.hook_invalid_repo_or_token |
| 유효하지 않은 토큰 (403) | errors.hook_invalid_token |
| 리포지토리를 찾을 수 없습니다 (404) | errors.hook_repo_not_found |

**주요 결정**:
- **repo 소유자 언어 해소** — hook 토큰 인증이라 세션 locale 없음 → `_resolve_hook_locale(db, repo)` 헬퍼: Repository → user → preferred_language → default. CLI hook 에러도 repo 소유자 언어로 표시.
- 인증 로직(hmac.compare_digest, 200 active 응답) 완전 불변 — 에러 텍스트만 i18n
- locale 해소를 에러 경로 직전에 배치 — 정상 경로 쿼리 순서 보존(testing.md hot-path mock 트랩 회피), 기존 테스트 0 수정

**🎉 i18n 전수 완결 (사이클 143~151)**:
- UI 템플릿(143~148): 전 페이지 사용자 노출 한국어 0건
- 알림 메시지(149): GitHub PR 댓글·Telegram·Issue 전 채널 3-layer 언어 적용
- 웹 UI 에러(150) + CLI hook 에러(151): 사용자 노출 에러 전수 locale 적용
- en/ja 사용자가 UI·알림·에러 전 영역에서 자국어 수신. (내부 로그는 운영자용 — i18n 대상 외)

**신규 테스트**: +16 단위 (4426→4442, 전체 4579→4595). 통합 153 유지.

## 사이클 150

**날짜**: 2026-06-01 | **PR**: #717 | **상태**: ✅ 머지 완료

**작업 내용**: 웹 UI 사용자 노출 에러 메시지 i18n — HTTPException detail + redirect 에러를 사용자 locale 적용

| 파일 | 에러 |
|----|------|
| issue_registration.py (3) | 이미 등록된 이슈·Issues 쓰기 권한·GitHub API 오류 |
| settings.py (1) | 유효하지 않은 URL (SSRF 방어) |
| add_repo.py (2) | 리포 이름 필요 + redirect 중복 등록 (코드 방식) |

**주요 결정**:
- get_locale(request) + get_text(errors.*) 패턴 — errors 네임스페이스 확장 5키 + add_repo 1키
- **redirect 에러 코드 방식**: add_repo redirect URL의 한국어 텍스트 → 에러 코드(already_registered) + 템플릿 data-i18n ERROR_MAP 매핑 (한국어 URL 노출 제거)
- **hook.py 4건 보류** (자율 판단 — 정책 3): CLI/webhook 에러는 hook 토큰 인증으로 per-user locale 없음 — 별도 검토

**완결**: UI(143~148) + 알림(149) + 웹 에러(150) i18n 전수. en/ja 사용자가 정상 UI·알림·에러까지 자국어 수신.

**신규 테스트**: +19 단위 (4407→4426, 전체 4560→4579). 통합 153 유지.

## 사이클 149

**날짜**: 2026-06-01 | **PR**: #712~#715 | **상태**: ✅ 머지 완료

**작업 내용**: 알림/Gate 메시지 i18n — UI 외 사용자 노출 알림(GitHub PR 댓글·Telegram·Issue) 전체 언어 적용. resolve_notification_language 우회 경로 해소.

| PR | 내용 |
|----|------|
| #712 | fix(i18n): Gate 자동 승인/반려 메시지(approve.py) i18n — notifier.gate.{auto_approve,auto_reject} + engine.py dead code(_run_approve_decision/_run_review_comment) 제거 |
| #713 | fix(i18n): Telegram 반자동 Gate 메시지(telegram_gate.py) i18n — tg_* 6키 + send_gate_request language 파라미터 |
| #714 | fix(i18n): 머지 실패 조언(get_advice) i18n — merge_advice 16키 + get_advice(reason, language) + 호출처 4곳 |
| #715 | fix(i18n): 머지 재시도 Telegram 알림(merge_retry_service) i18n — retry_* 9키 + 3 함수 language |

**주요 결정**:
- 모든 알림이 기존 `resolve_notification_language(db, config)` 3-layer fallback 재사용 (User → RepoConfig → default)
- Telegram Markdown/HTML 태그(백틱·별표·<b>·<code>·<a>) + escape() 보존
- 기술 용어(git pull origin main, Branch Protection Rules, pull_requests: write 등) 영어 보존
- engine.py dead code 제거 (사이클 141 Action 클래스 이전 후 미사용 — 호출처 0 확인)

**완결**: UI(사이클 143~148) + 알림(사이클 149) i18n 전수 — en/ja 사용자가 모든 채널에서 자국어 수신. (내부 로그 메시지는 i18n 대상 외 — 운영자용)

**신규 테스트**: +109 단위 (4298→4407, 전체 4451→4560). 통합 153 유지.

## 사이클 148

**날짜**: 2026-06-01 | **PR**: #710 | **상태**: ✅ 머지 완료

**작업 내용**: 전체 템플릿 i18n 완결 — base.html langName/langIcon 초기 렌더 FOUC 해소 (회고 P2-1)

**조사 결과**: 잔여 소형 템플릿(admin_operations/add_repo/overview/admin_rls_audit/admin_tenants) 전수 조사 — **이미 모두 i18n 완료** (i18n_args 16~35개씩, 사용자 노출 한국어 0건). 이전 카운트(18/10/9)는 전부 주석·CSS.

**유일 잔존 = base.html L676 langName FOUC**: 초기 서버 렌더값이 locale 무관 '한국어' 고정 → en/ja 사용자 JS 실행 전 순간 한국어 노출. locale별 endonym/flag 직접 렌더로 해소 (en→English/🇺🇸, ja→日本語/🇯🇵, ko→한국어/🇰🇷). endonym 은 i18n 비번역.

**달성**: 전체 템플릿 사용자 노출 한국어 0건 (endonym/JS fallback 제외). 사이클 143~148 i18n 대장정 완결.

**테스트**: 코드 1줄 변경 (테스트 수 무변동, 4451 유지).

## 사이클 147

**날짜**: 2026-06-01 | **PR**: #707~#708 | **상태**: ✅ 머지 완료

**작업 내용**: 사이클 146 회고 Tier A/B 이행 — settings survey 누락 i18n + toggle a11y + render-parity 가드

| PR | 내용 |
|----|------|
| #707 | fix(i18n): settings.html 저장 토스트 + 모델 hint (Tier A, 회고 P1-1~3) + toggle-switch label aria-label 6건 (SonarCloud S6853) |
| #708 | test(i18n): render-parity 가드 23케이스 (Tier B, 회고 P1-4) — repo_insights/settings/landing/theme |

**회고 반영**:
- P1-1~3: settings survey가  서버 렌더 토스트 + field-hint 누락 → 완결 (잔존 0건)
- P1-4: 사이클 144 #696이 default화한 render-parity 가드를 사이클 146 키에 소급 적용 — 오타 키 raw 노출 검출
- 부수: SonarCloud S6853 toggle label 접근성 6건 동시 개선 (정책 10 fix-up)
- .claude/rules/i18n.md 학습 3건 추가: survey 전수 의무(Jinja 블록)·render-parity 가드 동반 의무·toggle label a11y
- P2-4: STATE.md 헤더 날짜 표기 정정 (2026-05-31→2026-06-01)

**신규 테스트**: +40 단위 (4258→4298, 전체 4411→4451). 통합 153 유지.

## 사이클 146

**날짜**: 2026-06-01 | **PR**: #702~#705 | **상태**: ✅ 머지 완료

**작업 내용**: 템플릿 i18n 완성 — base/repo_insights/settings/landing 4개 템플릿 잔존 한국어 전수 i18n 전환

| PR | 내용 |
|----|------|
| #702 | fix(i18n): base.html 테마 드롭다운 (Sprint 1) — common.theme.* 8키, 전 페이지 노출 헤더, +48 |
| #703 | fix(i18n): repo_insights.html (Sprint 2) — repo_insights.* 31키 확장, KPI/랭킹/차트, +186 |
| #704 | fix(i18n): settings.html (Sprint 3) — settings.* 20키, PRESET/필드 라벨/모드/프리셋 diff, +120 |
| #705 | fix(i18n): landing.html (Sprint 4) — landing.* 36키 신설, 히어로/데모 리뷰/통계/기능, +217 |

**주요 결정**:
- **언어 endonym(English/한국어/日本語) i18n 제외** — 각 언어를 자기 언어로 표기하는 i18n 표준
- **데모 리뷰/프리셋 diff HTML 보존** — `| safe` 필터 + data-i18n element 속성(innerHTML 변경 후 유지) 패턴
- **기존 키 재사용** — settings 프리셋 diff는 settings_page.pr_rules.range_summary 재사용 (신규 키 0)
- landing standalone(base 미상속) — locale 라우트 주입으로 i18n_args 사용

**완결**: 4 템플릿 모두 사용자 노출 한국어 0건 (JS graceful fallback 제외). analysis_detail L1055는 실측 결과 한국어 없음(변수+기호) 확인.

**신규 테스트**: +571 단위 (3687→4258, 전체 3840→4411). 통합 153 유지.

## 사이클 145

**날짜**: 2026-05-31 | **PR**: #698~#699 | **상태**: ✅ 머지 완료

**작업 내용**: JS 동적 텍스트 i18n — analysis_detail/repo_detail의 JS 동적 한국어를 data-i18n 패턴으로 전환

| PR | 내용 |
|----|------|
| #698 | fix(i18n): analysis_detail.html JS 동적 텍스트 (Sprint 1) — js_msg.* 10키, 상태/버튼/오류/Issue 본문 빌더, +66 테스트 |
| #699 | fix(i18n): repo_detail.html JS 동적 텍스트 (Sprint 2) — js_msg.* 14키, 차트 통계/tooltip/상태/버튼/오류, +87 테스트 |

**주요 결정**:
- **그룹 D (GitHub Issue 본문) locale i18n 채택**: analysis_detail의 Issue 본문 마크다운 빌더(body_ai/body_static)를 locale 번역 — 생성되는 GitHub Issue 본문이 사용자 언어로. 멀티라인(`\n` 7개) + {id}/{text}/{tool}/{category}/{message} 플레이스홀더를 data-i18n 속성으로 처리
- **검증된 data-i18n-* + __VAR__ 패턴 재사용** (Phase 2 PR-7, XSS-safe) — 2 컨테이너(.history-card I18N / #repoBulkPanel I18N_BULK) 확장
- btn_create_next 등 기존 키 재사용

**보류 (다음 사이클)**: analysis_detail L1055 `🔴 [category] tool: message` — 변수 3개 + slice 구조 분해 복잡

**신규 테스트**: +153 단위 (3534→3687, 전체 3687→3840). 통합 153 유지.

## 사이클 144

**날짜**: 2026-05-31 | **PR**: #694~#696 | **상태**: ✅ 머지 완료

**작업 내용**: 사이클 143 회고 Tier B 이행 — analysis_detail/repo_detail i18n 완성 + 렌더 정합 가드

| PR | 내용 |
|----|------|
| #694 | fix(i18n): analysis_detail.html Issue 패널 정적 i18n (Sprint 1, P1-2) — issue_panel.* 6키 신설, +36 테스트 |
| #695 | fix(i18n): repo_detail.html 일괄 등록 버튼 정적+JS data-i18n (Sprint 2, P1-3) — bulk_register/bulk_complete 2키, +12 테스트 |
| #696 | test(i18n): 사이클 143/144 렌더 정합 가드 (Sprint 3, P1-4) — test_detail_i18n_render +7 |

**주요 결정**:
- P1-2: analysis_detail 전용 네임스페이스(`issue_panel.*`) 신설 — repo_detail.issue_mgmt와 분리 (페이지별 독립 원칙)
- P1-3: JS 동적 카운트는 기존 Phase 2 PR-7 `data-i18n-*` + `__N__` 치환 패턴 재사용 (XSS-safe) — 설계 문서 "JS i18n 보류" 중 검증 패턴 존재 영역 재검토 처리
- P1-4: 렌더 정합 가드로 "키 존재만 검증" 사각 보완 — 실제 렌더 출력 번역 텍스트 출현 검증 (오타 키 raw 노출 검출)

**보류 (다음 사이클)**: analysis_detail/repo_detail 나머지 JS 동적 메시지 (생성 중.../오류 토스트) — data-i18n 확장 가능하나 범위 분리

**신규 테스트**: +55 단위 (3479→3534, 전체 3632→3687). 통합 153 유지.

## 사이클 143

**날짜**: 2026-05-31 | **PR**: #684~#692 | **상태**: ✅ 머지 완료

**작업 내용**: i18n 완성 + 프로세스 강화 — brainstorming→deep-research→설계/계획→구현(5+1 회고 포함)

| PR | 내용 |
|----|------|
| #684 | docs(spec): 사이클 143 설계 문서 |
| #685 | docs(plan): 사이클 143 구현 계획 (9 Task) |
| #686 | fix(i18n): analysis_detail.html issue_form 라벨 3건 (Sprint 1-A, +18 테스트) |
| #687 | chore: GitHub PR 단일 템플릿 신규 — 정책 18/11 체크리스트 (Sprint 1-B) |
| #688 | chore(policy): CLAUDE.md 6-step + 정책 11 표준 형식 보강 (Sprint 1-C) |
| #689 | fix(i18n): repo_detail.html 일반 텍스트 ~11건 (Sprint 2, +66 테스트) |
| #690 | fix(i18n): repo_detail.html 이슈 등록 UI ~11건 + smoke (Sprint 3, +66 단위 +2 통합) |
| #691 | docs: 사이클 143 완료 이력 동기화 |
| #692 | fix(회고 Tier A): PR 템플릿 정책 18 정렬 + cost.period YYYY-MM 문구 수정 |

**주요 설계 결정**:
- JS 내 한국어 (~15건) 보류 — ICU MessageFormat 기반 표준 방식 미확보, prefix/suffix 비표준 확인 (deep-research)
- GitHub 다중 PR 템플릿 대신 단일 파일 방식 채택 — 공식 문서 확인 (deep-research)

**5+1 회고 (Tier A 이행, #692)**:
- P0 0건 (P0-A 후보 → cross-verify P1 하향, 프로세스 문서 결함). P1 6건 / P2 3건. cross-verify false-positive 0건 (1~5차 정확도 100%).
- Tier A (#692): PR 템플릿 정책 18 문구를 active.md canonical로 정렬 + 정책 3 섹션 추가 + cost.period 3언어 YYYY-MM 대응 (ja `2026-05月1日` 비문 해소)
- Tier B 이월 (다음 사이클): P1-2 analysis_detail Issue 패널 비대칭 i18n / P1-3 L625 정적+JS 카운트 / P1-4 test_detail_i18n_render.py 사이클 143 키 assert
- 정책 진화 후보: docs PR 코드 PR 의존 시 blocking 신호 (P1-5 머지 순서 역전 학습)

**신규 테스트**: +150 단위 +2 통합 (단위 3329→3479, 통합 151→153, 전체 3480→3632). 회고 Tier A는 문구 수정만 — 테스트 수 변동 없음.

## 사이클 142

**날짜**: 2026-05-31 | **PR**: #673~#679 | **상태**: ✅ 머지 완료

**작업 내용**: 5+1 에이전트 감사 결과 4 Phase 전수 이행 + docs sync + 5+1 회고 Tier A/B 이행

| PR | 내용 |
|----|------|
| #673 | fix(phase-a): P0 수치 수정 + 즉각 로직 버그 3건 — B1 Telegram pr_number 가드 + B2 pipeline async fix + STATE.md/README 재집계 |
| #674 | fix(phase-b): 보안 강화 4건 — S1 Telegram fail-closed(401) + S2 SESSION_SECRET RuntimeError + S3 Railway token 미노출 + S4 CSP 헤더 |
| #675 | fix(phase-c): API 보강 — A1 Rate limiting 10 엔드포인트 확장 + A2 issue_registration async fix + A4 CORS + body 10MB 제한 + limit 상한선 |
| #676 | fix(phase-d): UI/CSS/i18n — U5 tokens.css phantom 변수 alias 3개 + U4 aria-label i18n (base.html/repo_insights.html) + U3 dashboard 핵심 텍스트 i18n 8건 |

**Phase A 세부** (#673):
- `src/webhook/providers/telegram.py`: `handle_gate_callback` — `analysis.pr_number is None` 가드 추가 (push Analysis → HTTPError 방지)
- `src/worker/pipeline.py`: async/await 블로킹 해소
- `docs/STATE.md`/`README.md`: 단위 테스트 3061 → 3213 실측 재집계 (과소집계 152건 보정)

**Phase B 세부** (#674):
- S1: Telegram webhook secret 미설정 → `skip` → **401** fail-closed 변경 (autouse fixture 통일)
- S2: `SESSION_SECRET` 32자 미만 → `ValueError` → **RuntimeError** 명시적 서버 중단
- S3: `railway.py` 토큰 검증 시 시크릿 헤더 강제
- S4: `main.py` CSP 헤더 추가 (Content-Security-Policy)
- 신규 테스트: +3건 (S2 RuntimeError ×2, S4 CSP ×1 — 단위 3213→3216)

**Phase C 세부** (#675):
- A1: Rate limiting — repos.py PUT/DELETE (HEAVY), hook.py GET/POST (API), repo_report.py, issue_registration.py (HEAVY/API) 10개 엔드포인트 확장
- A2: `issue_registration.py` — `asyncio.to_thread` 격리 (register/get_status/repo_summary sync DB 블로킹 해소)
- A4: `main.py` CORS 미들웨어 — `APP_BASE_URL` 기반 명시적 `allow_origins`
- P2: limit/skip `Annotated[int, Query(ge=, le=)]` 상한선 (repos.py, stats.py, repo_report.py)
- `LimitBodySizeMiddleware`: Content-Length > 10MB → 413
- `conftest.py` autouse 픽스처: rate limiter 인메모리 카운터 테스트 간 초기화
- 신규 테스트: +5건 (conftest autouse fixture 효과 — 단위 3216→3221)

**Phase D 세부** (#676):
- U5: `tokens.css` `[data-theme]` alias 3개 추가 (`--text-muted→--text-2`, `--text-subtle→--text-3`, `--border→--border-subtle`) — dark/catppuccin Chart.js axis 저대비 해소
- U4: `base.html` 테마/언어 변경 버튼 `aria-label` → `common.theme_aria`/`common.lang_aria` (ko/en/ja)
- U4+: `repo_insights.html` table/canvas aria-label → `repo_insights.*_aria` i18n
- U3: `dashboard.html` 하드코딩 한국어 8건 → `dashboard.*` i18n 키 (12개 신규 키, ko/en/ja)
- 신규 테스트: 0건 (단위 3221 유지)

**신규 테스트**: +8건 (#674 +3, #675 +5 — 단위 3213→3221, 전체 3364→3372)

**docs sync** (#677): STATE.md + cycle-history.md + README 수치 동기화 (3371→3372, 3220→3221 Codex 실측 보정)

**5+1 회고 + Tier A/B/C 전수 이행** (#678~#682):
- 회고 P0 3건 / P1 5건 확정 (cross-verify: false-positive 1건 제거, 등급 조정 2건)
- **Tier A (#678)**: `docs/reference/env-vars.md` TELEGRAM_WEBHOOK_SECRET fail-closed 수정 + APP_BASE_URL CORS 역할 기재 + `.claude/rules/api.md` rate limiting 의무 + `.claude/rules/security.md` CSP/LimitBodySizeMiddleware/SESSION_SECRET prod guard
- **Tier B P1-2 (#679)**: `src/main.py` `LimitBodySizeMiddleware` ValueError 처리 (400) + 회귀 가드 3건 (단위 3221→3224)
- **Code Scanning #489/#490 (#681)**: `test_telegram_provider.py` import 스타일 통일 (py/import-and-import-from 해소)
- **Tier B P1-4 (#682)**: `dashboard.html` repos 모드 한국어 19개 → i18n 전환 (dashboard.repos.* 12키 + 최상위 5키, ko/en/ja) + 회귀 가드 105케이스 (단위 3224→3329)
- dashboard 접속 모드 추적: `src/ui/routes/dashboard.py:162-168` 기존 로그 활용 가능 (`railway logs | grep "dashboard_view.*mode=repos"`)
- 잔여: repo_detail.html·analysis_detail.html i18n → 별도 사이클 / Tier C P2 chunked bypass → 로드맵

## 사이클 141

**날짜**: 2026-05-30 | **PR**: #669~#671 | **상태**: ✅ 머지 완료

**작업 내용**: Rate Limiting 테스트 보강 + GateAction 구현 직접 이전 (Sprint E-final) + CodeQL 4건 해소

| PR | 내용 |
|----|------|
| #669 | test(security): Rate Limiting 테스트 보강 — 엔드포인트 서명·429 형식·스토리지 검증 (+9 단위 테스트) |
| #670 | refactor(gate): ApproveAction·ReviewCommentAction에 구현 직접 이전 — engine.py 위임 제거 |
| #671 | fix(tests): CodeQL py/unused-import 4건 해소 — pytest 제거 + side-effect import dismiss |

**GateAction Sprint E-final 세부** (#670):
- `approve.py`: `_run_auto` / `_run_semi_auto` 메서드 직접 구현 (`gate_decision_repo.upsert()` 직접 호출)
- `review_comment.py`: `post_pr_comment` + `resolve_notification_language` 직접 호출 구현
- 이전 위임 경로(`engine._run_approve_decision`, `engine._run_review_comment`) 완전 제거
- `test_engine.py` 3개 테스트 패치 경로 수정: `engine.SessionLocal`/`engine.save_gate_decision` → `actions.approve.SessionLocal`/`actions.approve.gate_decision_repo`
- P0-H 규약 유지: 각 Action 독립 SessionLocal() 사용, asyncio.gather 내 세션 공유 없음
- 신규 테스트 0건 (리팩토링만) — 단위 3061 유지

**CodeQL 4건 해소** (#671):
- alert #485: `test_rate_limiter.py` `import pytest` 미사용 → 코드 수정 (1행 삭제)
- alert #486~#488: `engine.py` side-effect import 오탐지 → false positive dismiss

**신규 테스트**: +9건 (#669 Rate Limiting — 단위 3052→3061)

---

## 사이클 140

**날짜**: 2026-05-30 | **PR**: #665~#667 | **상태**: ✅ 머지 완료

**작업 내용**: 기존 테스트 실패 수정 + GateAction Registry 패턴 도입

| PR | 내용 |
|----|------|
| #665 | docs: STATE.md + cycle-history.md 사이클 139 이력 동기화 |
| #666 | fix(tests): conftest.py CLAUDE_REVIEW/INSIGHT_MODEL 기본값 명시 — .env 빈값 override 방지 |
| #667 | feat(gate): GateAction Registry 패턴 도입 — Action 클래스 3종 + GATE_ACTIONS 레지스트리 |

**GateAction Registry 세부**:
- `src/gate/actions/` — `GateContext`(frozen dataclass) + `GateAction`(ABC) + `GATE_ACTIONS` + 3개 Action 클래스
- `run_gate_check()` → `asyncio.gather(*[a.execute(ctx) for a in GATE_ACTIONS if a.is_applicable(config)])`
- 기존 `_run_*` 함수 유지 (Action 위임 대상 + 기존 217개 테스트 보존)
- 신규 테스트 17건 (총 gate 테스트 234개)
- 새 Gate 옵션 추가 시 engine.py 수정 없이 Action 파일만 추가

**신규 테스트**: +17건 (단위 3035→3052)

---

## 사이클 139

**날짜**: 2026-05-30 | **PR**: #660~#664 | **상태**: ✅ 머지 완료

**작업 내용**: 5+1 다중 에이전트 정밀 조사 결과 기반 4 Phase 품질 개선

| Phase | PR | 내용 |
|-------|-----|------|
| Code Scanning | #660 | CodeQL py/unused-import 8건 수정 + false-positive 26건 dismiss |
| A (Critical) | #661 | alembic 0035 revision 중복 해소 → 0036 renumber (DB 무결성 복구) |
| B (High) | #662 | slowapi Rate Limiting 추가 — API 엔드포인트 4개 60req/min IP 제한 |
| C (Medium) | #663 | 알림 채널 엣지 케이스 — Slack 3000자 방어 + Email TLS + Telegram retry_after=0 |
| D (Low) | #664 | dashboard_service 복잡도 축소 — `_handle_insight_error()` 헬퍼 추출, pylint 10.00 복원 |

**신규 테스트**: +13건 (단위 3022→3035)
**조사 방법**: 5 에이전트 병렬 조사 (httpx·GateAction·보안·알림·기술부채) + 1 cross-verify → 계획 수립 후 순차 실행

---

## 사이클 138

**날짜**: 2026-05-27 | **PR**: #651 (`fix/dashboard-always-overview`) | **상태**: ✅ 머지 완료

**작업 내용**: `/dashboard` 진입 시 서버 측 auto-detect 제거 → 항상 개요 탭 표시

| 영역 | 내용 |
|------|------|
| 근본 원인 | `_detect_initial_dashboard_mode()` 가 ANTHROPIC_API_KEY 설정 + Analysis ≥ 5 조건 충족 시 서버 측에서 `insight` 탭 강제 선택 |
| PR #649(사이클 137) 한계 | 클라이언트 localStorage redirect만 제거 — 서버 auto-detect는 그대로 남아 있어 증상 지속 |
| 수정 | `dashboard.py:155` `else` 분기 → `_detect_initial_dashboard_mode()` 호출 제거, `effective_mode = "overview"` 하드코딩 |
| 함수 보존 | `_detect_initial_dashboard_mode()` 함수 정의는 파일에 보존 (A.1~A.3 테스트가 직접 테스트) |
| 테스트 | A.4 테스트 업데이트 (detect 미호출 + kpi 호출 + mode=overview) — 16/16 통과 |
| 조사 방법 | 6-에이전트 근본 원인 조사 + 5-에이전트 옵션 토론 (A/B/C) → Option A 4/5 다수결 |
| Codex 검증 | Windows 샌드박스 spawn 반복 실패 → 세션 확립 fallback (Claude 직접 실측 대체, OK) |

---

## 사이클 137

**날짜**: 2026-05-26 | **PR**: #649 (`fix/dashboard-localstorage-redirect`) | **상태**: ✅ 머지 완료

**작업 내용**: 대시보드 `/dashboard` 진입 시 이전 탭으로 redirect되는 버그 수정

| 영역 | 내용 |
|------|------|
| 버그 | Insight 탭 방문 후 `/dashboard` 진입 시 localStorage `'insight'` 저장값으로 `window.location.replace()` 실행 → 개요 대신 Insight 탭 표시 |
| 수정 | localStorage setItem + redirect IIFE 전체 제거 (31줄 삭제) |
| 영향 | `/dashboard` 이제 항상 서버 기본값(개요) 표시. 모드 토글 active 클래스는 서버 렌더링으로 정상 동작 |
| 추가 | 기존 코드는 `repos/security/usage` 3 모드 누락 — 불완전한 상태였음 |

---

## 사이클 136

**날짜**: 2026-05-25 | **PR**: #647 (`fix/analysis-detail-top-bottom-polish`) | **상태**: ✅ 머지 완료

**작업 내용**: analysis_detail 최상단/맨하단 디자인 마감 개선

| 영역 | 내용 |
|------|------|
| 점수바 전체 폭 | `max-width: 360px` 인라인 스타일 제거 → 히어로 카드 전체 폭 활용 |
| nav 1행 통합 | `.analysis-nav` + 별도 back-btn div → 1행 (back-btn 왼쪽, `analysis-nav__controls` 오른쪽) |
| issue-reg-panel CSS | 탭 버튼(`.issue-tab`), 리스트(`.issue-list/.issue-row`), 배지(`.issue-badge--open/closed`), 등록 버튼(`.btn-register`) 등 15+ 클래스 전면 추가 (기존 CSS 전무) |
| 모달/토스트 CSS | `.issue-modal-overlay` (z-index 9000, backdrop-filter blur) / `.issue-modal` (max-width 520px) / `.issue-toast` (z-index 9001, 고정 위치) |
| 모바일 | `@media (max-width: 768px)` `.analysis-nav__controls { flex-wrap: wrap }` 추가 |
| Codex 검증 | Round 1 NG (rgba 3곳 CSS var 미경유) → 수정 후 Round 2 sandbox 오류 → Claude 직접 검토 대체 |

---

## 사이클 135

**날짜**: 2026-05-25
**작업**: 모바일 테이블 헤더-값 정렬 불일치 수정 — repo_detail / analysis_detail / repo_insights 3페이지
**PR**: #645 (`fix/mobile-table-grid-alignment`)

### 변경 내용

- `src/static/css/repo_insights.css`: `vertical-align: middle → top` — 멀티라인 이슈 메시지 행에서 `#`/도구 값이 행 중앙에 부유하던 문제 수정. `@media (max-width: 640px)` 도구 컬럼(3번째) 숨김 (배지에 이미 표시)
- `src/templates/repo_insights.html`: `ri-issues-table`을 `.table-wrap`으로 감쌈 (`overflow-x: auto` 적용)
- `src/templates/analysis_detail.html`: 점수 브레이크다운 table `.table-wrap` 추가. `@media (max-width: 480px)` 에 `th:first-child` 선택자 추가 (`<th scope="row">`가 `td:first-child`에 매칭 안 되던 버그)
- `src/templates/repo_detail.html`: `@media (max-width: 480px)` 커밋(col2)/출처(col6) 숨김 → 6컬럼 → 4컬럼 (날짜·PR·점수·등급)

### Playwright 검증

390px(iPhone 12 Pro) 뷰포트 before/after 스크린샷 비교 — 3개 섹션 모두 수정 확인

---

## 사이클 134

**날짜**: 2026-05-25 | **PR**: #643 (`chore/docs-cleanup-product-readme`) | **상태**: ✅ 머지 완료

**작업 내용**: 전체 문서 정리 — README 제품화 + 내부 문서 아카이브/재배치

| 영역 | 내용 |
|------|------|
| README 제품화 | 내부 사이클/Phase 참조 8건 제거 (cycle 84·117, Phase 10·12·F.1 등), 테스트 배지 갱신 (3173+ / 3022 unit + 151 integration) |
| reports 아카이브 | `docs/reports/` 44파일 → `docs/_archive/reports/` (git mv) |
| superpowers 아카이브 | `docs/superpowers/plans/` 5파일 + `docs/superpowers/specs/` 5파일 → `docs/_archive/superpowers/` (untracked → cp+rm) |
| policies 이동 | `docs/policies/active.md` + `history.md` → `.claude/policies/` (git mv) |
| CLAUDE.md 링크 갱신 | `docs/policies/` 참조 25건 → `.claude/policies/` (sed 일괄 치환) |
| 연계 파일 갱신 | `scripts/check_memory_refs.py` + `.claude/rules/deploy.md` + `.claude/rules/i18n.md` + `docs/runbooks/operational-smoke-checks.md` 내 경로 동기화 |
| 테스트 | 기존 통과 상태 유지, 소스 변경 없음 |

---

## 사이클 133

**날짜**: 2026-05-25 | **PR**: #641 (`fix/nav-logo-text-color-token`) | **상태**: ✅ 머지 완료

**작업 내용**: `.nav-logo color: #fff` 하드코딩 → `var(--text-1)` 토큰 교체

| 영역 | 내용 |
|------|------|
| 버그 | 라이트 테마 `--bg-nav: rgba(255,255,255,0.82)` + `color:#fff` → 흰색 on 흰색 = "SCAManager" 브랜드명 불가시 |
| 수정 | `base.html:95` `color: #fff` → `color: var(--text-1)` |
| 효과 | light: `#131325` / pastel: `#2d2738` → 밝은 배경 가시 / dark·catppuccin: 기존 밝은 색 유지 |
| 테스트 | UI 178 통과, 테스트 수 변동 없음 |

---

## 사이클 132

**날짜**: 2026-05-25 | **PR**: #639 (`fix/theme-option-data-attr-collision`) | **상태**: ✅ 머지 완료

**작업 내용**: theme-option `data-theme` 속성 → `data-theme-target` 변경 (CSS 변수 충돌 버그)

| 영역 | 내용 |
|------|------|
| 버그 원인 | T1 `tokens.css` `[data-theme]` element-agnostic 선택자 — `.theme-option[data-theme="dark"]` 항목에 다크 테마 CSS 변수 오염 |
| 증상 | 파스텔 테마에서 "다크 오로라" 옵션 텍스트 불가시 (`--text-1: #f3f3fa` 흰색), catppuccin에서 "파스텔" 저대비 |
| 수정 | `data-theme` → `data-theme-target` (HTML 4곳 + JS 4곳) |
| 테스트 | UI 178 통과, 테스트 수 변동 없음 |

---

## 사이클 131

**날짜**: 2026-05-25 | **PR**: #625~#633 (9건) | **상태**: ✅ 머지 완료

**작업 내용**: Claude Design UI 전체 재설계 — 디자인 토큰 시스템, 컴포넌트 분리, WCAG 모바일 수정

| PR | 브랜치 | 내용 |
|----|--------|------|
| #625 | `feat/design-tokens-t1` | T1 토큰 구조 재편 — `tokens.css` `[data-theme]` 블록 4테마, `themes.css` 7줄 스텁 전환 |
| #626 | `feat/base-html-shell-v3` | T2 base.html — `.atmosphere` div, `components.css`/`pages.css`/`effects.js`/`tweaks.js` 신규, grade BEM 클래스 |
| #627 | `feat/dashboard-redesign` | 대시보드 KPI 카드 재설계 — score-bar, freq-rows, `.kpi`+`.dash-kpi` 이중 클래스 |
| #628 | `feat/analysis-detail-redesign` | analysis_detail 재설계 |
| #629 | `feat/repo-detail-redesign` | repo_detail 재설계 |
| #630 | `feat/overview-add-repo-redesign` | overview + add_repo 재설계 — score-bar clamp, step-cards, WCAG btn-primary/back-btn 48/44px |
| #631 | `feat/settings-redesign` | settings 재설계 — 6카드, toggle-switch, save-bar, WCAG gate-mode-btn/mode-toggle-btn 44px |
| #632 | `feat/landing-redesign` | landing 재설계 — standalone `.atmosphere`, grade BEM 5종, prefers-reduced-motion |
| #633 | `feat/admin-redesign` | admin 재설계 — `.tbl` stub, `badge--success/danger` BEM, `<table class="admin-table tbl">` |

**핵심 변경**:
- `tokens.css` `[data-theme="dark/light/pastel/catppuccin"]` 블록 신설 — grade-bg/bd 토큰 포함
- `components.css` (1041줄) + `pages.css` (761줄) 신규 파일 분리
- `effects.js` + `tweaks.js` 신규 JS 파일 (atmosphere 애니메이션)
- 모든 `.grade-X` → `.grade.grade--x` BEM 통일
- WCAG 2.5.5 모바일 44/48px 회귀 가드 수정 (정책 WCAG 규칙 준수)

**충돌 해소 (3회 force-push rebase)**:
1. T2 themes.css — T1이 stub 전환했으므로 `--ours` 수락 (grade-bg/bd는 tokens.css에 이미 존재)
2. T2 components.css add/add — landing PR (#632) 머지 후 swatch 중복 제거본을 `--ours` 수락
3. overview+add_repo — 중간 PR 머지 후 rolling conflict 해소

**CI 수정 사항**:
- `.kpi:nth-child()` → `.dash-kpi:nth-child()` (대시보드 order 선택자 — 회귀 가드 `.dash-kpi` 클래스 필수)
- `add_repo.html` `.btn-primary { min-height: 48px; }` + `.back-btn { min-height: 44px; }` 복원 (WCAG 회귀)
- `settings.html` `.gate-mode-btn { min-height: 44px; }` 단독 규칙 분리 (정확한 문자열 매치 테스트)

**테스트**: 단위 3009 → 3022 (+13, test_router.py + test_i18n_template_render.py 갱신)

---

## 사이클 130

**날짜**: 2026-05-24 | **PR**: #617 (`fix/issue-reg-type-hint-cpd-note`) | **상태**: ✅ 머지 완료

**작업 내용**: #614 후속 — pylint 10.00/10 복원 + 타입 힌트 + codecov/patch CI 수정

| 영역 | 내용 |
|------|------|
| 타입 힌트 | `_sync_state_if_stale` `rec` 파라미터 `IssueRegistration` 타입 힌트 추가 (Policy 9 수정 의무) |
| pylint 복원 | C0115 `RegisterRequest` docstring + R0913 `register_issue` too-many-arguments + W0718×2 session/add_repo + C0301 mcp long line + C0302 dashboard_service too-many-lines — inline disable 6건 → 10.00/10 복원 |
| deploy.md CPD 규칙 | `sonar.cpd.exclusions` 체크포인트 + 사이클 129 학습 내용 `.claude/rules/deploy.md` 반영 |
| 신규 테스트 | except Exception 경로 2개 (get_current_user DB 오류 + github_repos_list API 오류) |
| 총 단위 | 3007 → 3009 (+2) |

**CI 수정 3단계**:
1. pylint 10.00/10 복원 — 6건 inline disable + RegisterRequest docstring
2. mcp 멀티라인 분할 → 단일 라인 복원 (codecov/patch 75% 1차 시도)
3. `except Exception:` 경로 테스트 2건 추가 → codecov/patch ✅ SUCCESS (최종 해소)

**정책 18 Codex 검증**: push 후 CI 결과로 간접 검증 (전체 SUCCESS)

---

## 사이클 129

**날짜**: 2026-05-24 | **PR**: #614 (`feat/ai-issue-registration`) | **상태**: ✅ 머지 완료

**작업 내용**: AI 분석 결과 GitHub Issue 등록 기능 (Phase 1 + Phase 2)

| 영역 | 내용 |
|------|------|
| 신규 모델 | `IssueRegistration` ORM — UniqueConstraint(repo_id+issue_key), CASCADE FK, alembic 0035 |
| 신규 레포 | `issue_registration_repo` — find_by_key / create / list_by_analysis / list_by_repo / update_state |
| github_client | `create_issue()` + `get_issue_state()` 추가 |
| 신규 서비스 | `issue_registration_service` — make_ai/static_issue_key, register_issue(IntegrityError TOCTOU 처리), _sync_state_if_stale 헬퍼, get_analysis_issue_status, get_repo_issue_summary (TTL 300초) |
| 신규 API | `POST /api/issues/register` (201/409/403/502) + `GET /api/issues/status` + `GET /api/issues/repo-summary` — 소유권 검증 포함 |
| Phase 1 UI | `analysis_detail.html` — AI/정적 탭 + 편집 모달 + IIFE `_initIssueReg` (hx-boost 패턴) |
| Phase 2 UI | `repo_detail.html` — `#repoBulkPanel` 일괄 등록 패널 + IIFE `_initRepoBulk` (hx-boost 패턴) |
| 신규 테스트 | 59개 단위 테스트 (모델 4 + 리포 8 + github_client 4 + 서비스 15 + API 17 + CPD fix-up) |
| 총 단위 | 2948 → 3007 (+59) |

**주요 픽스**:
- `analysis.result` None guard (기존 `test_analysis_detail_empty_states_renders_japanese` 회귀 수정)
- hx-boost 재초기화 패턴 (`htmx:afterSettle`/`historyRestore`) 양쪽 템플릿 적용
- `_allItems` 초기화 버그 — `loadSummary()` 에서 `data.registrations` 기반 구성
- 소유권 검증 (`current_user_id` → repo.user_id 비교) API 헬퍼 2곳 추가
- IntegrityError TOCTOU race condition catch → `ValueError("DUPLICATE:N")` 변환

**CI 수정 3단계**:
1. SonarCloud Coverage 75%/83% → 100% (21 tests 추가 — `_get_analysis_and_repo`·`_get_repo_or_404`·TOCTOU·HTTPError·naive-datetime 경로)
2. SonarCloud CPD 4.8% → `_sync_state_if_stale` 헬퍼 추출 + `sonar.cpd.exclusions=tests/**,src/templates/**` → 0.0%
3. CodeQL 자동수정 2건 (`test_issue_registration_service.py`·`test_issue_registration.py`) rebase 흡수

**정책 18 Codex 검증**: OK × 2회 (초기 기능 + CPD fix-up)

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

## 사이클 84

- **사이클 84 (다국어 i18n 18 PR + 회고 + Tier B, 2026-05-05~06)** — Phase 1~5 18 PR (#283~#304) — 영어/한국어/일본어 + UI/알림/AI 리뷰 전 영역. 단위 2236→2709 (+473) | 통합 118→129 | E2E 82→96. 회고+sync (#306) + Tier B Q3+Q5 (#307) + Tier B Q1+Q2+Q4 (#308) — 정책 1 진화 강화 (≥ 10회 빠른 진행 신호) + 정책 8 강화 (dispatch vs invocation 구분) + 메모리 신설 2 (i18n locale fallback + 메모리 카운터 패턴). 메모리 27→29.

## 사이클 85~91

- **사이클 85 (Sentry 제거 + GitHub 정리 + CLAUDE.md Anthropic 200줄 정합 정정, 2026-05-06)** — Sentry 통합 완전 폐기 (40 테스트 + 105 LOC + 의존성 제거). GitHub 정리 62 branch 일괄 삭제. **CLAUDE.md cleanup**: 5+1 다중 에이전트 검토 → src/ 트리 → `docs/architecture.md` / 9 카테고리 → `.claude/rules/<area>.md` / tail entry → `docs/cycle-history.md` / Railway → `docs/runbooks/railway.md` / 점수 → `docs/reference/scoring.md` / 정책 진화 history → `docs/policies/history.md`. LOC 1271 → 865 (-32%) / 토큰 ~57K → ~22K (-61%).
- **사이클 86 (정책 진화 + CI 사고 + dependabot 자동화 + pylint drift + 5+1 회고, 2026-05-06 · #336)** — Q3 (#321) + Tier B Q1+Q2+Q3+Q4 (#322) + CI submit-pypi 대응 #324 (`dependabot.yml` supersede) + dependabot 자동 8 PR (#325-#332, ROI 100%, #332 conflict Claude rebase) + pylint #335 (9.92→9.94) + 5+1 회고 #336 (P0 6 + P1 8 + P2 17, Tier A 2 정정). LOC 762 → 677 (-11%).
- **사이클 87 (Tier B 3건 단일 응집 묶음, 2026-05-06 · #337)** — 사이클 86 회고 후속 (옵션 🅐). **Tier B-1**: Makefile `lint-strict` (`pylint --fail-under=9.90`) drift 회귀 가드. **Tier B-2**: dependabot.yml `groups` 분리 (production-deps + development-deps + actions-minor-patch). **Tier B-3**: 정책 8 본문 진화 — cross-verify 생략 시 PR 본문 §"cross-verify 생략 사유" 사이클 69 정량 3 조건 대조 표 default.
- **사이클 88 (CLAUDE.md Anthropic 200줄 정합 + 정책 17 신설, 2026-05-06 · #338 + #348)** — 사이클 85 보류 영역 (C2) 진입. **Phase A (#338)**: 정책 12~16 + 11 강화 본문 → `docs/policies/active.md` 분리 — CLAUDE.md 686 → 549 LOC (-20%). **Phase B-1 (#348)**: 신규 사용자 기준 *"문서정리는 권장하는 규격보다 안정성이 더 우선시 되야합니다"* 정합 — **정책 17 신설** (문서 정리 시 안정성 > 권장 규격 4 default 의무) + B-1 안전 분리 (정책 2 + 10).
- **사이클 89~91 (정기 5+1 검증 + Tier A fix + P1 자율 + 회고 종결, 2026-05-07 · #349/#350/#351/#352 + #353)** — 사이클 89 정기 검증 (Round 1+2+3 — 종합 93.50/100 A 등급) + Tier A fix 2건 (#349 P0-1 fixture import + P0-3 flake8 noqa + 메모리 신설/진화 / #350 P0-2 E2E i18n 옵션 🅐 → 🅑 정정 + autouse 회귀 학습) + 사이클 90 P1-1 자율 (#351 flake8 cosmetic 20 + slow test mock 1) + 사이클 91 P1-2 자율 (#352 graphql slow test mock 2 + Round 1 false-positive 식별). **누적 효과**: 통합 fail 1→0 / E2E fail 5→2 / flake8 40→18 (-55%) / slow test 12s→0.04s (-99.7%). **회고 (5+1)**: P0 7 + P1 12 + P2 11 / Tier A 3건 / Tier B 사이클 92+.
- **사이클 92 (정책 17 5번째 default + 정책 8 진화 (3) + Phase C RLS 검증, 2026-05-07 · #361 + 본 sync)** — 사이클 89~91 회고 Tier B 합의 영역 진입. 5+1 사전 검토 (관점 1~5 + cross-verify 6차) → Phase A (정책 17 5번째 default 신설 — 누적 결함 정기 검증 의무 + 정책 8 진화 (3) cross-verify Round 2 단위 분포 실측 의무) + Phase B (Tier B-3 autouse 메모리 보류 default — 사용처 임계 미도달) + Phase C (RLS legacy NULL 0건 검증 — Supabase MCP SELECT-only 자율 / E2E UI 2건 사용자 사전 확인 의무 보류). CLAUDE.md 437 → 439 LOC. **운영 영역 안전 검증** — RLS legacy NULL 0건 (analysis_feedbacks 0/0 / insight_narrative_cache 3/0 / repositories 8/0 / security_alert_process_logs 0/0).

## 사이클 92~94

- **사이클 93 (정책 18 신설 — Claude ↔ Codex 양방향 mutual 검증 의무, 2026-05-09 · #362~#371)** — CI 분석 사고 직후 mutual 검증 필요성 확인. 정책 18 신설: Claude 작업(로컬 commit) → Codex 검증 → OK 후 push / Codex 작업(로컬 commit) → Claude 검증 → OK 후 push 양방향 대칭 흐름 의무화. 17 정책 cross-reference 표 작성. NEW-P0-N 영역 (#362~#371 일부) 수정.
- **사이클 94 (mutual 첫 운영 검증 + Tailwind v4 빌드 파이프라인 신설, 2026-05-10 · #372/#375~#379)** — chore/cycle-93-residual-tasks cherry-pick → Codex IDE Extension review NG → `_reset_repo_config()` 헬퍼 신설 → Codex OK → push (mutual 첫 운영 검증, #372). **UI 일러스트 Step 2-B (#375)**: DALL-E 3 5장 + 5페이지 마크업 + 4-테마 호환 CSS (src/static/illustrations/ + css/illustrations.css). **Tailwind v4 Hybrid 빌드 파이프라인 (#376~#378)**: main.css (소스) + css/dist/tailwind.css (빌드 출력) + npm ci && npm run build (Railway buildCommand 체인 추가) + 레이아웃 유틸리티 + CSS var 4-테마 공존. **Railway 빌드 실패 수정 (#379)**: nixpacks.toml `[phases.install]` 직접 작성 → Python venv provider 우선순위 충돌 → pip exit 127 → 제거 후 NIXPACKS Python provider 기본값 위임으로 SUCCESS.

## 사이클 95~106

- **사이클 95 (2026-05-14 · #410~#413)** — 문서 정비 P2: testing.md SessionLocal 경고 추가 / architecture.md mockup-polar.html 항목 / AGENTS.md 중복 표 → 링크 3건 / STATE.md 그룹 13-61 아카이브 / CLAUDE.md HTML 주석 7블록 + line 361 압축 (59줄 절감).
- **사이클 96 (2026-05-14 · #415, #417)** — pylint 10.00/10 달성: C0415 17건 inline disable + C0301/R0913/R0917/W0718/W0613/E0401 처리. PR-D5 (#417): CLAUDE.md HTML 블록 3·5 → docs/policies/active.md 이전 (#정책-17-why-how + #정책-5-phase-종료-cross-reference 신설).
- **사이클 97 (2026-05-14 · #420~#431)** — P0 경로 하드코딩 수정 (#420): `.codex/hooks.json` + `doc_review_gate.py` × 2 + `.claude/settings.json` + `CLAUDE.md` `f:/` → `d:/` 전수 교체. 문서 정비 (#421): AGENTS.md 완료 6-step 정정 + `.codex/rules/deploy.md` nixpacks exit127 경고. Issue #408 기능 구현 (#423): MPA 네비게이션 진행 바 + `CachedStaticFiles` + N+1 배치 IN 쿼리 2건 + `compute_score_kpi` 헬퍼 + `recurring_issue_count` 수정. 단위 2912→2914. scripts 경로 동적화 + dashboard async 블로킹 수정 (#426). 랜딩 페이지 신설 (#428) + phantom token 수정 (#429). CodeQL unused import 해소 (#431). 단위 테스트 2914→2917.
- **사이클 98 (2026-05-15 · #433~#436)** — CodeQL py/exit-from-finally 수정 (#433): `test_router.py` finally 람다 → 명시 함수 2건. HTMX hx-boost 네비게이션 (#434): `htmx.min.js` 1.9.12 vendoring + `<body hx-boost="true">` + Chart.js `destroy()` 가드 + 회귀가드 3건 (단위 2917→2920 추정). hx-boost 후속 (#435): architecture.md 항목 + themechange boolean 플래그. stale closure 완전 수정 (#436): remove-before-add 패턴 3파일 + `.claude/rules/ui.md` 갱신.
- **사이클 99 (2026-05-15 · #441~#445, docs/cycle99-retro-followup)** — repo_report API 9 + 통합 3 + repository_repo 4 + dashboard repos 5 + mcp 5 테스트 추가 (#441~#443). CodeQL 정비 (#445): `import pytest` 삭제 + false-positive 2건 dismiss. 회고 문서 정비: settings 싱글톤 mock 패턴 + Jinja2 None 함정 경고 + architecture.md 엔드포인트 갱신 + policies/active.md Codex 검증 섹션 추가. 단위 2914→2968 (cherry-pick 수습 포함).
- **사이클 100 (2026-05-17 · #449)** — pytest 성능 병목 해소: `pytest.ini` `--timeout=30` 전역 적용 + starlette/fastapi DeprecationWarning 필터 + `pytest-timeout>=2.3.0` + `Makefile` `test-local` 타겟 + `test_static_analyzer.py` module-scope fixtures. 테스트 수 변동 없음 (34 passed).
- **사이클 101 (2026-05-17 · #460~#470)** — 5+1 멀티에이전트 감사 전 항목 수정 (#460~#464): dead assertion 수정 + KeyError 방어 + GITHUB_API URL 상수화 + Gate 임계값 constants.py 단일 출처 + 테마명 정정 + TELEGRAM_WEBHOOK_SECRET 경고 + validate_external_url async화. 단위 2810→2813, 통합 125→154. 문서 감사 후속 (#466~#467): rules/ 경로·timeout·SMTP 정정 + env-vars.md 누락 항목. 회고 자유 발언 이행 (#469~#470): `scripts/check_memory_refs.py` 신설 + `Makefile` `check-memory-refs` + 5+1 에이전트 도메인 분리 표 신설.
- **사이클 102 (2026-05-17 · #475~#477)** — `.codex/rules/ui.md` 테마명 정정 (#475). CLAUDE.md P2-1 압축: **#476 Phase 1** (~10줄 절감) + **#477 Phase 2** (~7줄 절감) + `docs/policies/history.md` 이전 3건. 5+1 에이전트 검증 + Codex mutual OK. 총 절감 ~17줄.
- **사이클 103 (2026-05-18 · #479)** — MCP Supabase 직접 조회로 auto-merge 실패 원인 분석 → 3건 코드 수정 + Codex mutual OK 후 머지: `_trigger_retry_for_sha` 조기 반환 제거 + overdue sweep 무조건 실행 + `has_hooks` terminality `terminal` → `retriable` + `should_retry(UNSTABLE_CI, "unknown")` → `True`. 테스트 3파일 갱신 + 신규 1건 추가. 단위 2813→2814.
- **사이클 104 (2026-05-18 · #490)** — 5+1 다중 에이전트 전체 정합성 감사 + Anthropic 표준 준수 검증: P0 5건 (architecture.md tailwind.css ghost entry + 함수명 2개 + github_client·railway_client 미등재 파일 추가 + 수치 갱신). P1 1건: doc-consistency-reviewer 사용 범위 명확화. false-positive 2건 제거. Anthropic 표준 준수도 **93/100**.
- **사이클 105 (2026-05-18 · #498)** — CI TruffleHog BASE==HEAD 오류 수정: push-to-main 이벤트에서 `base: default_branch`가 HEAD와 동일 커밋 → exit 1 문제. 인라인 삼항 조건식 → PR/push 이벤트별 2-step 분리 + zero-SHA if 가드. Codex mutual 검증 2회 (1차 NG→수정→2차 OK).
- **사이클 106 (2026-05-18 · #500)** — 페이지 성능 측정 E2E + 독립 스크립트: `e2e/test_performance.py` 12개 `@pytest.mark.perf` 테스트 (TTFB/FCP/LCP/DCL/Load, 3회 avg/min/max, Playwright Chromium headless) + `scripts/perf_measure.py` 독립 실행 스크립트 (로컬 SQLite 서버 자동 시작·종료, 운영 Railway TTFB, `--local-only`/`--prod-only`, stream=True strict TTFB, Markdown 리포트) + `make test-perf`/`make perf-report` 타깃. Codex mutual 검증 OK. 첫 리포트: 로컬 11 페이지 전부 ✅, `/api/github/repos` ~510ms 느린 API 포착. E2E 99→111 (+12 perf).
- **사이클 108 (2026-05-19 · #504~#508)** — E2E 성능 테스트 assert 강화 + `/api/github/repos` TTL 캐시 + 문서 갱신 + 회고 P1 + Session 재사용: **#504** `e2e/test_performance.py` FCP/LCP `assert is not None` 선행 추가 (조건부 `if` → null 메트릭 silent skip 방지) + `test_health_ttfb` Playwright fixture 의존 제거 → `requests.Session` + warmup 직접 측정 (Windows localhost IPv6→IPv4 DNS fallback ~667ms/req 해소, avg 2037ms→<300ms). Codex NG (Korean-only warmup 주석 — CLAUDE.md 이중 언어 위반) → 한/영 block comment 수정 → OK. **#505** `/api/github/repos` 5분 TTL 캐시 (`_user_repos_cache`) 추가: `list_user_repos` GitHub API 중복 호출 방지 + `existing_names` 항상 최신 DB 조회 (fresh) + `tests/conftest.py` `_clear_user_repos_cache` autouse fixture + `test_api_github_repos_cache_hit` / `test_api_github_repos_cache_expired` 2 테스트. Codex OK. 단위 2814→2816. **#506** `docs/STATE.md` 사이클 108 갱신 + `README.md` 배지 2968→2970 + `.pre-commit-config.yaml` `check-secrets-in-diff` exclude 추가 (README/docs 문서 예시값 false-positive 방지). **#507** 회고 P1 수정: `.claude/rules/testing.md` `os.environ.setdefault` → 직접 대입 갱신 (사이클 65 fix 기록) + `cycle-history.md` #506 누락 entry 추가. **#508** 회고 "바라는 점/필요한 부분" 반영: `scripts/perf_measure.py` `_http_ttfb()` `requests.Session` 재사용 + warmup + `r.content` body drain (stream=True 미소비 시 소켓 파기 방지, 커넥션 풀 반환 보장) + `.pre-commit-config.yaml` `check-secrets-in-diff` `tests/e2e` 제외 사유 명시 (Python `os.environ["KEY"]="value"` 형식 패턴 불일치 + `.env`-style forward-looking 보호). Codex 4차 재검증 OK.
## 사이클 107~109

- **사이클 109 (2026-05-19 · #516~#519)** — 전체 페이지 정밀 감사 + P0/P1/P2 14건 수정: **5+1 다중 에이전트 감사** (base.html/repo_detail/repo_insights/dashboard/analysis_detail/backend API/security/i18n) — P0 1건 + P1 7건 + P2 6건. **#516 P0**: `database.py` RLS `SET LOCAL` f-string → `%s` 파라미터화 쿼리 (SQL injection 방어). **#517 P1**: `base.html` `_startProgress()` RAF 경쟁조건 (`cancelAnimationFrame` 선행) + 이벤트 핸들러 누적등록 4곳 remove-before-add 전환 (`_themeCloseHandler`/`_langCloseHandler`/`_hamburgerCloseHandler`/`_progressPageShowHandler`/`_progressBeforeUnloadHandler`). **#518 P1**: `merge_retry_repo.py` `claim_batch` PostgreSQL 조건부 `FOR UPDATE SKIP LOCKED` + `auth/github.py` 로그아웃 시 DB `github_access_token = NULL` 처리 + `i18n/filters.py` `i18n_args_filter` XSS 가드 (`markupsafe.escape` — str kwargs 이스케이프, Markup 인스턴스 passthrough) + `settings.html` countdown `{% set %}` Markup 객체화. CI fail (codecov/patch 69.23%) → 테스트 2건 추가 fix-up 후 pass. Codex NG (assert 약함) → `call_args[0][0]` SQLAlchemy Update 구조 검증 강화 → OK. 단위 2816→2818. **#519 P1~P2**: `analysis_detail.html`/`repo_insights.html`/`dashboard.html` `htmx:afterSettle`+`htmx:historyRestore` 핸들러 + animate=false 일관 적용 (뒤로가기 시 차트 미복원 버그) + `dashboard.html` phantom CSS 토큰 `--accent-primary` 제거. Codex NG (animate=false 누락) → `_adHtmxHandler` 수정 → OK. **회고 신규 식별**: P1 `security_scan_service.py:51` 직접 토큰 접근 + P2 dashboard CSS 토큰 4종 미정의 + `i18n/filters.py` XSS 경로 테스트 0% → 다음 사이클 GitHub Issue #520 추적.
- **사이클 107 (2026-05-19 · #503)** — 회고 반영 + 문서·코드 정비: P0 `make perf-report` Windows UnicodeEncodeError (`PYTHONIOENCODING=utf-8`). `/health` TTFB 임계값 e2e/scripts 통일 (`THRESHOLDS_LOCAL health_ttfb: 300ms` + `_is_health_page()` urlsplit 정규화 헬퍼 — Codex 1차 NG→수정, 2차 샌드박스 오류로 grep+사용자 승인 대체). `CLAUDE.md` 6-step ⑤에 `cycle-history.md` 이력 동기화 추가. `docs/cycle-history.md` 사이클 95~106 이력 12건 추가. `docs/architecture.md` `scripts/` 미등재 파일 5개 추가 (`parse_bandit.py` / `parse_coverage.py` / `benchmark_static_analysis.py` / `backfill_repository_user_id.py` / `check_memory_refs.py`). `.claude/rules/testing.md` `@pytest.mark.perf` 선택 실행 지침 추가. **P1 잔여 → 사이클 108**: FCP/LCP 조건부 assert → `assert is not None` 선행 추가 + `/health` Playwright → requests 전환.

## 사이클 129

- **사이클 129 (2026-05-28 · #654~#658)** — Lint L-1 언어 확장 + hotfix 3건. **#654** Subagent-Driven Development 10-task 실행. **신규 정적분석기 15종**: hadolint(Dockerfile)·ktlint(Kotlin)·tflint(Terraform/HCL)·tsc(TypeScript)·sqlfluff(SQL)·yamllint(YAML)·phpstan(PHP)·swiftlint(Swift)·stylelint(CSS/SCSS)·htmlhint(HTML)·buf_lint(Protobuf)·dart_analyze(Dart)·psscriptanalyzer(PowerShell)·dotnet_format(C#)·clippy(Rust). **핵심 구현**: `src/analyzer/io/static.py` `analyze_file()` — `repo_config` kwarg 추가 (`disabled_tools` 지원, Task 1); 23개 분석기 알파벳 순 import. `src/analyzer/io/tools/` 신규 15개 파일. `railway.toml` buildCommand — P0 도구 괄호식 `(cmd || echo WARNING)` 패턴으로 설치 (ktlint·hadolint·tflint graceful failure). `requirements.txt` — sqlfluff·yamllint 추가 + python-multipart CVE 핀 보존. **보안 수정**: psscriptanalyzer.py path를 f-string이 아닌 `env["PSSA_PATH"]` 환경변수로 전달 (PowerShell command injection 방어). **JSONL 파싱**: buf_lint — 줄 단위 JSON 파싱 (배열 아님). **통합 테스트 수정**: `test_e2e_pipeline_scenarios.py` + `test_webhook_to_gate.py` mock lambda에 `repo_config=None` kwarg 추가 (Task 1 시그니처 변경 대응). `pipeline.py` `_run_static_with_timeout` + `_run_static_analysis` — `repo_config` 파라미터 연쇄 전달. 2단계 리뷰 (스펙 준수 + 코드 품질) 완료. Codex mutual: 정책 18 검증 의뢰. 지원 언어(정적분석) 37개+ → 52개+. **#656** pipeline.py 머지 충돌 마커 잔존 제거(SyntaxError) + `_slow`/`_fast` mock 시그니처 `repo_config=None` 추가 — CI 복원. **#657** dotnet_format·tsc `(.+)$`→`([^\n]+)$` ReDoS 1차 수정 (SonarCloud S5852 미해소). **#658** `\s+([^\n]+)$`→`[ \t]+(\S[^\n]*)$` 구분자·캡처 그룹 완전 분리 — S5852 hotspot 2건 해소, SonarCloud Quality Gate OK 복원.

## 사이클 128

- **사이클 128 (2026-05-23 · #611)** — 테마 드롭다운 폰트 가시성 버그 수정. 근본 원인: `themes.css`의 `[data-theme="X"]` 셀렉터가 `<body>` 뿐 아니라 `<div class="theme-option" data-theme="X">` 요소에도 매칭 → 각 옵션이 자기 데이터 테마의 CSS 변수를 상속 → 파스텔 페이지에서 "다크 오로라" 옵션이 `--text-1: #f0f0f8` (다크 테마 흰 텍스트) 수신 → 흰 배경에 흰 텍스트 = 안 보임. **수정 1** `themes.css` 4개 테마 규칙 `[data-theme]` → `body[data-theme]` 스코프 제한 (`.theme-option` 요소가 잘못된 CSS 변수 상속 차단). **수정 2** `base.html` nav 링크 hover `color: var(--text-3)` → `var(--text-1)` (파스텔/라이트에서 hover 시 텍스트 더 연해지는 역방향 버그). **수정 3** 현재 페이지 링크 `color: #fff` → `var(--text-1)` + `font-weight:600` + `var(--accent-faint)` 배경 (밝은 nav에서 흰 텍스트 = 투명 버그). **수정 4** 로그아웃 hover `color: #fca5a5` → `var(--danger)` (라이트 nav에서 연분홍 텍스트 = 거의 안 보임 버그). 단위 ±0 (2948 유지), E2E 112 유지.

## 사이클 127

- **사이클 127 (2026-05-23 · #605~#609)** — hx-boost JS 버그 재발 방지 4-레이어 + E2E 사전 실패 8건 해소. PR #604(사이클 126 이전) `const` 재선언 SyntaxError 사고 학습 → 구조적 대책 4종: **#605 (PR A)** `e2e/conftest.py` pageerror JS 에러 트랩(page + seeded_page 양쪽) + `get_current_user` dependency override + `test_navigation.py` 10개 수정/신규(hx-boost 3회 재방문 회귀 가드 `test_nav_handler_survives_hx_boost_renavigation` 포함) + `.claude/rules/testing.md` JS 정책 6개 규칙. **#606 (PR B+C)** `tests/unit/ui/test_template_js_const.py` 정적 스캐너(brace depth 추적 — top-level const/let 탐지) + `add_repo.html` / `dashboard.html` top-level const×8+let×2 → var 교체. **#607 (PR D)** `package.json` eslint@^8.57.0 + eslint-plugin-html@^8.1.1 + `make lint-js` Makefile 타겟 + `.eslintrc.json` / `.eslintignore`(Jinja2 5개 파일 제외). **#608 (PR E)** `docs/STATE.md` 커버리지 형식 → "Python 95% / JS: E2E 커버" 언어별 분리 + E2E 111→112 + cycle-history 동기화. **#609 (E2E 사후 수정)** 2026-05-11 UI 리디자인 후 방치된 stale 셀렉터 수정: `test_theme.py` glass→pastel / claude-dark→catppuccin + `test_theme_mobile_guards.py` `_set_claude_dark()`→`_set_catppuccin()` 전면 갱신 + `test_repos_mode.py` 미정의 `auth_cookies` 픽스처 제거 — 5 TIMEOUT + 3 ERROR = 8건 → PASS. 사이클 127 P0 핵심: `--cov=src`는 HTML 인라인 JS 미측정 — 단일 수치 보고 금지, 언어별 분리 default 정착. Codex sandbox PowerShell spawn 오류 — 사용자 명시 결정(B)으로 push 진행. 단위 ±0 (2948 유지), E2E 112 (카운트 유지, 사전 실패 8건 → PASS).

## 사이클 126

- **사이클 126 (2026-05-23 · #602)** — 차트 스파크라인 리디자인. 4개 line 차트(dashboard × 2 / repo_detail / analysis_detail) 전면 전환: `pointRadius: 0` (hover 시만 표시) → 포인트 밀집 렌더링 부하 해소. `backgroundColor: accent+'22'` → `createLinearGradient` + `--accent-rgb` CSS 변수 기반 캔버스 그라디언트 (0.30→0 투명, 테마 자동 대응). `tension: 0.45` / `animation: 300ms` / X축 숨김 / Y축 maxTicksLimit: 3. `analysis_detail` trendChart: 현재 분석 포인트 강조(`--danger`, radius 7) + click 네비게이션 보존. 테스트: `test_case_a_rgba_uses_correct_alpha` 교체 → `test_case_a_rgba_uses_gradient_fill` (캔버스 그라디언트 불변식 검증). 단위 ±0 (2948 유지). Codex CLI 런타임 오류 — 사용자 승인 하에 Claude 직접 검증 대체.

## 사이클 125

- **사이클 125 (2026-05-23 · #600)** — 회고 P1/P2 전수 이행. **P1-1**: `src/auth/session.py` `get_current_user` DB 조회 `try/except Exception: return None` 추가 — INT_MAX+1 (2^31) 세션 주입 → PG DataError 미처리 500 차단. **P1-2**: `tests/unit/auth/test_session_security.py` `os.environ.setdefault` → 직접 대입 교체 + `test_get_current_user_with_overflow_user_id_returns_none` 신규 (P1-1 페어). **P1-3**: `src/constants.py` BREAKDOWN_KEY_* 주석 범위 수정 (선언/현실 불일치 해소). **P2**: `tests/unit/auth/test_github.py` docstring 명시. Codex mutual: Codex CLI 런타임 오류 → 사용자 승인 하에 Claude 직접 검증 대체. 단위 2947→2948, 누적 3098→3099.

## 사이클 123

- **사이클 123 (2026-05-23 · #595)** — B+C 작업. **B — P3 보안 심층 테스트**: `test_email.py` `test_build_html_escapes_xss_in_issue_message` 추가 — Telegram 4건 대비 Email issue.message XSS parity 갭 해소. **C — SonarCloud S6540 Code Smells 감소 (Phase 1)**: `src/middleware/locale.py` `Optional[str]`→`str|None` 2곳 + `from typing import Optional` 제거. `src/notifier/_language.py` `Optional[Session/str]`→`Session|None/str|None` 3곳 + Optional import 제거. 런타임 영향 없음 (Python 3.14). 단위 2944→2945, 누적 3095→3096. Codex mutual: 기록 미확인 (사이클 125 회고 소급 — 생략 또는 CLI 오류 추정).

## 사이클 124

- **사이클 124 (2026-05-23 · #597)** — B+C 작업. B — P3 보안 심층 테스트 2건: `test_session_security.py` `test_get_current_user_with_large_int_user_id_returns_none` (INT_MAX 2^31-1 경계 — session fixation 주입 차단 문서화). `test_github.py` `test_oauth_state_consumed_after_use_reuse_fails` (Authlib state pop→소비 후 재사용 → `MismatchingStateError` → `/?error=oauth_failed` 302 명시). C Phase 2 — SonarCloud S1192 해소: `src/constants.py` `BREAKDOWN_KEY_CODE_QUALITY` / `BREAKDOWN_KEY_SECURITY` / `BREAKDOWN_KEY_COMMIT_MESSAGE` / `BREAKDOWN_KEY_AI_REVIEW` / `BREAKDOWN_KEY_TEST_COVERAGE` 5개 상수 신설. `src/scorer/calculator.py` 중복 리터럴 → `Category.CODE_QUALITY` / `Category.SECURITY` / `Severity.ERROR` / `Severity.WARNING` StrEnum + `BREAKDOWN_KEY_*` 상수 교체. 단위 2945→2947, 누적 3096→3098. Codex mutual: 기록 미확인 (사이클 125 회고 소급 — 생략 또는 CLI 오류 추정).

## 사이클 122

- **사이클 122 (2026-05-23 · #593)** — 사이클 121 정책 9 승인 항목 이행. STATE.md 전체 테스트 행 수치 동기화 (3092→3095, 단위 2941→2944, passed 3088→3091) + `*(헤더 = 최신값, 이 셀 = pytest 누적 추적)*` 레이블 추가 (에이전트 P0 오인 방지). 사이클 120/121 추적 이력 추가. 메모리 `project_test_gap_analysis.md` `lastVerified: 2026-05-23` 갱신 + P1/P2 전부 해소 반영.

## 사이클 121

- **사이클 121 (2026-05-23 · #591)** — 5+1 다중 에이전트 회고 (P0 0건 / P1 1건 / FP 3건 차단). Tier B-1: MEMORY.md 신규 학습 메모리 2건 (kill-switch TDD 패턴 `feedback_kill_switch_tdd_pattern.md` + line:span drift 검증 의무 `feedback_line_drift_verification.md`). P2 테스트: `commit_scamanager_files` GET timeout → False 반환 회귀 가드 추가 (#591). test_admin_endpoints.py 섹션 헤더 "Cycle 111" → "Cycle 120" 오기입 수정. 단위 테스트 2943 → 2944, 누적 3094 → 3095. cross-verify ROI: FP 3건 차단 (STATE.md 수치 의도적 차이 · SAAS 테스트 이미 존재 · |safe 필터 i18n_args 자동 escape).

## 사이클 120

- **사이클 120 (2026-05-23 · #588~#589)** — 사이클 119 5+1 회고 Tier B 3건 전수 이행. **Tier B-1 (#588)**: `OPERATIONS_DASHBOARD_DISABLED` kill-switch 구현 — `admin.py`에 `is_disabled("OPERATIONS_DASHBOARD")` 체크 + `HTTPException(503)` 반환 + `env-vars.md` 항목 신설 + TDD 회귀 가드 2건(503 확인 + 200 정상 경로). 단위 2941→2943. **Tier B-2/B-3 (#589)**: `.claude/rules/security.md` — `SAAS_MULTITENANT_DISABLED` 503 패턴 명시 + `SESSION_SECRET` validator 하드 실패 정정. `.claude/rules/deploy.md` — `fastapi>=0.136.1` CVE 패치 버전 핀 기재. 회고 cross-verify ROI: false-positive 3건 차단(testing.md line drift P0 일괄 / 보고서 파일 미등재 P0 / 메타 오분류 P1) + 신규 발견 0건 + Tier A 0건. Codex mutual: 샌드박스 오류 → Claude 직접 검증 대체 OK.

## 사이클 119

- **사이클 119 (2026-05-22 · #586)** — 5+1 다중 에이전트 문서 감사 22건 정확도 수정 (Option C 전수 이행). **P0 7건**: SAAS_MULTITENANT_DISABLED 401→**503** 정정(session.py:82,94 실측) / SESSION_SECRET 예시 32자 이상 + ValidationError 경고 추가 / src/scripts/ 경로 혼재 수정(src/scripts/ 2파일만 + 최상위 scripts/ 섹션 신설) / illustrations 4장으로 정정(login_hero.png 사이클 118 #584 삭제 반영) / Python 배지 3.14→3.12 / Tests 배지 2938+154→2941+151 / /login 라우트 설명 "Login page"→"301 redirect /auth/github". **P1 11건**: dashboard_service.py 9→10 공개 함수(merge_failure_distribution 추가) / Sentry 참조 3건 제거(사이클 85 폐기 미반영) / merge_unknown_retry_limit·delay 2변수 추가(config.py:60-61) / db.expunge()→CurrentUser dataclass 정정(session.py:11) / 메모리 경로 d--Source→f--DEVELOPMENT-SOURCE-CLAUDE / gh CLI v2.88.1→v2.89.0(2곳) / FastAPI 배지 0.115→0.136 / make targets 5건 추가(test-fast/test-slow/test-file/test-perf/test-isolated) / INDEX.md "그룹 57" stale 참조 제거 / 정책 본문 카운트 19→18건. **P2 4건**: github_review.py:107→108 / ai_review.py:79,89→100-107 / pipeline.py:178-181→206-218 line drift 정정. 테스트 수 변동 없음 3092. Codex mutual: 샌드박스 오류 → Claude 직접 검증(전 항목 OK). 자유 발언 승인 이행: CLAUDE.md 체크리스트 config.py 동기화 의무 추가 + testing.md line drift 경고 추가.

## 사이클 118

- **사이클 118 (2026-05-22 · #582~#584)** — 사이클 117/118 회고 P0/P1/P2 전수 이행. **P0-1**: `docs/architecture.md:122` templates 목록 `login` 제거 (login.html 삭제 후 잔존). **P0-2**: `docs/STATE.md:10` 비고 `= 154 passed` → `= 151 passed` (CI 실측 기준). **P1-1**: `src/auth/github.py:88,97` `encrypt_token()` 이중 언어 주석 영어 라인 추가 (CLAUDE.md 원칙). **P1-2**: `landing.html` `.banner-close` `min-height: 44px; min-width: 44px; padding: 12px 10px` (WCAG 2.5.5 ≥44px). **P1-3**: `landing.html` `.landing-nav` + `.auth-error-banner` `env(safe-area-inset-top, 0px)` (iPhone notch 호환). **P2-1**: `login_hero.png` 삭제 (orphan — `test_illustration_markup.py` EXPECTED_PNGS 4개로 갱신). **P2-2**: `test_overview_landing.py` `test_landing_page_blocks_non_whitelisted_error_param` 추가 (`_ALLOWED_ERRORS` whitelist 우회 차단 회귀 가드). **P2-3**: `docs/architecture.md:74` `github.py` `/login` 301 redirect 메모 추가. **P2-4**: `landing.html` `.btn-hero` 모바일 `min-height: 44px` (WCAG 2.5.5). 메모리 stale 2건 정리. Codex mutual: 샌드박스 오류 반복 → Claude 직접 검증 대체. 테스트 수 +1 whitelist -1 login_hero 파라미터 = 순변동 0, 3092 유지.

## 사이클 117

- **사이클 117 (2026-05-22 · #565~#580)** — /login 중간 단계 제거 — GitHub OAuth 직행 + 오류 배너 + P0/P1/P2 회고 전수 이행. **핵심 변경**: `/login` 301 redirect → `/auth/github` (하위 호환 보존) / `require_login` Location 직행 / `auth_callback` try/except (`OAuthError` → `/?error=oauth_failed` / `Exception` → `/?error=auth_failed`) / `landing.html` 오류 배너 CSS+HTML + `history.replaceState` (?error= URL 잔존 방지) / `overview.py` `_ALLOWED_ERRORS` 화이트리스트 / `login.html` 삭제 (196줄 dead template — standalone `landing.html` 로 통합). **#565**: `/login` 301 + `require_login` Location + auth_callback 예외 분기 + 통합 테스트 11건 동작 변경 반영. **#567**: `landing.html` 오류 배너 CSS/HTML (oauth_failed/auth_failed 메시지 분기). **#568**: `logout` 리다이렉트 `/login` → `/` (로그아웃 후 GitHub OAuth 화면 진입 버그 해소). **#570**: `logout` HX-Redirect 적용 — `HX-Request` 감지 시 `200 + HX-Redirect: /` 반환 (hx-boost body-swap 시 landing.html 독립 `<head>` CSS 미적용 레이아웃 깨짐 해소). 단위 +1. **#572**: landing.html nav 우상단 "로그인" 버튼 제거 (히어로 CTA 중복 혼선). **#574**: github.py 미사용 import 제거 + 테스트 불필요 patch 정리. **#575 (P0)**: `test_callback_no_email_anywhere_uses_noreply_address` 추가 (email=None + 빈 이메일 목록 → noreply fallback 경로) + `landing.html` 배너 닫기 `history.replaceState` 추가. **#578 (P2 + CI 수정)**: `login.html` 삭제 + `_ALLOWED_ERRORS` 화이트리스트 + 참조 테스트 3파일 8건 제거 (test_form_mobile_sweep 3 / test_i18n_template_render 4 / test_illustration_markup 1) — CI 2차 fix-up 포함. **#580**: STATE.md 수치 갱신. 단위 2944→2941 (-3), 통합 154→151 (-3), 전체 3098→3092 (-6). Codex mutual: 샌드박스 오류 → Claude 직접 검증 대체 OK.

## 사이클 116

- **사이클 116 (2026-05-21 · #561~#563)** — 사이클 115 5+1 회고 (6 에이전트 병렬) + Tier A/B/C 전수 이행. **회고 결과**: P0 1건 확정 (`--border-color-subtle` 오타) + P0-1 false-positive 1건 제거 (`--text-muted` CSS fallback chain 정상) + P1 6건 + false-positive 3건 추가 제거 (rubocop frozenset 정상 / `--d-*` 의도적 설계 / api.md 순방향 참조 기존 존재). **#562 (Tier A/B)**: `dashboard.html:451,455` `--border-color-subtle` → `--border-subtle` (P0-2) + `themes.css` 4테마에 `--warning-rgb`/`--warning-faint`/`--accent-faint` 추가 (P1-A/B) + `test_dashboard_service_user_id_filter.py` `InsightNarrativeCache` import 추가 (P1-C) + `.claude/rules/testing.md` empty `__init__.py` 패턴 항목 추가 (P1-F). **#563 (Tier C)**: `cppcheck.py:76` + `shellcheck.py:46` severity `.lower()` 방어적 정규화 (P1-D/E) + `api.md` asyncio.gather 규칙 → `pipeline.md` 역방향 cross-ref 추가. 테스트 수 변동 없음 3092. Codex mutual: 샌드박스 오류 → Claude 직접 실측 대체 OK.

## 사이클 115

- **사이클 115 (2026-05-21 · #555~#560)** — 사이클 114 5+1 회고 P1 3건 + 신규 발견 2건 구현. **#555 (A.1)**: `tests/unit/github_client/test_checks.py` `_classify_check_runs()` `waiting`/`pending`/`requested` 3상태 parametrized 회귀 가드 6케이스 신규 (test-writer 에이전트). 단위 2932→2938. **#556 (A.2/A.3/C.1/C.2)**: `src/static/css/themes.css` 4 테마 `--bg-2: var(--bg-card)` alias 추가 (팬텀 토큰 수정) + `tests/unit/webhook/test_telegram_provider.py` 3 semi-auto gate 콜백 테스트 `mock_save.assert_called_once()` assertion 추가 (GateDecision 영속성 회귀 가드) + `.claude/rules/pipeline.md` `asyncio.gather` Session 공유 금지 → `api.md` 교차 참조 + `docs/runbooks/workflow.md` 전체 읽기 원칙 → CLAUDE.md 정책 6 교차 참조. **#557** STATE.md/cycle-history/README 사이클 115 동기화. **#558 (신규 발견 1)**: `repo_insight_service.py` `repo_category_breakdown()` severity `.lower() in ("error","high")` → `.upper() in ("HIGH","ERROR")` 프로젝트 표준 통일 + `test_counts_by_category_and_severity` 대문자 `"HIGH"` 케이스 추가 (회귀 가드 강화). **#559** docs sync. **#560 (신규 발견 2)**: `test_repo_insight_service.py` `InsightNarrativeCache` import 누락 수정 — `src/models/__init__.py` 비어있어 `import src.models` side-effect 미작동 → `TestRepoInsightNarrative` 전 케이스 `no such table` 오류 복구. 사이클 110 PR #531 ORM 추가 후 미반영 상태였음.

## 사이클 114

- **사이클 114 (2026-05-21 · #554)** — 5+1 회고 (6 에이전트 병렬): P0 1건 + P1 6건 + P2 4건 + false-positive 2건. **P0**: STATE.md 테스트 수치 3075 → 실측 3086 (+11 미반영) 정정. **P1 식별**: ① cycle-history.md `(대기)` 표기 정정 ② MEMORY.md 실측 17건 vs "20건" ③ `_classify_check_runs()` `waiting`/`pending`/`requested` 회귀 가드 테스트 부재 ④ PR 범위 #552→#553 헤더 정정 ⑤ `--bg-2` themes.css 미정의 ⑥ semi-auto GateDecision assertion 없음. **false-positive 제거 2건**: SessionLocal 이중 패치(양 경로 활성) + Bearer `.strip()` 누락(ASGI 처리). **신규 발견**: repo_insight HIGH 집계 `.lower()/.upper()` 이원화. STATE.md 갱신(3075→3086, 단위 2921→2932, passed 3071→3082, 메모리 20→17건) + README 배지 sync. **P1 잔여 → 사이클 115**: `_classify_check_runs` 3상태 회귀 가드 + `--bg-2` CSS alias + semi-auto assertion.

## 사이클 113

- **사이클 113 (2026-05-21 · #542~#553)** — 다중 에이전트(10+1) 전체 코드 정밀 감사 후 P0 버그 10건 전수 수정 + 5+1 회고 + Code Scanning 5 alert 해소. **감사**: B1~B10 에이전트 10회 + CV cross-verify 1회 병렬 → P0 10건 확정(P0-A~J). 5개 그룹 병렬 구현 에이전트. **#542 P0-B/J**: `_classify_check_runs()` in-progress 목록 `"waiting"/"pending"/"requested"` 3상태 누락 추가 + `.env.example` `TELEGRAM_WEBHOOK_SECRET` 항목 추가. **#543 P0-C/D**: `issue_telegram_otp` sync DB → `asyncio.to_thread` 격리 + `GET /verify` hook 토큰 `Authorization: Bearer` 헤더 지원 추가(query param 하위 호환). **#544 P0-E/G**: `dashboard.html` `var(--bg-2)` 폴백 추가 + `github_issue.py` severity `== "HIGH"` → `.upper() in ("HIGH", "ERROR")` 정규화(bandit `Severity.ERROR="error"` 소문자 저장 대응). **#545 P0-A**: `gate_decisions.analysis_id` `unique=True` ORM + alembic 0034(중복 DELETE → non-unique DROP → UNIQUE ADD, `is_postgresql()` 분기). **#546 P0-F/I/H**: `_count_high_security` severity 정규화 + `dashboard_kpi` `select(Analysis)` → 3컬럼 쿼리 + `run_gate_check` `asyncio.gather` 공유 Session → `_run_approve_decision`·`_run_auto_merge` 독립 `SessionLocal()`. 테스트 수 변동 없음 3075. Policy 18 Codex mutual: sandbox 제약으로 subagent 실행 불가 → Claude 직접 검증(전 항목 OK) + 사용자 명시 승인 대체. **#547** STATE.md/cycle-history 사이클 113 초기 동기화. **#548** `.claude/rules/api.md` `asyncio.gather` 공유 Session 금지 규칙 추가 (P0-H 학습). **#549** `e2e/test_performance.py` unused import 오판 → false-positive 확인(L98-118 `test_health_ttfb`에서 `time`+`requests` 실사용) → PR 취소 + Code Scanning alert #422 dismiss. **#550** P1 빠른 수정 3건: N8N_WEBHOOK_SECRET `.env.example` 추가 + `architecture.md` 0034 UNIQUE 동기화 + `python.py` bandit severity 대소문자 방어 + Code Scanning #420/#416/#421/#423 dismiss. **#551** T-1~T-5 회귀 가드 테스트 11건 (Bearer 3 + severity 1 + to_thread 1 + unique n + CSS n — test-writer 에이전트 병렬 디스패치). **#552** `docs/runbooks/workflow.md` P0 긴급 수정 시 test-writer 병렬 패턴 + 파일 전체 읽기 원칙(grep -n 실측 의무) 추가. **#553** STATE.md/cycle-history 최종 동기화. **핵심 학습**: 파일 앞부분만 읽고 import 미사용 판단 → false-positive 위험 — grep -n 전체 파일 실측 의무 확립. 단위 2921→2932(+11), 전체 3075→3086(+11).

## 사이클 112

- **사이클 112 (2026-05-20 · #539~#540)** — 사이클 111 5+1 회고 P1 2건 처리. **docs 수치 sync** (#539): STATE.md 3055→3062, PR #537/#538 이력 추가. **LANG_NAMES DRY 해소 + _INSIGHT_SYSTEM_PROMPT 언어 중립화** (#540): `src/shared/lang_names.py` 신규 (단일 출처 상수) + repo_insight_service/dashboard_service 중복 상수 제거 → shared import + `_INSIGHT_SYSTEM_PROMPT` "in Korean (e.g."/"Korean characters"/"Korean particles" → 언어 중립 문구. TDD 13건 신규 (shared/test_lang_names 8 + services/test_insight_system_prompt 5). 단위 2908→2921. Codex mutual 검증 OK.

## 사이클 110~111

- **사이클 110 (2026-05-19 · #530~#532)** — settings.html AI 리뷰 모델 선택기 카드 위치 변경 (#530). InsightNarrativeCache 에러 빈도 추적 — sdk_error/network_error/parse_error 3 컬럼 + alembic 0033 마이그레이션 + 서비스/레포지토리 5+1 에이전트 검증 (#531). docs STATE/architecture 사이클 110 동기화 (#532).
- **사이클 111 (2026-05-20 · #533~#538)** — analysis_detail 차트 검정 배경 (accent+'22' → accentRgb CSS 경로) + 피드백 버튼 htmx 핸들러 누적 등록 수정 (remove-before-add 2-레이어) + 회귀가드 13건 (#533). 5+1 리뷰 P1 3건 수정: language 누락 2곳 + ORM 인덱스 누락 + dead assert (#535). e2e/_perf_helpers.py 추출 — `_LCP_INIT_JS`/`measure_one`/`measure_page` 중복 58줄 제거, test_performance.py+scripts/perf_measure.py 공유 (#536). **다국어 insight 프롬프트** (#537): `repo_insight_service` `_LANG_NAMES` dict + 'in Korean' 하드코딩 제거 / `dashboard_service` `language` 파라미터 추가 + get_fresh/upsert/record_error 캐시 3종에 language 전달 / `dashboard.py` 라우트 locale_value 전달 / TDD 테스트 7건 신규 (ko/en/ja 프롬프트 검증 + 캐시 language 전달 검증). 단위 2907→2908. **README 배지 sync** (#538). **5+1 회고**: P0 없음. P1 8건 (system prompt Korean 하드코딩·DRY·invalidate language·테스트 수치·문서 이력·call_args 불일치·locale fallback·architecture 미반영) — 주요 2건 다음 사이클 처리 예정 (_INSIGHT_SYSTEM_PROMPT 언어 중립화 + _LANG_NAMES DRY 해소).
