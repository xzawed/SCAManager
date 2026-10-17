"""0048 — 개요 집계 인덱스 교체 회귀 가드 (검증 점수 부분 인덱스 → 기록된 점수 3열 인덱스).

0048 — regression guard for the overview aggregate index swap.

실 PostgreSQL 왕복과 ORM↔스키마 대조는 CI `pg-concurrency` 만 돈다
(`test_0020_round_trip` · `test_orm_alembic_parity`). 여기서는 로컬에서도 보이는 것 —
호출 순서 · 이름 · 열 · 잠금 대기 상한 — 을 `op` 모의로 잡는다.
"""
# pylint: disable=wrong-import-position
import importlib.util
import os
import pathlib
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from src.models.analysis import Analysis

_VERSIONS = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
_NEW = "ix_analyses_repo_scores"
_NEW_COLUMNS = ["repo_id", "score", "score_unreliable"]
_OLD = "ix_analyses_reliable_scores"
_OLD_WHERE = "score IS NOT NULL AND score_unreliable IS NOT TRUE"
_BOUND = "SET LOCAL lock_timeout = '5s'"


def _load():
    """alembic/versions/0048_*.py 동적 로드 — 0029 가드 패턴."""
    candidates = sorted(_VERSIONS.glob("0048_*.py"))
    assert len(candidates) == 1, f"alembic/versions/0048_*.py 가 정확히 하나여야 한다: {candidates}"
    spec = importlib.util.spec_from_file_location(f"alembic_0048_{candidates[0].stem}", candidates[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(step: str, dialect: str) -> list[tuple]:
    """`step`(upgrade|downgrade)을 `dialect` 모의 위에서 돌려 op 호출을 **순서대로** 모은다."""
    module = _load()
    calls: list[tuple] = []
    fake_bind = MagicMock()
    fake_bind.dialect.name = dialect
    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        mock_op.execute.side_effect = lambda sql, *_a, **_k: calls.append(("execute", str(sql)))
        mock_op.create_index.side_effect = (
            lambda name, table, columns, **kw: calls.append(("create_index", name, table, list(columns), kw)))
        mock_op.drop_index.side_effect = lambda name, **kw: calls.append(("drop_index", name, kw))
        getattr(module, step)()
    return calls


def _index_ops(calls: list[tuple]) -> list[tuple]:
    return [c for c in calls if c[0] != "execute"]


def test_revision_chain():
    module = _load()
    assert module.revision == "0048"
    assert module.down_revision == "0047"


def test_upgrade_builds_the_new_index_before_dropping_the_old_one():
    """🔴 만들고 나서 지운다 — `DROP INDEX` 의 ACCESS EXCLUSIVE(읽기까지 막는다)를 빌드 동안 쥐지 않는다.

    순서가 뒤집히면 한 트랜잭션 안에서 인덱스 빌드 내내 analyses 읽기가 멈춘다.
    새 인덱스는 부분 인덱스가 아니다 — 술어가 없어야 기록된 점수 집계와 옛 «검증 점수만» 모양
    둘 다 이 인덱스만으로 답한다.
    """
    ops = _index_ops(_run("upgrade", "postgresql"))
    assert [op[:2] for op in ops] == [("create_index", _NEW), ("drop_index", _OLD)], ops
    _, _, table, columns, kw = ops[0]
    assert (table, columns) == ("analyses", _NEW_COLUMNS), ops[0]
    assert not {k for k in kw if k.endswith("_where")}, f"새 인덱스에 부분 술어가 붙었다: {kw}"
    assert ops[1][2] == {"table_name": "analyses", "if_exists": True}, ops[1]


def test_upgrade_bounds_every_lock_wait_until_commit():
    """🔴 잠금 대기 상한 — 운영 마이그레이션 세션은 `lock_timeout = 0`·`statement_timeout = 2min` 이다(실측).

    상한이 없으면 열린 트랜잭션 하나가 `DROP INDEX` 를 세우고, 그 뒤에 줄 선 analyses 읽기가
    최대 2분 멈춘다(로컬 PG 17.6 재현: 대기 중 SELECT 가 상한까지 막혔다). 상한은 잠금 대기마다
    걸린다 — 읽기는 DROP 대기에만 막혀 5초 이내, 쓰기는 CREATE 가 잡은 SHARE 가 롤백까지 남아
    두 대기가 겹치면 약 10초까지 막힌다(Grok `17d38a6e` 반증 · 실측 5.8초). 상한을 넘기면
    트랜잭션 전체가 롤백되고 pre-deploy 가 실패해 이전 배포가 계속 서비스한다.

    🔴 상한을 **되돌리지 않는다** — DROP 이 잡은 ACCESS EXCLUSIVE 는 COMMIT 까지 남아, 그 뒤의
    대기(alembic_version 갱신 · 같은 트랜잭션의 다음 리비전)가 상한 없이 기다리면 그동안 analyses
    읽기가 멈춘다(Grok `17d38a6e` 2차 반증). `SET LOCAL` 은 트랜잭션이 끝나면 사라진다.
    """
    calls = _run("upgrade", "postgresql")
    kinds = [c[0] if c[0] != "execute" else c[1] for c in calls]
    assert kinds == [_BOUND, "create_index", "drop_index"], kinds


def test_sqlite_runs_the_same_index_swap_without_session_settings():
    """SQLite 에는 `SET LOCAL` 이 없다 — 인덱스 교체만 같은 순서로 돈다."""
    calls = _run("upgrade", "sqlite")
    assert [c for c in calls if c[0] == "execute"] == [], calls
    assert [op[:2] for op in _index_ops(calls)] == [("create_index", _NEW), ("drop_index", _OLD)]


def test_downgrade_restores_the_0046_partial_index():
    """되돌리면 0046 이 만든 부분 인덱스가 **같은 이름·열·술어**로 돌아온다(양 방언)."""
    calls = _run("downgrade", "postgresql")
    kinds = [c[0] if c[0] != "execute" else c[1] for c in calls]
    assert kinds == [_BOUND, "create_index", "drop_index"], kinds
    create, drop = _index_ops(calls)
    _, name, table, columns, kw = create
    assert (name, table, columns) == (_OLD, "analyses", ["repo_id", "score"]), create
    assert str(kw.get("postgresql_where")) == _OLD_WHERE, kw
    assert str(kw.get("sqlite_where")) == _OLD_WHERE, kw
    assert drop[1:] == (_NEW, {"table_name": "analyses", "if_exists": True}), drop
    # 되살리는 술어가 0046 원본과 같은 글자인가 — 다르면 왕복 뒤 스키마가 0047 과 갈린다.
    source_0046 = next(_VERSIONS.glob("0046_*.py")).read_text(encoding="utf-8")
    assert f'_INDEX = "{_OLD}"' in source_0046
    assert source_0046.count(f'"{_OLD_WHERE}"') == 2, "0046 의 양 방언 술어가 바뀌었다"


def test_the_model_declares_what_the_migration_creates():
    """🔴 모델과 마이그레이션이 **같은 인덱스**를 말한다 — 이름·열·순서·비부분.

    갈리면 운영에는 마이그레이션이 만든 인덱스가 남고 ORM 은 다른 것을 기대한다. 그 축
    (`test_orm_alembic_parity`)은 PostgreSQL 이 있을 때만 돌아 로컬에서는 보이지 않는다.
    옛 부분 인덱스가 모델에 되살아나도 여기서 red 다.
    """
    _, name, _, columns, _ = _index_ops(_run("upgrade", "postgresql"))[0]
    declared = {ix.name: ix for ix in Analysis.__table__.indexes}
    assert name in declared, f"모델이 {name} 을 선언하지 않는다 (선언된 것: {sorted(declared)})"
    assert [c.name for c in declared[name].columns] == columns
    for dialect in ("postgresql", "sqlite"):
        assert declared[name].dialect_options[dialect].get("where") is None, f"{dialect} 부분 술어가 있다"
    assert _OLD not in declared, f"모델에 지운 인덱스 {_OLD} 가 남아 있다"
