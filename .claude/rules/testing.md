---
description: 테스트 작성 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "tests/**"
  - "e2e/**"
  - "**/conftest.py"
  - "pytest.ini"
---

# 테스트 규칙

> 🔴 **사고 재현·측정 로그는 [`docs/_archive/rules-incident-log.md#testing`](../../docs/_archive/rules-incident-log.md#testing) 로 옮겼다 — 규칙을 완화·삭제하려면 아카이브를 먼저 읽을 것** (2026-08-12 밀도 압축).
> 여기 남은 것은 규칙 · 왜 한 줄 · 가드 파일명뿐이며, 서사가 짧아진 것이 규칙이 약해졌다는 뜻이 아니다.
> 역링크·앵커·절 보존 집행: `tests/unit/scripts/test_rules_archive_backlink.py`.
>
> **먼저 열 것 2건** (2026-08-13 3층 분리): 순서 = [`docs/process/guard-authoring.md`](../../docs/process/guard-authoring.md) ·
> 함정 = [`.claude/traps.md`](../traps.md). 아래는 **테스트 표면에만 있는 계약**이다.

## 3-불변식 (정본 SSOT = [`AGENTS.md`](../../AGENTS.md))

새 가드/테스트/완전성 검사/kill-switch 저술 시 **예외 없이**:

1. **fail-closed** — 통과 조건이 '문자열/echo/주석/advisory 존재' 면 안 된다. AST·실행 관측을 쓴다.
2. **실경로 뮤테이션** — 합성 픽스처 금지. 실파일/심볼을 깨뜨려 red 확인 + `assert mutated != orig`.
3. **배선 테스트** — 정의≠배선, 순수함수 옳음≠진입점 도달. 산문 grep 이 아니라 실제 실행/호출 관측.

핵심 질문: *보호 장치를 삭제해도 여전히 참으로 보이는 것은?*

## 통과가 아무것도 보장하지 않는 형태

- **"기존 테스트가 왜 통과하는가" 자문 의무** — 감사가 지목한 Critical 항목을 고칠 때
  단위 통과만으로 검증 완료를 단정하지 말 것. 하드코딩 픽스처가 실제 결함을 가린 전례가 있다
  (모든 semi-auto 콜백이 운영에서 401 이었는데 테스트는 통과).
- **순서 의존 통과 금지** — 알파벳 순서 덕에 통과하던 가드가 있었다(순서를 바꾸면 6건 FAIL).
  `pytest-randomly`·파일명 변경·샤딩 중 하나만으로 조용히 깨진다.
- **심볼 리네임 시 크로스파일 테스트 동기화** — `grep -rn '<old_symbol>' tests/` 전수.
  한 파일만 갱신하면 다른 파일이 구 심볼을 patch 한 채 통과한다(실함수가 MagicMock DB 에 silent 실행).
- **Python 커버리지 ≠ JS 커버리지** — `--cov=src` 는 템플릿 인라인 JS 를 측정하지 않는다.
  보고 시 "Python N% / JS: E2E 커버" 로 **언어별 분리 명시 의무**.

## 환경 / 격리

- **`asyncio_mode = auto`**(`pytest.ini`) 필수 — 없으면 모든 async 테스트가 **경고 없이** 실패.
- **`tests/conftest.py` 는 `os.environ[k] = v` 직접 대입**(`setdefault` 금지 — 셸 export 시 운영 토큰 유입).
  src 모듈은 import 시점에 `Settings()` 를 만들므로 conftest 가 먼저 실행돼야 한다.
- **`e2e/` 는 최상위 별도 디렉토리**(`tests/e2e/` 금지) — `asyncio_mode=auto` 와 `sys.modules` 삭제가 충돌한다.
  **e2e ↔ tests/integration 동시 실행 금지**(`e2e/pytest.ini` 가 의도적으로 asyncio_mode 미설정).
- **`importlib.reload(src.database)` 는 세션 전체를 오염시킨다** — 새 `Base` 를 만들어 기존 모델이
  옛 Base 에 남고 `Base.metadata.tables` 가 **영구히 빈다**. 신규 reload 테스트는
  `tests/unit/conftest.py` 의 `database_module_isolation` fixture(모듈 `__dict__` 전체 스냅샷/복원) 동반 의무.
- 🔴 **PG 전용 동시성 테스트는 `pg-concurrency` job 에서만 활성** — 기본 CI(SQLite)에서 항상 skip 이라 회귀를 못 잡는다.
  (1) env 는 `DATABASE_URL_TEST_POSTGRES` 단일 (2) 명시 단일 파일 경로만
  = `tests/integration/test_retry_concurrency_postgres.py`.
  (3) 🔴 **race 테스트는 `threading.Barrier(2, timeout=N)` 동반 의무** — 없으면 SELECT 윈도우 비중첩으로
  보호를 제거해도 spurious-pass (4) `--timeout=60`.
  현행 유일 소비자이자 패턴 정본: `tests/integration/test_retry_concurrency_postgres.py`.
- ⚠️ **실 semgrep 을 태우는 테스트는 `--timeout=30` 여유가 3배 미만**이라 부하 시 전체 실행에서만 타임아웃한다.
  전체 실행이 거기서 죽으면 **먼저 부하 flake 를 의심**하되, (a) main 전체 (b) 파일 단독 (c) 브랜치 재실행
  **3중 대조 없이 flake 로 판정 금지**.

## Mock / Fixture

- **`SessionLocal` Mock 은 ORM 속성 오류를 감지하지 못한다** — 핵심 라우트는 실 DB 테스트 병행 필수.
- **settings 싱글톤은 `monkeypatch.setenv` 로 안 바뀐다**(import 시점 인스턴스화).
  `monkeypatch.setattr("src.api.auth.settings.api_key", ...)` 로 인스턴스 속성을 직접 교체할 것.
- 🔴 **side-effect ORM import 는 `# noqa: F401` 단독 금지** — noqa 는 flake8 전용이라 CodeQL 은 계속 발화한다
  (3회 재발). 집행: `scripts/check_noqa_sideeffect.py`.
  **튜플-참조 패턴**으로 CodeQL 도 'used' 로 인식시키고 소실 시 loud-fail 하게 만든다:
  ```python
  _FK_TARGET_MODELS = (User,)
  if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
      raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록")
  ```
  🔴 이 이름(`_FK_TARGET_MODELS`)은 `scripts/check_noqa_sideeffect.py` 의 가드가 문서에서 찾는 대상이라 지우면 red 다.
- **모듈 레벨 캐시 추가 시 autouse clear fixture 동반**(`_clear_webhook_secret_cache` 패턴).
- **`require_login` 우회는 `app.dependency_overrides`**, **mock `side_effect` 안에서 원본 mock 호출 금지**(재귀).
- **hot-path repository 함수 시그니처 변경 금지** — 70+ 테스트가 mock chain 에 의존한다.
  신규 옵션은 별도 함수로 분리(`find_by_full_name_with_owner` 패턴).
- **의도적 중복 코드는 `PARITY GUARD` 표지 + 동등성 가드 의무**(양쪽 docstring 명시).
- **모듈 패치는 string-path 우선**(`monkeypatch.setattr("src.x.attr", ...)`) — `import as` + `from import`
  동시 사용은 CodeQL `py/import-and-import-from` 유발. 기존 28 occurrence 는 의도적 허용.

## 금지 패턴

- 🔴 **"does not raise" 를 `try/except + pytest.fail` 로 감싸지 말 것.**
  *왜*: SonarCloud S5779(`except Exception` 이 AssertionError 를 삼킴)와 CodeQL
  `py/uninitialized-local-variable` 이 **서로를 유발**한다. 해결 = wrapper 제거하고 직접 호출.
  기계 집행: `tests/unit/scripts/test_does_not_raise_wrapper_guard.py`(AST 차단, `# does-not-raise-ok:` 로 면제).
- 🔴 **`<script>` top-level `const`/`let` 금지** — hx-boost 재실행 시 SyntaxError. IIFE 또는 `var`.
  정적 축 집행: `tests/unit/ui/test_template_js_const.py`(`src/templates/*.html` 의 `<script>` 블록 전수 스캔).
- 🔴 **`base.html` `<script>` 변경 시 3회 이상 hx-boost 재방문 E2E 의무** — `page.goto()` 단독은
  fresh JS 컨텍스트라 재선언 SyntaxError 를 감지하지 못한다. 실브라우저 축: `e2e/test_navigation.py`.
- 🔴 **`pageerror` 트랩 의무** — Playwright 는 uncaught JS exception 을 기본 묵살한다.
  `e2e/conftest.py` 의 `page`/`seeded_page` 양쪽에 등록 + teardown 에서 `pytest.fail`.
  트랩이 실제로 발화하는지는 `e2e/test_navigation.py` 재방문 시나리오가 관측한다.

## 손유지 목록

- 🔴 **`_KEYS` 같은 손유지 parametrize 목록은 SSOT 와 drift 한다** — 단방향(존재만) 검증이면
  템플릿 추가·목록 누락이 silent 커버리지 갭이 된다. **양방향 대조 가드 동반 의무**
  (`set(_KEYS) == 템플릿 참조 집합`). 현행 사례: `tests/unit/test_i18n_settings.py`.

## R0914 정리 결정

1. **헬퍼 추출 default** — 신규 함수 작성 시.
2. **inline `# pylint: disable=too-many-locals` + 사유** — 기존 시그니처 확장이라 헬퍼 추출이 응집을 깨뜨릴 때.
   현재 사용처 목록은 `grep -rn "too-many-locals" src/` 실측이 정본(하드코딩 카운트는 drift 한다).
