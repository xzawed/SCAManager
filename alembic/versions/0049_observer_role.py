"""관측 역할 scamanager_observer — 운영 DB 를 읽기만 하는 별도 역할 (회고 원장 L02).

Observer role scamanager_observer — a separate role that can only read production rows (retro ledger L02).

Revision ID: 0049
Revises: 0048

에이전트가 운영 DB 를 읽을 때 앱 역할 자격을 쓰지 않게 한다. 앱 자격으로 Supavisor 6543 을 거쳐
`SET SESSION …` 을 보내면 그 설정이 풀의 서버 연결에 남아 앱 쓰기가 막힌다. 별도 역할은 별도 풀이다.
Lets the agent read production without the app's credentials: a session setting sent through the
transaction pooler with the app role sticks to a pooled server connection; a separate role has its own pool.

- 컬럼 단위 `SELECT` 만 준다(`_ALLOWED`). 비밀값 · 개인정보 · 사용자 내용 컬럼은 없다. 테이블 단위 권한과
  기본 권한(`ALTER DEFAULT PRIVILEGES`)은 주지 않는다 — 새 테이블 · 새 컬럼은 GRANT 하는 revision 전까지 안 보인다.
- `BYPASSRLS` — RLS 정책이 `app.user_id` 로 행을 거르므로, 없으면 legacy 행만 보인다. 컬럼 권한이 읽을 수 있는
  범위를 정하고, 이 속성은 행 필터만 푼다.
- 쓰기 · 행 잠금 · 앱 백엔드 종료는 권한이 막는다(읽기 전용 기본값을 꺼도). 기본값은 심층 방어다.
- 로그인 비밀번호는 여기서 정하지 않는다(`NOLOGIN`). 운영자가 `scripts/observer_setup.py` 의 SCRAM 검증값으로
  `ALTER ROLE … LOGIN PASSWORD` 를 실행한다 — 운영은 `log_statement=ddl` 이라 평문을 쓰면 로그에 남는다.
- 🔴 권한이 모자라면(`insufficient_privilege`) 경고만 남기고 넘어간다 — 관측 역할 때문에 pre-deploy 가 실패하면
  그 뒤 모든 배포가 막힌다. 블록 하나라 반쯤 만들어진 역할은 남지 않는다. 다른 오류(없는 컬럼 등)는 그대로 실패한다.
- 역할은 클러스터 전역이다 — 스키마를 지우고 다시 올리는 CI 왕복에서 이미 있을 수 있어 «없으면 만든다».

Column-level SELECT only, no table-level or default privileges (new tables/columns stay invisible);
BYPASSRLS lifts only the row filter. Writes, row locks and terminating app backends are refused by
privileges. NOLOGIN until the operator sets a SCRAM verifier. An insufficient_privilege error only warns,
so the observer can never block a deploy; any other error still fails the migration.
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

ROLE = "scamanager_observer"

# 읽어도 되는 컬럼 — 운영 진단에 쓰는 식별자 · 상태 · 수치 · 시각 · 오류 부류만. 오류 글은 `_redact` 를 거쳐 출력한다.
# 뺀 것: 토큰 · 웹훅 비밀과 주소 · OTP(비밀값), 이메일 · 표시 이름 · GitHub 로그인 · 텔레그램 ID · 메일 수신자 ·
# 결정자(`gate_decisions.decided_by` = 텔레그램 `이름(id:N)`)(개인정보), 커밋 메시지 · AI 리뷰 본문 · 피드백 글 ·
# 인사이트 서술 · AI 판단 사유(사용자 내용), `merge_retry_queue.claim_token`(내부 CAS 값 — 진단에 안 쓴다).
# Readable columns: identifiers, states, numbers, timestamps and error classes used for operations.
_ALLOWED = {
    "alembic_version": ("version_num",),
    "analyses": ("id", "repo_id", "commit_sha", "pr_number", "score", "grade", "created_at", "review_model",
                 "input_tokens", "output_tokens", "score_unreliable"),
    "analysis_attempts": ("id", "repo_id", "commit_sha", "pr_number", "event", "started_at"),
    "analysis_feedbacks": ("id", "analysis_id", "user_id", "thumbs", "created_at", "updated_at"),
    "claude_api_calls": ("id", "created_at", "model", "status", "input_tokens", "output_tokens", "cache_read_tokens",
                         "cache_creation_tokens", "cost_usd", "duration_ms", "repo_id", "user_id", "error_type"),
    "gate_decisions": ("id", "analysis_id", "decision", "mode", "decided_at", "state", "post_claimed_at"),
    "insight_narrative_cache": ("id", "user_id", "days", "language", "repo_id", "created_at", "expires_at",
                                "last_error_at", "error_count", "last_error_type"),
    "issue_registrations": ("id", "analysis_id", "repo_id", "issue_type", "issue_key", "github_issue_number",
                            "github_issue_state", "github_issue_synced_at", "sync_error", "created_at"),
    "merge_attempts": ("id", "analysis_id", "repo_name", "pr_number", "score", "threshold", "success",
                       "failure_reason", "detail_message", "attempted_at", "state", "enabled_at", "merged_at",
                       "disabled_at"),
    "merge_retry_queue": ("id", "repo_full_name", "pr_number", "analysis_id", "commit_sha", "score",
                          "threshold_at_enqueue", "status", "attempts_count", "max_attempts", "next_retry_at",
                          "last_attempt_at", "claimed_at", "last_failure_reason", "last_detail_message",
                          "created_at", "updated_at"),
    "repo_configs": ("id", "repo_full_name", "pr_review_comment", "approve_mode", "approve_threshold",
                     "reject_threshold", "auto_merge", "merge_threshold", "commit_comment", "create_issue",
                     "railway_deploy_alerts", "auto_merge_issue_on_failure", "notification_language", "review_model",
                     "disabled_tools", "ai_review_enabled", "created_at", "updated_at"),
    "repositories": ("id", "full_name", "created_at", "user_id", "webhook_id"),
    "security_alert_process_logs": ("id", "repo_id", "alert_type", "alert_number", "severity", "rule_id",
                                    "ai_classification", "ai_confidence", "user_decision", "user_id",
                                    "processed_at"),
    "users": ("id", "created_at", "preferred_language"),
}

# 역할 기본값 — 심층 방어(권한이 본체). 5초는 배포 마이그레이션과 겹칠 때 앱이 줄 서는 상한이다.
# Role defaults — defense in depth (privileges are the boundary). 5 s bounds how long a migration queue can stall the app.
_SETTINGS = (
    ("default_transaction_read_only", "on"),
    ("statement_timeout", "'5s'"),
    ("idle_in_transaction_session_timeout", "'10s'"),
)

# 큰 정렬의 임시 파일 상한 — superuser 전용 설정이라 Supabase `postgres` 가 거절할 수 있어 따로 시도한다.
# Temp-file cap; superuser-only, so it is tried separately and may be refused on Supabase.
_TEMP_FILE_LIMIT = "'256MB'"


def _grants() -> str:
    lines = [f"GRANT USAGE ON SCHEMA public TO {ROLE};"]
    for table, columns in _ALLOWED.items():
        lines.append(f"GRANT SELECT ({', '.join(columns)}) ON {table} TO {ROLE};")
    return "\n        ".join(lines)


def _settings() -> str:
    return "\n        ".join(f"ALTER ROLE {ROLE} SET {name} = {value};" for name, value in _SETTINGS)


def upgrade() -> None:
    """관측 역할을 만들고 허용 컬럼만 읽게 한다 (PostgreSQL 만).
    Create the observer role and grant the allowlisted columns (PostgreSQL only)."""
    if not is_postgresql(op.get_bind()):
        return  # SQLite 단위 테스트 — 역할 · 권한이 없다 / SQLite unit tests have no roles
    op.execute(f"""
    DO $observer$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            CREATE ROLE {ROLE} NOLOGIN BYPASSRLS CONNECTION LIMIT 2;
        END IF;
        {_settings()}
        {_grants()}
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE WARNING '{ROLE} not provisioned (insufficient privilege): %', SQLERRM;
    END
    $observer$;
    """)
    op.execute(f"""
    DO $observer$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            ALTER ROLE {ROLE} SET temp_file_limit = {_TEMP_FILE_LIMIT};
        END IF;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE WARNING '{ROLE}: temp_file_limit not set (superuser-only setting): %', SQLERRM;
    END
    $observer$;
    """)


def downgrade() -> None:
    """이 DB 의 권한을 거두고 역할을 지운다 — 다른 DB 에 권한이 남아 있으면 역할은 남긴다.
    `DROP OWNED BY` 는 쓰지 않는다 — 슈퍼유저가 아닌 소유자(Supabase `postgres`)는 그 역할의 권한을 갖지 않아
    «permission denied to drop objects» 로 막힌다(로컬 PG 16 · 17 실측). 권한을 준 쪽이 REVOKE 한다.
    Revoke this database's privileges and drop the role; keep the role if another database still references it.
    No DROP OWNED BY: a non-superuser owner lacks the role's privileges and is refused (measured on PG 16/17)."""
    if not is_postgresql(op.get_bind()):
        return
    op.execute(f"""
    DO $observer$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE};
            REVOKE ALL ON SCHEMA public FROM {ROLE};
            BEGIN
                DROP ROLE {ROLE};
            EXCEPTION WHEN dependent_objects_still_exist THEN
                RAISE WARNING '{ROLE} kept (still referenced by another database): %', SQLERRM;
            END;
        END IF;
    END
    $observer$;
    """)
