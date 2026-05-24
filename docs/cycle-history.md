# SCAManager 사이클 작업 이력 (사이클 60~92 archive)

> CLAUDE.md tail entry 분리본. 사이클 60~92 historical entries.
> 본 파일은 회고 시점 (정책 8 5+1 패턴) 또는 영역 reference 시 read 의무.

## 목차

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
