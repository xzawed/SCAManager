"""alembic/env.py 가 전 ORM 모델 모듈을 import 하는지 검증하는 정적 완전성 가드.

Static completeness guard: assert alembic/env.py imports every ORM model module.

감사 migration-integrity-001 (2026-06-25): env.py 가 `target_metadata = Base.metadata` 를 쓰는데
11 ORM 모델 중 일부만 import 하면, autogenerate 가 미등록 테이블을 ORM 에 "없는" 것으로 보고
`op.drop_table()` 을 생성한다 → `make revision --autogenerate` 시 데이터 손실 함정.

The autogenerate path compares Base.metadata against the live DB; if env.py imports only a subset of
models, the unimported tables look "removed" and autogenerate emits destructive drop_table ops.

🔴 empty `__init__.py` 규칙 보존 (testing.md 사이클 115) — `src/models/__init__.py` 는 빈 파일 유지.
aggregate import 대신 env.py 가 모든 모델 모듈을 명시적으로 import 해 완전성을 확보한다.
The empty-__init__ convention is preserved; env.py imports each model module explicitly.
"""
import ast
import pathlib

# tests/unit/migrations/<this>.py → parents[3] = 레포 루트 / repo root
_ROOT = pathlib.Path(__file__).resolve().parents[3]
_ENV_PY = _ROOT / "alembic" / "env.py"
_MODELS_DIR = _ROOT / "src" / "models"


def _model_modules() -> set[str]:
    """src/models/ 의 ORM 모델 모듈명 집합 (__init__ 제외)."""
    # Set of ORM model module stems under src/models/ (excluding __init__).
    return {p.stem for p in _MODELS_DIR.glob("*.py") if p.stem != "__init__"}


def _env_imported_model_modules() -> set[str]:
    """alembic/env.py 가 import 하는 src.models.* 모듈명 집합 (AST 실측)."""
    # Module stems that env.py imports from src.models.* (measured via AST).
    tree = ast.parse(_ENV_PY.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.models."):
            imported.add(node.module.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src.models."):
                    imported.add(alias.name.split(".")[-1])
    return imported


def test_env_imports_every_orm_model_module():
    """env.py 가 모든 ORM 모델 모듈을 import 해야 autogenerate drop_table 함정이 차단된다."""
    models = _model_modules()
    # 모델 모듈이 실제로 존재함을 먼저 보장 (glob 빈 집합 시 vacuous pass 방지)
    # Guard against a vacuous pass if the glob returns nothing.
    assert len(models) >= 11, f"src/models/ 모델 모듈 수가 예상보다 적음: {sorted(models)}"
    missing = models - _env_imported_model_modules()
    assert not missing, (
        f"alembic/env.py 가 ORM 모델 모듈 {sorted(missing)} 를 import 하지 않음 — "
        "autogenerate(target_metadata=Base.metadata) 시 해당 테이블에 drop_table 생성 위험. "
        "env.py 상단에 `from src.models.<module> import <Model>  # noqa: F401` 추가 의무."
    )
