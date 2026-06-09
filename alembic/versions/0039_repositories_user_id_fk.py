"""add DB-level FK on repositories.user_id → users.id (정합성 감사 P2 #18 drift ④)

정합성 감사 full(2026-06-08) #18 가드가 발견한 사전존재 drift ④ —
`repositories.user_id` 는 ORM 에 `ForeignKey("users.id")` 로 선언됐으나 0005 가
컬럼+인덱스만 추가하고 **DB 레벨 FK 제약은 생성하지 않았다**. referential integrity
미강제로 고아 user_id(users 미존재 id) 가능. ORM↔DB 정합(#14류) + 무결성 1차 안전망.

repositories.user_id 는 nullable 이므로 **ondelete=SET NULL** (user 삭제 시 repo 는
보존하되 소유자만 해제 — ui.md: user_id=NULL repo 는 전 로그인 사용자에게 노출됨).
analyses(0038, NOT NULL→CASCADE) 와 대비되는 nullable 컬럼의 자연스러운 정책.

🔴 FK 추가 전 **고아 정리 선행** (사용자 결정 A): users.id 에 없는 user_id 를 NULL 로
정리해야 FK 생성이 기존 행 검증에서 실패하지 않는다.

repositories.user_id has no DB-level FK (0005 added only the column+index). Add the FK
with ondelete=SET NULL (nullable column). Orphan user_ids (no matching users.id) are set
to NULL first so the FK can be created without failing on existing rows.

PostgreSQL: orphan cleanup + CREATE CONSTRAINT (FK 없던 상태 → DROP 불요).
SQLite: ALTER 로 FK 추가 불가 — 운영 DB(Postgres)만 처리.
단위 테스트는 ORM Base.metadata.create_all 로 신규 ondelete='SET NULL' 자동 적용.

add DB-level FK on repositories.user_id — see 0038 (analyses) for the ALTER pattern.
user_id is nullable so SET NULL fits; orphans are nulled before the FK is created.

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-09
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql


revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

# Postgres 기본 FK 명명 규칙 (table_column_fkey) — compare_metadata 는 이름이 아닌
# (컬럼·참조·ondelete) 시그니처로 대조하므로 ORM unnamed FK 와 정합.
# Default Postgres FK name convention; compare_metadata matches by signature, not name.
_FK_NAME = "repositories_user_id_fkey"


def upgrade() -> None:
    # SQLite 는 ALTER 로 FK 추가 불가 — 운영 DB(Postgres)만 처리.
    # 단위 테스트는 ORM Base.metadata.create_all 로 신규 ondelete='SET NULL' 적용.
    # SQLite cannot ALTER-add FKs — only Postgres; tests get the FK via ORM create_all.
    bind = op.get_bind()
    if not is_postgresql(bind):
        return

    # 고아 user_id 정리 (users.id 미존재) → NULL — FK 생성 전 기존 행 검증 통과 보장.
    # Null out orphan user_ids (no matching users.id) before adding the FK.
    op.execute(
        "UPDATE repositories SET user_id = NULL "
        "WHERE user_id IS NOT NULL "
        "AND user_id NOT IN (SELECT id FROM users)"
    )
    op.create_foreign_key(
        _FK_NAME,
        "repositories",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not is_postgresql(bind):
        return

    op.drop_constraint(_FK_NAME, "repositories", type_="foreignkey")
