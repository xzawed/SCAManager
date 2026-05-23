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
- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ[key] = value` 직접 대입으로 환경변수를 주입함 (사이클 65 fix — `setdefault`는 셸 환경 export 시 무시되어 운영 토큰이 설정으로 유입되는 버그가 있었음). src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함.
- **E2E 격리**: `e2e/`를 최상위 별도 디렉토리로 분리 (`tests/` 아래 금지) — `tests/e2e/`가 있으면 `asyncio_mode=auto`와 `sys.modules` 삭제가 충돌해 단위 테스트 98개 실패. E2E 서버는 `uvicorn.Server.serve()`를 `asyncio.new_event_loop()` + `loop.run_until_complete()`로 실행.
- 🔴 **e2e ↔ tests/integration 동시 실행 금지**: `e2e/pytest.ini` 가 의도적으로 asyncio_mode 미설정 (위 E2E 격리 사유) — `pytest e2e/ tests/integration/` 같은 동시 실행 시 integration 의 async 테스트가 sync 처럼 실행 → "coroutine was never awaited" RuntimeWarning + fail. 분리 실행 default — `make test-e2e` (e2e) ↔ `pytest tests/` 또는 CI command (testpaths=tests, e2e 자동 격리).
- **`@pytest.mark.perf` 선택 실행**: `make test-perf` = `pytest e2e/ -m perf -v --timeout=120 -p no:asyncio`. 일반 E2E(`make test-e2e`)와 분리 실행 — CI `testpaths=tests`에 포함되지 않음(자동 격리). `perf` 마커는 루트 `pytest.ini`와 `e2e/pytest.ini` 양쪽 등록됨.

## Mock + Fixture 패턴

- **require_login 우회**: `tests/unit/ui/test_router.py`는 `app.dependency_overrides[require_login] = lambda: _test_user`로 의존성 override. 신규 UI 라우트 테스트 작성 시 동일 패턴 사용.
- **Mock side_effect 재귀**: `mock.add.side_effect = fn` 설정 후 fn 내에서 `original_add(obj)` 호출 시 재귀 발생. side_effect 함수에서는 원본 mock을 호출하지 말 것 — 캡처만 하고 return None.
- **모듈 레벨 캐시 격리**: `src/webhook/_helpers.py`의 `_webhook_secret_cache`는 모듈 레벨 dict. `tests/conftest.py`의 `_clear_webhook_secret_cache` autouse fixture가 테스트마다 자동 클리어. 신규 모듈 레벨 캐시 추가 시 동일한 autouse fixture 패턴 적용 필수.
- **`services/analytics_service.py` 테스트 패턴**: `db: Session` 인자 + `now: datetime | None = None` 의존성 주입(freezegun 미사용). 각 테스트 파일은 자체 in-memory SQLite engine fixture (`tests/unit/repositories/test_analysis_feedback_repo.py:20-58` 참조). `func.count/avg/min/max` 호출 시 `# pylint: disable=not-callable` 인라인 주석 필수.
- **SessionLocal Mock 한계**: `SessionLocal` Mock 은 ORM 속성 오류 미감지 — 핵심 라우트에 실 DB 테스트 병행 필수.
- 🔴 **empty `__init__.py` + explicit ORM import 의무 (사이클 115 PR #560 / 사이클 116 P1-C)**: `src/models/__init__.py` 가 빈 파일이므로 `import src.models` 에 side-effect 없음 — `Base.metadata.create_all()` 호출 전 **테스트 파일 최상단에 각 ORM 모델을 명시적으로 import** 해야 해당 테이블이 in-memory SQLite 에 생성됨. 누락 시 "no such table: <model>" 런타임 에러. 신규 ORM 모델 추가 시 관련 테스트 파일의 top-level import 확인 필수. 패턴: `from src.models.insight_narrative_cache import InsightNarrativeCache  # noqa: F401`.
- 🔴 **settings 싱글톤 mock — `monkeypatch.setenv` 무효**: `src/api/auth.py` 의 `settings = Settings()` 는 모듈 import 시점에 인스턴스화 완료. `monkeypatch.setenv("API_KEY", ...)` 는 이미 생성된 singleton 에 미반영 → `require_api_key` 가 항상 원래 값으로 판정. 올바른 패턴: `monkeypatch.setattr("src.api.auth.settings.api_key", _VALID_KEY)` — singleton 인스턴스 속성 직접 교체. (사이클 99 PR #441 fix-up `7e13d72` 검증 패턴). 다른 `Settings` 필드도 동일 규칙 적용.

## 회귀 차단 트랩 (사고 검증 영역)

- 🔴 **감사 식별 Critical 항목은 단순 hardening 단정 금지 (Phase H PR-5C 교훈)**: 12-에이전트 감사 등이 식별한 Critical 항목을 처리할 때 단위 테스트 통과만으로 검증 완료 단정 금지. `_TOKEN_42` 같은 하드코딩 fixture 가 receiver pattern 을 받아쓰기 (사이드웨이) 로 우회해 functional bug 를 가릴 수 있음 — PR-5C 사례 (모든 semi-auto Telegram 콜백이 실제 운영에서 401 거부됐으나 테스트는 통과). TDD Red 단계에서 "기존 테스트가 왜 통과하는가" 자문 의무.
- 🔴 **`find_by_full_name` 같은 hot-path repository 함수 시그니처 변경 금지 (Phase H PR-3B)**: 70+ 단위 테스트가 `db.query.return_value.filter.return_value.first` mock chain 사용. `.options(joinedload(...))` 같은 메서드 추가 시 chain 깨짐 → 70+ 회귀 (Phase S.4 트랩 재발견). 신규 옵션은 별도 함수 (`find_by_full_name_with_owner` 패턴) 로 분리 — 기존 시그니처 불변.
- 🔴 **의도적 중복 코드의 PARITY GUARD 패턴 (Phase H PR-5A)**: 두 모듈에 의도적으로 동일 함수가 있는 경우 (예: `_get_ci_status_safe` engine + service), 양쪽 docstring 에 `🔴 **PARITY GUARD**` 표지 + 변경 시 동시 수정 의무 명시 + parity 회귀 가드 테스트 (시그니처 + 행동 동등성) 의무.

## R0914 too-many-locals cleanup 결정 트리

pylint R0914 발생 시 두 패턴 중 선택:
1. **헬퍼 추출 default** — 신규 함수 작성 시. 단일 책임 원칙 + 테스트 격리 + 향후 재사용 가능성 시 default.
2. **inline `# pylint: disable=too-many-locals` + 사유 주석** — 기존 함수 시그니처 확장 시. 함수 자체의 응집 단위 보호 + 헬퍼 추출이 응집 깨뜨릴 때.

현재 inline disable 사용처 (5건): `gate/github_review.py:108` (merge_pr) / `notifier/merge_failure_issue.py:59` / `services/merge_retry_service.py:100` / `services/dashboard_service.py:77` (dashboard_kpi) + `:224` (frequent_issues_v2). 모두 시그니처 확장 사례.

🔴 **line:span drift 주의**: 위 목록의 line 번호는 코드 변경 시 자연 drift 발생 — 인용 또는 업데이트 시 `grep -n` 실측 의무 (정책 6). 가능 시 commit hash 병기 권장 (예: `github_review.py:108 (#586)`).

## JavaScript 테스트 정책 (사이클 127 P0 학습)

사이클 127 PR #604 회귀 분석: hx-boost `const` 재선언 SyntaxError 는 Python 커버리지 95.7% + 103개 E2E `page.goto()` 테스트 모두 통과했으나 검출 실패. 구조적 원인 3가지 → 아래 규칙으로 봉인.

- 🔴 **Python 커버리지 = JS 커버리지 대체 불가**: `--cov=src` 는 `src/templates/*.html` 인라인 JS 미측정. 커버리지 보고 시 "Python N% / JS: E2E 커버" 형식으로 언어별 분리 명시 의무. "커버리지 95%" 단독 보고 = false 안도감 유발 금지.
- 🔴 **hx-boost 재방문 E2E 테스트 의무 (PR #604 회귀 가드)**: `base.html` `<script>` 블록 변경 시 **3회 이상 hx-boost 재방문 시나리오 E2E 테스트** 작성 의무. `page.goto()` 단독 = fresh JS 컨텍스트 → hx-boost `const` 재선언 SyntaxError 미감지. 패턴: `e2e/test_navigation.py::test_nav_handler_survives_hx_boost_renavigation` 참조.
- 🔴 **`pageerror` JS 에러 트랩 의무 (사이클 127 conftest 반영)**: `e2e/conftest.py` `page` + `seeded_page` fixture 양쪽에 `pg.on("pageerror", ...)` 등록 후 fixture teardown 에서 `pytest.fail()` 변환. Playwright 기본 동작은 uncaught JS exception 묵살 — 트랩 없으면 SyntaxError 재발 감지 불가.
- 🔴 **`get_current_user` override 의무 (사이클 127 conftest 반영)**: `_start_uvicorn` 에서 `require_login` 뿐 아니라 `get_current_user` 도 override 필수. Overview 같은 public 라우트는 `get_current_user` (optional, returns `None`) 의존 → override 없으면 `{% if current_user %}` nav 블록 미렌더링 → nav 링크 존재 여부 테스트 불가.
- **hx-boost 이후 URL 인코딩 predicate 패턴**: `page.goto("owner%2Ftestrepo")` 후 anchor 클릭 시 브라우저 URL 이 decoded `owner/testrepo` 로 변경됨. `wait_for_url(encoded_url)` timeout → `wait_for_url(lambda url: "owner" in url and "testrepo" in url and "/settings" not in url)` predicate 사용.
- **`<script>` top-level `const`/`let` 금지 (PR #604 근본 원인)**: `base.html` + 각 템플릿 `<body>` 안 `<script>` 블록의 top-level `const`/`let` 은 hx-boost 재실행 시 SyntaxError. 모든 변수는 IIFE `(function() { var x = ...; })();` 또는 `var` 단독 선언 사용. `src/templates/*.html` 신규 `<script>` 작성 시 자동 적용.
