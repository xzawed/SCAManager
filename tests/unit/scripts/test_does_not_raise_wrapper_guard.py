"""does-not-raise wrapper 가드 — `try: … except (Exception|bare): pytest.fail(…)` 안티패턴 봉인.
does-not-raise wrapper guard — seals the `try: … except (Exception|bare): pytest.fail(…)` antipattern.

## 배경 (#1170 → 이 가드) / Background

2026-07-22 회고 P1-⑤: #1170 이 "does not raise" 테스트의 `try/except+pytest.fail` 안티패턴을
**산문 규칙(`.claude/rules/testing.md`)으로만** 봉인했는데, 실제 위반 인스턴스(`test_failover.py:304`)가
살아 있었다 = 문서-only 시정 재생산(정책 8-5 직격). 이 가드가 그 규칙을 **기계 집행**으로 승격한다.

## 왜 안티패턴인가 / Why it is an antipattern

`try: result = f() / except Exception: pytest.fail(...)` 는:
- 예외가 나면 **pytest 가 이미 traceback 으로 실패 보고**한다("does not raise" 의 본질) → wrapper 무의미.
- try 안에 assert 를 두면 **S5779**(except 가 AssertionError 삼킴), 밖에 두면 **CodeQL
  py/uninitialized-local**(result 미할당) — 두 정적 관측자를 동시에 깬다. 직접 호출이 셋 다 만족.

## 판정 = AST (guards.md 불변식 1 fail-closed) / Detection

`ExceptHandler` 의 본문이 **오직 `pytest.fail(...)` 한 문장**이고, 잡는 예외가 **broad**
(`Exception` 또는 bare)일 때만 플래그. 🔴 **특정 예외**(`except ValueError:`)는 제외 —
"그 예외가 나면 실패" 는 의도적일 수 있어 guard-suicide(오탐) 위험(정책 17 안정성).
정당한 예외(예: 루프 컨텍스트 진단 메시지)는 `# does-not-raise-ok:` escape 주석으로 면제.
"""
import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
# 이 안티패턴은 pytest.fail 을 쓰는 테스트 코드에서만 발생 — tests/ 로 스코프.
# The antipattern only occurs in test code (pytest.fail) — scope to tests/.
_SCOPED_DIR = "tests"
# 정당한 사용(루프 컨텍스트 진단 등) 면제 — B8 의 `# fail-open-reviewed:` 와 동형.
# Escape hatch for legitimate uses (loop-context diagnostics) — mirrors B8's escape comment.
_ESCAPE = "does-not-raise-ok"


def _is_pytest_fail(call):
    """호출이 `pytest.fail(...)` 또는 (from pytest import fail) `fail(...)` 인가.
    Whether a call node is `pytest.fail(...)` or a bare `fail(...)` from `from pytest import fail`."""
    if not isinstance(call, ast.Call):
        return False
    fn = call.func
    if isinstance(fn, ast.Attribute) and fn.attr == "fail" and isinstance(fn.value, ast.Name):
        return fn.value.id == "pytest"
    return isinstance(fn, ast.Name) and fn.id == "fail"


def _is_broad_catch(handler):
    """잡는 예외가 broad 인가 — bare(`except:`) 또는 `except Exception:` 만 True.
    Whether the caught type is broad — only bare or `except Exception:` (specific types excluded)."""
    if handler.type is None:
        return True  # bare except
    return isinstance(handler.type, ast.Name) and handler.type.id == "Exception"


def find_does_not_raise_wrappers(source):
    """본문이 `pytest.fail(...)` 단독 + broad catch 인 except 핸들러의 라인 번호 목록.
    Line numbers of except handlers whose sole body is `pytest.fail(...)` with a broad catch.

    escape 주석(`# does-not-raise-ok`)이 except~fail 구간에 있으면 면제(정당한 사용).
    """
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # 파싱 불가 파일은 대상 아님 — 다른 가드가 다룸 / unparsable: out of scope
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if len(node.body) != 1:
            continue
        stmt = node.body[0]
        if not (isinstance(stmt, ast.Expr) and _is_pytest_fail(stmt.value)):
            continue
        if not _is_broad_catch(node):
            continue  # 특정 예외 catch 는 의도적일 수 있어 제외 (오탐 방지)
        # except 라인부터 fail 라인까지 escape 주석이 있으면 면제.
        # An escape comment anywhere in the except..fail span exempts it.
        span = lines[node.lineno - 1:stmt.value.lineno]
        if any(_ESCAPE in line for line in span):
            continue
        out.append(node.lineno)
    return out


def _scoped_py_files():
    for path in sorted((_ROOT / _SCOPED_DIR).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


# --- 탐지기 자체 검증 (긍정/부정 통제) / detector self-checks -------------------


def test_detects_broad_except_pytest_fail():
    """🔴 긍정 통제 — broad except 의 pytest.fail wrapper 는 탐지된다(탐지기 무력화 시 전체 가드 spurious-pass).
    Positive control — the broad-except pytest.fail wrapper IS detected."""
    src = "def t():\n    try:\n        f()\n    except Exception:\n        pytest.fail('boom')\n"
    assert find_does_not_raise_wrappers(src) == [4]


def test_detects_bare_except_pytest_fail():
    """bare `except:` + pytest.fail 도 broad 로 탐지."""
    src = "def t():\n    try:\n        f()\n    except:\n        pytest.fail('boom')\n"
    assert find_does_not_raise_wrappers(src) == [4]


def test_specific_exception_is_not_flagged():
    """🔴 오탐 방지 — 특정 예외 catch 는 의도적일 수 있어 제외(guard-suicide 방지, 정책 17).
    False-positive guard — a specific-exception catch is NOT flagged (intent may be deliberate)."""
    src = "def t():\n    try:\n        f()\n    except ValueError:\n        pytest.fail('boom')\n"
    assert find_does_not_raise_wrappers(src) == []


def test_handler_with_real_body_is_ignored():
    """pytest.fail 이 아닌 본문(실제 처리)은 대상 아님."""
    src = "def t():\n    try:\n        f()\n    except Exception:\n        logger.warning('x')\n"
    assert find_does_not_raise_wrappers(src) == []


def test_multi_statement_handler_is_ignored():
    """본문이 여러 문장이면 단순 wrapper 가 아니므로 제외(보수적)."""
    src = (
        "def t():\n    try:\n        f()\n    except Exception as e:\n"
        "        log(e)\n        pytest.fail('boom')\n"
    )
    assert find_does_not_raise_wrappers(src) == []


def test_escape_comment_exempts_legitimate_use():
    """🔴 escape 주석(`# does-not-raise-ok`)이 있으면 면제 — 정당한 루프 컨텍스트 진단 등."""
    src = (
        "def t():\n    for i in range(3):\n        try:\n            step(i)\n"
        "        except Exception as e:  # does-not-raise-ok: 반복 컨텍스트 진단\n"
        "            pytest.fail(f'step {i}: {e}')\n"
    )
    assert find_does_not_raise_wrappers(src) == []


def test_non_pytest_fail_attribute_is_not_flagged():
    """`something.fail()` 은 pytest.fail 이 아니므로 제외(정밀도 — 무관한 .fail 호출 오탐 방지)."""
    src = "def t():\n    try:\n        f()\n    except Exception:\n        client.fail('x')\n"
    assert find_does_not_raise_wrappers(src) == []


# --- 저장소 불변식 / repo invariant ------------------------------------------


def test_no_does_not_raise_wrapper_in_tests():
    """🔴 tests/ 전역에 broad-except pytest.fail wrapper 0건 (#1170 P1-⑤ 기계 집행).
    Zero broad-except pytest.fail wrappers across tests/ (mechanical enforcement of the #1170 rule)."""
    violations = []
    for path in _scoped_py_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        for lineno in find_does_not_raise_wrappers(source):
            violations.append(f"{path.relative_to(_ROOT).as_posix()}:{lineno}")
    if violations:
        pytest.fail(
            "does-not-raise wrapper (try/except+pytest.fail) 안티패턴:\n  "
            + "\n  ".join(violations)
            + "\n해결 / Fix: try/except+pytest.fail wrapper 를 제거하고 직접 호출하세요 "
            "— 예외가 나면 pytest 가 그대로 실패 보고합니다. 정당한 사용이면 "
            "`# does-not-raise-ok: <사유>` 주석으로 면제 (.claude/rules/testing.md 참조)."
        )
