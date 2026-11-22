"""리뷰 모델 저장값 검증 — 폼 · API 가 함께 지나는 upsert 에서, 값이 바뀔 때만 (Issue #1905 ③a).

Validating the stored review model at the one place the form and the API both pass, only when the value changes.
받는 값 = `auto:<아는 계열>` · 목록(또는 대체 목록)에 있는 판 id(날짜 붙은 id 는 별칭으로) · 빈 값.
바뀌지 않은 값은 검증하지 않는다 — 내린 판으로 고정된 리포가 다른 설정을 저장할 때 막히면 안 된다(K10).
Accepted: auto:<known line>, a listed (or fallback) model id, or blank; an unchanged value is never re-validated.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.config_manager.manager import RepoConfigData, get_repo_config, upsert_repo_config  # noqa: E402
from src.database import Base  # noqa: E402
from src.main import app  # noqa: E402
from src.models.repo_config import RepoConfig  # noqa: E402
from src.shared import model_catalog as mc  # noqa: E402

_TABLE_MODELS = (RepoConfig,)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")


@pytest.mark.parametrize(("value", "stored"), [
    ("auto:sonnet", "auto:sonnet"), (" auto:haiku ", "auto:haiku"), ("claude-sonnet-5", "claude-sonnet-5"),
    ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"), ("", None), (None, None),
])
def test_accepted_model_values(value, stored):
    assert mc.validate_model_value(value) == stored


# witness-corpus: 받지 않는 저장값 — 모르는 계열 · 비어 있는 계열 · 목록에 없는 판 · 다른 회사 모델 · 접두만 같은 이름
@pytest.mark.parametrize("value", ["auto:gpt", "auto:", "claude-unknown-9", "gpt-4o", "claude-sonnet-5-5-preview"])
def test_rejected_model_values(value):
    with pytest.raises(ValueError):
        mc.validate_model_value(value)


@pytest.fixture(name="db")
def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_saving_a_new_unknown_model_is_refused(db):
    with pytest.raises(ValueError):
        upsert_repo_config(db, RepoConfigData(repo_full_name="o/m", review_model="auto:gpt"))
    assert get_repo_config(db, "o/m").review_model is None


def test_an_unchanged_stored_value_is_not_revalidated(db):
    # 검증이 생기기 전에 저장된 값(목록에 없는 내린 판) — 다른 설정을 저장해도 그대로 둔다
    # A value stored before validation existed stays when another setting is saved.
    db.add(RepoConfig(repo_full_name="o/legacy", review_model="claude-sonnet-4-6"))
    db.commit()
    upsert_repo_config(db, RepoConfigData(repo_full_name="o/legacy", review_model="claude-sonnet-4-6",
                                          auto_merge=True))
    stored = get_repo_config(db, "o/legacy")
    assert (stored.review_model, stored.auto_merge) == ("claude-sonnet-4-6", True)


def test_the_api_answers_an_invalid_model_with_422():
    client = TestClient(app)
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    with patch("src.api.repos.SessionLocal", return_value=session), \
         patch("src.api.repos.get_repo_config", return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.api.repos.upsert_repo_config", side_effect=ValueError("review_model: unknown value")):
        response = client.put("/api/repos/owner%2Frepo/config", json={"review_model": "auto:gpt"})
    assert response.status_code == 422
