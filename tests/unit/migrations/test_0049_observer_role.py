"""0049 관측 역할 — 허용 목록에 비밀값 · 개인정보 · 사용자 내용 컬럼이 없다 (정적 · PG 불필요).
0049 observer role: the allowlist holds no secret, personal or user-authored column (static; no PostgreSQL).

권한이 실제로 그렇게 걸리는지는 tests/integration/test_observer_role_postgres.py 가 실 PG 로 잰다.
여기서는 허용 목록 자체를 본다 — 마이그레이션을 import 하지 않고 구문 트리에서 리터럴로 읽는다.
Whether the grants really apply is measured on real PG elsewhere; this reads the allowlist literal from the syntax tree.
"""
import importlib
from pathlib import Path

import pytest

from src.database import Base
from tests.unit.migrations._migration_source import later_observer_grants, module_constants

_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION = _ROOT / "alembic" / "versions" / "0049_observer_role.py"

# 모델 모듈을 하나씩 불러야 Base.metadata 에 테이블이 다 올라온다(`src/models/__init__.py` 는 비어 있다)
# Import each model module to fill Base.metadata (the package __init__ registers nothing).
for _path in sorted((_ROOT / "src" / "models").glob("*.py")):
    if _path.stem != "__init__":
        importlib.import_module(f"src.models.{_path.stem}")

# 뺀 컬럼과 그 까닭 — 허용 목록과 겹치면 안 된다 / excluded columns by reason; must not meet the allowlist
_EXCLUDED = {
    # 비밀값 / secrets
    ("users", "github_access_token"), ("users", "telegram_otp"), ("repositories", "webhook_secret"),
    ("repo_configs", "hook_token"), ("repo_configs", "railway_webhook_token"), ("repo_configs", "railway_api_token"),
    ("repo_configs", "n8n_webhook_url"), ("repo_configs", "discord_webhook_url"),
    ("repo_configs", "slack_webhook_url"), ("repo_configs", "custom_webhook_url"),
    ("merge_retry_queue", "claim_token"),
    # 개인정보 / personal data
    ("users", "github_id"), ("users", "github_login"), ("users", "email"), ("users", "display_name"),
    ("users", "telegram_user_id"), ("users", "telegram_otp_expires_at"), ("repositories", "telegram_chat_id"),
    ("repo_configs", "email_recipients"), ("repo_configs", "notify_chat_id"), ("merge_retry_queue", "notify_chat_id"),
    ("analyses", "author_login"), ("gate_decisions", "decided_by"),
    # 사용자 내용 / user-authored content
    ("analyses", "commit_message"), ("analyses", "result"), ("analysis_feedbacks", "comment"),
    ("insight_narrative_cache", "response_json"), ("security_alert_process_logs", "ai_reason"),
}


def _allowed() -> set[tuple[str, str]]:
    constants = module_constants(_MIGRATION)
    assert "_ALLOWED" in constants, "허용 목록을 리터럴로 못 읽었다 — 못 재면 red / _ALLOWED is not a literal"
    allowed = {(table, column) for table, columns in constants["_ALLOWED"].items() for column in columns}
    assert allowed, "허용 목록이 비었다 / empty allowlist"
    # 뒤 revision 이 더 준 컬럼(0051 · 0053 …)도 같은 검사를 받는다 / later grants face the same checks
    return allowed | later_observer_grants(_ROOT / "alembic" / "versions")


def _leaks(allowed: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return allowed & _EXCLUDED


def test_allowlist_holds_no_excluded_column():
    assert _leaks(_allowed()) == set()


@pytest.mark.parametrize("planted", [("users", "email"), ("repo_configs", "railway_api_token")])
def test_the_check_catches_a_planted_column(planted):
    """계기 뒤집기 — 뺀 컬럼을 하나 심으면 잡는다 / flip: a planted excluded column is caught."""
    assert _leaks(_allowed() | {planted}) == {planted}


def test_excluded_columns_are_real():
    """뺀 목록이 실제 컬럼을 가리킨다 — 철자가 틀리면 이 검사는 빈 손으로 초록이 된다.
    Every excluded entry names a real ORM column; a typo would make the check pass empty-handed."""
    orm = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns}
    assert _EXCLUDED - orm == set()


def test_allowlisted_tables_exist():
    """허용 목록의 테이블은 ORM 테이블이거나 alembic_version 이다 / allowlisted tables exist."""
    orm_tables = set(Base.metadata.tables) | {"alembic_version"}
    assert {table for table, _column in _allowed()} - orm_tables == set()


def _observed_columns(allowed: set[tuple[str, str]]) -> set[tuple[str, str]]:
    tables = {table for table, _column in allowed}
    return {(t.name, c.name) for t in Base.metadata.tables.values() if t.name in tables for c in t.columns}


def _unclassified(allowed: set[tuple[str, str]], observed: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return observed - allowed - _EXCLUDED


def test_every_observed_column_is_granted_or_excluded():
    """관측 표의 컬럼은 허용(0049 + 뒤 revision 의 `_ADDED_GRANTS`)이거나 뺀 목록이다.

    컬럼 단위 GRANT 라 새 컬럼은 저절로 보이지 않는다(0051) — 비밀값이 아니면 그 컬럼을 더하는 revision 이
    GRANT 하고, 비밀값 · 개인정보 · 사용자 내용이면 `_EXCLUDED` 에 둔다. 둘 다 아니면 운영 확인이 그 컬럼을 못 읽는다.
    Every column of an observed table is granted or excluded; column grants never cover a new column by themselves.
    """
    allowed = _allowed()
    observed = _observed_columns(allowed)
    assert observed, "관측 표의 ORM 컬럼을 못 읽었다 — 못 재면 red / no observed column read"
    assert _unclassified(allowed, observed) == set()


@pytest.mark.parametrize("planted", [("repo_configs", "planted_setting"), ("analyses", "planted_flag")])
def test_the_coverage_check_catches_a_planted_column(planted):
    """계기 뒤집기 — 분류되지 않은 컬럼을 심으면 잡는다 / flip: a planted unclassified column is caught."""
    allowed = _allowed()
    assert _unclassified(allowed, _observed_columns(allowed) | {planted}) == {planted}
