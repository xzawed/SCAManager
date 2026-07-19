"""`scripts/*.py` 가 비-ASCII 를 출력하면 stdout UTF-8 가드를 갖도록 강제한다.

## 사고 / Incident (2026-07-19)

`scripts/check_dual_import.py` 는 **위반을 발견했을 때만** 이모지·한글로 사유를 출력한다.
그런데 Windows 기본 stdout 인코딩은 cp949 라 그 출력 시점에 크래시했다:

    UnicodeEncodeError: 'cp949' codec can't encode character '\\U0001f534'

즉 **정상 경로는 멀쩡하고 위반 경로만 죽는다** — 가드가 일해야 하는 바로 그 순간 침묵한다.
CI(Ubuntu/UTF-8)에서는 재현되지 않아 오래 남아 있었다.
The guard crashed *only* on the violation path, and only on Windows — invisible in CI.

## 🔴 이 가드가 잠그는 것: 비대칭 / The asymmetry this locks

발견 시점 실측 = `scripts/*.py` 중 비-ASCII 를 출력하는 15개 가운데 **11개는 가드가 있고
4개는 없었다**. 같은 관용구를 대부분 적용해 두고 일부만 빠뜨린 전형적 only-one-side-guarded
패턴이다. 개별 파일을 고치는 것으로는 **다음 스크립트에서 또 빠진다** — 그래서 파일이 아니라
**규칙**을 잠근다.
11 of 15 scripts had the guard; 4 did not. Fixing files does not stop the next omission — so this
locks the rule instead.

## 왜 공유 헬퍼가 아닌가 / Why the idiom is duplicated

`scripts/` 는 `__init__.py` 가 없고 `python scripts/x.py` 로 **standalone 실행**된다
(pre-commit · CI · SessionStart 훅). 공유 모듈을 import 하려면 sys.path 조작이 필요해지고,
그 자체가 새로운 취약점이 된다. 따라서 검증된 4줄 관용구를 복제하고 **누락은 이 테스트가**
막는다 (정책 16 최소 추상화 — 추상화 비용 > 중복 비용인 경우).
"""
import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "scripts"

# 가드로 인정하는 표지 — 두 관용구 모두 허용(기존 자산 보존).
#   1. sys.stdout.reconfigure(encoding="utf-8", ...)   ← 정본(캡처 stream 대비 try/except)
#   2. io.TextIOWrapper(sys.stdout.buffer, ...)        ← 구 관용구(다수 파일에 이미 존재)
# Accepted guard markers; both existing idioms count.
_GUARD_MARKERS = ("sys.stdout.reconfigure", "TextIOWrapper(sys.stdout.buffer")


def _prints_non_ascii(source: str) -> bool:
    """`print(...)` 인자에 비-ASCII 리터럴이 있는가 — AST 로 판정(주석·문자열 오탐 회피).

    Whether any print() call has a non-ASCII string literal argument (AST-based).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - 문법 오류는 별도 문제
        return False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print"):
            continue
        for literal in ast.walk(node):
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                if any(ord(ch) > 127 for ch in literal.value):
                    return True
    return False


def _script_files() -> list[Path]:
    return sorted(p for p in _SCRIPTS.glob("*.py") if p.name != "__init__.py")


def test_every_non_ascii_printing_script_guards_stdout():
    """🔴 비-ASCII 를 출력하는 스크립트는 전부 stdout UTF-8 가드를 가져야 한다.

    누락 시 Windows 로컬에서 **출력 시점에** UnicodeEncodeError 로 죽는다 — 가드 스크립트라면
    위반을 보고해야 할 바로 그 순간이다.
    """
    unguarded = []
    for path in _script_files():
        source = path.read_text(encoding="utf-8")
        if _prints_non_ascii(source) and not any(m in source for m in _GUARD_MARKERS):
            unguarded.append(path.name)

    assert not unguarded, (
        f"비-ASCII 를 출력하는데 stdout UTF-8 가드가 없는 스크립트: {unguarded}\n"
        "→ Windows(cp949) 에서 그 출력 시점에 UnicodeEncodeError 로 죽는다.\n"
        "   진입 함수 첫 줄에 `_make_stdout_safe()` 를 추가할 것 "
        "(관용구: scripts/check_dual_import.py 참조)."
    )


def test_detector_flags_a_synthetic_unguarded_script(tmp_path):
    """🔴 탐지기 자가 검증(양성) — 가드 없는 비-ASCII 출력을 실제로 잡는가.

    통과만 하고 아무것도 안 잡는 가드를 차단한다.
    """
    source = 'print("\\U0001f534 위반")\n'
    assert _prints_non_ascii(source) is True
    assert not any(m in source for m in _GUARD_MARKERS)


def test_detector_ignores_ascii_only_script():
    """부정 통제 — ASCII 만 출력하는 스크립트는 가드를 요구하지 않는다(불필요한 강제 방지)."""
    assert _prints_non_ascii('print("plain ascii")\n') is False


def test_detector_ignores_non_ascii_outside_print():
    """부정 통제 — 주석·docstring 의 한글은 대상이 아니다(출력이 아니므로 크래시 없음).

    `_prints_non_ascii` 가 단순 문자열 검색이었다면 여기서 오탐한다 — AST 를 쓰는 이유다.
    """
    source = '# 한글 주석\n"""한글 docstring"""\nprint("ascii only")\n'
    assert _prints_non_ascii(source) is False


def test_guarded_scripts_actually_call_their_helper():
    """🔴 헬퍼 **정의만** 하고 호출을 안 하면 dead code 다 — 정의 ≠ 배선.

    `_make_stdout_safe` 를 정의한 스크립트는 반드시 호출도 해야 한다
    (2026-07-17 '미배선 dead code 인데 전 스위트 green' 학습).
    """
    defined_but_uncalled = []
    for path in _script_files():
        source = path.read_text(encoding="utf-8")
        if "def _make_stdout_safe" not in source:
            continue
        # 정의 라인을 제외한 호출 흔적
        calls = re.findall(r"^\s*_make_stdout_safe\(\)", source, re.M)
        if not calls:
            defined_but_uncalled.append(path.name)

    assert not defined_but_uncalled, (
        f"`_make_stdout_safe` 를 정의만 하고 호출하지 않는 스크립트: {defined_but_uncalled}\n"
        "→ 가드가 dead code 다. 진입 함수 첫 줄에서 호출할 것."
    )
