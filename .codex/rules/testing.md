---
description: Test 작성·실행 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "tests/**"
  - "e2e/**"
  - "**/conftest.py"
  - "pytest.ini"
---

# 테스트 규칙 (Codex)

## 환경 + 격리

- `asyncio_mode = auto` 필수 (`pytest.ini` 에 이미 설정됨 — 수정 금지)
- E2E는 `e2e/` 최상위 디렉터리 — `tests/` 아래 배치 금지
- 🔴 `e2e/`와 `tests/integration/` 동시 실행 금지 → `make test-e2e` 분리 실행

## conftest.py 패턴

```python
# src 모듈 임포트 전 환경변수 주입 필수
# Must inject env vars before importing src modules
import os
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
```

## Mock + Fixture 패턴

- `require_login` 우회: `app.dependency_overrides[require_login] = lambda: _test_user`
- Mock `side_effect` 에서 원본 mock 호출 금지 (재귀 발생) — 캡처만 하고 `return None`
- `_webhook_secret_cache`: `tests/conftest.py` 의 `_clear_webhook_secret_cache` autouse fixture 자동 클리어
- `SessionLocal` Mock 은 ORM 속성 오류 미감지 — 핵심 라우트에 실 DB 테스트 병행 필수

## 주의사항

- `func.count/avg/min/max` 호출 시 `# pylint: disable=not-callable` 인라인 주석 필수
- 기존 hot-path 함수 시그니처 변경 금지 (`find_by_full_name` 등) — 신규 함수로 분리
- 🔴 TDD Red 단계에서 "기존 테스트가 왜 통과하는가" 자문 의무 (fixture 우회 가능성 확인)

## pylint R0914 결정 트리

1. 신규 함수 작성: 헬퍼 추출 default
2. 기존 함수 시그니처 확장: `# pylint: disable=too-many-locals` + 사유 주석
