# 환경변수

정본은 `src/config.py` 의 `Settings` 클래스다. 이 문서는 그 필드 전량 + 코드가 `os.environ` 에서
직접 읽는 변수를 옮긴 표다.

**변수를 추가하는 절차** — ① `Settings` 에 필드 선언(또는 `is_disabled()` 사용) → ② 아래 표에
`` | `ENV_NAME` | `` 행 추가 → ③ `.env.example` 갱신 → ④ `py -3 scripts/check_env_vars_sync.py`
(등재 누락이면 exit 1).

🔴 **빈 값 ≠ 미설정** — pydantic-settings 는 `VAR=` 도 *설정된 값*으로 읽어 기본값을 빈 문자열로
덮는다. 되돌리는 validator 가 붙은 것은 `CLAUDE_REVIEW_MODEL`·`CLAUDE_INSIGHT_MODEL`·`SMTP_PORT`
셋뿐이다. **기본값** 이 필요하면 변수를 아예 지운다.

## Settings 필드

| 변수 | 기본값 | 무엇을 바꾸는가 |
|---|---|---|
| **DB** | | |
| `DATABASE_URL` | **필수** | 앱 DB 연결. `postgres://`→`postgresql://` 정규화, Supabase 호스트면 `sslmode=require` 자동 추가 |
| `DATABASE_URL_WORKER` | `""` | background(webhook·worker·gate·cron·CLI) 전용 연결. BYPASSRLS role 이어야 함. 빈 값=`DATABASE_URL` 재사용 |
| `DATABASE_URL_FALLBACK` | `""` | primary 장애 시 전환할 보조 DB. 빈 값=failover 없음 |
| `MIGRATION_DATABASE_URL` | `""` | alembic 전용(owner role). 빈 값이면 `DATABASE_URL` |
| `DB_FAILOVER_PROBE_INTERVAL` | `30` | primary 복구 확인 주기(초, ge=1) |
| `DB_SSLMODE` | `""` | 연결 SSL 모드(`require`·`verify-full`…) |
| `DB_FORCE_IPV4` | `false` | Railway IPv4 강제 |
| `DB_POOL_SIZE` | `5` | 풀 크기(ge=1) |
| `DB_MAX_OVERFLOW` | `10` | 풀 초과 연결 수(`-1`=무제한) |
| `DB_POOL_TIMEOUT` | `30` | 풀 대기 초(ge=1) |
| `DB_POOL_RECYCLE` | `1800` | 연결 재활용 초(`-1`=비활성) |
| **인증·하드닝** | | |
| `SESSION_SECRET` | `dev-secret-change-in-production` | 세션 쿠키 서명. 커스텀 값이 32자 미만이면 기동 차단, 기본값 그대로면 경고만 |
| `ENVIRONMENT` | `""` | `production` 이면 HSTS·쿠키 Secure·/docs 비노출 강제. 미설정 시 `APP_BASE_URL` 의 https 여부로 판정 |
| `APP_BASE_URL` | `""` | OAuth redirect_uri https 강제 + CORS allow_origins |
| `GITHUB_CLIENT_ID` | `""` | GitHub OAuth 로그인 |
| `GITHUB_CLIENT_SECRET` | `""` | 위와 쌍 |
| `GITHUB_WEBHOOK_SECRET` | `""` | 리포별 시크릿이 없을 때 쓰는 fallback HMAC. 헤더 없음·불일치·빈 시크릿이면 401 |
| `GITHUB_TOKEN` | `""` | OAuth 토큰 없는 레거시 리포의 API fallback |
| `TOKEN_ENCRYPTION_KEY` | `""` | GitHub 토큰 Fernet 암호화. 미설정 시 평문 저장 |
| `STRICT_TOKEN_ENCRYPTION` | `false` | `true` 면 위 키 미설정·형식오류 시 startup 차단 |
| `STRICT_MIGRATION` | `false` | `true` 면 startup 마이그레이션 실패·timeout 시 기동 차단 |
| `API_KEY` | `""` | REST API `X-Api-Key` 인증. 미설정 + 아래 플래그 off = 503, 불일치 = 401 |
| `API_AUTH_DISABLED` | `false` | `1` 이면 키 없이 REST 통과 — 로컬 전용 |
| `INTERNAL_CRON_API_KEY` | `""` | `/api/internal/cron/*` 전용 키. 미설정 503 / 불일치 401. 인앱 스케줄러는 이 키 없이도 돈다 |
| `SAAS_ADMIN_EMAILS` | `""` | admin 허용 email CSV. 미설정이면 `/admin/*` 503, 불일치 403 |
| **AI** | | |
| `ANTHROPIC_API_KEY` | `""` | Claude 리뷰·인사이트 키. 빈 값이면 AI 항목 기본값 |
| `CLAUDE_REVIEW_MODEL` | `claude-sonnet-4-6` | 코드리뷰 모델 |
| `CLAUDE_INSIGHT_MODEL` | `claude-haiku-4-5` | 인사이트 내러티브 모델 |
| `CLAUDE_REVIEW_MAX_TOKENS` | `8192` | 리뷰 출력 상한(ge=1). 모델 출력 한도보다 크면 400 → `api_error` |
| `DISABLE_PROMPT_CACHE` | `false` | Anthropic prompt cache opt-out |
| **알림** | | |
| `TELEGRAM_BOT_TOKEN` | **필수** | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | **필수** | 알림 수신 chat |
| `TELEGRAM_WEBHOOK_SECRET` | `""` | callback 헤더 검증. 미설정이면 401 = 버튼 게이트 전면 비활성 |
| `N8N_WEBHOOK_SECRET` | `""` | n8n 전송 HMAC. 빈 값이면 서명 생략 |
| `N8N_RELAY_REPO_TOKEN` | `false` | n8n issue 릴레이에 repo OAuth 토큰 동봉(위 시크릿 설정 시에만) |
| `SMTP_HOST` | `""` | 메일 서버 |
| `SMTP_PORT` | `587` | `465`=implicit TLS / 그 외=STARTTLS. 빈 문자열은 587로 보정 |
| `SMTP_USER` | `""` | SMTP 인증 계정 |
| `SMTP_PASS` | `""` | SMTP 인증 비밀번호 |
| **자동 머지** | | |
| `MERGE_RETRY_ENABLED` | `true` | CI 대기 재시도 큐. `false`=단일 시도 |
| `MERGE_RETRY_MAX_ATTEMPTS` | `30` | 큐 행당 재시도 횟수(ge=1) |
| `MERGE_RETRY_MAX_AGE_HOURS` | `24` | 큐 행 만료(ge=1) |
| `MERGE_RETRY_INITIAL_BACKOFF_SECONDS` | `60` | 첫 백오프(ge=1) |
| `MERGE_RETRY_MAX_BACKOFF_SECONDS` | `600` | 최대 백오프. initial 보다 작으면 startup 실패 |
| `MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED` | `true` | `check_suite.completed` 즉시 트리거 |
| `MERGE_RETRY_WORKER_BATCH_SIZE` | `50` | sweep 1회 처리 행 수(ge=1) |
| `MERGE_UNKNOWN_RETRY_LIMIT` | `3` | `mergeable_state=unknown` 폴링 횟수 |
| `MERGE_UNKNOWN_RETRY_DELAY` | `3.0` | 그 폴링 간격(초) |
| **머지 검증자(2nd-LLM)** | | |
| `OPENAI_API_KEY` | `""` | 검증자 키. 빈 값=검증자 완전 비활성(비용 0) |
| `VERIFIER_BASE_URL` | `""` | OpenAI 호환 공급자 엔드포인트. 빈 값=OpenAI |
| `OPENAI_VERIFIER_MODEL` | `gpt-5-mini` | 검증자 모델 |
| `MERGE_VERIFIER_BAND` | `10` | `merge_threshold ~ +N` 점만 검증(ge=1) |
| **i18n** | | |
| `DEFAULT_LOCALE` | `en` | 신규 사용자 기본 언어. `SUPPORTED_LOCALES` 밖이면 startup 실패 |
| `SUPPORTED_LOCALES` | `en,ko,ja` | 지원 코드 CSV(각 2~10자 영숫자/하이픈) |
| `LOCALE_FALLBACK` | `en` | 감지·번역 실패 시 최종 언어. `SUPPORTED_LOCALES` 밖이면 startup 실패 |
| `I18N_TRANSLATIONS_DIR` | `src/i18n/translations` | JSON 번역 파일 위치 |
| `I18N_DISABLED` | `false` | LocaleMiddleware skip + 영문 고정 |
| **주기 작업** | | |
| `SCHEDULER_DISABLED` | `false` | 인앱 스케줄러 6종 job 중단. 스케줄러 자체가 운영 판정에서만 기동한다 |
| `SCAMANAGER_SELF_ANALYSIS_DISABLED` | `false` | 모든 webhook 분석 즉시 skip(202) |

## `os.environ` 직접 read (kill-switch)

`src/shared/feature_kill_switch.py::is_disabled("X")` → `X_DISABLED` 가 `1`/`true`/`yes` 면 참.
`Settings` 필드가 아니라 재기동 없이 반영된다. 사고 대비로 Railway Variables 에 미리 만들어 둔다.

| 변수 | 기본값 | 무엇을 바꾸는가 |
|---|---|---|
| `AI_REVIEW_DISABLED` | `0` | AI 코드리뷰 전역 차단(정적분석·게이트는 그대로) |
| `INSIGHT_DISABLED` | `0` | 대시보드·리포 인사이트 내러티브 차단 |
| `MERGE_VERIFIER_DISABLED` | `0` | 2nd-LLM 검증 차단 |
| `SENSITIVE_PATH_GUARD_DISABLED` | `0` | 인증·마이그레이션·CI 파일 변경 PR 의 자동머지 보류를 해제 |
| `SECURITY_AUTO_PROCESS_DISABLED` | `0` | Code/Secret Scanning 자동 처리 중단 |
| `SAAS_MULTITENANT_DISABLED` | `0` | admin 영역 503 |
| `OPERATIONS_DASHBOARD_DISABLED` | `0` | `/admin/operations` 503 |

## 로컬 전용 (배포 env 아님)

| 변수 | 기본값 | 무엇을 바꾸는가 |
|---|---|---|
| `DOC_REVIEW_GATE_DISABLED` | `0` | 문서 리뷰 훅의 Anthropic 호출 차단 |
| `DOC_REVIEW_GATE_LEDGER` | ON | 훅 판정 원장 기록. `0`/`false`/`no` 만 끈다 |
| `SKIP_MAIN_RED_CHECK` | 미설정 | SessionStart 의 main CI red 관측을 건너뛴다 |
| `PERF_PROD_URL` | Railway 운영 URL | `scripts/perf_measure.py` 측정 대상 |
| `PERF_API_KEY` | `""` | 그 측정의 `X-Api-Key` |

Sentry 는 없다 — 남은 `SENTRY_*` 는 `extra: "ignore"` 로 버려진다. 관측은 `claude_api_call` ·
`pipeline_stage` 구조화 로그이며 env 설정이 필요 없다. env 아닌 튜닝 상수는 `src/constants.py`.
`.env` 는 커밋하지 않는다.
