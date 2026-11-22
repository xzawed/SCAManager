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
_NOT_A_UI_LEVEL = ["max", "xhigh", "turbo", "1", "hihg"]


@pytest.mark.parametrize("sent", _NOT_A_UI_LEVEL)
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


def test_the_settings_form_posts_the_review_effort(db):
    # 설정 화면의 effort 칸(③b) — 고른 단계를 보내고, 빈 값은 운영 변수로 되돌린다
    # The settings screen's effort field posts the chosen level; blank goes back to the global setting.
    from src.ui.routes.settings import build_repo_config_from_form  # pylint: disable=import-outside-toplevel

    upsert_repo_config(db, RepoConfigData(repo_full_name="o/effort", review_effort="medium"))
    assert build_repo_config_from_form(db, "o/effort", {"review_effort": "low"}).review_effort == "low"
    assert build_repo_config_from_form(db, "o/effort", {"review_effort": ""}).review_effort is None


# witness-corpus: 저장 관문이 받지 않는 effort — 모르는 낱말 · 띄어 쓴 단계 · 번역어 · 숫자 단계
_NOT_AN_EFFORT = ["extreme", "lo w", "중간", "2"]


@pytest.mark.parametrize("sent", [*_NOT_AN_EFFORT, "max", "xhigh"])
def test_the_store_refuses_other_effort_values(db, sent):
    # 폼 · API 가 함께 지나는 관문 — 폼이 고르지 않은 값을 보내도 저장되지 않는다
    # The gate both the form and the API pass: a value the screen does not offer is never stored.
    with pytest.raises(ValueError):
        upsert_repo_config(db, RepoConfigData(repo_full_name="o/e", review_effort=sent))
    assert get_repo_config(db, "o/e").review_effort is None


def test_the_store_folds_case_and_spaces(db):
    upsert_repo_config(db, RepoConfigData(repo_full_name="o/e", review_effort=" HIGH "))
    assert get_repo_config(db, "o/e").review_effort == "high"


def test_an_unchanged_stored_effort_is_not_revalidated(db):
    # 검사가 생기기 전에 저장된 값 — 다른 설정을 저장해도 그대로 둔다(리뷰 모델과 같은 원칙)
    # A value stored before the check existed stays when another setting is saved.
    db.add(RepoConfig(repo_full_name="o/legacy", review_effort="xhigh"))
    db.commit()
    upsert_repo_config(db, RepoConfigData(repo_full_name="o/legacy", review_effort="xhigh", auto_merge=True))
    stored = get_repo_config(db, "o/legacy")
    assert (stored.review_effort, stored.auto_merge) == ("xhigh", True)


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


def test_a_form_without_the_effort_field_keeps_the_stored_effort(db):
    # 이 배포 전에 열어 둔 탭에는 effort 칸이 없다 — 키가 없으면 저장값을 그대로 둔다(③b 검토 Important 2)
    # A tab rendered before this deploy has no effort field; a missing key keeps the stored value.
    from src.ui.routes.settings import build_repo_config_from_form  # pylint: disable=import-outside-toplevel

    upsert_repo_config(db, RepoConfigData(repo_full_name="o/effort", review_effort="medium"))
    assert build_repo_config_from_form(db, "o/effort", {"approve_mode": "disabled"}).review_effort == "medium"
