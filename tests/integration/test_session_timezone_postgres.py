"""PostgreSQL 세션 TimeZone 이 UTC 로 고정되는가 — naive 컬럼 저장값의 기준.

Whether the PostgreSQL session TimeZone is pinned to UTC, which sets the frame of
reference for every naive DateTime column in this repo.

## 무엇이 걸려 있나 (실측 2026-08-22)

이 저장소의 DateTime 컬럼은 전부 naive(`TIMESTAMP WITHOUT TIME ZONE`)인데, 모델 default
18곳(`default=` 15 + `onupdate=` 3)은 aware `datetime.now(timezone.utc)` 를 그 컬럼에 넣는다.
psycopg2 는 aware 값을 timestamptz 로 보내고, PostgreSQL 은 `timestamp` 로 캐스팅할 때
**세션 TimeZone** 을 쓴다.

DB 기본 TimeZone 을 `Asia/Seoul` 로 둔 실제 인스턴스에서 잰 값:

    핀 없음   세션TZ=Asia/Seoul   UTC 정오 → 저장 `2026-04-26 21:00:00`   ← 9시간 이동
    핀 있음   세션TZ=UTC          UTC 정오 → 저장 `2026-04-26 12:00:00`

이동한 값 위에서 이후의 모든 naive 비교(윈도우 경계·`is_expired`·보존 sweep)가 어긋난다.
`src/database.py` 에는 이 타임존을 고정하는 것이 없었고 서버/역할 기본값에 의존했다.

## 왜 SQLite 단위 테스트로는 못 잡나

SQLite 는 tzinfo 를 그냥 벗겨 저장한다 — 세션 타임존이라는 개념 자체가 없어 이 축이
**원리적으로 관측되지 않는다**. 그래서 이 파일은 PostgreSQL 전용이다.

실행 조건 / Execution guard: `DATABASE_URL_TEST_POSTGRES` 설정 시에만 (pg-concurrency CI job).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from src.database import _build_connect_args

_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_postgres = pytest.mark.skipif(
    not _PG_URL, reason="세션 TimeZone 검증은 PostgreSQL 필요 — DATABASE_URL_TEST_POSTGRES",
)

# UTC 정오 — 어느 방향으로 밀려도 날짜가 바뀌지 않아 오프셋만 순수하게 보인다.
_AWARE_NOON_UTC = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
_EXPECTED_NAIVE = datetime(2026, 4, 26, 12, 0, 0)


def _engine(connect_args: dict):
    return create_engine(_PG_URL, connect_args=connect_args, pool_pre_ping=False)


def _store_and_read(connect_args: dict, table: str) -> tuple[str, datetime]:
    """주어진 연결 인수로 aware UTC 값을 naive 컬럼에 넣고 (세션TZ, 저장된 값) 반환."""
    engine = _engine(connect_args)
    try:
        with engine.begin() as conn:
            tz = conn.execute(text("SHOW TimeZone")).scalar()
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            conn.execute(text(f"CREATE TABLE {table} (id serial primary key, t TIMESTAMP)"))
            conn.execute(text(f"INSERT INTO {table} (t) VALUES (:v)"), {"v": _AWARE_NOON_UTC})
            stored = conn.execute(
                text(f"SELECT t FROM {table} ORDER BY id DESC LIMIT 1")
            ).scalar()
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        return tz, stored
    finally:
        engine.dispose()


@_requires_postgres
def test_app_connect_args_pin_the_session_to_utc():
    """앱이 실제로 만드는 연결 인수로 붙었을 때 세션이 UTC 인가.

    🔴 `_build_connect_args` 를 **직접 호출**한다 — 테스트가 자기 손으로 options 를 적으면
    앱 경로가 그것을 잃어도 초록이다.
    """
    tz, _ = _store_and_read(_build_connect_args(_PG_URL), "tz_probe_app")

    assert tz.upper() == "UTC", (
        f"앱 연결의 세션 TimeZone 이 {tz!r} 다 — naive 컬럼 저장값이 그 오프셋만큼 이동한다."
    )


@_requires_postgres
def test_aware_value_lands_unshifted_in_a_naive_column():
    """동작 축 — aware UTC 값이 naive 컬럼에 **그대로** 들어간다.

    세션 TZ 만 보는 것으로는 부족하다. 실제로 값이 안 밀리는지가 이 핀의 목적이다.
    """
    _, stored = _store_and_read(_build_connect_args(_PG_URL), "tz_probe_value")

    assert stored == _EXPECTED_NAIVE, (
        f"UTC 정오를 넣었는데 {stored} 로 저장됐다 (기대 {_EXPECTED_NAIVE}) — "
        f"차이 {stored - _EXPECTED_NAIVE}. 세션 TimeZone 이 UTC 가 아니다."
    )


@_requires_postgres
def test_the_shift_is_real_without_the_pin():
    """🔴 대조축 — 핀이 없으면 **실제로 밀린다**. 이게 없으면 위 두 축이 공허할 수 있다.

    CI 의 DB 기본 TimeZone 은 UTC 라, 핀을 지워도 위 두 축은 그대로 통과한다.
    그러면 「핀이 있어서 초록」인지 「원래 UTC 라서 초록」인지 구별되지 않는다.
    여기서 세션을 명시적으로 비-UTC 로 만들어 **기전이 실재함**을 보인다.

    Without this control, the two axes above pass on a UTC-default server even if the pin
    is deleted — they could not distinguish "pinned" from "happened to be UTC".
    """
    tz, shifted = _store_and_read({"options": "-c timezone=Asia/Seoul"}, "tz_probe_control")

    assert tz == "Asia/Seoul", f"대조 연결의 세션 TZ 설정 실패: {tz!r}"
    assert shifted - _EXPECTED_NAIVE == timedelta(hours=9), (
        f"Asia/Seoul(UTC+9) 세션인데 이동량이 {shifted - _EXPECTED_NAIVE} 다 — "
        "이 기전이 예상대로 동작하지 않는다면 위 두 축과 `_build_connect_args` 의 "
        "options 는 근거를 잃는다."
    )


# 🔴 **이 파일이 잡지 못하는 것**: CI 의 DB 기본 TimeZone 은 UTC 라, `_build_connect_args`
#    에서 options 를 지워도 위 두 축은 그대로 통과한다(원래 UTC 니까). 핀의 **존재**는
#    `tests/unit/test_database.py::test_postgres_connect_args_pin_the_session_timezone_to_utc`
#    가 환경과 무관하게 잡고, 이 파일은 그 핀이 **실제 서버에서 무엇을 하는지**를 잰다.
#    두 축은 대체재가 아니라 짝이다 — 어느 하나만으로는 "핀이 있고 효과가 있다" 를 못 낸다.
# What this file cannot catch: on a UTC-default server, deleting the pin still passes the two
# axes above. The unit test owns "the pin exists"; this file owns "the pin does something".
