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
| `GITHUB_TOKEN` | GitHub API Personal Access Token (레거시 리포 fallback) | `ghp_xxxx` |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 API 키 (없으면 AI 항목 기본값 적용) | `sk-ant-xxxx` |
| `API_KEY` | Dashboard REST API 인증 키 (없으면 인증 생략) | `any-secret-string` |
| `APP_BASE_URL` | Railway 등 리버스 프록시에서 HTTPS redirect_uri 강제 지정 | `https://your-app.railway.app` |
| `TOKEN_ENCRYPTION_KEY` | GitHub Access Token 암호화 키 (미설정 시 평문 저장) | `32자 이상 랜덤` |
| `CLAUDE_REVIEW_MODEL` | AI 코드리뷰에 사용할 Claude 모델 ID | `claude-sonnet-4-6` (기본) |
| `TELEGRAM_WEBHOOK_SECRET` | Telegram `setWebhook` 시크릿 토큰 (미설정 시 헤더 검증 생략) | 빈 문자열 (기본) |
| `N8N_WEBHOOK_SECRET` | n8n 전송 HMAC 서명 시크릿 (미설정 시 서명 생략) | 빈 문자열 (기본) |

## Observability (선택, Phase E.2)

| 변수 | 설명 | 예시 |
|------|------|------|
| `SENTRY_DSN` | Sentry 프로젝트 DSN — 미설정 시 Sentry 비활성 (graceful no-op) | `https://abc@o1.ingest.sentry.io/123` |
| `SENTRY_ENVIRONMENT` | Sentry 에 기록될 환경 태그 | `production` (기본) / `staging` / `development` |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance tracing 샘플링 비율 (0.0~1.0) | `0.1` (기본, 10%) |

Sentry 설정 방법:
1. [Sentry 무료 플랜](https://sentry.io) 에서 Python 프로젝트 생성
2. DSN 을 Railway Variables 의 `SENTRY_DSN` 에 추가
3. 배포 후 이벤트 자동 수집 시작

Claude API 메트릭 (자동, env 설정 불필요):
- 분석 1건당 `claude_api_call` 로그 자동 기록 — model / duration_ms / input_tokens / output_tokens / cost_usd / status
- 파이프라인 단계별 `pipeline_stage` 로그 자동 기록 — collect_files / analyze / score_and_save / notify / pipeline_total

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

## DB Failover (온프레미스 장애 시 Supabase 자동 전환)

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL_FALLBACK` | Failover용 보조 DB URL (빈 값이면 failover 비활성) | `postgresql://user:pass@supabase.co/db?sslmode=require` |
| `DB_FAILOVER_PROBE_INTERVAL` | Primary DB 복구 확인 주기 (초) | `30` |

**주의:** `.env` 파일은 절대 git commit 하지 말 것 (`.gitignore`에 포함됨)
