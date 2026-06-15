"""rename ix_users_google_id → ix_users_github_id (정합성 감사 #18 drift ①)

정합성 감사 full(2026-06-08) #18 가드가 발견한 사전존재 drift ① — 0005 가 `google_id`
컬럼에 unique 인덱스 `ix_users_google_id` 를 생성했고, 0006 이 컬럼을 `github_id` 로
리네임(`alter_column new_column_name`)했으나 **인덱스명은 리네임하지 않음**. 결과적으로
운영 PG 에는 `ix_users_google_id` 인덱스가 잔존하나 ORM(user.py:19 `index=True`)은
자동명 `ix_users_github_id` 를 선언 → ORM↔DB 인덱스명 drift.

운영 무해(둘 다 동일 `github_id` 컬럼의 unique 인덱스 — 기능 동등, 명칭만 stale)이나
ORM↔DB 정합을 위해 인덱스명 리네임. ALTER INDEX RENAME 은 unique·컬럼 등 속성 보존.

PostgreSQL: `ALTER INDEX ... RENAME TO ...`.
SQLite: 컬럼 리네임 이력(0006)이 batch_alter_table 재생성으로 ORM 자동명을 이미 사용 +
단위 테스트는 ORM create_all 로 `ix_users_github_id` 생성 → rename 무의미·skip.

rename ix_users_google_id → ix_users_github_id (index name only; PG ALTER INDEX RENAME).
The column was renamed google_id→github_id in 0006 but the index name was not. PG-only.

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-09
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql


revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 운영 DB(Postgres)만 — SQLite 는 ORM create_all 로 이미 ix_users_github_id 사용.
    # Only Postgres; SQLite already uses ix_users_github_id via ORM create_all.
    bind = op.get_bind()
    if not is_postgresql(bind):
        return

    # 🔴 멱등성 + end-state 보장 (Codex mutual) — 시작 상태와 무관하게 종료 시 항상
    # `ix_users_github_id`(UNIQUE) 존재 + `ix_users_google_id` 부재가 되도록 3단계 구성.
    # github_id 는 ORM `unique=True` (0005 도 unique 인덱스) — CREATE UNIQUE 정합.
    #   (1) 정상(google 존재·github 부재): 이름만 stale 한 인덱스를 rename — 인덱스 정의 보존.
    #   (2) neither(둘 다 부재): ORM 정합 UNIQUE 인덱스 신규 생성으로 end-state 보장.
    #   (3) 병존/재실행: 잔존 stale source(google) 제거. CI clean DB 는 (1) 경로(=rename).
    # Guarantees the end state regardless of the starting state: rename when only the old index
    # exists (preserves its definition), create the ORM-matching UNIQUE index if neither exists,
    # then drop any stale source. github_id is UNIQUE in the ORM (and 0005), so CREATE UNIQUE matches.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'ix_users_google_id')
               AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'ix_users_github_id') THEN
                ALTER INDEX ix_users_google_id RENAME TO ix_users_github_id;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_github_id ON users (github_id)")
    op.execute("DROP INDEX IF EXISTS ix_users_google_id")


def downgrade() -> None:
    bind = op.get_bind()
    if not is_postgresql(bind):
        return

    op.execute("ALTER INDEX ix_users_github_id RENAME TO ix_users_google_id")
