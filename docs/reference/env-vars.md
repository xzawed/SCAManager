# SCAManager 환경변수 레퍼런스

## 필수 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@host/db` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 | `123456:ABC-xxx` |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID | `-100xxxxxxxxx` |
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID | `Ov23li...` |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 | `github_...` |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 권장) | `random-secret-key` |

## 선택 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `GITHUB_WEBHOOK_SECRET` | GitHub Webhook HMAC 서명 시크릿 (Phase 8B 이후 선택적) | `your-secret-here` |
| `GITHUB_TOKEN` | GitHub API Personal Access Token (레거시 리포 fallback) | `your-github-token` |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 API 키 (없으면 AI 항목 기본값 적용) | `your-anthropic-api-key` |
| `API_KEY` | Dashboard REST API 인증 키 (없으면 인증 생략) | `any-secret-string` |
| `APP_BASE_URL` | Railway 등 리버스 프록시에서 HTTPS redirect_uri 강제 지정 | `https://your-app.railway.app` |
| `TOKEN_ENCRYPTION_KEY` | GitHub Access Token 암호화 키 (미설정 시 평문 저장) | `32자 이상 랜덤` |
| `CLAUDE_REVIEW_MODEL` | AI 코드리뷰에 사용할 Claude 모델 ID | `claude-sonnet-4-6` (기본) |
| `TELEGRAM_WEBHOOK_SECRET` | Telegram `setWebhook` 시크릿 토큰 (미설정 시 헤더 검증 생략) | 빈 문자열 (기본) |
| `N8N_WEBHOOK_SECRET` | n8n 전송 HMAC 서명 시크릿 (미설정 시 서명 생략) | 빈 문자열 (기본) |

## Observability (선택, Phase E.2)

| 변수 | 설명 | 예시 |
|------|------|------|
| `SENTRY_DSN` | Sentry-compatible DSN — 미설정 시 비활성 (graceful no-op) | `your-sentry-dsn` |
| `SENTRY_ENVIRONMENT` | 환경 태그 | `production` (기본) / `staging` / `development` |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance tracing 샘플링 비율 (0.0~1.0) | `0.1` (기본, 10%) |

### 현재 권장 — 연동 보류

Sentry 의 Developer 무료 플랜이 14일 Trial 로 확인됨 (2026-04-23 사용자 검증).
Phase E.2b/c 의 Claude API 메트릭 + 파이프라인 타이밍은 **Sentry 없이도 Railway
로그에 자동 기록**되므로 당분간 `SENTRY_DSN` 빈 문자열 유지 권장.

### 원할 때 활성화 방안

`sentry-sdk` 는 DSN 형식 호환 서비스라면 어느 것이든 받아들임. 즉 **코드 변경
없이** DSN 만 Railway Variables 에 추가하면 즉시 활성화:

- **GlitchTip** ([glitchtip.com](https://glitchtip.com)) — Sentry-compatible API,
  소규모 프로젝트 영구 무료. 추천.
- **Self-hosted Sentry** — Docker Compose 로 자체 호스팅 가능, 기능 전부 무료.
- **Sentry 유료** — 필요 시.

### 자동 로깅 (env 설정 불필요)

- `claude_api_call` 로그 — model / duration_ms / input_tokens / output_tokens / cost_usd / status
- `pipeline_stage` 로그 — collect_files / analyze / score_and_save / notify / pipeline_total
- Railway Logs 에서 grep / filter 로 조회 가능 (structured log shipper 미연동 상태)

## 알림 채널 (선택)

| 변수 | 설명 |
|------|------|
| `SMTP_HOST` | SMTP 메일 서버 호스트 (예: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP 포트 (기본 587) — Railway에서 빈 문자열 설정 시 크래시, 삭제하거나 숫자로 설정 |
| `SMTP_USER` | SMTP 인증 사용자 |
| `SMTP_PASS` | SMTP 인증 비밀번호 |

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
| `MERGE_RETRY_MAX_ATTEMPTS` | 큐 행당 최대 재시도 횟수 | `30` |
| `MERGE_RETRY_MAX_AGE_HOURS` | 큐 행 만료 시간 (시간) | `24` |
| `MERGE_RETRY_INITIAL_BACKOFF_SECONDS` | 첫 재시도 백오프 (초) | `60` |
| `MERGE_RETRY_MAX_BACKOFF_SECONDS` | 최대 백오프 (초) | `600` |
| `MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED` | `check_suite.completed` 웹훅 즉각 트리거 활성화 | `true` |
| `MERGE_RETRY_WORKER_BATCH_SIZE` | cron sweep 1회 처리 최대 행 수 | `50` |

> 기본값으로 운영 환경에 최적화되어 있어 별도 설정 없이 즉시 동작한다.
> 운영 runbook: `docs/runbooks/merge-retry.md`

## DB Failover (온프레미스 장애 시 Supabase 자동 전환)

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL_FALLBACK` | Failover용 보조 DB URL (빈 값이면 failover 비활성) | `postgresql://user:pass@supabase.co/db?sslmode=require` |
| `DB_FAILOVER_PROBE_INTERVAL` | Primary DB 복구 확인 주기 (초) | `30` |

**주의:** `.env` 파일은 절대 git commit 하지 말 것 (`.gitignore`에 포함됨)

---

## 내부 모듈 상수 (참고 — env var 아님)

환경변수가 아닌 코드 내 모듈 상수지만, 운영 동작 가시성 / 튜닝 시 인지가 필요한 값. 변경은 코드 수정 (PR) 으로만 가능.

| 상수 | 위치 | 값 | 의미 |
|------|------|------|------|
| `WEBHOOK_SECRET_CACHE_TTL` | `src/constants.py` | `300` (초) | 리포 시크릿 캐시 TTL — 변경 후 최대 5분간 구 시크릿으로 검증 |
| `STATIC_ANALYSIS_TIMEOUT` | `src/constants.py` | `30` (초) | 정적 분석 도구 (slither 등) subprocess 타임아웃 |
| `HTTP_CLIENT_TIMEOUT` | `src/constants.py` | `10.0` (초) | 신뢰 API HTTP 호출 타임아웃 (GitHub/Telegram/Railway/SMTP — Anthropic SDK 만 60s 별도) |
| `TELEGRAM_RETRY_AFTER_MAX_SECONDS` | `src/notifier/telegram.py` | `30` | Telegram 429 응답의 retry_after 최대 sleep 시간 (cap) — Phase H PR-2B |
| `_GRAPHQL_MAX_ATTEMPTS` | `src/github_client/graphql.py` | `3` | GitHub GraphQL 5xx + network error 최대 재시도 횟수 — Phase H PR-1B-2 |
| `_GRAPHQL_INITIAL_BACKOFF_SECONDS` | `src/github_client/graphql.py` | `1.0` | GraphQL 재시도 초기 backoff (지수 증가: 1s → 2s) — Phase H PR-1B-2 |
