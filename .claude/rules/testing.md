---
description: Test 작성·실행 시 적용되는 SCAManager 규칙 (path-scoped, Anthropic 공식 권고 정합)
paths:
  - "tests/**"
  - "e2e/**"
  - "**/conftest.py"
  - "pytest.ini"
---

# 테스트 규칙

## 환경 + 격리

- 🔴 **asyncio_mode = auto**: `pytest.ini`의 `asyncio_mode = auto` 필수 — 없으면 모든 async 테스트가 경고 없이 실패.
- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ.setdefault`로 환경변수를 주입함. src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함.
- **E2E 격리**: `e2e/`를 최상위 별도 디렉토리로 분리 (`tests/` 아래 금지) — `tests/e2e/`가 있으면 `asyncio_mode=auto`와 `sys.modules` 삭제가 충돌해 단위 테스트 98개 실패. E2E 서버는 `uvicorn.Server.serve()`를 `asyncio.new_event_loop()` + `loop.run_until_complete()`로 실행.
- 🔴 **e2e ↔ tests/integration 동시 실행 금지**: `e2e/pytest.ini` 가 의도적으로 asyncio_mode 미설정 (위 E2E 격리 사유) — `pytest e2e/ tests/integration/` 같은 동시 실행 시 integration 의 async 테스트가 sync 처럼 실행 → "coroutine was never awaited" RuntimeWarning + fail. 분리 실행 default — `make test-e2e` (e2e) ↔ `pytest tests/` 또는 CI command (testpaths=tests, e2e 자동 격리).

## Mock + Fixture 패턴

- **require_login 우회**: `tests/test_ui_router.py`는 `app.dependency_overrides[require_login] = lambda: _test_user`로 의존성 override. 신규 UI 라우트 테스트 작성 시 동일 패턴 사용.
- **Mock side_effect 재귀**: `mock.add.side_effect = fn` 설정 후 fn 내에서 `original_add(obj)` 호출 시 재귀 발생. side_effect 함수에서는 원본 mock을 호출하지 말 것 — 캡처만 하고 return None.
- **모듈 레벨 캐시 격리**: `src/webhook/_helpers.py`의 `_webhook_secret_cache`는 모듈 레벨 dict. `tests/conftest.py`의 `_clear_webhook_secret_cache` autouse fixture가 테스트마다 자동 클리어. 신규 모듈 레벨 캐시 추가 시 동일한 autouse fixture 패턴 적용 필수.
- **`services/analytics_service.py` 테스트 패턴**: `db: Session` 인자 + `now: datetime | None = None` 의존성 주입(freezegun 미사용). 각 테스트 파일은 자체 in-memory SQLite engine fixture (`tests/unit/repositories/test_analysis_feedback_repo.py:20-58` 참조). `func.count/avg/min/max` 호출 시 `# pylint: disable=not-callable` 인라인 주석 필수.
- **SessionLocal Mock 한계**: `SessionLocal` Mock 은 ORM 속성 오류 미감지 — 핵심 라우트에 실 DB 테스트 병행 필수.

## 회귀 차단 트랩 (사고 검증 영역)

- 🔴 **감사 식별 Critical 항목은 단순 hardening 단정 금지 (Phase H PR-5C 교훈)**: 12-에이전트 감사 등이 식별한 Critical 항목을 처리할 때 단위 테스트 통과만으로 검증 완료 단정 금지. `_TOKEN_42` 같은 하드코딩 fixture 가 receiver pattern 을 받아쓰기 (사이드웨이) 로 우회해 functional bug 를 가릴 수 있음 — PR-5C 사례 (모든 semi-auto Telegram 콜백이 실제 운영에서 401 거부됐으나 테스트는 통과). TDD Red 단계에서 "기존 테스트가 왜 통과하는가" 자문 의무.
- 🔴 **`find_by_full_name` 같은 hot-path repository 함수 시그니처 변경 금지 (Phase H PR-3B)**: 70+ 단위 테스트가 `db.query.return_value.filter.return_value.first` mock chain 사용. `.options(joinedload(...))` 같은 메서드 추가 시 chain 깨짐 → 70+ 회귀 (Phase S.4 트랩 재발견). 신규 옵션은 별도 함수 (`find_by_full_name_with_owner` 패턴) 로 분리 — 기존 시그니처 불변.
- 🔴 **의도적 중복 코드의 PARITY GUARD 패턴 (Phase H PR-5A)**: 두 모듈에 의도적으로 동일 함수가 있는 경우 (예: `_get_ci_status_safe` engine + service), 양쪽 docstring 에 `🔴 **PARITY GUARD**` 표지 + 변경 시 동시 수정 의무 명시 + parity 회귀 가드 테스트 (시그니처 + 행동 동등성) 의무.

## R0914 too-many-locals cleanup 결정 트리

pylint R0914 발생 시 두 패턴 중 선택:
1. **헬퍼 추출 default** — 신규 함수 작성 시. 단일 책임 원칙 + 테스트 격리 + 향후 재사용 가능성 시 default.
2. **inline `# pylint: disable=too-many-locals` + 사유 주석** — 기존 함수 시그니처 확장 시. 함수 자체의 응집 단위 보호 + 헬퍼 추출이 응집 깨뜨릴 때.

현재 inline disable 사용처 (5건): `gate/github_review.py:107` (merge_pr) / `notifier/merge_failure_issue.py:59` / `services/merge_retry_service.py:100` / `services/dashboard_service.py:77` (dashboard_kpi) + `:224` (frequent_issues_v2). 모두 시그니처 확장 사례.
