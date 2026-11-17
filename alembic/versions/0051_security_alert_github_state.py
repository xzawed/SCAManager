"""보안 알림 기록에 GitHub 쪽 상태(`github_state`)를 더한다 (회고 원장 L05 P1-35).

폴링은 GitHub 의 «열린» 알림만 받아, GitHub 에서 해결 · 무시로 닫힌 알림도 대시보드의 «신규 pending» 에 영원히
남았다 — 닫힘을 적을 자리가 없었다. 이제 폴링이 열린 목록을 **끝까지** 받으면 그 목록에 없는 행을 "closed" 로,
다시 나타난 행을 "open" 으로 적는다.

🔴 `server_default` 는 "open" 이다 — 행이 있는 운영 테이블이라 `nullable=False` 에 기본값이 필수이고(db.md 4-1),
지금 있는 행은 다음 폴링이 열린 목록과 대조해 바로잡는다.
🔴 관측 역할(0049)은 컬럼 단위 GRANT 라 새 컬럼이 저절로 보이지 않는다 — 비밀값이 아닌 상태 값이라 이 revision 이
그 컬럼 하나를 GRANT 한다(역할이 없거나 권한이 모자라면 경고만 하고 넘어간다 — 0049 와 같은 원칙).

Add the alert's GitHub-side state. The poller only fetched open alerts, so alerts closed on GitHub stayed "pending" forever.
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None

ROLE = "scamanager_observer"

# 이 revision 이 관측 역할에 더 주는 컬럼 — 0049 `_ALLOWED` 와 합친 것이 관측 역할이 읽는 전부다.
# Columns this revision adds to the observer allowlist; together with 0049 `_ALLOWED` this is everything it reads.
_ADDED_GRANTS = {"security_alert_process_logs": ("github_state",)}


def upgrade() -> None:
    op.add_column(
        "security_alert_process_logs",
        sa.Column("github_state", sa.String(), nullable=False, server_default="open"),
    )
    if not is_postgresql(op.get_bind()):
        return  # SQLite 단위 테스트 — 역할 · 권한이 없다 / SQLite unit tests have no roles
    grants = "\n        ".join(
        f"GRANT SELECT ({', '.join(columns)}) ON {table} TO {ROLE};" for table, columns in _ADDED_GRANTS.items()
    )
    op.execute(f"""
    DO $observer$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            {grants}
        END IF;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE WARNING '{ROLE}: github_state not granted (insufficient privilege): %', SQLERRM;
    END
    $observer$;
    """)


def downgrade() -> None:
    # 컬럼을 지우면 그 컬럼 권한도 함께 사라진다 / dropping the column drops its column privileges too
    op.drop_column("security_alert_process_logs", "github_state")
