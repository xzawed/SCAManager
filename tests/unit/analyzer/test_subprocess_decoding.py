"""외부 도구의 출력을 **읽을 수 있는가** — 로케일 독립 디코딩 계약 (#1586).

`subprocess.run(..., text=True)` 는 `locale.getpreferredencoding(False)` 로 디코딩한다.
비-UTF-8 로케일에서 도구가 비-ASCII 를 내면 리더 스레드가 `UnicodeDecodeError` 로 죽고
**`r.stdout` 이 `None`** 이 된다 — 빈 문자열이 아니다.

그러면 두 갈래로 갈린다. 어느 쪽이든 **도구의 실제 출력은 유실된다**:

    `r.stdout.strip()` 을 하는 어댑터   → AttributeError
    `not r.stdout` 을 보는 어댑터       → 「출력 없음」 = 크래시 판별식이 오발화

실측(2026-08-30, cp949 머신): `dotnet format` 이 낸 2989바이트 중 480바이트가 비-ASCII 라
`stdout=''`·`stderr=None` 이 됐고, 그 값으로 잰 `#1565` 의 처방 채점이 **탐지력 유무를
뒤바꿔** 나왔다. 프로덕션(Railway·CI)은 UTF-8 이라 이 결함의 실현된 피해는 **로컬 측정**이다 —
이 리포는 어댑터 판별식을 로컬 실측으로 정하는 일이 잦다. 계기가 먼저 거짓말한 자리다.

## 이 파일이 하는 것

1. **파생 판정** — `src/` 의 모든 `subprocess.run` 이 `text=True` 면 `encoding=` 과 `errors=` 를
   함께 준다. 손으로 센 목록을 두지 않는다. 🔴 어댑터로 좁히지 않는다 — 같은 결함이
   `src/cli/git_diff.py` 에도 있었다(이 리포의 diff 는 한국어를 담는다).
2. **행동 판정** — 그 호출들이 실제로 쓰는 kwargs 를 AST 에서 뽑아 **그대로** 진짜
   subprocess 에 먹인다. 손으로 베낀 사본을 재면 사본만 옳고 실물은 틀린 상태가 초록이 된다.

🔴 이 파일은 CI(UTF-8)에서도 **공허하지 않다.** 프로브가 내는 바이트는 cp949 와 UTF-8
**양쪽에서 모두** 불법이라(`\xff\xfe\xfd`), `errors=` 가 없으면 어느 호스트에서도 red 다.
`encoding="utf-8"` 만으로는 부족하다는 것이 이 축의 부정 통제다.

Locale-independent decoding: `text=True` without `encoding=` yields `stdout is None` on a
non-UTF-8 host. The kwargs under test are read from the real call sites' AST, not copied by hand.
"""
from __future__ import annotations

import ast
import subprocess  # nosec B404
import sys
from pathlib import Path

import pytest

# 🔴 어댑터만 보지 않는다 — 같은 결함이 `src/cli/git_diff.py` 에도 있었다(실측).
#    쓰는 쪽을 넓히면서 읽는 쪽을 안 넓히면 그 자리는 조용히 남는다.
_SRC = Path("src")

# 🔴 cp949 · UTF-8 **양쪽에서 불법**인 바이트. 한쪽에서만 불법인 값을 쓰면 다른 호스트에서
#    이 시험이 조용히 공허해진다(CI 는 UTF-8 이다).
#    `\xff` 는 UTF-8 의 어떤 시퀀스에도 없고 cp949 의 적법한 선행 바이트도 아니다.
# Invalid in BOTH cp949 and UTF-8: a one-sided choice would make this vacuous on the other host.
_UNDECODABLE = b"\xff\xfe\xfd"


def _decoding_run_calls() -> list[tuple[str, int, ast.Call]]:
    """`src/` 전체의 `*.run(...)` 호출 — `(경로, 줄번호, 노드)`.

    🔴 이름으로 좁히지 않는다(`subprocess.run` 만 찾기). 별칭 임포트나 래퍼를 쓰면 그 자리에
    눈멀고, 그것은 이 리포가 반복해 온 관용구 열거와 같은 실패다. `.run(` 을 전부 모은 뒤
    `text=` 를 넘기는 것만 대상으로 좁힌다 — 그 kwarg 가 디코딩을 켜는 스위치다.
    """
    out: list[tuple[str, int, ast.Call]] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "run"
                    and any(kw.arg == "text" for kw in node.keywords)):
                out.append((path.as_posix(), node.lineno, node))
    return out


def _decoding_kwargs(call: ast.Call) -> dict[str, object]:
    """이 호출이 실제로 넘기는 디코딩 kwargs — 리터럴만 읽는다."""
    out: dict[str, object] = {}
    for kw in call.keywords:
        if kw.arg in ("text", "encoding", "errors") and isinstance(kw.value, ast.Constant):
            out[kw.arg] = kw.value.value
    return out


def test_the_scan_actually_finds_calls():
    """🔴 호출을 0건 찾으면 이 파일 전체가 공허하다."""
    calls = _decoding_run_calls()
    assert calls, (
        "`src/` 에서 `text=` 를 넘기는 `.run(...)` 을 하나도 못 찾았다 — "
        "AST 탐색이 깨졌거나 코드가 다른 기전으로 옮겼다. 후자면 이 파일을 다시 써라."
    )


def test_every_call_pins_encoding_and_errors():
    """🔴 `text=True` 인 호출은 `encoding=` 과 `errors=` 를 함께 준다.

    `encoding=` 만으로는 부족하다 — 지정한 인코딩으로도 못 읽는 바이트에서 다시 죽는다.
    """
    offenders = [
        f"{name}:{lineno} ({sorted(kw)})"
        for name, lineno, call in _decoding_run_calls()
        if (kw := _decoding_kwargs(call)).get("text") is True
        and not ("encoding" in kw and "errors" in kw)
    ]
    assert not offenders, (
        f"{len(offenders)}곳이 로케일에 디코딩을 맡긴다: {offenders}\n"
        "  `text=True` 는 `locale.getpreferredencoding(False)` 를 쓴다 — 비-UTF-8 호스트에서\n"
        "  도구가 비-ASCII 를 내면 `r.stdout` 이 **None** 이 되고 출력이 통째로 유실된다.\n"
        '  `encoding="utf-8", errors="replace"` 를 함께 넘겨라.'
    )


def test_the_kwargs_the_code_actually_uses_can_read_undecodable_bytes():
    """🔴 행동 판정 — AST 에서 뽑은 **실물 kwargs** 로 진짜 subprocess 를 태운다.

    손으로 베낀 kwargs 를 재면 사본만 옳고 실물은 틀린 상태가 초록이 된다.
    프로브는 cp949·UTF-8 양쪽에서 불법인 바이트를 내므로 이 단언은 **어느 호스트에서도**
    판별력이 있다 — CI(UTF-8)에서 공허해지지 않는다.
    """
    signatures = {
        tuple(sorted(_decoding_kwargs(call).items()))
        for _, _, call in _decoding_run_calls()
    }
    assert signatures, "kwargs 시그니처가 0건 — 위 공허화 가드가 먼저 잡았어야 한다"

    probe = f"import sys; sys.stdout.buffer.write({_UNDECODABLE!r})"
    for sig in sorted(signatures, key=repr):
        kwargs = dict(sig)
        if kwargs.get("text") is not True:
            continue
        r = subprocess.run(  # nosec B603
            [sys.executable, "-c", probe], capture_output=True, check=False,
            timeout=30, **kwargs,
        )
        assert r.stdout is not None, (
            f"kwargs={kwargs} 로는 도구 출력을 읽지 못한다 — `r.stdout` 이 None 이다.\n"
            "  리더 스레드가 UnicodeDecodeError 로 죽었다는 뜻이고, 어댑터는 그 결과를\n"
            "  「출력 없음」으로 판정한다(= 크래시 판별식 오발화 또는 AttributeError)."
        )


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"text": True}, "로케일에 맡긴다"),
        ({"text": True, "encoding": "utf-8"}, "`errors=` 가 없으면 UTF-8 도 못 읽는 바이트에서 죽는다"),
    ],
)
def test_negative_control_the_shapes_we_rejected_really_do_fail(kwargs, reason):
    """🔴 부정 통제 — 우리가 거부한 두 모양이 **실제로** 출력을 잃는지 확인한다.

    이것이 없으면 위 단언이 무엇을 막는지 알 수 없다. 이 시험이 초록이라는 것은
    `encoding=`+`errors=` 조합이 **공짜 초록이 아니라는** 뜻이다.
    """
    probe = f"import sys; sys.stdout.buffer.write({_UNDECODABLE!r})"
    r = subprocess.run(  # nosec B603
        [sys.executable, "-c", probe], capture_output=True, check=False,
        timeout=30, **kwargs,
    )
    assert r.stdout is None, (
        f"{kwargs} 가 출력을 읽어냈다 ({reason}) — 이 인터프리터/로케일에서는 이 축이 "
        "판별력이 없다. `_UNDECODABLE` 이 정말 양쪽에서 불법인지 다시 재라."
    )
