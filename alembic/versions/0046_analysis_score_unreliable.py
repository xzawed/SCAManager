"""analyses.score_unreliable — score_is_unreliable(result) 의 비정규화 캐시

analyses.score_unreliable — denormalized cache of score_is_unreliable(result).

Revision ID: 0046
Revises: 0045

집계(평균·추세)는 `score_is_unreliable(result)` 로 행을 걸러내는데, 판정 근거가 `result`
JSON 안에 있어 그 전량을 읽어야 했다. 실측(로컬 PG17, 운영 동형 5,164행 · 33 MB):

    json 전체 blob 로드            16.2 ms · 5,164행 · 33 MB 전송
    json 5경로 `->` 추출          422.5 ms  ← `json` 은 텍스트라 접근마다 재파싱
    jsonb 5경로 `->`               74.7 ms  (테이블 재작성 필요, 여전히 5,164행)
    이 컬럼 + 부분인덱스             0.45 ms · **4행** · 버퍼 6 (Index Only Scan)

운영 실측(2026-08-24): 5,166행 중 신뢰불가 3,660(70.8%) → 부분 인덱스는 1,506행만 덮는다.

🔴 **백필은 파이썬 `score_is_unreliable` 을 호출한다.** SQL 로 판정을 다시 쓰면 정의가 두
   벌이 되고, 이 리포는 이미 그 형태로 한 번 다쳤다(JSON 불린 `"false"` 가 파이썬에선
   truthy·SQL 투영에선 False). 정의는 하나여야 한다.

🔴 `server_default=text("false")` 필수 — `nullable=False` 만 두면 **데이터가 있는 운영
   테이블에서만** 실패한다(SQLite 테스트는 create_all 이라 안 보인다).

PG 11+ 에서 상수 DEFAULT + NOT NULL 은 카탈로그 변경뿐이라 테이블 재작성이 없다.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

from src.scorer.reliability import score_is_unreliable

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

# 한 번에 읽는 행 수 — 30 MB 를 통째로 메모리에 올리지 않는다.
# 🔴 마이그레이션은 배포 전(preDeploy) 또는 앱 lifespan(30s 타임아웃, `src/main.py`)에서
#    돈다. 청크 + executemany 로 5천 행을 한 트랜잭션에 끝낸다.
_CHUNK = 500

_INDEX = "ix_analyses_reliable_scores"


def _backfill(conn) -> int:
    """기존 행을 파이썬 판정으로 채운다. 갱신한 행 수 반환."""
    updated = 0
    last_id = 0
    while True:
        rows = conn.execute(
            sa.text(
                "SELECT id, result FROM analyses WHERE id > :last ORDER BY id LIMIT :lim"
            ),
            {"last": last_id, "lim": _CHUNK},
        ).fetchall()
        if not rows:
            break
        payload = []
        for row_id, result in rows:
            # SQLite 는 JSON 컬럼을 문자열로 돌려줄 수 있다 — 판정 입력은 dict 여야 한다.
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except (ValueError, TypeError):
                    result = None
            payload.append({
                "row_id": row_id,
                "flag": bool(score_is_unreliable(result if isinstance(result, dict) else None)),
            })
        conn.execute(
            sa.text("UPDATE analyses SET score_unreliable = :flag WHERE id = :row_id"),
            payload,
        )
        updated += len(payload)
        last_id = rows[-1][0]
    return updated


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "score_unreliable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    _backfill(op.get_bind())
    # 🔴 부분 인덱스 — 집계는 «점수가 있고 신뢰 가능한» 행만 본다. 운영 기준 29% 만 덮어
    #    Index Only Scan 이 된다(실측 0.45 ms · 버퍼 6, 인덱스 없으면 2.17 ms · 버퍼 1,145).
    #    양 방언 선언 — ORM↔alembic 정합(`docs/workflow/db.md`).
    op.create_index(
        _INDEX,
        "analyses",
        ["repo_id", "score"],
        unique=False,
        postgresql_where=sa.text("score IS NOT NULL AND score_unreliable IS NOT TRUE"),
        sqlite_where=sa.text("score IS NOT NULL AND score_unreliable IS NOT TRUE"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="analyses")
    op.drop_column("analyses", "score_unreliable")
