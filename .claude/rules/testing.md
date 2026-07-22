---
description: Test 작성·실행 시 적용되는 SCAManager 규칙 (path-scoped, Anthropic 공식 권고 정합)
paths:
  - "tests/**"
  - "e2e/**"
  - "**/conftest.py"
  - "pytest.ini"
---

# 테스트 규칙

## 🔴🔴 가드/테스트 저술 3-불변식 (SSOT = `AGENTS.md`)

> 이 저장소 최다 반복 실수(observer-lie — 코드는 고쳤는데 관측자가 거짓말)의 **저술-시점 규율**.
> **정본은 [`AGENTS.md`](../../AGENTS.md) §가드/관측자 저술 3-불변식** (Claude·Grok dual-consumer).
> 새 가드/테스트/완전성 검사/kill-switch 를 쓸 때 예외 없이 적용한다:
>
> 1. **fail-closed** — 통과 조건이 '문자열/echo/주석/advisory 존재' 면 안 된다. AST·실행 관측을 쓴다(#1136).
> 2. **실경로 뮤테이션** — 합성 픽스처 금지. 실파일/심볼을 깨뜨려 red 확인 + `assert mutated != orig`(#1121).
> 3. **배선 테스트** — 정의≠배선, 순수함수 옳음≠진입점 도달. 산문 grep 아닌 실제 실행/호출 관측(#1145).
>
> 🔴 핵심 질문: *보호 장치를 삭제해도 여전히 참으로 보이는 것은?* 아래 개별 사고 규칙은 이 3 불변식의 인스턴스다.

## 환경 + 격리

- 🔴 **asyncio_mode = auto**: `pytest.ini`의 `asyncio_mode = auto` 필수 — 없으면 모든 async 테스트가 경고 없이 실패.
- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ[key] = value` 직접 대입으로 환경변수를 주입함 (사이클 65 fix — `setdefault`는 셸 환경 export 시 무시되어 운영 토큰이 설정으로 유입되는 버그가 있었음). src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함.
- **E2E 격리**: `e2e/`를 최상위 별도 디렉토리로 분리 (`tests/` 아래 금지) — `tests/e2e/`가 있으면 `asyncio_mode=auto`와 `sys.modules` 삭제가 충돌해 단위 테스트 98개 실패. E2E 서버는 `uvicorn.Server.serve()`를 `asyncio.new_event_loop()` + `loop.run_until_complete()`로 실행.
- 🔴 **e2e ↔ tests/integration 동시 실행 금지**: `e2e/pytest.ini` 가 의도적으로 asyncio_mode 미설정 (위 E2E 격리 사유) — `pytest e2e/ tests/integration/` 같은 동시 실행 시 integration 의 async 테스트가 sync 처럼 실행 → "coroutine was never awaited" RuntimeWarning + fail. 분리 실행 default — `make test-e2e` (e2e) ↔ `pytest tests/` 또는 CI command (testpaths=tests, e2e 자동 격리).
- **`@pytest.mark.perf` 선택 실행**: `make test-perf` = `pytest e2e/ -m perf -v --timeout=120 -p no:asyncio`. 일반 E2E(`make test-e2e`)와 분리 실행 — CI `testpaths=tests`에 포함되지 않음(자동 격리). `perf` 마커는 루트 `pytest.ini`와 `e2e/pytest.ini` 양쪽 등록됨.
- 🔴 **PG 의존 동시성 테스트 CI 활성화 패턴 (사이클 156 S3)**: `FOR UPDATE SKIP LOCKED` 등 PostgreSQL 전용 기능 테스트(`tests/integration/test_retry_concurrency_postgres.py`)는 `@pytest.mark.skipif(not DATABASE_URL_TEST_POSTGRES)` 가드 — 기본 CI(SQLite)에서 **항상 skip**되어 회귀를 못 잡는다. `.github/workflows/ci.yml` 의 별도 `pg-concurrency` job(`services: postgres:16` + health-check)에서 활성화. **(1) env 는 `DATABASE_URL_TEST_POSTGRES` 단일만 — `DATABASE_URL` 은 `conftest.py` 가 sqlite 로 덮어써 무의미.** (2) 명시 단일 파일 경로만 실행 — e2e/integration 혼입 금지(위 🔴 격리 규칙). (3) **동시성 race 테스트는 `threading.Barrier(2, timeout=N)` 동반 의무** — barrier 미동반 시 두 워커 SELECT 윈도우 비중첩으로 회귀(SKIP LOCKED 제거)조차 spurious-pass. `timeout` 은 한 워커 조기 예외 시 deadlock guard. (4) `--timeout=60`.

## Mock + Fixture 패턴

- 🔴 **`importlib.reload(src.database)` 는 세션 전체를 오염시킨다 — `database_module_isolation` fixture 의무 (2026-07-19 회고 B1, #1114)**: `reload` 는 모듈 본문을 재실행해 **`Base = declarative_base()` 로 새 Base 객체를 만든다**. 그런데 이미 import 된 13개 ORM 모델 클래스는 **옛 Base 에 묶인 채** 남으므로 새 `Base.metadata.tables` 는 **영구히 빈다**(실측: 모델 import 후 3 테이블 → reload 후 **0 테이블**). 그 결과 `alembic/env.py` 의 모델 완전성 가드(`_REGISTERED_MODELS`)가 이후 **세션 전체**에서 `RuntimeError` 를 내고, env.py 를 실행하는 모든 테스트가 깨진다.
  - **복구 방식 = 모듈 `__dict__` 전체 스냅샷/복원.** reload 는 네임스페이스를 통째로 갈아끼우므로 개별 속성만 되돌리면 누락이 생긴다. `tests/unit/conftest.py::database_module_isolation` 참조.
  - 🔴 **이 사고가 드러낸 더 큰 문제 — 가드가 알파벳 순서 덕에 살아있었다**: `test_alembic_env_logging_guard.py`(#1102 회귀 가드)가 통과하던 유일한 이유는 **파일명이 알파벳 순으로 앞서 실행되기 때문**이었다. `pytest-randomly` · 파일명 변경 · 샤딩 중 **하나만 있어도 조용히 깨진다**(실측: 순서를 바꾸면 6건 FAIL). **테스트 통과가 실행 순서에 의존하고 있지 않은지 자문할 것** — 순서 의존은 통과가 아무것도 보장하지 않는 대표적 형태다.
  - 신규로 모듈을 `reload` 하는 테스트를 작성하면 **동일 격리 fixture 동반 의무**.

- **require_login 우회**: `tests/unit/ui/test_router.py`는 `app.dependency_overrides[require_login] = lambda: _test_user`로 의존성 override. 신규 UI 라우트 테스트 작성 시 동일 패턴 사용.
- **Mock side_effect 재귀**: `mock.add.side_effect = fn` 설정 후 fn 내에서 `original_add(obj)` 호출 시 재귀 발생. side_effect 함수에서는 원본 mock을 호출하지 말 것 — 캡처만 하고 return None.
- **모듈 레벨 캐시 격리**: `src/webhook/_helpers.py`의 `_webhook_secret_cache`는 모듈 레벨 dict. `tests/conftest.py`의 `_clear_webhook_secret_cache` autouse fixture가 테스트마다 자동 클리어. 신규 모듈 레벨 캐시 추가 시 동일한 autouse fixture 패턴 적용 필수.
- **`services/analytics_service.py` 테스트 패턴**: `db: Session` 인자 + `now: datetime | None = None` 의존성 주입(freezegun 미사용). 각 테스트 파일은 자체 in-memory SQLite engine fixture (`tests/unit/repositories/test_analysis_feedback_repo.py:20-58` 참조). `func.count/avg/min/max` 호출 시 `# pylint: disable=not-callable` 인라인 주석 필수.
- **SessionLocal Mock 한계**: `SessionLocal` Mock 은 ORM 속성 오류 미감지 — 핵심 라우트에 실 DB 테스트 병행 필수.
- 🔴 **empty `__init__.py` + explicit ORM import 의무 (사이클 115 PR #560 / 사이클 116 P1-C)**: `src/models/__init__.py` 가 빈 파일이므로 `import src.models` 에 side-effect 없음 — `Base.metadata.create_all()` 호출 전 **테스트 파일 최상단에 각 ORM 모델을 명시적으로 import** 해야 해당 테이블이 in-memory SQLite 에 생성됨. 누락 시 "no such table: <model>" 런타임 에러. 신규 ORM 모델 추가 시 관련 테스트 파일의 top-level import 확인 필수.
  - **모델을 본문에서 사용하는 경우** (인스턴스화·assert 등): 일반 import (`from src.models.user import User as UserModel`) — 참조가 있어 CodeQL 무관.
  - 🔴 **모델을 create_all 부작용용으로만 import (본문 미참조)**: `# noqa: F401` **단독 금지** — `# noqa` 는 flake8 전용이라 CodeQL `py/unused-import` 은 여전히 발화(main 전체 스캔·#540~545 3회 재발). 대신 **튜플-참조 패턴**을 써서 CodeQL 도 'used' 로 인식 + import 소실 시 loud-fail 하게 한다 (회고 2026-07-18 P1 테마 B, `check_noqa_sideeffect.py` 가 신규 도입을 pre-merge 차단):
    ```python
    from src.models.user import User

    # FK 대상 테이블 등록 — 튜플 참조로 CodeQL py/unused-import 봉인 + 소실 시 loud-fail.
    _FK_TARGET_MODELS = (User,)
    if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
        raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록")
    ```
    선례: `tests/unit/ui/test_repo_detail_query.py` · `alembic/env.py` `_REGISTERED_MODELS`.
- 🔴 **settings 싱글톤 mock — `monkeypatch.setenv` 무효**: `src/api/auth.py` 의 `settings = Settings()` 는 모듈 import 시점에 인스턴스화 완료. `monkeypatch.setenv("API_KEY", ...)` 는 이미 생성된 singleton 에 미반영 → `require_api_key` 가 항상 원래 값으로 판정. 올바른 패턴: `monkeypatch.setattr("src.api.auth.settings.api_key", _VALID_KEY)` — singleton 인스턴스 속성 직접 교체. (사이클 99 PR #441 fix-up `7e13d72` 검증 패턴). 다른 `Settings` 필드도 동일 규칙 적용.

## 회귀 차단 트랩 (사고 검증 영역)

- 🔴 **감사 식별 Critical 항목은 단순 hardening 단정 금지 (Phase H PR-5C 교훈)**: 12-에이전트 감사 등이 식별한 Critical 항목을 처리할 때 단위 테스트 통과만으로 검증 완료 단정 금지. `_TOKEN_42` 같은 하드코딩 fixture 가 receiver pattern 을 받아쓰기 (사이드웨이) 로 우회해 functional bug 를 가릴 수 있음 — PR-5C 사례 (모든 semi-auto Telegram 콜백이 실제 운영에서 401 거부됐으나 테스트는 통과). TDD Red 단계에서 "기존 테스트가 왜 통과하는가" 자문 의무.
- 🔴 **`find_by_full_name` 같은 hot-path repository 함수 시그니처 변경 금지 (Phase H PR-3B)**: 70+ 단위 테스트가 `db.query.return_value.filter.return_value.first` mock chain 사용. `.options(joinedload(...))` 같은 메서드 추가 시 chain 깨짐 → 70+ 회귀 (Phase S.4 트랩 재발견). 신규 옵션은 별도 함수 (`find_by_full_name_with_owner` 패턴) 로 분리 — 기존 시그니처 불변.
- 🔴 **의도적 중복 코드의 PARITY GUARD 패턴 (Phase H PR-5A)**: 두 모듈에 의도적으로 동일 함수가 있는 경우 (예: `_get_ci_status_safe` engine + service, `_coerce_score`(ai_review)↔`_coerce_raw_score`(hook) [사이클 165 #812 — 사용처 2 < 3 이라 공유추출 대신 인라인+가드, 정책16]), 양쪽 docstring 에 `🔴 **PARITY GUARD**` 표지 + 변경 시 동시 수정 의무 명시 + parity 회귀 가드 테스트 (시그니처 + 행동 동등성) 의무.
- 🔴 **모듈 패치 시 이중 import 회피 — string-path 우선 (회고 #520/PR1 학습, 2026-06-23)**: 테스트에서 모듈 속성을 패치할 때 `import src.x as mod` + 상단 `from src.x import fn` 동시 사용은 CodeQL `py/import-and-import-from`(maintainability, main full-scan 만 노출)을 유발한다(#517/#520). **신규 정적 가드/패치 테스트는 `monkeypatch.setattr("src.x.attr", ...)` string-path 우선** — `import as` 별칭 추가 전 상단 from-import 존재 여부 자가 점검. ⚠️ **기존 28개 occurrence(`import X as mod`[mock] + `from X import fn`[호출] idiom)는 의도적 허용** — 차단 pre-commit 훅은 idiom churn/legacy 편집 차단으로 부적절(정책 16/17, 회고 WF-1 EXACT 재평가 결과 hook DROP). 신규 작성 시만 string-path 권장.
- 🔴 **호출 심볼 리네임 시 크로스파일 테스트 동기화 (사이클 165 #811 stale-mock 사고)**: production 함수/심볼 리네임·교체 시(예: `save_gate_decision`→`claim_decision`) 동일 seam 을 patch 하는 테스트가 여러 파일에 분산돼 있으면, 한 파일만 갱신하고 다른 파일은 구 심볼을 patch 한 채 통과(unpatched 실함수가 MagicMock DB 에 silent 실행)하는 사고가 난다. **리네임 PR 필수 체크: `grep -rn '<old_symbol>' tests/` 로 전 테스트 파일 patch 대상 일괄 갱신**. 사이클 165: telegram `save_gate_decision`→`claim_decision` 전환 시 `test_gate_i18n_seam.py` 3곳을 초기 누락(Codex R2 적발 → 교정). 위 "기존 테스트가 왜 통과하는가" 자문을 **크로스파일로 확장** 의무.
- 🔴 **"does not raise" 테스트를 `try/except + pytest.fail` 로 감싸지 말 것 — S5779 ↔ CodeQL 교차 충돌 (#1168 2-round rework 학습)**: `try: result = f() / except Exception: pytest.fail(...)` 패턴은 두 정적 관측자를 **동시에** 위반한다. (a) SonarCloud **S5779** = `except Exception` 이 뒤따르는 assert 의 `AssertionError`(Exception 하위)를 삼켜 실패를 "예외 발생" 으로 오도 → 이를 피하려 assert 를 try **밖**으로 옮기면 (b) CodeQL **`py/uninitialized-local-variable`**(error) = `result` 가 예외 경로에서 미할당(CodeQL 은 `pytest.fail` 을 `NoReturn` 으로 모델링하지 않아 assert 도달 가능으로 판정). 한 관측자를 만족시키면 다른 관측자가 발화하는 observer 연쇄다. **해결 = wrapper 자체 제거**: 예외가 나면 pytest 가 traceback 으로 그대로 실패 보고하므로("does_not_raise" 의 본질) `result = f(); assert isinstance(result, str)` **직접 호출**이 두 관측자 + 테스트 의미를 모두 만족한다(정책 16 단순화). 불필요해진 `import pytest` 는 F401 방지로 함께 제거. 🔴 **기계 집행 (2026-07-22 회고 P1-⑤)**: 이 규칙은 이제 산문뿐이 아니다 — `tests/unit/scripts/test_does_not_raise_wrapper_guard.py` 가 `tests/` 전역에서 broad-except(`Exception`/bare) + `pytest.fail` 단독 wrapper 를 **AST 로 차단**한다(#1170 이 산문-only 라 `test_failover.py:304` 실위반이 살아있던 것을 봉인). 정당한 사용(루프 컨텍스트 진단 등)은 `# does-not-raise-ok: <사유>` escape 주석으로 면제(특정 예외 catch 는 애초 미대상 — 오탐 방지).

## R0914 too-many-locals cleanup 결정 트리

pylint R0914 발생 시 두 패턴 중 선택:
1. **헬퍼 추출 default** — 신규 함수 작성 시. 단일 책임 원칙 + 테스트 격리 + 향후 재사용 가능성 시 default.
2. **inline `# pylint: disable=too-many-locals` + 사유 주석** — 기존 함수 시그니처 확장 시. 함수 자체의 응집 단위 보호 + 헬퍼 추출이 응집 깨뜨릴 때.

현재 inline disable 사용처: src/ 전반 다수 (2026-06-23 기준 ~28개 함수 — **전체·정확 목록은 `grep -rn "too-many-locals" src/` 실측**, 하드코딩 카운트는 자연 drift라 지양). 대표 사례: `gate/github_review.py:108` (merge_pr) · `gate/engine.py:95/144/395` (_run_auto_merge*) · `services/merge_retry_service.py:143` (_process_single_retry) · `services/dashboard_service.py` (dashboard_kpi/frequent_issues_v2/repo_insight_cards/insight_narrative) · notifier `_build_*` 다수 · `worker/pipeline.py:657` (run_analysis_pipeline). 모두 시그니처 확장 사례(헬퍼 추출이 응집 깨뜨릴 때).

🔴 **line:span drift 주의**: 위 목록의 line 번호는 코드 변경 시 자연 drift 발생 — 인용 또는 업데이트 시 `grep -n` 실측 의무 (정책 6). 가능 시 commit hash 병기 권장 (예: `github_review.py:108 (#586)`).

## 손유지 i18n 키 목록 ↔ 템플릿 양방향 가드 (2026-07-09 #1041 6-fail 학습)

- 🔴 **`_KEYS` 같은 손유지 parametrize 목록은 SSOT(템플릿)와 drift 한다**: `tests/unit/test_i18n_settings.py::_KEYS` 는 `settings.*` i18n 키를 손으로 나열한다. #1041 에서 settings 키 제거 시 `_KEYS` 잔존 → `test_settings_key_exists`/`non_empty` parametrize 연쇄가 **다른 영역**(i18n)에서 CI 6-fail (3 로케일 × 2 함수). 근본 = (a) 로컬에서 `tests/unit/ui`+`i18n` 서브셋만 실행 (전체 미실행 = 정책 18 §2 push-전 전체 게이트로 봉인) + (b) `_KEYS` 단방향 검증(키 존재만). **가드**: `test_keys_match_template` 이 `set(_KEYS) == settings.html 의 settings.* 참조 집합`을 강제 → 양방향 drift(템플릿 추가/`_KEYS` 누락 = silent 커버리지 갭, `_KEYS` 잔존/템플릿 제거 = dead 참조) 가시화. 신규 손유지 i18n 키 목록 도입 시 동일 템플릿-대조 가드 동반 권장.
- **settings.* 키 추가/제거 시**: `src/i18n/translations/{ko,en,ja}.json` 의 `settings` 블록 + `settings.html` 참조 + `test_i18n_settings._KEYS` **3곳 동시 갱신** (하나라도 누락 시 위 가드 또는 존재 테스트가 CI fail). JS/base.html 전용 예외 키는 `test_keys_match_template` docstring 규칙대로 명시적 예외 집합 추가.

## JavaScript 테스트 정책 (사이클 127 P0 학습)

사이클 127 PR #604 회귀 분석: hx-boost `const` 재선언 SyntaxError 는 Python 커버리지 95.7% + 103개 E2E `page.goto()` 테스트 모두 통과했으나 검출 실패. 구조적 원인 3가지 → 아래 규칙으로 봉인.

- 🔴 **Python 커버리지 = JS 커버리지 대체 불가**: `--cov=src` 는 `src/templates/*.html` 인라인 JS 미측정. 커버리지 보고 시 "Python N% / JS: E2E 커버" 형식으로 언어별 분리 명시 의무. "커버리지 95%" 단독 보고 = false 안도감 유발 금지.
- 🔴 **hx-boost 재방문 E2E 테스트 의무 (PR #604 회귀 가드)**: `base.html` `<script>` 블록 변경 시 **3회 이상 hx-boost 재방문 시나리오 E2E 테스트** 작성 의무. `page.goto()` 단독 = fresh JS 컨텍스트 → hx-boost `const` 재선언 SyntaxError 미감지. 패턴: `e2e/test_navigation.py::test_nav_handler_survives_hx_boost_renavigation` 참조.
- 🔴 **`pageerror` JS 에러 트랩 의무 (사이클 127 conftest 반영)**: `e2e/conftest.py` `page` + `seeded_page` fixture 양쪽에 `pg.on("pageerror", ...)` 등록 후 fixture teardown 에서 `pytest.fail()` 변환. Playwright 기본 동작은 uncaught JS exception 묵살 — 트랩 없으면 SyntaxError 재발 감지 불가.
- 🔴 **`get_current_user` override 의무 (사이클 127 conftest 반영)**: `_start_uvicorn` 에서 `require_login` 뿐 아니라 `get_current_user` 도 override 필수. Overview 같은 public 라우트는 `get_current_user` (optional, returns `None`) 의존 → override 없으면 `{% if current_user %}` nav 블록 미렌더링 → nav 링크 존재 여부 테스트 불가.
- **hx-boost 이후 URL 인코딩 predicate 패턴**: `page.goto("owner%2Ftestrepo")` 후 anchor 클릭 시 브라우저 URL 이 decoded `owner/testrepo` 로 변경됨. `wait_for_url(encoded_url)` timeout → `wait_for_url(lambda url: "owner" in url and "testrepo" in url and "/settings" not in url)` predicate 사용.
- **`<script>` top-level `const`/`let` 금지 (PR #604 근본 원인)**: `base.html` + 각 템플릿 `<body>` 안 `<script>` 블록의 top-level `const`/`let` 은 hx-boost 재실행 시 SyntaxError. 모든 변수는 IIFE `(function() { var x = ...; })();` 또는 `var` 단독 선언 사용. `src/templates/*.html` 신규 `<script>` 작성 시 자동 적용.
