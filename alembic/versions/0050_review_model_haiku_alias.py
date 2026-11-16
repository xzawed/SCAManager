"""repo_configs.review_model — Haiku 날짜 스냅샷 id 를 별칭으로 옮긴다

repo_configs.review_model — move the dated Haiku snapshot id to its alias.

Revision ID: 0050
Revises: 0049

모델 카탈로그(`src/constants.py::CLAUDE_MODELS`)의 Haiku 항목이 날짜 스냅샷 id 였고 인사이트 기본값은 별칭이라, 앱이 같은
모델을 두 이름으로 불렀다(회고 원장 이관 K11 P2-38 · P2-55). 카탈로그를 별칭으로 바꾸면서 그 날짜 id 로 고정된 리포 설정도
별칭으로 옮긴다 — 사용자 11-17 결정 «별칭 통일+5개 이전 (Recommended)». 별칭과 전체 id 는 같은 모델이라 리뷰 결과와 비용은
그대로다.

- 설정만 옮긴다. 분석 · 호출 기록(`analyses.review_model` · `claude_api_calls.model`)은 그때 쓴 이름 그대로 둔다 — 요율은
  계열(haiku)로 같게 매겨진다(`src/shared/claude_metrics.py`).
- 되돌리기는 별칭을 날짜 id 로 돌린다. 원래부터 별칭이던 행도 날짜 id 가 되지만 같은 모델이라 감수한다.
- PostgreSQL 에서 이 역할이 RLS 를 우회하지 못하면 일부 행만 바뀐다 — 그때는 경고만 남긴다. 안 바뀐 행도 유효한 모델 id
  이고 설정 화면은 카탈로그 밖 값을 지우지 않고 보여 준다(#1748) — 배포를 막지 않는다.
Settings only; history keeps the names it used. Downgrade maps the alias back. A role that cannot
bypass RLS only logs a warning: unmoved rows still name a valid model.
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None

DATED_ID = "claude-haiku-4-5-20251001"
ALIAS_ID = "claude-haiku-4-5"

logger = logging.getLogger("alembic.runtime.migration")


def _rename(conn, old: str, new: str) -> int:
    """`review_model` 이 정확히 `old` 인 리포 설정을 `new` 로 — 바꾼 행 수를 돌려준다."""
    result = conn.execute(
        sa.text("UPDATE repo_configs SET review_model = :new WHERE review_model = :old"),
        {"new": new, "old": old},
    )
    return result.rowcount or 0


def _warn_if_rls_may_hide_rows(conn) -> None:
    """PostgreSQL 에서 현재 역할이 RLS 를 우회하지 못하면 경고 — 그 역할에겐 일부 행만 보인다."""
    if not is_postgresql(conn):
        return
    bypass = conn.execute(sa.text(
        "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")).scalar()
    if not bypass:
        logger.warning("0050: 이 역할은 RLS 를 우회하지 못한다 — 보이는 리포 설정만 옮긴다(나머지도 유효한 모델 id)")


def upgrade() -> None:
    conn = op.get_bind()
    _warn_if_rls_may_hide_rows(conn)
    moved = _rename(conn, DATED_ID, ALIAS_ID)
    logger.info("0050: review_model %s -> %s (%d rows)", DATED_ID, ALIAS_ID, moved)


def downgrade() -> None:
    conn = op.get_bind()
    _warn_if_rls_may_hide_rows(conn)
    moved = _rename(conn, ALIAS_ID, DATED_ID)
    logger.info("0050 downgrade: review_model %s -> %s (%d rows)", ALIAS_ID, DATED_ID, moved)
