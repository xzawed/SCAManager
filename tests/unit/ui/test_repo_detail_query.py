"""repo_detail 분석 이력 쿼리 — source 파생 보존 + result blob 미로드 (준비도 감사 #6).

repo_detail analyses query — preserves source derivation while not loading the result blob.

## 왜

`repo_detail` 은 저장소당 최대 100건의 `Analysis` full ORM 을 로드했는데, result JSON blob
(file_feedbacks·ai_summary 등 최대 수백 KB)에서 **`source` 한 값만** 사용했다(나머지는 스칼라
컬럼). 저장소 상세 진입마다 100개 blob 을 역직렬화하는 낭비(감사 유일 CONFIRMED perf).

수정 = 컬럼-select + `result['source']` SQL JSON 추출(blob 미로드). 이 테스트는 그 최적화가
`source` 파생 동작을 정확히 보존하는지 봉인한다.

`source` = 저장된 `result["source"]` 우선, 없으면 `("pr" if pr_number else "push")` fallback.
JSON 추출은 양 방언 동등 검증됨 (SQLite JSON_EXTRACT / PG `->>`, 둘 다 따옴표 없는 텍스트).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "x")
os.environ.setdefault("GITHUB_TOKEN", "x")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1:x")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User  # noqa: F401 — FK 대상 테이블 등록 (create_all)
from src.ui.routes.detail import _load_repo_analyses


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed(db, **kwargs):
    repo = db.query(Repository).filter_by(full_name="o/r").first()
    if repo is None:
        repo = Repository(full_name="o/r")
        db.add(repo)
        db.commit()
    base = {"repo_id": repo.id, "commit_sha": "a" * 7, "score": 80, "grade": "B"}
    base.update(kwargs)
    a = Analysis(**base)
    db.add(a)
    db.commit()
    return repo.id


def test_source_uses_stored_result_value(db):
    """저장된 result['source'] 가 있으면 그 값을 쓴다 (fallback 보다 우선)."""
    repo_id = _seed(db, commit_sha="s1", pr_number=5, result={"source": "push", "ai_summary": "big"})
    rows = _load_repo_analyses(db, repo_id)
    assert rows[0]["source"] == "push", "저장된 source(push) 대신 pr_number fallback 이 적용됨"


def test_source_falls_back_to_pr_number_when_result_null(db):
    """result 가 NULL 이면 pr_number 기반 fallback (pr_number 有 → 'pr')."""
    repo_id = _seed(db, commit_sha="s2", pr_number=9, result=None)
    rows = _load_repo_analyses(db, repo_id)
    assert rows[0]["source"] == "pr"


def test_source_falls_back_to_push_when_no_pr_and_no_result(db):
    """result 없음 + pr_number 없음 → 'push'."""
    repo_id = _seed(db, commit_sha="s3", pr_number=None, result={})
    rows = _load_repo_analyses(db, repo_id)
    assert rows[0]["source"] == "push"


def test_returns_expected_scalar_fields(db):
    """반환 dict 는 템플릿이 요구하는 스칼라 필드를 포함한다."""
    repo_id = _seed(
        db, commit_sha="s4", pr_number=3, commit_message="fix bug",
        score=72, grade="C", result={"source": "pr"},
    )
    row = _load_repo_analyses(db, repo_id)[0]
    assert row["commit_sha"] == "s4"
    assert row["pr_number"] == 3
    assert row["commit_message"] == "fix bug"
    assert row["score"] == 72
    assert row["grade"] == "C"
    assert row["created_at"] is not None
    assert "id" in row


def test_ordered_desc_and_limited(db):
    """created_at desc 정렬 + limit 적용."""
    repo_id = None
    for i in range(3):
        repo_id = _seed(db, commit_sha=f"c{i}", score=60 + i)
    rows = _load_repo_analyses(db, repo_id, limit=2)
    assert len(rows) == 2, "limit 미적용"
    # 최신순 — 마지막 삽입(c2)이 먼저
    assert rows[0]["commit_sha"] == "c2"


def test_default_limit_is_100(db):
    """🔴 기본 limit=100 — repo_detail 이 저장소당 최대 100건만 로드한다 (route 계약).

    구 route 테스트 test_repo_detail_queries_limit_100 의 '100건' 계약을 헬퍼로 이관.
    """
    import inspect  # pylint: disable=import-outside-toplevel
    assert inspect.signature(_load_repo_analyses).parameters["limit"].default == 100
