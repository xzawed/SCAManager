## 지금 켜져 있는 것

| 장치 | 발동 조건 | 좌표 |
|---|---|---|
| 보안 헤더 + CSP | 모든 응답 | `src/main.py::class SecurityHeadersMiddleware` |
| HSTS | prod 만 | `src/main.py::Strict-Transport-Security` |
| 본문 10MB 초과 → 413 | 모든 요청 | `src/main.py::class LimitBodySizeMiddleware` |
| /docs·/redoc·/openapi.json 차단 | prod 만 | `src/main.py::docs_url=` |
| 세션 쿠키 Secure·lax·7일 | Secure 는 prod 만 | `src/main.py::max_age=60 * 60 * 24 * 7` |
| CORS = APP_BASE_URL 단일 출처 | APP_BASE_URL 있을 때 | `src/main.py::allow_origins=[_CORS_ORIGIN]` |
| Rate limit 60/분 (IP·메모리) | 데코레이터 부착 라우트 | `src/middleware/rate_limiter.py::limiter = Limiter(` |
| RLS user_id 전파 | 모든 HTTP | `src/middleware/rls_session.py::async def __call__` |
| 로그 시크릿 마스킹 | 전 로거 | `src/logging_config.py::def _redact(` |

prod 판정 = `ENVIRONMENT=production` 이거나 `APP_BASE_URL` 이 https (`src/config.py::def is_production`).

## 운영 배포 전 6단계

1. `ENVIRONMENT=production` 설정.
2. `openssl rand -hex 32` → `SESSION_SECRET`. **커스텀 값이 32자 미만이면 기동 실패**, 기본값(dev-secret) 그대로면 **기동을 막지 않는다** (`src/config.py::def validate_session_secret`).
   기본 `SESSION_SECRET` 이 막히는 것은 prod 판정 시뿐이다 — lifespan `_validate_startup_config` 가 RuntimeError 를 내며, 판정은 `ENVIRONMENT=production` **또는** `APP_BASE_URL` 이 `https` 로 시작이다 (`src/config.py::environment.strip().lower()` · `src/main.py::def _validate_startup_config`).
3. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` → `TOKEN_ENCRYPTION_KEY` + `STRICT_TOKEN_ENCRYPTION=1`. 없으면 OAuth·Railway 토큰이 평문으로 저장된다 (`src/crypto.py::def encrypt_token`).
4. `API_KEY` · `GITHUB_WEBHOOK_SECRET` · `TELEGRAM_WEBHOOK_SECRET` · `INTERNAL_CRON_API_KEY` 설정 — `API_AUTH_DISABLED=1` 은 로컬 전용.
5. 기동 로그에서 `production hardening = ON` 확인 (`src/main.py::production hardening = %s`).
6. `curl -sI https://<host>/health` 로 CSP·HSTS 헤더 존재 확인.

## 시크릿 취급

1. 훅 설치 — `git config --unset-all core.hooksPath` 후 `py -3 -m pre_commit install`. `--hook-type pre-push` 는 붙이지 않는다(리포 자체 push 게이트를 밀어낸다).
2. 코드에는 `settings.<field>` 만 쓴다 — 리터럴 대입은 `check-secrets-in-diff` 가 차단 (`.pre-commit-config.yaml::id: check-secrets-in-diff`).
3. 커밋 메시지에는 토큰 대신 `<REDACTED>` (`.pre-commit-config.yaml::id: check-commit-msg-secrets`).
4. 유출 시: 발급처에서 즉시 회전 → `trufflehog git file://. --only-verified` 로 잔존 확인 → 이력에 남았으면 `git filter-repo` 후 force push.

## 새 코드에 붙이는 것

- 외부 URL: 저장 시 `is_safe_webhook_url()` (`src/shared/ssrf.py::def is_safe_webhook_url`), 발신 직전 `await validate_external_url()` + `build_safe_client()` (`src/notifier/_http.py::async def validate_external_url`), 로그에는 `url_host_for_log()` 만.
- 인증: 세션 `require_login` · 관리자 `require_admin` (`src/auth/session.py::def require_admin`) · 시스템 `require_api_key` (`src/api/auth.py::require_api_key = Depends`).
- 키·서명 비교는 `secure_str_compare` (`src/shared/secure_compare.py::def secure_str_compare`). 키 미설정은 통과가 아니라 503.
- 사용자 입력 로깅은 `sanitize_for_log` (`src/shared/log_safety.py::def sanitize_for_log`).
