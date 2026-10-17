"""analyses — 개요 집계 인덱스 교체: 검증 점수 부분 인덱스 → 기록된 점수 3열 인덱스.

analyses — swap the overview aggregate index: verified-score partial → recorded-score 3-column.

Revision ID: 0048
Revises: 0047

개요 카드 평균이 «검증된 점수만» 에서 «기록된 점수 전부» 로 바뀌었다
(`src/ui/routes/overview.py::def recorded_score_summary`). 0046 의 부분 인덱스는 술어
(`score_unreliable IS NOT TRUE`)를 새 집계가 함의하지 않아 **어떤 쿼리도 쓰지 못한다** —
집계가 매번 힙(`result` JSON 이 대부분 인라인이라 무겁다)을 통째로 읽는다.

    운영(2026-10-17, 읽기 전용 EXPLAIN)   새 집계 Seq Scan · 버퍼 1,185 · 5.8 ms (RLS 웹 역할 7.4 ms)
    로컬 PG 17.6 운영 동형               Seq Scan 버퍼 884 → 이 인덱스 + count(*) 버퍼 12
                                        행 10배에서 28 ms → 5.4 ms

🔴 `count(*)` 와 짝이다 — `count(analyses.id)` 는 id 가 이 인덱스에 없어 Index Only Scan 이
   막힌다(PG 17 은 NOT NULL 열의 count 를 count(*) 로 바꾸지 않는다).
🔴 키 열 3개 · 술어 없음 — B-tree 중복 제거는 INCLUDE 인덱스에 적용되지 않는다(실측 106 KB vs
   278 KB). 술어가 없어 옛 «검증 점수만» 모양의 집계도 이 인덱스로 답한다.
🔴 잠금 — `CREATE INDEX` 는 SHARE(쓰기만 막는다), `DROP INDEX` 는 ACCESS EXCLUSIVE(읽기까지
   막는다). 만들고 나서 지워 ACCESS EXCLUSIVE 를 빌드 동안 쥐지 않는다. 운영 마이그레이션
   세션은 `lock_timeout = 0` · `statement_timeout = 2min` 이라(실측) 열린 트랜잭션 하나가 DROP 을
   세우면 그 뒤에 줄 선 analyses 읽기가 최대 2분 멈춘다 — 잠금 대기마다 5초로 자른다.
   읽기는 DROP 대기에만 막혀 5초 이내다. 쓰기는 이미 잡은 SHARE 가 롤백까지 남아 CREATE 대기와
   DROP 대기가 겹치면 약 10초 + 빌드까지 막힌다(로컬 실측: 열린 쓰기 1초 + DROP 대기 5초 →
   줄 선 쓰기 5.8초). 넘기면 트랜잭션 전체가 롤백되고 pre-deploy 가 실패해 이전 배포가 계속
   서비스한다.
🔴 상한을 되돌리지 않는다 — DROP 이 잡은 ACCESS EXCLUSIVE 는 COMMIT 까지 남는다. 그 뒤의 대기
   (alembic_version 갱신 · 같은 트랜잭션의 다음 리비전)가 상한 없이 기다리면 analyses 읽기가
   그동안 멈춘다(Grok `17d38a6e` 반증). 상한은 잠금 «대기» 에만 걸린다 — 같은 배포의 뒤 리비전이
   오래 «실행» 되면 그동안도 analyses 가 잠긴다(이 리비전 뒤 작업은 alembic_version 갱신뿐이다).
   `SET LOCAL` 은 COMMIT·ROLLBACK 에서 끝난다.

Create before drop so ACCESS EXCLUSIVE is never held across the build, and bound each lock wait:
the production migration session has no lock_timeout, so a stuck DROP would queue every read.
Reads wait at most one bounded wait; writes can wait for both (the SHARE lock stays until rollback).
The bound is kept until COMMIT because ACCESS EXCLUSIVE is held until then.
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

_NEW = "ix_analyses_repo_scores"
_OLD = "ix_analyses_reliable_scores"
_OLD_WHERE = "score IS NOT NULL AND score_unreliable IS NOT TRUE"


def _bound_lock_waits() -> None:
    """이 트랜잭션이 끝날 때까지 잠금 대기마다 5초 상한 — 되돌리지 않는다(위 docstring).

    Cap every lock wait until the transaction ends; never reset (ACCESS EXCLUSIVE outlives DROP).
    """
    if is_postgresql(op.get_bind()):
        op.execute("SET LOCAL lock_timeout = '5s'")


def upgrade() -> None:
    _bound_lock_waits()
    op.create_index(_NEW, "analyses", ["repo_id", "score", "score_unreliable"])
    op.drop_index(_OLD, table_name="analyses", if_exists=True)


def downgrade() -> None:
    _bound_lock_waits()
    # 0046 이 만든 그대로 — 이름 · 열 · 양 방언 술어.
    # Exactly as 0046 created it: name, columns, and the predicate for both dialects.
    op.create_index(
        _OLD, "analyses", ["repo_id", "score"],
        postgresql_where=sa.text(_OLD_WHERE), sqlite_where=sa.text(_OLD_WHERE),
    )
    op.drop_index(_NEW, table_name="analyses", if_exists=True)
