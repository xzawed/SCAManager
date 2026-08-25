"""`import src.models` 는 테이블을 0건 등록한다 — 그 사실과, 그것에 기대는 코드를 막는다 (#1508).

🔴 왜 이 파일이 있는가 — 거짓 주석이 실제로 사람을 잘못 이끌었다.

`src/models/__init__.py` 는 **0 바이트**다. 하위 모듈을 아무것도 import 하지 않으므로
`import src.models` 는 `Base.metadata` 에 테이블을 **하나도** 등록하지 않는다(실측).
그런데 세 테스트가 그 줄에 이런 주석을 달고 있었다:

    import src.models  # noqa: F401  side-effect: populate Base.metadata

**그 부작용은 존재하지 않는다.** 테스트가 통과한 이유는 따로 있다 — 두 곳은 구체 모델
클래스를 직접 import 하고(`from src.models.repository import Repository` 등), 한 곳은
`from src.main import app` 이 전이적으로 전 모델을 끌어온다(실측: `src.main` 이 12건 등록,
`src.models` 는 0건).

🔴 **이 거짓이 CI red 로 이어졌다.** PR #1507 에서 새 테스트를 쓰며 이 줄을 그대로
베꼈다 — 주석을 믿었기 때문이다. `check_noqa_sideeffect` 가 그 `# noqa` 를 막았고,
대체 패턴을 절반만 적용하는 바람에 CodeQL `py/unused-global-variable`(alert #596)로
`Analyze (python)` 이 실패했다.

🔴 **이 가드는 관용구를 금지하지 않는다 — 조건부다.** 누군가 `src/models/__init__.py`
에 전 모델 import 를 넣으면 그 줄은 **참이 되고**, 아래 테스트는 자동으로 통과한다.
「지금 사실이 아닌 것에 기대지 마라」이지 「영원히 쓰지 마라」가 아니다.

The bare `import src.models` registers zero tables (empty `__init__.py`); three tests claimed
otherwise in comments and one such comment propagated into a CI failure. The guard is
conditional: if `src/models/__init__.py` ever registers tables, the idiom becomes legitimate
and this guard stops complaining on its own.
"""
from __future__ import annotations

import ast
import importlib
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_TESTS = _ROOT / "tests"


def _tables_registered_by(module_name: str) -> set[str]:
    """`module_name` 을 import 했을 때 `Base.metadata` 에 **새로** 생기는 테이블 이름."""
    from src.database import Base  # noqa: PLC0415

    before = set(Base.metadata.tables)
    importlib.import_module(module_name)
    return set(Base.metadata.tables) - before


def _bare_src_models_imports() -> list[str]:
    """`import src.models` (하위모듈 아님) 를 쓰는 테스트 파일 — AST 판정.

    🔴 문자열 탐색이 아니라 AST 다. `grep "import src.models"` 는
    `import src.models.repository` 같은 **정상** 하위모듈 import 까지 센다 —
    이 이슈를 등록할 때 내가 그 오판으로 27건이라고 적었고, 실제는 3건이었다.
    """
    hits: list[str] = []
    for f in sorted(_TESTS.rglob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - 구문 오류 파일은 별도 가드의 몫
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name == "src.models" for a in node.names):
                hits.append(f"{f.relative_to(_ROOT).as_posix()}:{node.lineno}")
    return hits


def test_ast_matcher_separates_bare_from_submodule_imports():
    """계기 자기검증 — 판정기가 두 형태를 실제로 가르는지 먼저 확인한다.

    가르지 못하면 아래 단언이 정상 코드를 잡거나(위양성) 결함을 놓친다(위음성).
    """
    bare = ast.parse("import src.models\n")
    sub = ast.parse("import src.models.repository\n")

    def _is_bare(tree: ast.AST) -> bool:
        return any(
            isinstance(n, ast.Import) and any(a.name == "src.models" for a in n.names)
            for n in ast.walk(tree)
        )

    assert _is_bare(bare), "bare import 를 못 잡았다 — 판정기 고장"
    assert not _is_bare(sub), "하위모듈 import 를 bare 로 오판했다 — 정상 코드를 막는다"


def test_src_models_package_registers_no_tables():
    """🔴 사실 고정 — `import src.models` 는 테이블을 0건 등록한다.

    이 단언이 red 가 되면 `src/models/__init__.py` 가 채워졌다는 뜻이고, 그때는
    「side-effect: populate Base.metadata」 주석이 **비로소 참**이 된다.
    이 파일의 docstring 과 아래 가드를 그 시점에 재검토하라.
    """
    assert not _tables_registered_by("src.models"), (
        "src.models 가 테이블을 등록하기 시작했다 — __init__.py 가 채워졌다. "
        "이 파일의 전제가 바뀌었으니 docstring 과 아래 가드를 재검토하라"
    )


def test_no_test_relies_on_the_bare_import_while_it_is_a_noop():
    """🔴 무동작인 동안에는 아무도 그것에 기대지 않는다 — **조건부** 가드.

    `src.models` 가 실제로 등록하게 되면 이 테스트는 스스로 통과한다.
    관용구 금지가 아니라 「지금 거짓인 것에 기대지 마라」다.
    """
    if _tables_registered_by("src.models"):  # pragma: no cover - 전제가 바뀐 미래
        return  # 이제 진짜 부작용이 있다 — 쓰는 것이 정당하다

    hits = _bare_src_models_imports()
    assert not hits, (
        "`import src.models` 는 테이블을 0건 등록한다(src/models/__init__.py 가 비어 있음). "
        "필요한 모델을 구체적으로 import 하라 — `from src.models.repository import Repository`. "
        f"해당 지점: {hits}"
    )
