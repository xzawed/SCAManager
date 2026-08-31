"""게시 상태·in-flight 클레임(R2)과 동기화 실패 표시(R3)를 더한다 (#1504).

「결정했다」와 「GitHub 에 리뷰가 붙었다」는 다르다. 수동 게이트는 claim → POST 순서라,
POST 가 전송 오류로 실패하면 결정만 남고 리뷰는 없다. 그 상태를 표현할 수단이 없어서
재클릭이 리플레이로 막혔고 — 콜백 HMAC 이 만료되지 않는데도 — 재시도 수단이 없었다.

🔴 `state` 의 `server_default` 는 **"posted"** 다. 기존 행을 `pending_post` 로 채우면
만료 없는 HMAC 때문에 옛 버튼을 누르는 순간 **이력 전체가 재게시**된다. 오늘의 결함으로
실제 미게시인 행은 갇힌 채 남지만, 이력을 GitHub 재발화로 치유하지 않는 쪽이 옳다.

🔴 `post_claimed_at` 은 nullable 이다 — 게시 **진행 중** 임을 표시하는 리스이고,
`decided_at` 을 재사용할 수 없다(HMAC 무만료 때문에 늦은 클릭에서 즉시 만료로 보인다).

Decided is not posted. Existing rows default to "posted" because backfilling "pending_post"
would re-post every historical decision on the next click of a never-expiring button.
"""
import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 🔴 행이 있는 운영 테이블이라 `nullable=False` 에는 `server_default` 가 필수다 —
    #    없으면 pre-deploy 의 `alembic upgrade head` 가 운영에서만 실패한다(db.md 4-1).
    op.add_column(
        "gate_decisions",
        sa.Column("state", sa.String(), nullable=False, server_default="posted"),
    )
    op.add_column(
        "gate_decisions",
        sa.Column("post_claimed_at", sa.DateTime(), nullable=True),
    )
    # R3 — 마지막 동기화가 실패했으면 그 원인, 성공했으면 NULL.
    # 🔴 nullable 이라 `server_default` 가 필요 없다. 기존 행은 NULL = 「실패 표시 없음」이고
    #    그것이 옳다 — 과거의 동기화 성공/실패를 소급해 알 수 없으므로 다음 TTL 에 다시 잰다.
    # Nullable by design: existing rows carry no verdict, and the next TTL sync will set one.
    op.add_column(
        "issue_registrations",
        sa.Column("sync_error", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("issue_registrations", "sync_error")
    op.drop_column("gate_decisions", "post_claimed_at")
    op.drop_column("gate_decisions", "state")
