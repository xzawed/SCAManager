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
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_TESTS = _ROOT / "tests"


def _package_can_register() -> bool:
    """`src/models/__init__.py` 가 무언가를 등록할 **수** 있는가 — 정적 판정.

    🔴 **import-diff 로 재면 안 된다.** 첫 판을 그렇게 짰다가 공허해졌다:
    `importlib.import_module` 은 `sys.modules` 캐시를 반환하므로 **모듈을 재실행하지
    않는다.** 테스트 프로세스에서는 `src.models` 가 이미 import 된 뒤라 diff 가
    **항상 0건**이고, `__init__.py` 에 무엇을 넣든 통과한다(실측 확인). 즉 조건부
    분기가 영영 안 타고 사실-고정은 거짓 초록이 된다.

    그래서 **파일을 읽어** 판정한다. import 문도 호출식도 없는 모듈은 어떤 부작용도
    낼 수 없다 — 0 바이트 파일이 그 극단이다.

    Do NOT measure this with an import diff: import_module returns the cached module and
    never re-executes it, so the diff is always empty and the guard passes vacuously.
    """
    init = _ROOT / "src" / "models" / "__init__.py"
    assert init.exists(), "src/models/__init__.py 가 없다 — 스캐너 점검 필요"
    tree = ast.parse(init.read_text(encoding="utf-8"))
    return any(
        isinstance(n, (ast.Import, ast.ImportFrom, ast.Call))
        for n in ast.walk(tree)
    )


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


def test_src_models_package_is_import_free():
    """🔴 사실 고정 — `src/models/__init__.py` 는 아무 부작용도 낼 수 없다.

    이 단언이 red 가 되면 `__init__.py` 가 채워졌다는 뜻이고, 그때는
    「side-effect: populate Base.metadata」 주석이 **비로소 참**이 될 수 있다.
    이 파일의 docstring 과 아래 가드를 그 시점에 재검토하라.
    """
    assert not _package_can_register(), (
        "src/models/__init__.py 에 import/호출이 생겼다 — bare `import src.models` 가 "
        "부작용을 낼 수 있게 됐다. 이 파일의 전제가 바뀌었으니 재검토하라"
    )


def test_subprocess_confirms_the_bare_import_registers_nothing():
    """🔴 정적 판정을 **실물로** 교차 확인 — 캐시 없는 새 인터프리터에서 잰다.

    위 테스트는 파일을 읽어 판정한다(정적). 여기서는 새 프로세스를 띄워 실제로
    `import src.models` 만 하고 `Base.metadata` 에 몇 개가 생기는지 센다.
    두 축이 어긋나면 둘 중 하나가 거짓말하는 것이다.
    """
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    # 🔴 **센티널로 감싸 출력한다.** 첫 판은 마지막 줄을 int() 했는데, CI 는
    #   `--cov=src`(ci.yml:503)로 돌아 coverage 의 sitecustomize/pth 가 자식 프로세스에
    #   붙는다 — 접미 노이즈 한 줄이면 int() 가 터지고, 이 테스트가 **재려는 사실과
    #   무관한 이유로** red 가 된다. 아래에서 coverage 환경변수도 함께 제거한다.
    #   Sentinel-wrapped output: CI runs with --cov, whose child hooks can append noise.
    code = (
        "import src.models;"
        "from src.database import Base;"
        "print('<<TABLES:%d>>' % len(Base.metadata.tables))"
    )
    env = dict(os.environ)
    env.setdefault("DATABASE_URL", "sqlite:///:memory:")
    env.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
    env.setdefault("GITHUB_TOKEN", "ghp_test")
    env.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
    env.setdefault("TELEGRAM_CHAT_ID", "-100123")
    env.setdefault("ANTHROPIC_API_KEY", "")
    env["PYTHONIOENCODING"] = "utf-8"
    # coverage 가 자식에 붙지 않게 한다 — 이 테스트는 커버리지 대상이 아니다.
    for k in ("COV_CORE_SOURCE", "COV_CORE_CONFIG", "COV_CORE_DATAFILE", "COVERAGE_PROCESS_START"):
        env.pop(k, None)

    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=_ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert proc.returncode == 0, (
        "서브프로세스가 실패했다 — 이 테스트의 **계기**가 고장난 것이지 사실이 바뀐 것이 아니다. "
        f"stdout={proc.stdout[-300:]!r} stderr={proc.stderr[-400:]!r}"
    )
    found = re.findall(r"<<TABLES:(\d+)>>", proc.stdout)
    assert len(found) == 1, (
        "센티널을 찾지 못했다 — 계기 고장(자식 출력 오염). "
        f"stdout={proc.stdout[-300:]!r} stderr={proc.stderr[-400:]!r}"
    )
    counted = int(found[0])
    assert counted == 0, (
        f"새 인터프리터에서 `import src.models` 가 {counted}개 테이블을 등록했다 — "
        "정적 판정과 어긋난다"
    )


def test_no_test_relies_on_the_bare_import_while_it_is_a_noop():
    """🔴 무동작인 동안에는 아무도 그것에 기대지 않는다 — **조건부** 가드.

    `src.models` 가 실제로 등록하게 되면 이 테스트는 스스로 통과한다.
    관용구 금지가 아니라 「지금 거짓인 것에 기대지 마라」다.
    """
    if _package_can_register():  # pragma: no cover - 전제가 바뀐 미래
        return  # 이제 진짜 부작용이 있을 수 있다 — 쓰는 것이 정당하다

    hits = _bare_src_models_imports()
    assert not hits, (
        "`import src.models` 는 테이블을 0건 등록한다(src/models/__init__.py 가 비어 있음). "
        "필요한 모델을 구체적으로 import 하라 — `from src.models.repository import Repository`. "
        f"해당 지점: {hits}"
    )
