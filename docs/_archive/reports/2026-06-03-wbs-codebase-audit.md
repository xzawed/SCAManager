# SCAManager WBS 코드베이스 감사 보고서

> **일자**: 2026-06-03 | **범위**: `src/` 238파일 23,818 LOC + `.claude/hooks/` + `scripts/` + `alembic/versions/` + CI/배포
> **방식**: WBS 6 작업패키지 다중 에이전트 감사(13 에이전트) → 작업패키지별 적대적 검증(FP 차단) → 종합
> **결과**: 확정 **22건 — P0 1 / P1 2 / P2 19** (적대적 검증으로 framing 정정·심각도 조정 반영)

## 1. 총평

코드베이스의 **런타임 보안·안정성은 대체로 견고**하다 — 발신 SSRF 가드(`_http.py` https-only + IP 차단), webhook HMAC 검증, OAuth/세션, Supabase RLS, RATE_LIMIT 적용이 광범위하게 작동. 후보 P1 8건 중 6건이 cron 전용·가설적 체인·조건부 권한 의존으로 P2 강등될 만큼 운영 영향이 제한적임이 교차 검증됨.

**유일 P0 = 거버넌스 통제 사망** — 운영 코드(src/) 취약점이 아니라, 사용자가 신뢰하는 **문서/정책 회귀 차단 통제(`doc_review_gate.py`)가 현재 환경에서 100% 무음 무력화**된 상태. 즉시 수정 권장.

## 2. WBS 작업패키지 × 심각도

| 작업패키지 (차원) | P0 | P1 | P2 | 소계 |
|---|----|----|----|----|
| WP1 — 보안성 | 0 | 1 | 3 | 4 |
| WP2 — 은닉성/하드코딩 | 1 | 0 | 1 | 2 |
| WP3 — 안전성/안정성 | 0 | 1 | 2 | 3 |
| WP4 — 확장성 | 0 | 0 | 5 | 5 |
| WP5 — 잠재적 버그 | 0 | 0 | 3 | 3 |
| WP6 — 의존성/배포/CI | 0 | 0 | 5 | 5 |
| **합계** | **1** | **2** | **19** | **22** |

## 3. P0 (즉시 수정)

### WP2-1 · `doc_review_gate.py` 하드코딩 경로 stale → 문서 거버넌스 게이트 silent bypass
- **위치**: `.claude/hooks/doc_review_gate.py:15-17` (`_PROJECT_PREFIXES='d:/source/scamanager/'`), `:41-50`·`:53-70`·`:274-276`; `.claude/settings.json:13-16` (활성 등록); 회귀 출처 commit `7d20dc6`
- **확정 근거**: 실 환경 루트 = `F:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager` ↔ 하드코딩 prefix `d:/source/scamanager/` 미스매치. `classify_file_grade()`를 실 경로로 직접 실행 → `CLAUDE.md`·`STATE.md`·`settings.json` 모두 `grade='skip'` → 3-에이전트 문서 심의 `sys.exit(0)` 무음 스킵. commit `7d20dc6`("fix(p0)")가 제목과 정반대로 정상 prefix를 오류로 회귀시킴 + 동일 commit이 PostToolUse pytest 게이트 cd 경로도 동반 사망 + 기존 회귀 가드 테스트가 버그 prefix와 동일 값을 써서 결함 은폐.
- **영향**: CLAUDE.md/정책/agents/skills 오작성·회귀를 차단하는 통제가 운영 환경에서 무력화. (이번 세션의 모든 docs 편집에서 게이트가 안 뜬 직접 원인.)
- **조치**: 하드코딩 prefix 제거 → 런타임 결정(`Path(__file__).resolve().parents[2]`, `_load_context` L209 패턴 재사용) 또는 절대경로 무관 매칭. **회귀 가드**: 실 환경 절대경로(소문자/대문자/백슬래시)로 `classify='critical'` 단위 테스트 + 기존 은폐 테스트 환경독립 교체. `settings.json:26` PostToolUse cd 경로 동반 정정.

## 4. P1 (곧 수정)

### WP1-1 · 미소유(`user_id=NULL`) 리포 소유권을 GitHub 접근 검증 없이 폼 입력만으로 이전 (IDOR-인접)
- **위치**: `src/ui/routes/add_repo.py:96-108` (else 경로 `existing.user_id=current_user.id; db.commit()` 무조건 이전); `_helpers.py:67` 인가가 `user_id` 기반
- **조치**: 소유권 이전 전 현재 사용자 OAuth 토큰으로 GitHub repo 접근 검증(`list_user_repos` 멤버십 또는 `GET /repos/{full_name}` 200) 추가. 비멤버 403 회귀 가드. (정책 15 High tier — 인가 변경.)

### WP3-1 · `AsyncAnthropic` 클라이언트 per-call 생성 후 미종료 → httpx 커넥션 풀 누수 (3곳)
- **위치**: `src/analyzer/io/ai_review.py:93` · `src/services/dashboard_service.py:904`(+761-789) · `src/services/repo_insight_service.py:377`
- **조치**: 3곳 `async with` 또는 `try/finally aclose()`, 더 나은 방향은 `http_client.py` 패턴의 lifespan 싱글톤. aclose 호출 검증 테스트 3건(현재 0건).

## 5. P2 (개선 권장) — 작업패키지별

**WP1 보안 일관성**: DNS rebinding TOCTOU 잔여(`_http.py:70-97` — 검증 IP 미pin) / 폼 SSRF 비대칭(`settings.py:66` http 허용+CGNAT 100.64/10 미차단) / `checks.py:94-263` `_repo_path` 미적용(방어 비일관).
**WP2**: pre-push 훅 템플릿 토큰 query param 전달(`repos.py:157` → Bearer 헤더, 서버는 이미 지원).
**WP3 cron 안정성**: `cron_service.py:76,173` except db.rollback() 누락(#745 패턴) / `issue_registration_service.py:51-77` Issue 생성 후 DB insert TOCTOU(insert-first 권장).
**WP4 확장성**: `security_scan_service.py:183` 직렬 폴링(gather) / `cron_service.py` N+1 config 조회(batch) / `issue_registration_repo.py:63` 무제한 `.all()`(LIMIT) / `dashboard_service.py:225,270` result 컬럼 한정(OOM) / `admin.py:31-71` @limiter 누락.
**WP5 버그**: `pipeline.py:99,479` `or {}` 누락(AttributeError) / `merge_retry_service.py:162,188` head None / `retry_policy.py:44` has_hooks dead 매핑.
**WP6 공급망/CI**: `ci.yml:25,36` trufflehog@main 미핀 / `ci.yml` permissions 부재 / `railway.toml:3` releases/latest 무검증 설치 / `.env.example:11`+`config.py:126` 약한 SESSION_SECRET default 통과 / `railway.toml:16` cron 따옴표 모호.

## 6. 수정 로드맵 (정책 7 응집 단위 PR 분할)

1. **PR-1 (P0 즉시)** — `doc_review_gate.py` 경로 런타임 전환 + `settings.json` cd 정정 + 환경독립 회귀 가드 테스트(은폐 테스트 교체). 거버넌스 복구 = 최우선.
2. **PR-2 (P1 보안)** — add_repo 소유권 이전 GitHub 인가 검증 + 비멤버 403 가드.
3. **PR-3 (P1 안정성)** — AsyncAnthropic 3곳 풀 누수 차단 + aclose 검증 테스트.
4. **PR-4 (P2 SSRF/검증 일관성)** — settings.py https-only+CGNAT 차단 / _http.py IP pin / checks.py _repo_path — 공유 IP 헬퍼 단일화.
5. **PR-5 (P2 cron 안정성)** — cron_service rollback + repo_config batch + security_scan gather.
6. **PR-6 (P2 None-정규화 버그)** — pipeline/merge_retry `or {}` + retry_policy dead 매핑.
7. **PR-7 (P2 OOM/rate-limit)** — dashboard 컬럼 한정 / list LIMIT / admin limiter / issue insert-first.
8. **PR-8 (P2 공급망/CI hardening)** — ci.yml permissions+action 핀 / railway 핀 / SESSION_SECRET fail-fast / cron 따옴표. (deploy.md 동기화.)

각 PR: 정책 18(push 전 mutual — 현재 게이트 비활성 환경) + 정책 2(사용자 검증 필요) 적용. PR-1 머지 후 실 환경 CLAUDE.md edit 시 훅 작동 manual 확인 필수.

## 7. 미커버 영역 + 후속 감사 권고

본 감사는 각 차원 표면을 1~수 건씩 짚었으며, 아래는 **체계적 전수 후속 감사** 권장(모두 'WP1-1 인가 경계' 부류):

1. **RLS/멀티테넌시 cross-tenant 격리** (repositories 1578 — user_id 필터 전 쿼리 일관 적용 검증) ★ 최우선
2. **AI 프롬프트 인젝션** (analyzer 5403 최대 영역 — diff/커밋 메시지 삽입 표면)
3. **Gate self-approve 권한 경계** (gate 1779 — 본인 PR 자동 approve+merge 차단 여부)
4. 인증/세션 코어(OAuth state CSRF·쿠키 플래그·키 로테이션) / 동시성 전반(gather Session·멱등성·SKIP LOCKED) / 알림 메시지 인젝션·PII(notifier 2223) / alembic ORM drift.

---
> 본 보고서의 22 발견은 적대적 검증(작업패키지별 general-purpose 재검증)을 거친 확정 항목이며, 각 위치는 `grep -n`/Read 실측 기반(정책 6). 심각도는 P0(운영 통제 사망) → P1(보안/안정 결함) → P2(hardening) 순.
