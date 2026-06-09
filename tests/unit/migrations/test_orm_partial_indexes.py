"""정합성 감사 #18 drift ③④' — ORM 부분 인덱스 선언 회귀 가드.

정합성 감사 full(2026-06-08) #18 가드 발견 drift ③④' — alembic 이 생성한 부분 인덱스를
ORM `__table_args__` 가 미선언 → ORM↔alembic compare_metadata drift.
- ③ analyses `ix_analyses_repo_id_created_at_tokens` (0032, WHERE input_tokens IS NOT NULL)
- ④' insight_cache `uq_insight_cache_global`/`uq_insight_cache_repo` (0031, 부분 UNIQUE)

본 테스트는 ORM 측 선언(부분 WHERE + 양 방언)이 유지되는지 검증 (compare_metadata PG 가드 페어).
WHERE 절 누락 시 SQLite 가 전체 유니크 인덱스를 만들어 전역+리포 캐시 공존이 깨진다.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from src.models.analysis import Analysis
from src.models.insight_narrative_cache import InsightNarrativeCache


def _index(table, name):
    for ix in table.indexes:
        if ix.name == name:
            return ix
    return None


def _where_str(ix, dialect):
    """Index 의 방언별 부분 WHERE 술어 문자열 반환 (미설정 시 None).

    text() 로 선언한 WHERE 는 str() 가 원문 술어를 그대로 반환 — 술어 정확 비교로
    술어 뒤바뀜/오타(예: global↔repo NULL 술어 swap)를 차단 (Codex mutual 강화).
    """
    where = ix.dialect_options[dialect].get("where")
    return None if where is None else str(where)


def test_analyses_tokens_partial_index_declared():
    """analyses ix_analyses_repo_id_created_at_tokens 부분 인덱스 ORM 선언 (#18 drift ③)."""
    ix = _index(Analysis.__table__, "ix_analyses_repo_id_created_at_tokens")
    assert ix is not None, "ix_analyses_repo_id_created_at_tokens ORM 미선언 (#18 drift ③ 회귀)"
    assert [c.name for c in ix.columns] == ["repo_id", "created_at"]
    # 부분 WHERE 술어 정확 비교 — 양 방언 (PG compare_metadata 정합 + SQLite 부분 인덱스)
    assert _where_str(ix, "postgresql") == "input_tokens IS NOT NULL", "postgresql_where 술어 불일치"
    assert _where_str(ix, "sqlite") == "input_tokens IS NOT NULL", "sqlite_where 술어 불일치"


def test_insight_cache_partial_unique_indexes_declared():
    """insight_cache uq_insight_cache_global/repo 부분 유니크 인덱스 ORM 선언 (#18 drift ④')."""
    tbl = InsightNarrativeCache.__table__
    glob = _index(tbl, "uq_insight_cache_global")
    repo = _index(tbl, "uq_insight_cache_repo")
    assert glob is not None and repo is not None, "부분 유니크 인덱스 ORM 미선언 (#18 drift ④' 회귀)"
    # 유니크 + 부분 WHERE 술어 정확 비교 — 전역(repo_id IS NULL) / 리포별(repo_id IS NOT NULL).
    # 술어 정확 비교로 global↔repo NULL 술어 뒤바뀜 차단 (Codex mutual 강화).
    assert glob.unique and repo.unique, "부분 인덱스가 unique 가 아님 — 캐시 키 무결성 위반"
    assert [c.name for c in glob.columns] == ["user_id", "days", "language"]
    assert [c.name for c in repo.columns] == ["user_id", "days", "language", "repo_id"]
    for dialect in ("postgresql", "sqlite"):
        assert _where_str(glob, dialect) == "repo_id IS NULL", (
            f"uq_insight_cache_global {dialect}_where 술어 불일치 (전역=repo_id IS NULL)"
        )
        assert _where_str(repo, dialect) == "repo_id IS NOT NULL", (
            f"uq_insight_cache_repo {dialect}_where 술어 불일치 (리포별=repo_id IS NOT NULL)"
        )
