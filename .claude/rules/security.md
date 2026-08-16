---
description: 보안 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "src/auth/**"
  - "src/crypto.py"
  - "src/shared/log_safety.py"
  - "src/shared/ssrf.py"
  - "src/shared/secure_compare.py"
  - "src/api/auth.py"
  - "src/webhook/validator.py"
  - "src/main.py"
  - "src/logging_config.py"
---

# 보안 규칙

- **background/시스템 세션 라우팅 = `WorkerSessionLocal`** (본문 = [`db.md`](db.md) §WorkerSessionLocal).
  이 영역 소비자: `src/auth/github.py` (hybrid — callback=`WorkerSessionLocal` / logout=bare `SessionLocal`).
  웹 경로는 bare `SessionLocal`. hybrid 는 두 심볼을 **구분해** 쓴다 (alias 금지).
  `db.md` path 매칭이 이 파일을 포함하지 않아 자동 로드되지 않는다 — 세부는 `db.md` 를 연다.
  집행: `tests/unit/test_worker_session_routing.py`.

- **hook_token 비교**: `!=` 금지. `src/shared/secure_compare.py::secure_str_compare` (`hmac.compare_digest` + UTF-8). 직접 `compare_digest` 재구현 금지. 호출: `src/api/hook.py:147` (verify), `src/api/hook.py:199` (result). 빈 토큰은 비교 전에 거부 (`src/api/hook.py:188-199`).

- **Telegram 게이트 콜백 HMAC**: 콜백 `gate:{decision}:{id}:{token}`. token = `hmac(bot_token, f"{scope}:{id}", sha256).hexdigest()[:32]`.
  발신 `src/gate/telegram_gate.py::_make_callback_token` (`msg = f"{scope}:{payload_id}"`, 12-32행).
  수신 `src/webhook/providers/telegram.py::_parse_gate_callback` (`f"gate:{analysis_id}"`, 68-72행).
  한쪽만 바꾸면 모든 semi-auto 콜백이 401. 신규 HMAC 은 발신/수신 동일 msg + scope prefix 단위 테스트.

- 🔴 **`/health` 는 liveness 만** — `{"status": "ok"}` (`src/main.py:382`). `active_db` 등 내부 상태 금지. `tests/unit/test_main.py::test_health_returns_status_ok`. failover 는 logger. 운영 대시보드가 필요하면 `INTERNAL_CRON_API_KEY` 별도 엔드포인트.

- **GitHub Access Token**: `src/crypto.py` `encrypt_token()` / `decrypt_token()`. `TOKEN_ENCRYPTION_KEY` 미설정 시 평문 저장. 읽을 때는 `User.plaintext_token`. `user.github_access_token` 직접 사용 금지.

- **SESSION_SECRET 강도**: 운영은 32자 이상 랜덤 + `ENVIRONMENT=production` 또는 https `APP_BASE_URL` 중 하나 이상. 실패 모드 정본은 아래 **3분기**. 집행: `tests/unit/test_config.py`.

- 🔴 **REST API 인증 기본 = 키 없으면 503** — `src/api/auth.py::_check_api_key` (13-36행). `API_KEY` 미설정 시 `API_AUTH_DISABLED=1` 명시 opt-out 만 무인증 (`logger.warning` 후). URL 휴리스틱(`app_base_url.startswith("https")`)으로 노출을 결정하지 않는다. 노출 여부는 `settings.api_auth_disabled` 만. **`API_AUTH_DISABLED` 는 로컬 dev 전용.** `tests/conftest.py` 가 테스트에서 `API_AUTH_DISABLED=1` 을 켜고, `tests/unit/api/test_auth.py` 가 `api_auth_disabled=False` 경로를 직접 검증한다.

- **`SAAS_MULTITENANT_DISABLED` 반환 코드**: `require_admin` (`src/auth/session.py:87`, `src/auth/session.py:99`) 는 `HTTPException(status_code=503)`. 401 이 아니다. env-vars.md 인용 시 503.

- 🔴 **TOKEN_ENCRYPTION_KEY**: `_validate_startup_config` (`src/main.py:112` 정의 · 빈 키 분기 `:148-170`) 가 https `APP_BASE_URL` + 빈 키면 WARNING. 비-empty 이나 형식이 틀린 키도 `Fernet(key)` 가능 여부를 본다 — `_get_fernet()` 의 except 가 `_fernet=None` → `encrypt_token` 평문 반환을 막기 위함. `STRICT_TOKEN_ENCRYPTION=true` + prod 는 RuntimeError, 아니면 WARNING. `tests/unit/test_main.py::test_lifespan_strict_mode_raises_when_key_invalid_in_prod`.

- **Jinja2 autoescape**: `Jinja2Templates` 는 `.html` 에 autoescape=True. `| safe` 금지. notifier HTML 은 `html.escape()`.

- **OAuth CSRF state**: Authlib `authorize_access_token()` 이 session state 를 검증. `/auth/github` 를 거치지 않은 `/auth/callback` 은 `OAuthError` → `302 /?error=oauth_failed` (`src/auth/github.py:124-128`).

- **시크릿-in-URL 로그 — `sanitize_for_log` 와 별개**. `sanitize_for_log` 는 CR/LF 인젝션만 다룬다. URL 경로에 토큰이 실리는 채널(Telegram `bot<TOKEN>` · Slack `services/<SECRET>` · Discord `webhooks/<id>/<TOKEN>`)은 URL 전문 로깅이 credential 유출이다.

  - **계층 1** — 호출처가 URL 전문을 찍지 않는다. `src/notifier/_http.py::url_host_for_log`.
  - **계층 1b** — BackgroundTask 는 가드 래퍼. 무가드 예외는 ASGI 밖으로 나가 uvicorn 이 `exc_info` 에 URL 을 싣는다. 패턴: `src/webhook/providers/telegram.py::_post_message_guarded` — `except httpx.HTTPError` 후 `type(exc).__name__` 만 (`str(exc)` 금지).
  - **계층 2** — `src/logging_config.py::_RedactSecretsFilter` 가 `msg` · `exc_text` · `stack_info`. **root 핸들러 + uvicorn 계열 양쪽**. uvicorn 은 `propagate=False` + 자체 핸들러라 root 필터가 도달하지 못한다. 신규 채널은 `_SECRET_URL_PATTERNS` 등재.
  - 🔴 **계층 2 가 못 덮는 채널 — n8n · custom webhook**. 호스트가 사용자 지정이라 정규식 열거가 불가능하다. 호출처가 유일한 통제.
    - `src/worker/pipeline.py::_send_notifications` — `httpx.HTTPError` 는 타입명 + status 만. 그 외는 트레이스백 유지.
    - `src/webhook/providers/github.py::_notify_n8n_issue_guarded` — issue 릴레이 BackgroundTask 도 같은 래퍼.
    - `tests/unit/notifier/test_ssrf_log_redaction.py` — 실패 집계 + 래퍼 + **큐에 올린 태스크를 실제로 실행**해 배선 관측.
  - 🔴 **계층 2 를 본체로 쓰지 말 것** — 필터가 트레이스백을 가리면 호출처 결함이 안 보인다. 계층 1/1b 가 본체. 회귀: `tests/unit/test_logging_config.py` · `tests/unit/notifier/test_ssrf_log_redaction.py` · `tests/unit/webhook/test_telegram_provider.py`.

- **로그 인젝션 (`sanitize_for_log`)**: `src/shared/log_safety.py::sanitize_for_log(value, max_len=200)`. user-controlled 입력은 logger 전에 경유. CR/LF/TAB/NUL 제거 + 길이. `%r` 만으로는 Sonar `pythonsecurity:S5145` 를 통과하지 못한다.

- **URL path (`_repo_path`)**: `src/github_client/repos.py::_repo_path` — `urllib.parse.quote(safe='/')`. GitHub API URL 에 `repo_full_name`/path 를 넣을 때 경유.

- **webhook URL SSRF — send-time + storage-time**:
  (1) send-time = `src/notifier/_http.py::validate_external_url` (DNS 후 `is_dangerous_ip`, discord/slack/n8n/custom).
  (2) storage-time = `src/shared/ssrf.py::is_safe_webhook_url` (https-only + `_BLOCKED_WEBHOOK_HOSTS` + 리터럴 IP). settings 폼 (`ui/routes/settings.py::_validate_webhook_urls`) 과 REST (`api/repos.py::RepoConfigUpdate.validate_webhook_url`) 가 같은 헬퍼. 신규 입력 경로도 `is_safe_webhook_url`. 단일 출처 = `src/shared/ssrf.py`.

- **email To 헤더**: `src/notifier/email.py` 는 `recipients` 를 `msg["To"]` 에 넣기 전 CR/LF 제거.

- **FastAPI Annotated**: `Depends`/`Header` 는 `Annotated[Type, Depends(...)]` / `Annotated[str | None, Header()] = None`. default 있는 param 뒤에 default 없는 Annotated 를 두면 SyntaxError.

- **CSP**: `src/main.py` `SecurityHeadersMiddleware` (74-103행). `script-src 'unsafe-inline'` 은 HTMX + 인라인 스크립트용. 외부 CDN `<script src>` 금지 — `src/static/vendor/`.

- 🔴 **`LimitBodySizeMiddleware` — 이 심볼명을 바꾸면 인접 규칙의 집행자 인용이 끊긴다** (`scripts/check_red_budget.py` 가 블록의 집행자 이름으로 센다). (`src/main.py:54-71`): `Content-Length > 10MB` → 413. 비숫자 → 400 (`src/main.py:65-68`). `Transfer-Encoding: chunked` (헤더 없음)은 이 미들웨어가 못 막는다. `tests/unit/test_main.py` (413 + 비숫자 400). 이 이름을 지우면 빨강 예산 게이트가 인접 항목의 가드 이름을 빌려 계수한다 — 항목 사이에 한 줄이 끼면 사라진다.

- 🔴 **SESSION_SECRET 3분기 — 이 항목이 정본** (집행 = `tests/unit/test_config.py` · `tests/unit/test_main.py`). 운영 요구(32자 랜덤 + prod 신호 하나 이상)는 그대로다. 아래는 어겼을 때 코드가 **실제로** 하는 일.

  - **(1) 커스텀 ∧ 32자 미만** → 임포트 시 `field_validator` 가 거부 (`src/config.py:255-260`). `build_settings` (`src/config.py:565-577`) 가 `SettingsValidationError` (`src/config.py:464`, `ValueError` 하위)로 감싼다. 문서에 `ValidationError` 라 적으면 운영자가 없는 예외를 찾는다.
  - **(2) `SESSION_SECRET` 이 기본값 `"dev-secret-change-in-production"`** → `logger.warning` 후 `return v` (`src/config.py:248-254`) = **기동 성공**(차단 아님). dev 호환.
  - **(3) `SESSION_SECRET` 이 기본값 ∧ `is_production`** → lifespan 이 `RuntimeError` 로 **기동 차단** (`src/main.py:128-136`). `is_production` (`src/config.py:277-279`) = `ENVIRONMENT=production` **또는** `APP_BASE_URL` 이 `https` 로 시작 — APP_BASE_URL 단독이 아니다. 배선 `tests/unit/test_main.py` · 2신호 `tests/unit/test_config.py`.
  - 🔴 **남는 구멍** (`tests/unit/test_config.py` 의 `is_production` 2신호): 두 신호가 **둘 다** 없으면 (2)에 머물러 공개 기본 시크릿으로 기동한다. 위 운영 요구가 이 구멍을 막는 수단이다.
  - 회귀: `tests/unit/test_config.py` (3분기 실행 + 문서 단언 정합) · `tests/unit/test_main.py::test_lifespan_raises_when_default_session_secret_in_prod`.

- **SonarCloud FP suppress**: `sonar-project.properties` `sonar.issue.ignore.multicriteria`. 라인 예외는 `# NOSONAR <ruleKey> — 이유`.
