---
description: API / 알림 채널 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/api/**"
  - "src/notifier/**"
  - "src/webhook/**"
  - "src/gate/**"
  - "src/main.py"
---

# API / 알림 채널 규칙 (Codex)

- **keyword-only 강제**: 모든 `send_*` notifier 함수와 `run_gate_check()` 는 `def fn(*, arg1, arg2)` 형태 — 테스트에서 키워드 인자로 호출 필수.
- **RepoConfig 필드명**: `approve_mode` (구 `gate_mode`), `approve_threshold` (구 `auto_approve_threshold`) — 구 필드명 사용 시 AttributeError.
- **알림 채널 추가 체크리스트**: `RepoConfig` ORM → `RepoConfigData` dataclass → `RepoConfigUpdate` API body → UI 폼 4곳 동기화 필수.
- **GRADE 상수 단일 출처**: `src/constants.py` — 로컬 재정의 금지.
- **ChangedFile / github_api_headers**: `src/github_client/models.py` / `src/github_client/helpers.py` 사용.
- **http_client 싱글톤**: 신뢰 API 는 `src/shared/http_client.py::get_http_client()`, 외부 untrusted URL 은 `src/notifier/_http.py::build_safe_client()`. `async with httpx.AsyncClient()` 매번 생성 금지.
- **알림 독립성**: `asyncio.gather(return_exceptions=True)` — 한 채널 실패해도 나머지 정상 전송.
- **Webhook 서명 실패**: `HTTPException(401)` 반환 — 200 OK 금지.
- **FastAPI Annotated 패턴**: `Annotated[Type, Depends(...)]` / `Annotated[str | None, Header()] = None` 형식.
- **get_repo_or_404**: `src/api/deps.py::get_repo_or_404(repo_name, db)` 사용.
