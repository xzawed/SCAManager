"""`src/logging_config.py` 의 **리댁션 구조** 불변식 — 주석 진위는 검사하지 않는다.

## 사고 (2026-07-19 회고 P2 A17 — OPEN 1순위)

같은 파일의 두 주석이 정면으로 모순됐다:

  · 계층 2b: *"uvicorn 은 `propagate=False` 라 **root 핸들러 필터가 구조적으로 도달 못 한다**"*
  · 계층 2 : *"핸들러는 전파 후 최종 지점이라 **어떤 로거에서 온 레코드든 반드시 통과**한다"*

뒤쪽이 거짓이고, **`#1104` 를 거짓 봉인으로 만든 바로 그 오신념**이다. `#1104` 는 msg 축만
덮고 "2계층 봉인" 을 선언했으나 uvicorn 축이 열려 있어 봇 토큰이 계속 평문 유출됐다.
주석이 그 착각을 **능동적으로 가르치고** 있었다.

## 🔴 이 파일이 봉인하지 **않는** 것 (Grok 적대 검토 2026-07-20)

첫 판에는 "금지 문구가 본문에 없다" · "정정 문구가 본문에 있다" 는 **문자열 단언**이 있었다.
Grok 이 반증했고 맞았다:

  · 금지 문자열은 **패러프레이즈로 우회**된다 — *"2b 보완으로 root 필터가 실질적으로 모든
    로거를 본다"* 는 다른 낱말로 같은 거짓을 말하는데 검사는 green 이다.
  · 요구 문자열은 **더 나쁘다** — 인접한 아무 주석이나 그 토큰을 담고 있으면, 바로 옆에서
    정반대를 주장해도 통과한다. 이건 근거가 아니라 **공허한 green** 이다.

그래서 문자열 단언을 **삭제했다**. 이 파일은 *"주석이 참인가"* 를 묻지 않는다 — 그건 정적
검사로 판정 불가고, 판정 불가를 검사하는 척하는 것이 이 저장소가 반복해 만든 결함이다.

**대신 묻는 것**: 주석이 서술하는 **구조가 코드에 실재하는가**. 구조가 무너지면 여기서
깨지고, 그때 사람이 주석을 다시 읽게 된다. 그 이상은 주장하지 않는다.
This file asserts structure, not prose truth — and does not pretend the two are the same.
"""
import ast
import inspect
from pathlib import Path

import src.logging_config as lc

_SRC = Path(inspect.getfile(lc)).read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _func(name):
    for n in ast.walk(_TREE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f"{name} 을 찾을 수 없다 — 이 가드의 전제 붕괴")


def _calls_in(node):
    return {
        getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        for n in ast.walk(node) if isinstance(n, ast.Call)
    }


# ── 두 계층이 실재하고 서로 다른 집합을 덮는다 ──────────────────────────


def test_uvicorn_direct_attachment_exists_and_is_wired():
    """🔴 `propagate=False` 로거용 **직접 부착** 경로가 실재하고 호출돼야 한다.

    root 핸들러 필터만으로 충분하다면 이 경로는 불필요하다. **존재 자체가**
    "핸들러가 모든 레코드를 본다" 가 거짓이라는 코드 측 증거다 — 주석이 아니라 코드가 말한다.
    """
    assert hasattr(lc, "_attach_redaction_to_uvicorn"), (
        "uvicorn 직접 부착 경로가 사라졌다 — 계층 2b 제거 시 주석도 함께 재검토할 것"
    )
    assert "_attach_redaction_to_uvicorn" in _calls_in(_func("configure_logging")), (
        "계층 2b 가 정의만 되고 호출되지 않는다 — 미배선 dead code"
    )


def test_root_handler_also_carries_the_filter():
    """계층 2(root 핸들러 부착)도 함께 존재해야 한다 — 한쪽만 남으면 커버 집합이 준다."""
    assert "addFilter" in _calls_in(_func("configure_logging"))


def test_uvicorn_attachment_actually_installs_filters():
    """🔴 계층 2b 가 **실제로 필터를 설치**하는지 — 소스 문자열이 아니라 **효과**를 본다.

    초판은 소스에서 `"uvicorn…"` 상수 개수를 셌는데, 이름을 바꿔도 개수가 유지되면
    통과했다(뮤테이션 실측 green). 개수는 커버 범위의 증거가 아니다.
    Count-of-constants proved nothing; observe the installed filters instead.
    """
    import logging

    names = ("uvicorn", "uvicorn.access", "uvicorn.error")
    # 🔴 필터는 로거가 아니라 **각 핸들러**에 붙는다 — uvicorn 이 자체 핸들러를 갖기 때문이다.
    #   핸들러가 없는 로거는 부착 대상이 0개라, 테스트가 실제 운영 형태(핸들러 보유)를 만든다.
    # The filter attaches to each handler, not the logger; seed handlers to mirror runtime.
    seeded = []
    for name in names:
        lg = logging.getLogger(name)
        h = logging.NullHandler()
        lg.addHandler(h)
        seeded.append((lg, h))
    try:
        lc._attach_redaction_to_uvicorn()  # pylint: disable=protected-access
        covered = [
            lg.name for lg, h in seeded
            if any(type(f).__name__ == "_RedactSecretsFilter" for f in h.filters)
        ]
        assert len(covered) >= 2, (
            f"uvicorn 계열 중 리댁션 필터가 실제로 붙은 핸들러 보유 로거가 "
            f"{len(covered)}개다: {covered}"
        )
    finally:
        for lg, h in seeded:
            lg.removeHandler(h)


# ── 리댁션 축이 유지되는가 ──────────────────────────────────────────────


def test_message_axis_inspects_every_record():
    """`getMessage()` 가 **조건 없이** 호출된다 — 축이 조건부로 바뀌면 커버가 준다.

    (이 구조 때문에 '지연 포맷 보존' 이라는 옛 주석 표현이 부정확했다. 표현은 정정했고,
    여기서는 **구조만** 고정한다 — 표현이 참인지는 검사 대상이 아니다.)
    """
    fn = _func("_redact_message")
    assert "getMessage" in _calls_in(fn)
    guarded = any(
        isinstance(n, ast.If) and "getMessage" in _calls_in(n) for n in ast.walk(fn)
    )
    assert not guarded, "getMessage() 가 조건부 호출로 바뀌었다 — 주석 서술을 재검토할 것"


def test_traceback_axis_exists():
    """🔴 exc_info 축 — **실제 운영 유출 경로**였다. 사라지면 #1104 상태로 되돌아간다."""
    assert "_redact_traceback" in _calls_in(_func("filter")), (
        "exc_info 리댁션 축이 filter 에서 호출되지 않는다"
    )


def test_httpx_is_demoted_in_effect():
    """🔴 계층 1(httpx 침묵)을 **효과로** 확인한다 — 사라지면 요청 URL 전문이 다시 INFO 로 나간다.

    초판은 소스에 `getLogger("httpx")` 문자열이 있는지만 봤다. 그런데 **같은 파일 주석이
    httpx 를 설명하므로** 강등 코드를 통째로 지워도 통과했다(뮤테이션 실측 green).
    산문이 코드 검사를 만족시키는 정확한 형태 — 이 세션이 반복해 만난 결함이다.
    The old check was satisfied by the file's own prose about httpx; assert the level instead.
    """
    import logging

    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.NOTSET)   # 사전 상태 제거 / clear prior state
    lc.configure_logging()
    assert httpx_logger.level >= logging.WARNING, (
        f"httpx 로거 레벨이 {logging.getLevelName(httpx_logger.level)} 다 — "
        "INFO 이하면 요청 URL 전문(토큰 포함)이 다시 로그에 남는다"
    )
