"""리포마다 고르는 리뷰 effort — 저장 · 검증 · 폼 보존 · 리뷰 호출까지 (Issue #1905 ③a · 사용자 11-22 «A안을 승인합니다.»).

Per-repo review effort: storage, validation, form preservation and the review call.
비우면 운영 변수(`CLAUDE_CALL_EFFORT`, 기본 high)를 쓴다 — 화면이 고르는 단계는 low · medium · high 셋.
Blank falls back to CLAUDE_CALL_EFFORT (default high); the screen offers low, medium and high.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import src.worker.pipeline as pipeline  # noqa: E402
from src.api.repos import RepoConfigUpdate  # noqa: E402
from src.config_manager.manager import RepoConfigData, get_repo_config, upsert_repo_config  # noqa: E402
from src.database import Base  # noqa: E402
from src.github_client.diff import ChangedFile  # noqa: E402
from src.models.repo_config import RepoConfig  # noqa: E402

_TABLE_MODELS = (RepoConfig,)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")


@pytest.mark.parametrize(("sent", "stored"), [
    ("low", "low"), ("medium", "medium"), ("high", "high"), ("HIGH", "high"), ("", None), ("  ", None), (None, None),
])
def test_review_effort_takes_the_three_levels_or_blank(sent, stored):
    assert RepoConfigUpdate(review_effort=sent).review_effort == stored


# witness-corpus: 화면이 고르지 않는 값 — SDK 에는 있는 단계(max · xhigh) · 모르는 낱말 · 숫자 · 오타
@pytest.mark.parametrize("sent", ["max", "xhigh", "turbo", "1", "hihg"])
def test_review_effort_rejects_other_values(sent):
    with pytest.raises(ValidationError):
        RepoConfigUpdate(review_effort=sent)


@pytest.fixture(name="db")
def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_review_effort_round_trips_through_the_store(db):
    upsert_repo_config(db, RepoConfigData(repo_full_name="o/effort", review_effort="low"))
    assert get_repo_config(db, "o/effort").review_effort == "low"


def test_the_settings_form_keeps_a_stored_review_effort(db):
    # 화면에 칸이 생기기 전(③b)까지 폼은 이 값을 보내지 않는다 — 저장할 때마다 지워지면 안 된다
    # Until the screen has the field (③b) the form never posts it; a save must not wipe it.
    from src.ui.routes.settings import build_repo_config_from_form  # pylint: disable=import-outside-toplevel

    upsert_repo_config(db, RepoConfigData(repo_full_name="o/effort", review_effort="medium"))
    rebuilt = build_repo_config_from_form(db, "o/effort", {"approve_mode": "disabled"})
    assert rebuilt.review_effort == "medium"


_SHA = f"{1:040x}"
_PUSH = {"repository": {"full_name": "owner/repo"}, "after": _SHA, "head_commit": {"id": _SHA, "message": "p0"}}


async def _save_and_gate(_db, _params):
    return MagicMock(), 1, {"score": 80}


async def _send(_tasks, _names):
    return None


@pytest.mark.parametrize("stored", ["low", None])
async def test_the_repo_review_effort_reaches_the_review_call(stored):
    review = AsyncMock(return_value=MagicMock())
    with (
        patch("src.worker.pipeline.SessionLocal") as session_cls,
        patch("src.worker.pipeline._ensure_repo", return_value=(MagicMock(id=1), "tok")),
        patch("src.worker.pipeline._begin_attempt"),
        patch("src.worker.pipeline._finish_attempt"),
        patch("src.worker.pipeline._collect_files", return_value=[ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]),
        patch("src.worker.pipeline._resolve_review_language", return_value="en"),
        patch("src.worker.pipeline.get_repo_config",
              return_value=MagicMock(review_model=None, review_effort=stored, ai_review_enabled=True)),
        patch("src.worker.pipeline._run_static_with_timeout", new_callable=AsyncMock, return_value=([], False)),
        patch("src.worker.pipeline.review_code", review),
        patch("src.worker.pipeline.calculate_score", return_value=MagicMock(total=80)),
        patch("src.worker.pipeline._save_and_gate", side_effect=_save_and_gate),
        patch("src.worker.pipeline.build_notification_tasks", return_value=([], [_SHA])),
        patch("src.worker.pipeline._send_notifications", side_effect=_send),
    ):
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        session_cls.return_value = session
        await pipeline.run_analysis_pipeline("push", _PUSH)
    assert review.await_args.kwargs["effort"] == stored
