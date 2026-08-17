# 환경변수

정본 = `src/config.py` `Settings`. 추가: 필드 선언 → 표 행 → `.env.example` →
`py -3 scripts/check_env_vars_sync.py`(미등재 exit 1). 빈 칸=`""` · `DB_*`·`MERGE_*` ge=1 ·
튜닝 상수 = `src/constants.py` · `SENTRY_*` 는 `extra:"ignore"` 로 버려진다.

🔴 `VAR=` 는 기본값을 **빈 문자열로 덮는다** — 복구 validator 는
`CLAUDE_REVIEW_MODEL`·`CLAUDE_INSIGHT_MODEL`·`SMTP_PORT` 뿐.

|변수|기본값|무엇을 바꾸는가|
|---|---|---|
|`DATABASE_URL`|필수|Supabase=sslmode=require|
|`DATABASE_URL_WORKER`||background(BYPASSRLS)|
|`DATABASE_URL_FALLBACK`||장애 시 전환|
|`MIGRATION_DATABASE_URL`||alembic(owner)|
|`DB_FAILOVER_PROBE_INTERVAL`|30|
|`DB_SSLMODE`|
|`DB_FORCE_IPV4`|false|
|`DB_POOL_SIZE`|5|
|`DB_MAX_OVERFLOW`|10|-1=무제한|
|`DB_POOL_TIMEOUT`|30|
|`DB_POOL_RECYCLE`|1800|-1=비활성|
|`SESSION_SECRET`|dev-secret-change-in-production|커스텀 <32자=기동 차단 · 기본값=경고만|
|`ENVIRONMENT`||production 또는 https APP_BASE_URL=prod 하드닝(security.md)|
|`APP_BASE_URL`||OAuth redirect_uri + CORS origin|
|`GITHUB_CLIENT_ID`|
|`GITHUB_CLIENT_SECRET`|
|`GITHUB_WEBHOOK_SECRET`||리포별 없으면 HMAC fallback · 불일치 401|
|`GITHUB_TOKEN`||OAuth 없을 때 fallback|
|`TOKEN_ENCRYPTION_KEY`||미설정=평문 저장|
|`STRICT_TOKEN_ENCRYPTION`|false|true=키 없으면 기동 차단|
|`STRICT_MIGRATION`|false|true=마이그레이션 실패 차단|
|`API_KEY`||X-Api-Key · 503/401|
|`API_AUTH_DISABLED`|false|1=키 없이 통과|
|`INTERNAL_CRON_API_KEY`||cron · 503/401|
|`SAAS_ADMIN_EMAILS`||admin CSV · 503/403|
|`ANTHROPIC_API_KEY`|
|`CLAUDE_REVIEW_MODEL`|claude-sonnet-4-6|
|`CLAUDE_INSIGHT_MODEL`|claude-haiku-4-5|
|`CLAUDE_REVIEW_MAX_TOKENS`|8192|초과=400→api_error|
|`DISABLE_PROMPT_CACHE`|false|
|`OPENAI_API_KEY`||빈 값=검증자 비활성|
|`VERIFIER_BASE_URL`||OpenAI 호환|
|`OPENAI_VERIFIER_MODEL`|gpt-5-mini|
|`MERGE_VERIFIER_BAND`|10|threshold~+N 검증|
|`TELEGRAM_BOT_TOKEN`|필수|
|`TELEGRAM_CHAT_ID`|필수|
|`TELEGRAM_WEBHOOK_SECRET`||미설정=401(버튼 off)|
|`N8N_WEBHOOK_SECRET`||빈 값=서명 생략|
|`N8N_RELAY_REPO_TOKEN`|false|
|`SMTP_HOST`|
|`SMTP_PORT`|587|465=implicit TLS · 그 외 STARTTLS|
|`SMTP_USER`|
|`SMTP_PASS`|
|`MERGE_RETRY_ENABLED`|true|CI 대기 재시도 큐|
|`MERGE_RETRY_MAX_ATTEMPTS`|30|
|`MERGE_RETRY_MAX_AGE_HOURS`|24|
|`MERGE_RETRY_INITIAL_BACKOFF_SECONDS`|60|
|`MERGE_RETRY_MAX_BACKOFF_SECONDS`|600|initial 미만=기동 실패|
|`MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED`|true|check_suite 트리거|
|`MERGE_RETRY_WORKER_BATCH_SIZE`|50|
|`MERGE_UNKNOWN_RETRY_LIMIT`|3|
|`MERGE_UNKNOWN_RETRY_DELAY`|3.0|
|`DEFAULT_LOCALE`|en|목록 밖=기동 실패|
|`SUPPORTED_LOCALES`|en,ko,ja|
|`LOCALE_FALLBACK`|en|
|`I18N_TRANSLATIONS_DIR`|src/i18n/translations|
|`I18N_DISABLED`|false|영문 고정|
|`SCHEDULER_DISABLED`|false|
|`SCAMANAGER_SELF_ANALYSIS_DISABLED`|false|분석 skip(202)|
|**kill-switch**||이 아래는 `Settings` 밖 `os.environ` 직접 read 라 재기동 불요 · `1`/`true`/`yes` → `is_disabled` 참(`src/shared/feature_kill_switch.py`)|
|`AI_REVIEW_DISABLED`|0|정적·게이트 유지|
|`INSIGHT_DISABLED`|0|
|`MERGE_VERIFIER_DISABLED`|0|
|`SENSITIVE_PATH_GUARD_DISABLED`|0|자동머지 보류 해제|
|`SECURITY_AUTO_PROCESS_DISABLED`|0|
|`SAAS_MULTITENANT_DISABLED`|0|admin 503|
|`OPERATIONS_DASHBOARD_DISABLED`|0|/admin/operations 503|
|**로컬 전용**|
|`DOC_REVIEW_GATE_DISABLED`|0|Anthropic 호출 차단|
|`DOC_REVIEW_GATE_LEDGER`|ON|0/false/no 만 끈다|
| `SKIP_MAIN_RED_CHECK` | 미설정 | main CI red 관측 생략 |
|`PERF_PROD_URL`|운영 URL|perf_measure.py|
|`PERF_API_KEY`||X-Api-Key|
