## 지금 켜져 있는 것

| 장치 | 발동 조건 | 좌표 |
|---|---|---|
| 보안 헤더 + CSP | 모든 응답 | `src/main.py::class SecurityHeadersMiddleware` |
| HSTS | prod 만 | `src/main.py::Strict-Transport-Security` |
| 본문 10MB 초과 → 413 | 모든 요청 | `src/main.py::class LimitBodySizeMiddleware` |
| /docs·/redoc·/openapi.json 차단 | prod 만 | `src/main.py::docs_url=` |
| 세션 쿠키 Secure·lax·7일 | Secure 는 prod 만 | `src/main.py::max_age=60 * 60 * 24 * 7` |
| CORS = APP_BASE_URL 단일 출처 | APP_BASE_URL 있을 때 | `src/main.py::allow_origins=[_CORS_ORIGIN]` |
| Rate limit 60/분 (메모리) · 키 = 피어가 Railway 엣지 `100.64.0.0/10` 이면 X-Real-IP(IPv6 /64), 아니면 uvicorn client · 429 WARNING 에 이 키가 남는다(Railway HTTP 로그 `@srcIp` 와 같은 정보 — 수락) | 데코레이터 부착 라우트 | `src/middleware/rate_limiter.py::def rate_limit_key` |
| RLS user_id 전파 | 모든 HTTP | `src/middleware/rls_session.py::async def __call__` |
| 로그 시크릿 마스킹 | 전 로거 | `src/logging_config.py::def _redact(` |

prod 판정 = `ENVIRONMENT=production` 이거나 `APP_BASE_URL` 이 https (`src/config.py::def is_production`).

## 운영 배포 전 6단계

1. `ENVIRONMENT=production` 설정.
2. `openssl rand -hex 32` → `SESSION_SECRET`. **커스텀 값이 32자 미만이면 기동 실패**(`src/config.py::def validate_session_secret`). 기본값(dev-secret)은 prod 판정(`ENVIRONMENT=production` 포함)일 때만 lifespan 이 RuntimeError 로 막고, 아니면 **기동을 막지 않는다**(`src/main.py::def _validate_startup_config`).
3. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` → `TOKEN_ENCRYPTION_KEY` + `STRICT_TOKEN_ENCRYPTION=1`. 없으면 OAuth·Railway 토큰이 평문으로 저장된다 (`src/crypto.py::def encrypt_token`).
4. `API_KEY` · `GITHUB_WEBHOOK_SECRET` · `TELEGRAM_WEBHOOK_SECRET` · `INTERNAL_CRON_API_KEY` 설정 — `API_AUTH_DISABLED=1` 은 로컬 전용.
   서비스 변수에 `FORWARDED_ALLOW_IPS`·`UVICORN_FORWARDED_ALLOW_IPS` 를 넣지 않는다 — uvicorn 이 client 를 X-Forwarded-For 값으로 바꿔 키가 엣지의 XFF 처리(미검증)에 달린다. 가드(`tests/unit/api/test_rate_limiter.py::test_railway_start_command`)는 railway.toml 만 본다. 엣지가 위 대역을 벗어나면 키가 프록시 주소로 합쳐진다. 신호 = 프로세스당 1회 WARNING `rate-limit key fallback`.
5. 기동 로그 `src/main.py::production hardening = %s` 가 ON 인지 확인.
6. `curl -sI https://<host>/health` 로 CSP·HSTS 헤더 존재 확인.

## 시크릿 취급

1. 훅 설치 — `git config --unset-all core.hooksPath` 후 `py -3 -m pre_commit install`. `--hook-type pre-push` 는 붙이지 않는다(리포 자체 push 게이트를 밀어낸다).
2. 코드에는 `settings.<field>` 만 쓴다 — 리터럴 대입은 `.pre-commit-config.yaml::id: check-secrets-in-diff` 가 차단.
3. 커밋 메시지에는 토큰 대신 `<REDACTED>` (`.pre-commit-config.yaml::id: check-commit-msg-secrets`).
4. 유출 시: 발급처에서 즉시 회전 → `trufflehog git file://. --only-verified` 로 잔존 확인 → 이력에 남았으면 `git filter-repo` 후 force push.

## 새 코드에 붙이는 것

- 외부 URL: 저장 시 `src/shared/ssrf.py::def is_safe_webhook_url`, 발신 직전 `src/notifier/_http.py::async def validate_external_url` + `build_safe_client()` 만(https·redirect 금지), 로그에는 `url_host_for_log()` 만.
- 인증: 세션 `require_login` · 관리자 `src/auth/session.py::def require_admin` · 시스템 `src/api/auth.py::require_api_key = Depends`.
- 키·서명 비교는 `src/shared/secure_compare.py::def secure_str_compare`. 키 미설정은 통과가 아니라 503.
- 사용자 입력 로깅은 `src/shared/log_safety.py::def sanitize_for_log`.
