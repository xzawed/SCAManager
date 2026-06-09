"""정합성 감사 #18 drift ① — users github_id 인덱스명 회귀 가드.

정합성 감사 full(2026-06-08) #18 가드 발견 drift ① — 0005 가 `ix_users_google_id`
생성, 0006 이 컬럼 google_id→github_id 리네임했으나 인덱스명 미반영. ORM 은
자동명 `ix_users_github_id` 선언. alembic 0040 가 운영 PG 인덱스명 리네임.

본 테스트는 ORM 측 인덱스명이 `ix_users_github_id`(legacy 'google' 아님)인지 검증.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from src.models.user import User


def test_users_github_id_index_name_not_legacy_google():
    """User.github_id 인덱스명이 ix_users_github_id (legacy ix_users_google_id 아님) (#18 drift ①).

    0006 컬럼 리네임 후 인덱스명 stale → ORM↔DB drift. alembic 0040 가 운영 PG 정합.
    ORM `index=True` 자동명이 컬럼명(github_id) 기반인지 회귀 검증.
    """
    index_names = {ix.name for ix in User.__table__.indexes}
    assert "ix_users_github_id" in index_names, (
        f"users 인덱스에 ix_users_github_id 없음 — {index_names} (#18 drift ① 회귀)"
    )
    assert "ix_users_google_id" not in index_names, (
        "legacy ix_users_google_id 가 ORM 에 잔존 — github_id 컬럼명 정합 위반"
    )
