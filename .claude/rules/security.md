---
description: 보안 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "src/auth/**"
  - "src/crypto.py"
  - "src/shared/log_safety.py"
  - "src/api/auth.py"
  - "src/webhook/validator.py"
  - "src/main.py"
---

# 보안 규칙

- 🔴 **hook_token 비교**: `!=` 연산자는 타이밍 공격에 취약. `hmac.compare_digest(config.hook_token or "", token)` 사용 필수.
- 🔴 **Telegram 게이트 콜백 HMAC 인증 (Phase H PR-5C 후 정정)**: 콜백 데이터 형식 `gate:{decision}:{id}:{token}` — token 은 `hmac(bot_token, f"gate:{analysis_id}", sha256).hexdigest()[:32]` (128-bit). 발신측 (`telegram_gate._make_callback_token(scope="gate", id)`) 과 수신측 (`webhook/providers/telegram._parse_gate_callback`) 모두 동일 msg 형식 (`f"gate:{id}"`) 사용 의무 — 한쪽만 수정 시 모든 semi-auto 콜백 401 거부 (PR-5C 직전 functional bug 사례). 신규 HMAC 토큰 도입 시 발신/수신 동일 msg 형식 + scope prefix 단위 테스트 강제.
- 🔴 **`/health` 응답 내부 상태 미노출 (Phase H PR-5B)**: liveness probe 전용 — `active_db` / DB 연결 정보 등 내부 상태 추가 금지. `tests/unit/test_main.py::test_health_returns_status_ok` 가 회귀 차단. failover 모니터링은 logger 로그 (Railway) 경유. 인증된 운영 대시보드 필요 시 별도 엔드포인트 (`INTERNAL_CRON_API_KEY` 기반) 신설.
- **GitHub Access Token 암호화**: `src/crypto.py`의 `encrypt_token()`/`decrypt_token()` — `TOKEN_ENCRYPTION_KEY` 미설정 시 평문 저장. `User.plaintext_token` property가 DB 읽기 시 자동 복호화. `user.github_access_token` 직접 사용 금지 — `user.plaintext_token` 사용.
- **SESSION_SECRET 강도**: `validate_session_secret` validator (`src/config.py`) 가 32자 미만 또는 기본값이면 WARNING 출력. 프로덕션에서는 32자 이상 랜덤 문자열 필수.
- **TOKEN_ENCRYPTION_KEY prod 감지**: lifespan startup 에서 `APP_BASE_URL` 이 https:// 로 시작하고 키가 비어있으면 WARNING 배너 출력. dev 환경(http 또는 빈 URL)에서는 침묵.
- **Jinja2 autoescape**: `Jinja2Templates`는 `.html` 파일에 대해 autoescape=True(기본값). 템플릿 변수는 자동 이스케이프됨 — `| safe` 필터 사용 금지. notifier HTML 출력엔 `html.escape()` 직접 적용 필수.
- **OAuth CSRF state**: Authlib `authorize_access_token()`이 session state 검증을 내부 처리. `/auth/github`를 거치지 않은 직접 콜백(`/auth/callback`) 접근은 에러(500)로 차단됨 — 정상 동작.
- **로그 인젝션 방어 (`sanitize_for_log`)**: `src/shared/log_safety.py`의 `sanitize_for_log(value, max_len=200)` 헬퍼로 user-controlled 입력을 logger 에 전달하기 전 반드시 경유. CR/LF/TAB/NUL 제거 + 길이 제한. `%r` 포맷만으로는 SonarCloud `pythonsecurity:S5145` taint analysis 를 통과 못 함 — 명시적 함수 호출 필요. 예: `logger.info("...%s...", sanitize_for_log(body.repo))`.
- **URL Path 방어적 인코딩 (`_repo_path`)**: `src/github_client/repos.py::_repo_path(full_name)` 으로 `urllib.parse.quote(safe='/')` 적용. GitHub API URL 에 `repo_full_name`/path 변수 삽입 시 반드시 경유 — SonarCloud `pythonsecurity:S7044` 경고 회피 + 실질적 path injection 차단.
- **FastAPI Annotated 패턴 강제**: `Depends(...)`/`Header(...)` 는 `Annotated[Type, Depends(require_login)]` / `Annotated[str | None, Header()] = None` 형식으로 작성. `python:S8410` 규칙. `default 있는 param 뒤에 Annotated (default 없음)` 오면 SyntaxError — 함수 시그니처에서 `Annotated` 를 앞으로 이동 필요.
- **SonarCloud FP suppress 규약**: `sonar-project.properties` 의 `sonar.issue.ignore.multicriteria` 에 규칙별 예외 추가. 개별 라인 예외는 `# NOSONAR <ruleKey> — 이유` 주석. 커스텀 sanitizer 를 SonarCloud taint analysis 가 인식 못 할 때 NOSONAR 주석 + 이유 명시가 표준.
