"""빈 except 핸들러 가드 — 가드 스크립트/훅 계층의 CodeQL py/empty-except 사전 봉인.
Empty-except guard — pre-empts CodeQL py/empty-except across the guard script/hook layer.

배경 / Background: 세션2 가드 3종(`check_dead_code`·`check_noqa_sideeffect`·`posttool_pytest_smoke`)이
`sys.stdout.reconfigure` best-effort 관용구를 설명 주석 없이 복사해 CodeQL alert #547~#549 를 자초했다.
같은 관용구의 4번째 사본(`check_retro_cadence.py`)만 주석을 달고 있어 미발화 — 드리프트가 곧 alert 원인.
Session-2 guards copied the best-effort `sys.stdout.reconfigure` idiom without an explanatory comment,
self-inflicting CodeQL #547~#549. Only the 4th copy carried the comment — the drift *was* the alert.

🔴 CodeQL 동등 판정 — except 라인~pass 라인 구간에 주석이 하나라도 있으면 통과.
`perf_measure.py` 의 `except Exception:  # noqa: BLE001` 이 미발화인 실측과 parity 를 맞춘다.
Parity with CodeQL: any comment in the except..pass span counts as explanatory
(matches the observed non-flagging of `except Exception:  # noqa: BLE001`).
"""
import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
# 가드/훅 계층 — 정적 검사 스크립트가 모여 있어 관용구 복사가 잦은 영역.
# The guard/hook layer — where idiom copy-paste (and thus drift) concentrates.
_SCOPED_DIRS = ("scripts", ".claude/hooks")


def find_uncommented_empty_excepts(source):
    """설명 주석 없는 `except ...: pass` 핸들러의 라인 번호 목록.
    Line numbers of `except ...: pass` handlers that carry no explanatory comment."""
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if len(node.body) != 1 or not isinstance(node.body[0], ast.Pass):
            continue
        # except 라인부터 pass 라인까지 — 어느 라인이든 주석이 있으면 설명 있음.
        # From the except line through the pass line — a comment anywhere counts.
        span = lines[node.lineno - 1:node.body[0].lineno]
        if any("#" in line for line in span):
            continue
        out.append(node.lineno)
    return out


def _scoped_py_files():
    for rel in _SCOPED_DIRS:
        for path in sorted((_ROOT / rel).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


# --- 탐지기 자체 검증 (긍정/부정 통제) / detector self-checks -------------------


def test_detects_bare_pass_handler():
    """주석 없는 빈 except 는 탐지된다 (긍정 통제 — 탐지기 무력화 시 전체 가드가 spurious-pass).
    A comment-less empty except IS detected (positive control)."""
    assert find_uncommented_empty_excepts("try:\n    f()\nexcept ValueError:\n    pass\n") == [3]


def test_comment_on_except_line_passes():
    """except 라인 주석 = 설명 있음 (CodeQL parity — perf_measure.py 실측).
    A comment on the except line counts as explanatory (CodeQL parity)."""
    src = "try:\n    f()\nexcept ValueError:  # noqa: BLE001\n    pass\n"
    assert find_uncommented_empty_excepts(src) == []


def test_comment_on_pass_line_passes():
    """pass 라인 주석 = 설명 있음 (check_retro_cadence.py 가 쓰는 정본 형태).
    A comment on the pass line counts as explanatory (the canonical in-repo shape)."""
    src = "try:\n    f()\nexcept ValueError:\n    pass  # 미지원 스트림 — 무시 / unsupported stream\n"
    assert find_uncommented_empty_excepts(src) == []


def test_handler_with_real_body_ignored():
    """실제 처리 본문이 있는 핸들러는 대상 아님.
    A handler with a real body is out of scope."""
    src = "try:\n    f()\nexcept ValueError:\n    return 0\n"
    assert find_uncommented_empty_excepts(src) == []


# --- 저장소 불변식 / repo invariant ------------------------------------------


def test_no_uncommented_empty_except_in_guard_layer():
    """scripts/ + .claude/hooks/ 전역에 설명 없는 빈 except 0건.
    Zero comment-less empty excepts across scripts/ and .claude/hooks/."""
    violations = []
    for path in _scoped_py_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        for lineno in find_uncommented_empty_excepts(source):
            violations.append(f"{path.relative_to(_ROOT).as_posix()}:{lineno}")
    if violations:
        pytest.fail(
            "설명 주석 없는 빈 except (CodeQL py/empty-except 자초):\n  "
            + "\n  ".join(violations)
            + "\n해결 / Fix: `pass` 뒤에 사유 주석을 다세요 — `pass  # 사유 / reason`"
        )
