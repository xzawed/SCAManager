"""alembic/env.py 가 MIGRATION_DATABASE_URL 게이트를 사용하는지 잠그는 회귀 가드.
Regression guard locking alembic/env.py to the MIGRATION_DATABASE_URL gate.

RLS Phase 4 에서 DATABASE_URL 이 비-BYPASSRLS app role(`scamanager_app`)로 바뀌면,
env.py:30 이 `settings.database_url` 로 마이그레이션을 돌릴 경우 pre-deploy/lifespan
`alembic upgrade head` 가 app role 로 실행 → `alembic_version`(relrowsecurity=true·policy 0건
= default-deny) 차단 → 배포 실패. 따라서 env.py 는 `settings.effective_migration_url`
(= MIGRATION_DATABASE_URL or DATABASE_URL)을 sqlalchemy.url 로 사용해야 한다.
이 가드는 누군가 무심코 `settings.database_url` 로 되돌려 Phase 4 게이트를 무력화하는
회귀를 정적으로 차단한다.

In RLS Phase 4, DATABASE_URL switches to the non-BYPASSRLS app role; if env.py used
`settings.database_url` for migrations, the pre-deploy/lifespan `alembic upgrade head`
would run as the app role and hit `alembic_version` default-deny → deploy failure.
env.py must therefore use `settings.effective_migration_url` (MIGRATION_DATABASE_URL or
DATABASE_URL). This guard statically blocks a regression back to `settings.database_url`.

절차: docs/runbooks/rls-role-separation.md §6 마이그레이션 credential 게이트.
"""
import ast
import pathlib

_ENV_PY = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "env.py"


def _is_sqlalchemy_url_arg(arg: ast.AST) -> bool:
    """첫 인자가 리터럴 "sqlalchemy.url" 또는 상수 `_SQLALCHEMY_URL` 인지 판정."""
    if isinstance(arg, ast.Constant) and arg.value == "sqlalchemy.url":
        return True
    return isinstance(arg, ast.Name) and arg.id == "_SQLALCHEMY_URL"


def _set_main_option_url_arg() -> ast.AST:
    """env.py 의 `config.set_main_option(<url-key>, <arg>)` 호출의 <arg> AST 를 반환."""
    tree = ast.parse(_ENV_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "set_main_option"):
            continue
        # 첫 인자가 sqlalchemy.url 키(리터럴 또는 상수)인 호출만
        if node.args and _is_sqlalchemy_url_arg(node.args[0]):
            assert len(node.args) >= 2, "set_main_option(sqlalchemy.url, ...) 두 번째 인자 필요"
            return node.args[1]
    # 호출을 못 찾으면 명시적 raise — 함수 끝 fall-through(암묵 None) 제거로 py/mixed-returns 해소.
    # Explicit raise when not found — removes the implicit-None fall-through (resolves py/mixed-returns).
    raise AssertionError("alembic/env.py 에서 set_main_option(sqlalchemy.url, ...) 호출을 찾지 못함")


def test_env_uses_effective_migration_url():
    """env.py 가 sqlalchemy.url 을 settings.effective_migration_url 로 설정해야 한다."""
    arg = _set_main_option_url_arg()
    src = ast.unparse(arg)
    assert "effective_migration_url" in src, (
        "alembic/env.py 는 sqlalchemy.url 을 settings.effective_migration_url 로 설정해야 한다 "
        f"(현재: {src}). RLS Phase 4 마이그레이션 credential 게이트 회귀."
    )


def test_env_does_not_use_database_url_directly():
    """env.py 가 sqlalchemy.url 인자로 settings.database_url 을 직접 쓰면 안 된다 (Phase 4 게이트 무력화)."""
    arg = _set_main_option_url_arg()
    src = ast.unparse(arg)
    assert "database_url" not in src, (
        "alembic/env.py 가 sqlalchemy.url 을 settings.database_url 로 직접 설정 — "
        "RLS Phase 4 에서 app role 마이그레이션 → alembic_version default-deny 차단. "
        "settings.effective_migration_url 사용 필수."
    )
