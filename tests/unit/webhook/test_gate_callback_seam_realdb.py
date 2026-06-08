"""handle_gate_callback seam 실DB 테스트 (사이클 165 회고 testing P1-2).

claim_decision 을 patch 하지 않고 **실 in-memory DB**(StaticPool 공유 연결)로 콜백을 실행해,
호출 심볼 리네임(save_gate_decision→claim_decision 류) 시 fail-fast 를 보장한다. MagicMock DB 가
아닌 실 세션을 쓰므로 patch-target staleness 에 면역 — 콜백 seam 의 결정 claim 이 실제로 영속되는지
(첫 호출)와 리플레이 skip(둘째 호출, 결정 뒤집기 차단)을 검증한다.

real-DB test using a shared StaticPool in-memory engine so the callback runs the REAL claim_decision —
immune to stale patch targets; a symbol rename breaks the import and fails this test fast.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config_manager.manager import RepoConfigData
from src.database import Base
from src.models.analysis import Analysis  # noqa: F401 — create_all 테이블 등록
from src.models.gate_decision import GateDecision  # noqa: F401
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401


@pytest.fixture
def real_session_factory():
    """공유 연결(StaticPool) in-memory SQLite — 여러 세션이 동일 DB 를 본다.

    handle_gate_callback 이 자체 `with SessionLocal() as db:` 로 새 세션을 열기 때문에,
    기본 in-memory(연결별 별도 DB) 대신 StaticPool 로 단일 연결을 공유해야 seed 가 보인다.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _seed(factory) -> int:
    """User(telegram 연동) + Repository(소유자=User) + Analysis(pr_number 有) 시드 — analysis.id 반환."""
    with factory() as db:
        user = User(
            github_id="gh999", email="seam@test.com", display_name="Seam Tester",
            telegram_user_id="999", preferred_language="en",
        )
        db.add(user)
        db.flush()
        repo = Repository(full_name="owner/seam", user_id=user.id)
        db.add(repo)
        db.flush()
        analysis = Analysis(
            repo_id=repo.id, commit_sha="seamsha", pr_number=5,
            score=85, grade="B", result={"score": 85},
        )
        db.add(analysis)
        db.commit()
        return analysis.id


async def test_handle_gate_callback_real_db_claims_then_replay_skips(real_session_factory):
    """첫 콜백 = claim 실제 실행 → GateDecision 영속 + 리뷰 게시 / 둘째(리플레이) = claim False → skip.

    claim_decision 을 patch 하지 않으므로(실 DB 실행), 콜백 seam 이 claim_decision 을 실제로 호출·
    영속하는지 검증한다 — 심볼 리네임 시 import/실행 단계에서 즉시 fail.
    """
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    analysis_id = _seed(real_session_factory)
    config = RepoConfigData(repo_full_name="owner/seam", auto_merge=False)

    with patch("src.webhook.providers.telegram.SessionLocal", real_session_factory), \
         patch("src.webhook.providers.telegram.get_repo_config", return_value=config), \
         patch("src.webhook.providers.telegram.post_github_review",
               new_callable=AsyncMock) as mock_review:
        # 1차: claim 성공(first-writer) → 리뷰 게시 + GateDecision 실제 영속
        await handle_gate_callback(
            analysis_id=analysis_id, decision="approve",
            decided_by="tester", telegram_user_id="999",
        )
        assert mock_review.await_count == 1
        with real_session_factory() as db:
            assert db.query(GateDecision).filter_by(analysis_id=analysis_id).count() == 1

        # 2차(리플레이, 다른 결정으로 뒤집기 시도): claim False → 부수효과 skip
        await handle_gate_callback(
            analysis_id=analysis_id, decision="reject",
            decided_by="tester", telegram_user_id="999",
        )
        assert mock_review.await_count == 1  # 재게시 없음 (리플레이 차단)
        with real_session_factory() as db:
            rows = db.query(GateDecision).filter_by(analysis_id=analysis_id).all()
            assert len(rows) == 1                    # 중복 INSERT 없음
            assert rows[0].decision == "approve"     # 최초 결정 보존 (뒤집기 차단)
