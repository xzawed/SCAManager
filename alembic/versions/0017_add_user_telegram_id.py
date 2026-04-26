"""add telegram_user_id, telegram_otp, telegram_otp_expires_at to users

Revision ID: 0017addusertelegramid
Revises: 0016uniqueanalysissha
Create Date: 2026-04-26
"""
# Telegram 연동을 위한 users 테이블 컬럼 3개 추가 마이그레이션
# Migration that adds three columns to the users table for Telegram integration.

from alembic import op
import sqlalchemy as sa

revision = "0017addusertelegramid"
down_revision = "0016uniqueanalysissha"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # telegram_user_id — Telegram 사용자 고유 ID (NULL 허용, UNIQUE)
    # telegram_user_id — Telegram user unique ID (nullable, unique).
    op.add_column(
        "users",
        sa.Column("telegram_user_id", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_users_telegram_user_id",
        "users",
        ["telegram_user_id"],
    )

    # telegram_otp — 연동 인증용 일회용 패스코드 (NULL 허용)
    # telegram_otp — one-time passcode for Telegram linking (nullable).
    op.add_column(
        "users",
        sa.Column("telegram_otp", sa.String(), nullable=True),
    )

    # telegram_otp_expires_at — OTP 만료 시각 (타임존 포함, NULL 허용)
    # telegram_otp_expires_at — OTP expiry timestamp with timezone (nullable).
    op.add_column(
        "users",
        sa.Column(
            "telegram_otp_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # 역순으로 제거: constraint 먼저, 컬럼 나중
    # Remove in reverse order: constraint first, then columns.
    op.drop_constraint("uq_users_telegram_user_id", "users", type_="unique")
    op.drop_column("users", "telegram_otp_expires_at")
    op.drop_column("users", "telegram_otp")
    op.drop_column("users", "telegram_user_id")
