"""정합성 감사 #18 drift ④ — repositories.user_id → users.id FK 회귀 가드.

정합성 감사 full(2026-06-08) #18 가드 발견 drift ④ — `repositories.user_id` 가 ORM 에는
`ForeignKey("users.id")` 로 선언됐으나 0005 가 DB FK 제약을 생성하지 않음(컬럼+인덱스만).
referential integrity 미강제 → 고아 user_id 가능. alembic 0039 가 DB FK(SET NULL) 추가.

본 테스트는 ORM 정의 측 `ondelete="SET NULL"` 가 유지되는지 검증 (alembic 0039 페어).
nullable 컬럼이라 SET NULL (analyses 0038 의 NOT NULL→CASCADE 와 대비).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from src.models.repository import Repository


def test_repositories_user_id_fk_has_set_null_delete():
    """Repository.user_id FK 의 ondelete 가 SET NULL 인지 검증 (#18 drift ④).

    user 삭제 시 소유 repo 는 보존(소유자만 해제) — nullable 컬럼 정합. 미설정 시
    DB 레벨 referential integrity 부재(고아 user_id 가능). alembic 0039 가 DB FK 추가.
    """
    fks = list(Repository.__table__.c.user_id.foreign_keys)
    assert len(fks) == 1, "user_id 에 FK 가 정확히 1개 있어야 함"
    fk = fks[0]
    assert fk.column.table.name == "users", "user_id FK 는 users 테이블 참조"
    assert fk.ondelete == "SET NULL", (
        f"repositories.user_id FK ondelete='{fk.ondelete}' — "
        "'SET NULL' 이어야 함 (#18 drift ④ 회귀, nullable 컬럼)"
    )
