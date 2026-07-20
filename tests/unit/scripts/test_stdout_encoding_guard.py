"""`scripts/*.py` 전부가 stdout UTF-8 가드를 **호출**하도록 강제한다 — 탐지하지 않는다.

## 사고 1 (2026-07-19): 가드 자체의 부재

`scripts/check_dual_import.py` 는 **위반을 발견했을 때만** 이모지·한글로 사유를 출력한다.
Windows 기본 stdout 은 cp949 라 그 출력 시점에 크래시했다:

    UnicodeEncodeError: 'cp949' codec can't encode character '\\U0001f534'

**정상 경로는 멀쩡하고 위반 경로만 죽는다** — 가드가 일해야 하는 바로 그 순간 침묵한다.
CI(Ubuntu/UTF-8)에서는 재현되지 않아 오래 남아 있었다.

## 🔴 사고 2 (회고 P1): **탐지기가 사각을 가졌다**

1차 대응은 "비-ASCII 를 출력하는 스크립트에만 가드를 요구" 였고, 탐지는 AST 로
`print()` 인자의 **문자열 리터럴**만 봤다. 그래서 이런 형태를 통째로 놓쳤다:

    flag = " ⚠"                                  # ← 변수. print 인자의 리터럴이 아니다
    print(f"{pct:5.1f}%  {path}  ...{flag}")

`scripts/parse_coverage.py` 가 정확히 이 형태였고 **무가드로 남아 크래시가 재현됐다**.
게다가 이 파일은 `if __name__` 도 없는 모듈 레벨 스크립트라 "CLI 진입점" 판정으로도 빠진다.

**결론: 탐지 사각이 결함의 본체다.** 그래서 탐지를 없앴다 —
`scripts/*.py` 는 **예외 없이** 가드를 호출한다. ASCII 만 출력하는 스크립트에 붙는 중복
비용은 사각을 남기는 비용보다 싸다.
The detector's blind spots WERE the defect; requiring the guard unconditionally removes the class.

## 왜 공유 헬퍼가 아닌가

`scripts/` 는 `__init__.py` 가 없고 `python scripts/x.py` 로 **standalone 실행**된다
(pre-commit · CI · SessionStart 훅). 공유 모듈 import 는 `sys.path` 조작을 요구하고 그
자체가 새 취약점이 된다. 검증된 관용구를 복제하고 **누락은 이 테스트가** 막는다
(정책 16 최소 추상화 — 추상화 비용 > 중복 비용).
"""
import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "scripts"

# 가드로 인정하는 표지 — 두 관용구 모두 허용(기존 자산 보존).
#   1. sys.stdout.reconfigure(...)              ← 정본(캡처 stream 대비 try/except)
#   2. io.TextIOWrapper(sys.stdout.buffer, ...) ← 구 관용구(다수 파일에 이미 존재)
_GUARD_CALLS = ("reconfigure", "TextIOWrapper")


def _script_files() -> list[Path]:
    return sorted(p for p in _SCRIPTS.glob("*.py") if p.name != "__init__.py")


def _calls_guard(source: str) -> bool:
    """가드가 **호출**되는가 — AST 로 확인한다(주석·문자열 언급은 세지 않는다).

    Whether the guard is actually CALLED (AST), not merely mentioned in prose.

    🔴 문자열 검색이면 "가드를 붙일 것" 이라고 쓴 주석이 검사를 통과시킨다 —
    같은 세션에서 advisory-lock 가드가 정확히 그렇게 죽어 있었다(#1135).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - 문법 오류는 별도 문제
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name in _GUARD_CALLS:
            return True
        # `_make_stdout_safe()` 같은 래퍼 호출도 인정 — 단, 정의만으로는 안 된다(아래 테스트).
        if name == "_make_stdout_safe":
            return True
    return False


# ── 규칙: 예외 없이 전부 / the rule: every script, no exceptions ──────────


def test_every_script_calls_the_stdout_guard():
    """🔴 `scripts/*.py` 는 **전부** stdout UTF-8 가드를 호출한다 — 조건 없음.

    "이 스크립트는 비-ASCII 를 안 쓰니 면제" 같은 판단을 두지 않는다. 그 판단이 바로
    `parse_coverage.py`(변수 경유 `⚠`)를 놓쳤던 지점이다.
    """
    missing = [p.name for p in _script_files() if not _calls_guard(p.read_text(encoding="utf-8"))]
    assert not missing, (
        f"stdout UTF-8 가드를 호출하지 않는 스크립트: {missing}\n"
        "→ Windows(cp949) 에서 비-ASCII 출력 시점에 UnicodeEncodeError 로 죽는다.\n"
        "   진입 지점에 `_make_stdout_safe()` 를 추가할 것 "
        "(관용구: scripts/check_dual_import.py 참조). **면제 없음** — 탐지 사각이 사고의 원인이었다."
    )


def test_defined_guard_is_actually_called():
    """🔴 헬퍼를 **정의만** 하고 호출을 안 하면 dead code 다 — 정의 ≠ 배선.

    (2026-07-17 '미배선 dead code 인데 전 스위트 green' 학습)
    """
    uncalled = []
    for path in _script_files():
        source = path.read_text(encoding="utf-8")
        if "def _make_stdout_safe" not in source:
            continue
        if not re.search(r"^\s*_make_stdout_safe\(\)", source, re.M):
            uncalled.append(path.name)
    assert not uncalled, (
        f"`_make_stdout_safe` 를 정의만 하고 호출하지 않는 스크립트: {uncalled}"
    )


def test_called_guard_is_actually_defined():
    """🔴 역방향 — 호출하는데 **정의가 없으면** 실행 시 `NameError` 로 죽는다.

    이 단언이 없으면 헬퍼를 rename 하고 호출을 안 고친 상태가 전 스위트 green 이다
    (뮤테이션으로 실측 — 정의를 `_unused_guard` 로 바꿔도 6 passed 였다).
    "정의 ⇒ 호출" 과 "호출 ⇒ 정의" 는 **다른 단언**이고 둘 다 필요하다.
    Both directions are needed: renaming the def while leaving the call passes the other test.
    """
    broken = []
    for path in _script_files():
        source = path.read_text(encoding="utf-8")
        if not re.search(r"^\s*_make_stdout_safe\(\)", source, re.M):
            continue
        if "def _make_stdout_safe" not in source and "import _make_stdout_safe" not in source:
            broken.append(path.name)
    assert not broken, (
        f"`_make_stdout_safe()` 를 호출하는데 정의가 없는 스크립트: {broken}\n"
        "→ 실행 즉시 NameError. rename 시 호출부를 함께 고칠 것."
    )


# ── 탐지력 자가 검증 / self-verification ─────────────────────────────────


def test_guard_detector_requires_a_call_not_a_mention():
    """🔴 주석·문자열 언급만으로는 통과하면 안 된다 — advisory-lock 결함(#1135)과 동형."""
    prose = (
        '"""이 스크립트는 sys.stdout.reconfigure 를 붙여야 한다."""\n'
        "# TODO: _make_stdout_safe() 호출 추가\n"
        'HINT = "sys.stdout.reconfigure(encoding=\'utf-8\')"\n'
    )
    assert _calls_guard(prose) is False, "산문 언급이 가드 검사를 통과했다"


def test_guard_detector_accepts_a_real_call():
    """실제 호출은 통과 — 부정 통제(가드가 아무도 만족 못 시키면 규칙이 무의미하다)."""
    impl = "import sys\nsys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
    assert _calls_guard(impl) is True


def test_old_literal_only_detector_missed_variable_borne_non_ascii():
    """🔴 왜 탐지를 폐기했는지 고정 — 구 탐지기가 놓친 실제 형태를 재현한다.

    구 규칙은 "비-ASCII 를 출력하는 스크립트만 가드 필요" 였고, 탐지는 `print()` 인자의
    **리터럴**만 봤다. 아래는 `scripts/parse_coverage.py` 의 실제 형태이며 구 탐지기는
    이것을 '비-ASCII 출력 없음' 으로 판정해 무가드로 남겼다 — 크래시가 재현됐다.
    """
    real_shape = 'flag = " ⚠"\nprint(f"{pct:5.1f}%  {path}{flag}")\n'

    # 구 탐지기 재현: print() 인자의 문자열 리터럴에서만 비-ASCII 를 찾는다.
    def old_detector(src: str) -> bool:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print"):
                continue
            for lit in ast.walk(node):
                if isinstance(lit, ast.Constant) and isinstance(lit.value, str):
                    if any(ord(c) > 127 for c in lit.value):
                        return True
        return False

    assert old_detector(real_shape) is False, (
        "구 탐지기가 이 형태를 잡았다면 폐기 근거가 사라진다 — 전제 재확인 필요"
    )
    # 파일 자체에는 비-ASCII 가 분명히 있다 = 탐지기가 놓친 것이지 없는 게 아니다.
    assert any(ord(c) > 127 for c in real_shape)


def test_scripts_without_dunder_main_are_not_exempt():
    """🔴 `if __name__` 이 없는 모듈 레벨 스크립트도 대상이다.

    `parse_coverage.py`·`parse_bandit.py` 가 그 형태이고, "CLI 진입점" 판정으로 면제하면
    정확히 이 둘이 빠진다(실제로 빠져 있었다).
    """
    module_level = [
        p.name for p in _script_files()
        if "__main__" not in p.read_text(encoding="utf-8")
    ]
    assert module_level, "모듈 레벨 스크립트가 없다 — 이 가드의 전제가 사라졌다"
    for name in module_level:
        source = (_SCRIPTS / name).read_text(encoding="utf-8")
        assert _calls_guard(source), f"{name}: 모듈 레벨 스크립트가 무가드다"
