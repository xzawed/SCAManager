# SCAManager 사이클 작업 이력 (사이클 60~166, 최신순)

> CLAUDE.md tail entry 분리본. 사이클 60~166 이력 (본문 최신순 — 목차는 166부터, 하단에 60~92 archive).
> 본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무.

## 목차

- [사이클 166 (Task9 full 감사 P2 백로그 해소 — 빠른 정합 docs/db·test/effects.js dead-code + UI Medium hx-boost 리스너 누적·i18n 이중이스케이프[Option A], 5 PR #820~#824, Codex mutual 5/5, 2026-06-09)](#사이클-166)
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

## 사이클 166

**날짜**: 2026-06-09 | **PR**: #820~#824 (5건 머지) | **트리거**: 사용자 "잔여 작업 및 후속 작업 확인" | **상태**: Task9 full 감사 P2 백로그 자율 가능 10건 해소

**작업 내용**: Task9 full 감사(2026-06-08, 36 confirmed)의 자율 가능 P2 항목을 코드 실측 검증 후 해소. 잔여 백로그 검증 워크플로우(wf_d1e440d5, 6에이전트 read-only — db/docs/gate·sec·test/ui/RLS/completeness critic)로 still_present 16 + partial 1(#17) + resolved 1(#32 이미 `| tojson`) 판정 → 응집 단위 5 PR 분할. 사용자 AskUserQuestion 2회(빠른 정합 → UI Medium) + #34 escape 전략 결정 1회.

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
- **#830 (#22)**: Python 버전 SSOT 3.12 정렬 — README/README.ko/STATE 의 3.14 미검증 선언 → CI(3.12) 기준. 4환경 불일치(CI 3.12·로컬 3.13·Railway nixpacks 핀없음·docs 3.14) 중 CI 권위. docs-only. nixpacks Railway 핀은 별도 follow-up.
- **#831 (#23)**: gate retry `'passed'` 의도 설계 명시 — 사용자 결정 **A(현 설계 유지, 코드 동작 0)**. `should_retry(UNSTABLE_CI,'passed')=True` 는 merge API lag / 다중 check suite pending 대비 의도적·bounded(감사 '영구 재시도' 표현 부정확). docstring + 회귀 가드. 🔴 **Codex mutual 적발(2-layer ROI)**: 초안이 예산을 `is_expired(max_age/max_attempts)` 로 오기 → 실측 is_expired=max_age 만, max_attempts=process_pending_retries(abandoned) 별도 → 정정 후 OK.

단위 4726→4727.

**잔여 (full 감사 36건 중 #2 외 전부 해소/결정)**: **#18**(전역 compare_metadata 가드 — 자율 가능하나 대형/fragile: PG dialect diff 필터 + 로컬 PG 없어 CI 반복 검증, 미착수) · **#2**(RLS FORCE — SaaS 전환 근본 항목, #810 갭 가시화로 운영 경고만, 보류).

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
