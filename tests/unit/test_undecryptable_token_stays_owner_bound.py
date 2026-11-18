"""복호화 안 되는 저장 토큰은 소유자 쪽에 묶여 있다 — 운영자 토큰(앱 전역)으로 넘어가지 않는다 (회고 원장 R-16).

키 교체 뒤 다시 로그인하지 않은 사용자의 `users.github_access_token` 은 옛 키로 만든 Fernet 토큰이다. `decrypt_token` 은
그것을 빈 값이 아니라 **저장값 그대로** 돌려주고, 토큰을 쓰는 네 경로는 그 값을 소유자 토큰으로 써서 GitHub 가 401 로
거절한다 — 실패로 닫힌다. 빈 값을 돌려주게 «고치면» 네 경로 모두 «소유자 토큰이 비면 운영자 토큰» 꼴이라 다른 사용자의
리포에 운영자 신원으로 접근한다(Grok `123739c7`). 이 파일이 그 경계를 경로마다 고정한다.

계기 뒤집기(두 심음): 같은 시험이 «옛 키 토큰» 이면 소유자 값을, «토큰 없음» 이면 운영자 토큰을 보아야 한다 — 두 상태를
가르지 못하면 단언이 공허하다.
A stored token the current key cannot decrypt stays bound to its owner: each of the four token paths keeps using it
(GitHub rejects it with 401) and never falls back to the operator's app-wide token, which an empty value would trigger.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import logging
import uuid
from contextlib import nullcontext
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.config import settings
from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User

_TABLE_MODELS = (Analysis, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_REPO = "other-owner/other-repo"
_APP_TOKEN = "ghp_operator_app_wide_token_for_tests"
_OWNER_PLAINTEXT = "gho_owner_token_issued_before_key_rotation"


def _reset_fernet_cache() -> None:
    import src.crypto as crypto_mod  # noqa: PLC0415

    crypto_mod._fernet = False  # noqa: SLF001 — 키를 바꾼 뒤 다시 읽게 / re-read the key after patching it


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def rotated(monkeypatch):
    """옛 키로 만든 토큰과, 지금 키(다른 키) · 운영자 토큰을 건 환경 — 옛 키 토큰을 돌려준다."""
    old_key, new_key = Fernet.generate_key(), Fernet.generate_key()
    stored = Fernet(old_key).encrypt(_OWNER_PLAINTEXT.encode()).decode()
    monkeypatch.setattr(settings, "token_encryption_key", new_key.decode())
    monkeypatch.setattr(settings, "github_token", _APP_TOKEN)
    monkeypatch.setenv("GITHUB_TOKEN", _APP_TOKEN)
    _reset_fernet_cache()
    yield stored
    _reset_fernet_cache()


def _owner_with(db, stored: str) -> User:
    """`stored` 를 그대로 저장한 사용자 + 그 사용자의 리포."""
    user = User(github_id=f"r16-{uuid.uuid4().hex[:8]}", github_login="other-owner", email="o@x.com",
                display_name="O", github_access_token=stored)
    db.add(user)
    db.commit()
    db.add(Repository(full_name=_REPO, user_id=user.id))
    db.commit()
    return user


# «옛 키 토큰» 이면 저장값(소유자 쪽), «토큰 없음» 이면 운영자 토큰 — 두 상태가 서로의 대조군이다
# An old-key token resolves to the stored value; no token resolves to the operator's token. Each is the other's control.
_STATES = ["old_key", "missing"]


def _expected(state: str, stored: str) -> str:
    return stored if state == "old_key" else _APP_TOKEN


def _stored_for(state: str, stored: str) -> str | None:
    return stored if state == "old_key" else None


def test_decrypt_keeps_an_old_key_token_as_is_and_non_empty(rotated):
    """복호화가 실패해도 빈 값이 아니라 저장값 그대로 — 호출부의 «비면 운영자 토큰» 이 깨어나지 않는다."""
    from src.crypto import decrypt_token  # noqa: PLC0415

    assert decrypt_token(rotated) == rotated
    assert decrypt_token(rotated), "빈 값이면 모든 호출부가 운영자 토큰으로 넘어간다"


def test_the_warning_says_the_owner_must_log_in_again(rotated, caplog):
    """경고는 «평문을 돌려준다» 가 아니라 «소유자가 다시 로그인해야 한다 · 앱 토큰은 쓰지 않는다» 를 말한다."""
    from src.crypto import decrypt_token  # noqa: PLC0415

    with caplog.at_level(logging.WARNING, logger="src.crypto"):
        decrypt_token(rotated)
    text = caplog.text
    assert "owner must log in again" in text
    assert "app-wide token is not used" in text
    assert "returning as plaintext" not in text


@pytest.mark.parametrize("state", _STATES)
def test_analysis_pipeline_resolves_to_the_owner_side(db, rotated, state):
    """분석 경로(`_ensure_repo`) — 리뷰 · 댓글이 쓰는 토큰."""
    from src.worker.pipeline import _ensure_repo  # noqa: PLC0415

    _owner_with(db, _stored_for(state, rotated))
    resolved = _ensure_repo(db, _REPO, f"sha{uuid.uuid4().hex}")
    assert resolved is not None
    assert resolved[1] == _expected(state, rotated)


@pytest.mark.parametrize("state", _STATES)
def test_merge_retry_resolves_to_the_owner_side(db, rotated, state):
    """머지 재시도(`_resolve_github_token`)."""
    from src.services.merge_retry_service import _resolve_github_token  # noqa: PLC0415

    _owner_with(db, _stored_for(state, rotated))
    assert _resolve_github_token(db, _REPO) == _expected(state, rotated)


@pytest.mark.parametrize("state", _STATES)
def test_security_poll_resolves_to_the_owner_side(db, rotated, state):
    """보안 폴링(`_resolve_token`) — 운영자 토큰은 env `GITHUB_TOKEN` 에서 온다."""
    from src.services.security_scan_service import _resolve_token  # noqa: PLC0415

    user = _owner_with(db, _stored_for(state, rotated))
    assert _resolve_token(user) == _expected(state, rotated)


@pytest.mark.parametrize("state", _STATES)
async def test_merged_pr_issue_close_resolves_to_the_owner_side(db, rotated, state):
    """웹훅의 이슈 닫기(`_close_referenced_issues`) — `close_issue` 에 넘어간 토큰을 본다."""
    from src.webhook.providers import github as gh  # noqa: PLC0415

    _owner_with(db, _stored_for(state, rotated))
    close = AsyncMock()
    with patch.object(gh, "SessionLocal", lambda: nullcontext(db)), patch.object(gh, "close_issue", close):
        await gh._close_referenced_issues(_REPO, [7])  # noqa: SLF001 — 백그라운드 함수를 직접 / call the task directly
    assert close.await_count == 1
    assert close.await_args.kwargs["token"] == _expected(state, rotated)
