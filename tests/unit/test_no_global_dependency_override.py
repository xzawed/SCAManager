"""테스트가 **임포트 시점에** 서로의 로그인 상태를 덮어쓴다 (#1551).

pytest 는 실행 전에 대상 모듈을 **전부 임포트**한다. 그래서 모듈 최상위에서
`app.dependency_overrides` 를 바꾸면 **나중에 임포트된 파일이 앞의 것을 조용히
덮어쓴다.** 실행 순서가 아니라 임포트 순서가 결과를 정한다.

## 실측 (2026-08-27, pytest 없이 재현)

    importlib.import_module("tests.unit.ui.test_feedback_routes")
    app.dependency_overrides[require_login]().id   ->  1

    importlib.import_module("tests.unit.api.test_users_api")
    app.dependency_overrides[require_login]().id   ->  42     🔴 덮어썼다

그 결과 `test_feedback_routes` 의 소유권 검증이 다른 사용자를 보고 404 를 낸다:

    pytest tests/unit/ui/test_feedback_routes.py tests/unit/api/test_users_api.py -p no:randomly
    -> 5 failed  (assert 404 == 200)

조합별(고정 순서): `tests/unit/ui` 단독 0건 · `ui + services` 0건 ·
**`ui + api` 6건** · `api + ui` 0건(그때는 feedback 이 나중에 임포트돼 이긴다).

## 🔴 왜 CI 가 이것을 못 잡나

`pytest tests/unit` **전량**으로 돌리면 마지막에 이기는 override 가 우연히 맞다. CI 도
전량으로 돈다 — 즉 **CI 초록이 이 축을 보증하지 않는다.** `pytest-randomly` 가 켜져
있어 파일이 하나 늘거나 줄면 순서가 바뀌고, **무관한 PR 이 이 6건을 빨갛게 만들 수
있다.** #1550 작업 중 실제로 그렇게 드러났다.

`origin/main` 을 별도 worktree 로 떠서 같은 조합·같은 고정 순서로 돌려 동일한 6건을
재현했으므로 선재이고 특정 PR 과 무관하다.

## 🔴 이 가드가 닫지 **않는** 것

`dependency_overrides` 는 공유 가변 상태 **하나**다. 같은 부류의 다른 문은 열려 있다
(Grok 01a0437a Q2): 임포트 시점의 `os.environ` 대입(`tests/conftest.py` 등), 분석기
`REGISTRY` 같은 프로세스 전역 레지스트리, 모듈 속성 몽키패치.

그것들까지 한 번에 닫지 않는 이유는 각각 정당한 용법이 섞여 있어(테스트 환경변수는
임포트 때 세워야 한다) 판정이 따로 필요하기 때문이다. **이 파일은 한 문만 닫는다** —
「전역 오염이 끝났다」고 읽으면 안 된다.

## 이 파일이 강제하는 것

「어느 테스트가 초록인가」가 **다른 파일의 임포트 순서**로 정해지면 그 초록은 검사
결과가 아니라 부작용이다. 모듈 최상위에서 전역을 바꾸지 않는다 — fixture 로 옮기면
각 테스트가 자기 것을 쓰고 끝나고 되돌린다.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import ast  # noqa: E402
import pathlib  # noqa: E402

import pytest  # noqa: E402

_ROOT = pathlib.Path(__file__).parents[2]
_SCANNED = ("tests", "e2e")

# 🔴 이 이름을 모듈 최상위에서 대입하면 다른 파일이 그것을 물려받는다.
#    fixture 안(함수 본문)은 안전하다 — 그 창이 테스트 하나로 닫힌다.
_GLOBAL_APP_STATE = "dependency_overrides"


_FUNCTION_LIKE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _runs_at_import(node: ast.AST):
    """🔴 임포트 때 **실제로 실행되는** 노드만 내놓는다.

    함수 본문은 정의만 되고 실행되지 않으므로 잘라낸다. 그 밖은 전부 실행된다 —
    클래스 본문도, `for`·`while`·`if`·`with`·`try` 도.

    이 함수가 있는 이유: 첫 판은 문장 **타입을 나열**했다(`Assign | Expr | AugAssign`
    와 `With | If | Try`). 그래서 helper 호출·`for`·`while`·클래스 본문·`setattr` 을
    전부 놓쳤다(실측 6종 중 5종). 열거는 열거 밖에서 눈이 먼다 — 「임포트 때 실행되는가」
    라는 성질로 바꾼다.

    Yield only nodes that actually execute at import: prune function bodies, keep the rest.
    """
    if isinstance(node, _FUNCTION_LIKE):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _runs_at_import(child)


def _touches_global_state(node: ast.AST) -> bool:
    """🔴 **구조**로 본다 — 속성 접근이거나, 이름을 문자열로 넘기는 반사 호출이거나.

    부분문자열(`ast.dump` 안에 이름이 있는가)은 상태를 대신하지 못한다 — 첫 판은 이
    파일의 docstring 과 상수까지 위반으로 잡았다. 반대로 속성 접근만 보면
    `setattr(app, "dependency_overrides", ...)` 를 놓친다.

    Attribute access, or the name passed as a string to a reflective call.
    """
    if isinstance(node, ast.Attribute) and node.attr == _GLOBAL_APP_STATE:
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("setattr", "getattr"):
        return any(isinstance(a, ast.Constant) and a.value == _GLOBAL_APP_STATE
                   for a in node.args)
    return False


def _mutating_local_functions(tree: ast.Module) -> set[str]:
    """🔴 모듈 최상위에서 부르면 임포트 때 전역이 바뀌는 함수 이름.

    `def _setup(): app.dependency_overrides[x] = 1` 뒤에 `_setup()` 을 두면 결과는
    직접 대입과 같다. 한 단계는 따라간다.
    """
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and any(_touches_global_state(n) for n in ast.walk(node))
    }


def _module_level_mutations(path: pathlib.Path) -> list[int]:
    """모듈 **임포트 시점에** 전역을 바꾸는 줄 번호 — 함수 본문 안은 세지 않는다."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    mutators = _mutating_local_functions(tree)
    lines: list[int] = []
    for node in tree.body:
        for inner in _runs_at_import(node):
            if _touches_global_state(inner):
                lines.append(getattr(inner, "lineno", node.lineno))
            elif isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) \
                    and inner.func.id in mutators:
                lines.append(getattr(inner, "lineno", node.lineno))
    return sorted(set(lines))


def _scan() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for top in _SCANNED:
        for path in sorted((_ROOT / top).rglob("*.py")):
            lines = _module_level_mutations(path)
            if lines:
                found[path.relative_to(_ROOT).as_posix()] = lines
    return found


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


# 🔴 임포트 때 전역이 바뀌는 **형태 전부**. 첫 판은 문장 타입을 나열해
#    6종 중 5종을 놓쳤다(Grok 01a0437a Q1) — 열거는 열거 밖에서 눈이 먼다.
_CAUGHT = {
    "직접 대입": "app.dependency_overrides[x] = 1\n",
    "helper 호출": "def _s():\n    app.dependency_overrides[x] = 1\n_s()\n",
    "for 루프": "for k in ks:\n    app.dependency_overrides[k] = 1\n",
    "while 루프": "while 0:\n    app.dependency_overrides[x] = 1\n",
    "클래스 본문": "class C:\n    app.dependency_overrides[x] = 1\n",
    "setattr": 'setattr(app, "dependency_overrides", {})\n',
    "getattr": 'getattr(app, "dependency_overrides").clear()\n',
}

# 반대쪽 — 여기까지 잡으면 정당한 코드를 벌하고 사람이 가드를 끈다.
_ALLOWED = {
    "fixture 안": ("import pytest\n@pytest.fixture(autouse=True)\n"
                 "def _o():\n    app.dependency_overrides[x] = 1\n    yield\n"),
    "문자열 언급": 'NAME = "dependency_overrides"\n',
    "클래스 메서드": "class C:\n    def m(self):\n        app.dependency_overrides[x] = 1\n",
}


@pytest.mark.parametrize("shape", sorted(_CAUGHT))
def test_the_scanner_catches_every_import_time_shape(tmp_path, shape):
    """🔴 임포트 때 실행되는 모든 형태를 잡는다 — 하나만 놓쳐도 그 길로 샌다."""
    sample = tmp_path / f"{shape}.py"
    sample.write_text(_CAUGHT[shape], encoding="utf-8")
    assert _module_level_mutations(sample), f"{shape} 을 놓쳤다"


@pytest.mark.parametrize("shape", sorted(_ALLOWED))
def test_the_scanner_leaves_safe_shapes_alone(tmp_path, shape):
    """반대쪽 — 함수 본문과 문자열은 임포트 때 실행되지 않는다."""
    sample = tmp_path / f"{shape}.py"
    sample.write_text(_ALLOWED[shape], encoding="utf-8")
    assert _module_level_mutations(sample) == [], f"{shape} 까지 잡는다 — 과탐이다"


def test_a_string_mention_is_not_a_violation(tmp_path):
    """🔴 이 파일 자신이 그 이름을 문자열로 여러 번 쓴다 — 부분문자열 판정이면 자폭한다.

    첫 판이 실제로 자기 자신을 잡았다(docstring 1줄 + 상수 1줄).
    """
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""dependency_overrides 를 설명하는 docstring."""\n'
        'NAME = "dependency_overrides"\n', encoding="utf-8")
    assert _module_level_mutations(sample) == [], "문자열 언급을 위반으로 잡는다"


def test_the_guard_file_itself_is_clean():
    """이 파일이 자기 규칙을 지키는지 — 가드가 자기를 어기면 아무도 안 믿는다."""
    assert _module_level_mutations(pathlib.Path(__file__)) == []


def test_the_scan_covers_the_test_tree():
    """스캔 경로가 어긋나면 0건이 나오고, 그 0 은 「통과」가 아니라 「안 쟀음」이다."""
    for top in _SCANNED:
        assert (_ROOT / top).is_dir(), f"{top}/ 가 없다 — 스캔 경로가 늙었다"
    assert len(list((_ROOT / "tests").rglob("*.py"))) > 100, "테스트 트리를 못 찾았다"


# ─── 본체 ────────────────────────────────────────────────────────────────────


def test_no_test_module_mutates_the_app_at_import_time():
    """🔴 모듈 최상위에서 전역을 바꾸면 **나중에 임포트된 파일이 이긴다**.

    그러면 「어느 테스트가 초록인가」가 다른 파일의 임포트 순서로 정해진다.
    fixture 로 옮기면 각 테스트가 자기 것을 쓰고 끝나고 되돌린다.
    """
    offenders = _scan()
    assert not offenders, (
        "임포트 시점에 app.dependency_overrides 를 바꾼다 — fixture 로 옮겨라:\n"
        + "\n".join(f"  {path}: 줄 {lines}" for path, lines in sorted(offenders.items()))
    )


def test_importing_two_login_using_modules_leaves_the_app_alone():
    """🔴 실측으로 충돌했던 그 두 모듈을 임포트해도 앱 전역이 그대로여야 한다.

    이것이 결함의 본체다 — `id=1` 이 `id=42` 로 덮여 소유권 검증이 404 를 냈다.
    """
    import importlib  # noqa: PLC0415

    from src.main import app  # noqa: PLC0415

    before = dict(app.dependency_overrides)
    importlib.import_module("tests.unit.ui.test_feedback_routes")
    importlib.import_module("tests.unit.api.test_users_api")
    assert app.dependency_overrides == before, (
        "테스트 모듈 임포트가 앱 전역을 바꿨다 — 다음 모듈이 그것을 물려받는다"
    )
