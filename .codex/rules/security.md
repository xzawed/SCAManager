---
description: 보안 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/auth/**"
  - "src/crypto.py"
  - "src/shared/log_safety.py"
  - "src/api/auth.py"
  - "src/webhook/validator.py"
  - "src/main.py"
---

# 보안 규칙 (Codex)

- 🔴 **hook_token 비교**: `hmac.compare_digest(config.hook_token or "", token)` — `!=` 연산자 금지 (타이밍 공격 취약).
- 🔴 **`/health` 내부 상태 미노출**: DB 연결 정보 등 내부 상태 추가 금지.
- **GitHub Access Token**: `user.plaintext_token` 사용 (`src/crypto.py` 자동 복호화) — `user.github_access_token` 직접 사용 금지.
- **Jinja2 autoescape**: `.html` 파일 자동 이스케이프 — `| safe` 필터 사용 금지. notifier HTML 은 `html.escape()` 직접 적용.
- **로그 인젝션 방어**: `src/shared/log_safety.py::sanitize_for_log(value)` — user-controlled 입력을 logger 에 전달 전 반드시 경유.
- **URL Path 방어**: `src/github_client/repos.py::_repo_path(full_name)` 으로 `urllib.parse.quote(safe='/')` 적용.
- **SonarCloud FP suppress**: `sonar-project.properties` 예외 추가 또는 `# NOSONAR <ruleKey> — 이유` 주석.
