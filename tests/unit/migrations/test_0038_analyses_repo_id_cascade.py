"""정합성 감사 P2 #14 — analyses.repo_id ON DELETE CASCADE 회귀 가드.

정합성 감사 full(2026-06-08) P2 #14 — `analyses.repo_id` → repositories.id FK 가
ondelete 미설정. repositories → analyses 삭제 사슬에 DB 레벨 안전망 부재.
repo_id 는 NOT NULL 이라 CASCADE (SET NULL 불가) — db.md FK 매트릭스 정합.

본 테스트는 ORM 정의 측 `ondelete="CASCADE"` 가 유지되는지 검증 (alembic 0038 페어).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from src.models.analysis import Analysis


def test_analyses_repo_id_fk_has_cascade_delete():
    """Analysis.repo_id FK 의 ondelete 가 CASCADE 인지 검증 (#14).

    repositories → analyses 삭제 사슬 DB 레벨 안전망. 미설정 시 repo 삭제 →
    FK violation 또는 고아 행 (application delete_repo_cascade 우회 경로 보완).
    Child 4종(MergeAttempt/MergeRetryQueue/AnalysisFeedback/GateDecision) CASCADE 와 일관.
    """
    fk_columns = list(Analysis.__table__.c.repo_id.foreign_keys)
    assert len(fk_columns) == 1, "repo_id 에 FK 가 정확히 1개 있어야 함"
    fk = fk_columns[0]
    assert fk.ondelete == "CASCADE", (
        f"analyses.repo_id FK ondelete='{fk.ondelete}' — "
        "'CASCADE' 이어야 함 (#14 회귀)"
    )
