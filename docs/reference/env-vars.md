# SCAManager 환경변수 레퍼런스

## 필수 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@host/db` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 | `123456:ABC-xxx` |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID | `-100xxxxxxxxx` |
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID | `Ov23li...` |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 | `github_...` |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (**32자 이상 필수** — 미충족 시 `config.py` `ValidationError` 앱 기동 오류) | `your-32-char-or-longer-secret-key-here` |

## 선택 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `GITHUB_WEBHOOK_SECRET` | GitHub Webhook HMAC 서명 시크릿 (Phase 8B 이후 선택적) | `your-secret-here` |
| `GITHUB_TOKEN` | GitHub API Personal Access Token (레거시 리포 fallback) | `your-github-token` |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 API 키 (없으면 AI 항목 기본값 적용) | `your-anthropic-api-key` |
| `API_KEY` | Dashboard REST API 인증 키 (없으면 인증 생략) | `any-secret-string` |
| `APP_BASE_URL` | Railway 등 리버스 프록시에서 HTTPS redirect_uri 강제 지정 + **CORS allow_origins 출처 결정** (사이클 142 Phase C — `src/main.py` CORSMiddleware, 미설정 시 CORS 미등록) | `https://your-app.railway.app` |
| `TOKEN_ENCRYPTION_KEY` | GitHub Access Token 암호화 키 (미설정 시 평문 저장) | `32자 이상 랜덤` |
| `STRICT_TOKEN_ENCRYPTION` | `true` 설정 시 `TOKEN_ENCRYPTION_KEY` 미설정이면 lifespan startup 차단 (기본값 `false` = 평문 저장 허용 + WARNING 출력) | `false` (기본) |
| `CLAUDE_REVIEW_MODEL` | AI 코드리뷰에 사용할 Claude 모델 ID | `claude-sonnet-4-6` (기본) |
| `CLAUDE_REVIEW_MAX_TOKENS` | AI 코드리뷰 응답 출력 토큰 상한 — 한국어 리뷰 JSON(~2660 토큰) 여유값. 🔴 저한도 모델(claude-3-haiku/opus=4096)을 `CLAUDE_REVIEW_MODEL` 로 쓰면 이 값을 모델 출력 한도 이하로 낮춰야 함(8192 일괄 적용 시 Anthropic 400 → `api_error`). 구값 1500 이 응답을 절단해 `parse_error` 로 출시 이래 ~80% 리뷰 실패한 사고 fix (제약 `ge=1`) | `8192` (기본) |
| `CLAUDE_INSIGHT_MODEL` | Insight narrative (`/dashboard?mode=insight`) 4 카드 생성용 Claude 모델 ID — 코드리뷰보다 단순 task → Haiku 분기로 토큰 비용 ↓ (Cycle 74 PR-A #247) | `claude-haiku-4-5` (기본) |
| `DISABLE_PROMPT_CACHE` | Anthropic prompt caching (5분 ephemeral) opt-out — `1` 시 비활성 (Phase 3 PR 1 #218 신설). 운영 비용 통제용 — default `0` (caching 적용) | `0` (기본) / `1` (비활성) |
| `TELEGRAM_WEBHOOK_SECRET` | Telegram `setWebhook` 시크릿 토큰 — **미설정 시 401 fail-closed** (사이클 142 Phase B S1 #674 보안 강화 — 이전 "헤더 검증 생략"에서 변경). Railway에서 반드시 설정 필요, 미설정 시 Telegram gate callback 전체 비활성 | 빈 문자열 (기본, **운영 시 반드시 설정**) |
| `N8N_WEBHOOK_SECRET` | n8n 전송 HMAC 서명 시크릿 (미설정 시 서명 생략) | 빈 문자열 (기본) |
| `N8N_RELAY_REPO_TOKEN` | n8n issue 릴레이에 GitHub repo OAuth 토큰 포함 여부 — 명시적 opt-in (자격증명 유출 차단). `1`/`true` 이고 `N8N_WEBHOOK_SECRET` 설정 시에만 토큰 전송 | `false` (기본) |

## 내부 인증 (cron · admin · loop guard)

| 변수 | 설명 | 예시 |
|------|------|------|
| `INTERNAL_CRON_API_KEY` | **`POST /api/internal/cron/*` 전용 인증 키** (admin key 와 분리). Railway `[[deploy.cronJobs]]` 트리거. `hmac.compare_digest` 타이밍 안전 비교. **미설정 시 503 반환** — Phase 10 cron (weekly_summary, trend_check) 전부 비활성화. | `cron-internal-key-xxx` |
| `SAAS_ADMIN_EMAILS` | **SaaS admin 권한 allow-list** — `,` 분리 email 문자열. `current_user.email in saas_admin_emails` 일치 시 `/admin/{tenants,rls-audit,operations}` UI + `/api/admin/*` REST 접근 허용. 미설정 시 admin 영역 자동 비활성화 (Cycle 79 PR 2 #255 — `require_admin` Depends 페어). | 빈 문자열 (기본) / `admin@example.com,owner@example.com` |
| `SCAMANAGER_SELF_ANALYSIS_DISABLED` | **Loop Guard kill-switch** — `1` 설정 시 모든 webhook 분석 즉시 중단 (202 skipped). Phase 9 자기-분석 루프 사고 발생 시 즉각 차단용. | `0` (기본) / `1` (긴급 중단) |
| `SECURITY_AUTO_PROCESS_DISABLED` | **Code/Secret Scanning auto-process kill-switch** — `1` 설정 시 `security_scan_service` + `dashboard_service` security 영역 자동 처리 중단 (Cycle 73 #244 신설). false-positive 누적 시 긴급 차단용. | `0` (기본) / `1` (긴급 중단) |
| `SAAS_MULTITENANT_DISABLED` | **SaaS 멀티테넌트 영역 kill-switch** — `1` 설정 시 admin 영역 즉시 **503** 반환 (`session.py:86,99` — 401 아님). Cycle 79 PR 2 (#255) 신설 — SaaS 영역 운영 사고 시 즉각 차단용. | `0` (기본) / `1` (긴급 중단) |
| `OPERATIONS_DASHBOARD_DISABLED` | **운영 모니터링 대시보드 kill-switch** — `1` 설정 시 `/admin/operations` 라우트 즉시 **503** 반환 (`admin.py`). Cycle 120 신설 — 운영 KPI 대시보드 장애 시 긴급 차단용. | `0` (기본) / `1` (긴급 중단) |

> **🔴 운영 안전**: 위 6 변수는 운영 사고 발생 시 즉시 사용해야 하므로 Railway Variables 에 미리 배치 권장. `INTERNAL_CRON_API_KEY` 미설정 시 cron job 이 silent 503 으로 실패해 weekly_summary 등이 발송 안 됨 — 운영자 인지 어려움. `SAAS_ADMIN_EMAILS` 미설정 시 admin UI 영역 (`/admin/tenants` 등) 모든 사용자 401 — Cycle 79+ SaaS 영역 활성화 시 의무. kill-switch 신규 추가 시 `src/shared/feature_kill_switch.py::is_disabled(feature)` helper 사용 default (Cycle 78 NEW-P0-2 #253 — 사용처 ≥ 3 도달 시 자동 헬퍼 추출 정책 16 4번 원칙 정합).

## Observability (자동 로깅, env 설정 불필요)

> **사이클 85 (2026-05-06)**: Sentry 통합 완전 폐기 (사용자 명시 결정). 환경변수 3건 (`SENTRY_DSN`/`SENTRY_ENVIRONMENT`/`SENTRY_TRACES_SAMPLE_RATE`) + `src/shared/observability.py` + `sentry-sdk` 의존성 제거. Railway 잔존 env vars 는 `model_config = {"extra": "ignore"}` 로 silent skip. 운영 영향 0. 폐기 runbook = [`docs/runbooks/_archive/sentry-activation.md`](_archive/sentry-activation.md) (역사 자산).

Sentry 외 자동 로깅은 별도 환경변수 없이 동작:

- `claude_api_call` 로그 — model / duration_ms / input_tokens / output_tokens / cost_usd / status
- `pipeline_stage` 로그 — collect_files / analyze / score_and_save / notify / pipeline_total
- Railway Logs 에서 grep / filter 로 조회 가능 (structured log shipper 미연동 상태)

## 다국어 지원 (Phase 1 PR-1a, Cycle 84+)

`DEFAULT_LOCALE` / `SUPPORTED_LOCALES` / `LOCALE_FALLBACK` / `I18N_TRANSLATIONS_DIR` / `I18N_DISABLED` 5개 환경변수로 다국어 지원을 제어한다 (Jinja2 + JSON dict 자체 구현 — Babel 미사용, 정책 16 4번 원칙 정합 — 사용처 ≥ 3 임계 미달 시 표준 lib 우선). LocaleMiddleware (Phase 1 PR-1b 영역) 가 Cookie `preferred_language` → `Accept-Language` q-weight → User.preferred_language → DEFAULT_LOCALE → LOCALE_FALLBACK 5단계로 감지한다.

| 변수 | 설명 | 기본값 | 예시 |
|------|------|-------|------|
| `DEFAULT_LOCALE` | 신규 사용자 기본 언어 (User.preferred_language 초기값 — alembic 0030 페어, Phase 1 PR-1c 영역) | `en` | `en` / `ko` / `ja` |
| `SUPPORTED_LOCALES` | 지원 언어 목록 (쉼표 구분, 공백 제거 의무 — pydantic field_validator 검증) | `en,ko,ja` | `en,ko,ja` / `en,ko` |
| `LOCALE_FALLBACK` | 극한 fallback 언어 (모든 감지 실패 시 / 번역 파일 미존재 등) | `en` | `en` |
| `I18N_TRANSLATIONS_DIR` | JSON dict 번역 파일 위치 (en.json/ko.json/ja.json — 상대 또는 절대 경로) | `src/i18n/translations` | 개발: `src/i18n/translations` / 운영: `/app/src/i18n/translations` |
| `I18N_DISABLED` | i18n 기능 kill-switch (1=비활성, 운영 사고 시 응급 차단용) | `0` | `0` (활성) / `1` (긴급 차단) |

> **🔴 운영 안전**: `I18N_DISABLED` 는 운영 사고 (번역 파일 손상 등) 시 즉각 비활성용 — Railway Variables 에 미리 배치 권장. 사이클 78 NEW-P0-2 패턴 (`is_disabled("I18N")` helper) 페어. 신규 환경변수 추가 시 `src/shared/feature_kill_switch.py::is_disabled(feature)` helper 사용 default.

> **검증**: pydantic `field_validator` 4건 신설 (supported_locales / default_locale / locale_fallback) — 공백 제거 + 길이 2~10 + 영숫자/하이픈 제한. 단위 테스트 = `tests/unit/test_config.py` (Phase 1 PR-1a 회귀 가드 16건+).

## 알림 채널 (선택)

| 변수 | 설명 |
|------|------|
| `SMTP_HOST` | SMTP 메일 서버 호스트 (예: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP 포트 (기본 587) — `config.py`의 `coerce_smtp_port` validator가 빈 문자열을 587로 자동 변환 (크래시 없음). 명시적 숫자 설정 권장 |
| `SMTP_USER` | SMTP 인증 사용자 |
| `SMTP_PASS` | SMTP 인증 비밀번호 |

## 머지 검증자 (2nd-LLM cross-vendor, opt-in)

> Claude 리뷰를 **다른 vendor 의 LLM** 이 독립 검증 — **경계 점수 자동머지 후보**(`merge_threshold ~ +N`)만. `OPENAI_API_KEY` 미설정 시 완전 비활성(비용 0, 동작 변화 0 — 순수 opt-in). 불안전/조작/검증자 오류 시 자동머지 차단 + PR 코멘트(fail-closed).
>
> 🔴 **추가 비용 0/최소 활성화** (OpenAI 구독 무관): 클라이언트는 **OpenAI-호환 엔드포인트**면 모두 동작한다. **OpenAI 비구독자** = `VERIFIER_BASE_URL` 에 무료 OpenAI-호환 공급자(GitHub Models / Groq / OpenRouter 등) 엔드포인트 + `OPENAI_API_KEY` 에 그 공급자 키 + `OPENAI_VERIFIER_MODEL` 에 그 모델명. **OpenAI 보유자** = `VERIFIER_BASE_URL` 빈 값 유지 + 저가 모델. 공급자는 `chat/completions` + `response_format=json_object` 지원 필요. 무료 티어 rate-limit 으로 검증 실패 시 fail-closed(해당 PR 자동머지 보류=안전, 수동 검토로 폴백).

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `OPENAI_API_KEY` | 검증자 키 — **미설정 시 검증자 완전 비활성** (BYO key). OpenAI 키 또는 `VERIFIER_BASE_URL` 지정 시 해당 OpenAI-호환 공급자 키 | 빈 문자열 |
| `VERIFIER_BASE_URL` | 검증자 엔드포인트 base_url — 빈 값=OpenAI 기본. OpenAI-호환 무료/저가 공급자(GitHub Models·Groq·OpenRouter) 전환용 (`{base_url}/chat/completions` 로 호출) | 빈 문자열 |
| `OPENAI_VERIFIER_MODEL` | 검증자 모델 ID (저비용 소형 권장 / 공급자별 모델명) | `gpt-5-mini` |
| `MERGE_VERIFIER_BAND` | 경계 밴드 폭(점) — `merge_threshold ~ +N` 만 검증 (고득점 skip = 비용 절감) | `10` |
| `MERGE_VERIFIER_DISABLED` | kill-switch (`1` 시 비활성) | `0` |

## DB 연결 고급 설정

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DB_SSLMODE` | PostgreSQL SSL 모드 (`require`, `verify-full`, `disable` 등, 빈 값=미적용) | 빈 문자열 |
| `DB_FORCE_IPV4` | Railway IPv4 강제 연결 (온프레미스에서는 `false`) | `false` |
| `DB_POOL_SIZE` | SQLAlchemy 연결 풀 크기 (PostgreSQL 전용) | `5` |
| `DB_MAX_OVERFLOW` | 풀 초과 허용 연결 수 | `10` |
| `DB_POOL_TIMEOUT` | 풀 대기 타임아웃 (초) | `30` |
| `DB_POOL_RECYCLE` | 연결 재활용 주기 (초) | `1800` |

## CI-aware Auto Merge 재시도 (Phase 12)

`auto_merge=true` 설정 리포에서 CI 진행 중 머지 실패 시 자동 재시도 큐 동작을 제어한다.

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `MERGE_RETRY_ENABLED` | `false` 시 레거시 단일 시도 동작으로 fallback | `true` |
| `MERGE_RETRY_MAX_ATTEMPTS` | 큐 행당 최대 재시도 횟수 (**>= 1** 제약 — `Field(ge=1)`) | `30` |
| `MERGE_RETRY_MAX_AGE_HOURS` | 큐 행 만료 시간 (시간, **>= 1** 제약 — `Field(ge=1)`) | `24` |
| `MERGE_RETRY_INITIAL_BACKOFF_SECONDS` | 첫 재시도 백오프 (초, **>= 1** 제약 — `Field(ge=1)`) | `60` |
| `MERGE_RETRY_MAX_BACKOFF_SECONDS` | 최대 백오프 (초, **>= 1 AND >= INITIAL_BACKOFF** — `Field(ge=1)` + `model_validator` 경계 강제, max<initial 시 startup ValidationError) | `600` |
| `MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED` | `check_suite.completed` 웹훅 즉각 트리거 활성화 | `true` |
| `MERGE_RETRY_WORKER_BATCH_SIZE` | cron sweep 1회 처리 최대 행 수 (**>= 1** 제약 — `Field(ge=1)`) | `50` |
| `MERGE_UNKNOWN_RETRY_LIMIT` | `mergeable_state=unknown` 상태 폴링 최대 재시도 횟수 (`config.py` `merge_unknown_retry_limit`) | `3` |
| `MERGE_UNKNOWN_RETRY_DELAY` | `mergeable_state=unknown` 재시도 간격 (초, `config.py` `merge_unknown_retry_delay`) | `3.0` |

> 기본값으로 운영 환경에 최적화되어 있어 별도 설정 없이 즉시 동작한다.
> 운영 runbook: `docs/runbooks/merge-retry.md`

## DB Failover (온프레미스 장애 시 Supabase 자동 전환)

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL_FALLBACK` | Failover용 보조 DB URL (빈 값이면 failover 비활성) | `postgresql://user:pass@supabase.co/db?sslmode=require` |
| `DB_FAILOVER_PROBE_INTERVAL` | Primary DB 복구 확인 주기 (초) | `30` |
| `DATABASE_URL_WORKER` | background(webhook/worker/gate/notifier/cron/CLI hook) 전용 DB URL — RLS role 분리 옵션 A ([rls-role-separation.md](../runbooks/rls-role-separation.md) Phase 2). 빈 값이면 `DATABASE_URL` 팩토리 재사용 (현행 동작). 반드시 `BYPASSRLS` worker role(`scamanager_worker`) 자격 지정 — 비-BYPASSRLS role 지정 시 FORCE 활성 후 background 차단. ⚠️ 트레이드오프: worker 경로 failover 미지원 (primary 장애 시 background 중단) + 동일 프로세스 연결 풀 2배 (Supabase 연결 상한 고려) | `postgresql://scamanager_worker:pass@host/db` |
| `MIGRATION_DATABASE_URL` | alembic 마이그레이션 전용 DB URL (**owner role**) — RLS Phase 4 "두 번째 벽" ([rls-role-separation.md](../runbooks/rls-role-separation.md) §6 마이그레이션 credential 게이트). `alembic/env.py` 가 `effective_migration_url`(= 이 값 또는 `DATABASE_URL`)을 `sqlalchemy.url` 로 사용 → pre-deploy `alembic upgrade head` + lifespan 양쪽에 적용. 빈 값이면 `DATABASE_URL` 사용 (**현행 동작 보존 — 미설정 시 발효 0**). 🔴 Phase 4 에서 `DATABASE_URL` 이 비-BYPASSRLS app role(`scamanager_app`)로 전환될 때 설정 — 미설정 시 마이그레이션이 app role 로 돌아 `alembic_version` default-deny 차단. 🔴 런타임 `DATABASE_URL`/`DATABASE_URL_WORKER` 를 마이그레이션 credential 로 재사용 금지 | `postgresql://postgres:pass@host/db` |

**주의:** `.env` 파일은 절대 git commit 하지 말 것 (`.gitignore`에 포함됨)

---

## 성능 측정 스크립트 (scripts/perf_measure.py 전용)

`make perf-report` 또는 `python scripts/perf_measure.py` 실행 시에만 참조. 운영 서버 배포 환경변수가 아님.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `PERF_PROD_URL` | `https://scamanager-production.up.railway.app` | 운영 서버 측정 URL |
| `PERF_API_KEY` | `""` | 운영 API 키 (`X-Api-Key` 헤더 — `/api/repos` 등 API 엔드포인트 TTFB 측정용, 없으면 401 예상) |

## 내부 모듈 상수 (참고 — env var 아님)

환경변수가 아닌 코드 내 모듈 상수지만, 운영 동작 가시성 / 튜닝 시 인지가 필요한 값. 변경은 코드 수정 (PR) 으로만 가능.

| 상수 | 위치 | 값 | 의미 |
|------|------|------|------|
| `WEBHOOK_SECRET_CACHE_TTL` | `src/constants.py` | `300` (초) | 리포 시크릿 캐시 TTL — 변경 후 최대 5분간 구 시크릿으로 검증 |
| `WEBHOOK_SECRET_CACHE_MAX` | `src/constants.py` | `2048` | pre-auth 시크릿 캐시 엔트리 상한 — forged `full_name` DoS 방어 (#854) |
| `OPENAI_VERIFIER_TIMEOUT` | `src/constants.py` | `60.0` (초) | 2nd-LLM 머지 검증자 OpenAI 호출 타임아웃 — Claude review 60s 와 대칭 (#859) |
| `VERIFIER_DIFF_CHAR_CAP` | `src/constants.py` | `60000` (문자) | 검증자 diff 상한 — 초과 시 OpenAI 미호출 + fail-closed 차단 (대형 PR 수동 머지, #863) |
| `VERIFIER_MAX_OUTPUT_TOKENS` | `src/constants.py` | `8192` | 검증자 OpenAI 응답 토큰 상한 (`max_completion_tokens`) — gpt-5 계열 reasoning 소진 방지 (#863) |
| `STATIC_ANALYSIS_TIMEOUT` | `src/constants.py` | `30` (초) | 정적 분석 도구 (slither 등) subprocess 타임아웃 |
| `HTTP_CLIENT_TIMEOUT` | `src/constants.py` | `10.0` (초) | 신뢰 API HTTP 호출 타임아웃 (GitHub/Telegram/Railway/SMTP — Anthropic SDK 만 60s 별도) |
| `TELEGRAM_RETRY_AFTER_MAX_SECONDS` | `src/notifier/telegram.py` | `30` | Telegram 429 응답의 retry_after 최대 sleep 시간 (cap) — Phase H PR-2B |
| `_GRAPHQL_MAX_ATTEMPTS` | `src/github_client/graphql.py` | `3` | GitHub GraphQL 5xx + network error 최대 재시도 횟수 — Phase H PR-1B-2 |
| `_GRAPHQL_INITIAL_BACKOFF_SECONDS` | `src/github_client/graphql.py` | `1.0` | GraphQL 재시도 초기 backoff (지수 증가: 1s → 2s) — Phase H PR-1B-2 |
