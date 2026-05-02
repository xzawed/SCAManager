"""drop repo_config.leaderboard_opt_in

Revision ID: 0025dropleaderboardoptin
Revises: 0024gatedecisionscascade
Create Date: 2026-05-02

Phase 1+2 회고 후속 + 사용자 결정 (2026-05-02): 팀 리더보드 기능 완전 폐기.
- Q3 결정 정정: 그룹 60 PR #190 (Phase 1 PR 3) 시점 "컬럼 보존" → "정정 폐기".
- 사유: 사용자 *"코드 내 사용을 하지 않거나 보류의 내용은 없었으면"* 정신 일치
  (Phase 1 회고 사용자 발화 인용). 1인 운영 → SaaS 전환 의도 (Phase 3 로드맵 갱신
  반영) 시점에서도 기존 single-user leaderboard_opt_in 컬럼은 의미 부재.

폐기 자원 (본 마이그레이션):
- `repo_configs.leaderboard_opt_in` 컬럼 (Boolean, default=False, NOT NULL)

폐기 상위 자원 (그룹 60 PR #190 에서 이미 폐기):
- analytics_service.leaderboard() 함수
- src/api/insights.py::get_leaderboard 엔드포인트
- src/templates/insights.html (전체 페이지)

회귀 가드:
- tests/unit/services/test_analytics_service_deprecations.py — 컬럼 부활 차단 가드 신설
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0025dropleaderboardoptin'
down_revision = '0024gatedecisionscascade'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """leaderboard_opt_in 컬럼 drop."""
    # PostgreSQL 호환 — batch_alter_table 금지 (CLAUDE.md L823 — SQLite 전용 패턴).
    # PostgreSQL: drop column 직접 실행.
    op.drop_column('repo_configs', 'leaderboard_opt_in')


def downgrade() -> None:
    """downgrade 시 컬럼 복원 (default=False, NOT NULL).

    주의: 본 컬럼은 사용자 결정 정정으로 폐기됐으므로 downgrade 후에도
    `analytics_service.leaderboard()` / `/api/insights/leaderboard` 등은
    여전히 부재 (그룹 60 PR #190 머지 = 코드 레벨 폐기). downgrade 는 schema
    rollback 만 가능 — 기능 부활은 별도 PR + 사용자 재논의 필요.
    """
    op.add_column(
        'repo_configs',
        sa.Column(
            'leaderboard_opt_in',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
