"""log_claude_api_call 영속화 wire — record 호출 + DB 에러 fail-safe(no raise).
Cost persistence wire — calls record + swallows DB errors (fail-safe)."""
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.claude_api_call import ClaudeApiCall
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401
from src.shared.claude_metrics import log_claude_api_call


def test_persists_via_helper():
    with patch("src.shared.claude_metrics._persist_cost") as p:
        log_claude_api_call(model="claude-sonnet-4-6", duration_ms=10, input_tokens=1,
                            output_tokens=1, status="success", repo_id=3)
        assert p.called
        assert p.call_args.kwargs["repo_id"] == 3


def test_persist_failure_is_swallowed():
    # _persist_cost 가 raise 해도 log_claude_api_call 은 예외 미전파(API 흐름 보호).
    with patch("src.shared.claude_metrics._persist_cost", side_effect=RuntimeError("db down")):
        log_claude_api_call(model="m", duration_ms=1, input_tokens=0, output_tokens=0, status="success")
    # 예외 없이 반환 = 통과


def test_user_id_passed():
    with patch("src.shared.claude_metrics._persist_cost") as p:
        log_claude_api_call(model="claude-haiku-4-5", duration_ms=5, input_tokens=0,
                            output_tokens=0, status="success", user_id=7)
        assert p.call_args.kwargs["user_id"] == 7


def test_real_wire_writes_row_without_patching_persist_cost(monkeypatch):
    """_persist_cost 를 패치하지 않고 실 배선 검증 — log_claude_api_call → _persist_cost →
    claude_api_cost_repo.record → INSERT 까지 전부 실행해 실제로 1행 기록되는지 확인.
    이 테스트가 없으면 import/session/table 배선 버그가 fail-safe 에 묻혀 CI 에서 안 보이고
    운영에서만 비용 행이 조용히 유실될 수 있다 (다른 테스트들은 _persist_cost 자체를 패치해
    fail-safe 계약만 검증하므로 이 배선은 검증하지 않음).
    Real-wire check — no patching of `_persist_cost`; exercises the full
    `log_claude_api_call -> _persist_cost -> claude_api_cost_repo.record -> INSERT` path and
    confirms exactly one row is actually written. Without this test, an import/session/table
    wiring bug would be swallowed by the fail-safe and invisible in CI, silently dropping cost
    rows only in production (the other tests here patch `_persist_cost` itself, so they only
    cover the fail-safe contract, not this wire)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    real_session_local = sessionmaker(bind=engine)

    # 실제 흐름 재현용 최소 seed(repo/user) — SQLite 는 FK 를 enforce 하지 않지만 귀속 컬럼 검증을 위해 포함.
    # Minimal seed (repo/user) to mirror the real flow — SQLite doesn't enforce FKs, but this
    # lets us assert the attribution columns round-trip correctly.
    with real_session_local() as seed_db:
        seed_db.add_all([
            User(id=1, github_id="1", github_login="u1", email="u1@x.com", display_name="U1"),
            Repository(id=1, full_name="u1/repo", user_id=1),
        ])
        seed_db.commit()

    # `_persist_cost` 내부의 `from src.database import WorkerSessionLocal as SessionLocal` 가
    # 호출 시점에 매번 재-import 하므로, 모듈 속성 자체를 patch 하면 그대로 반영된다.
    # `_persist_cost`'s `from src.database import WorkerSessionLocal as SessionLocal` re-imports
    # on every call, so patching the module attribute itself takes effect.
    monkeypatch.setattr("src.database.WorkerSessionLocal", real_session_local)

    log_claude_api_call(
        model="claude-sonnet-4-6", duration_ms=10, input_tokens=100, output_tokens=50,
        status="success", repo_id=1, user_id=1,
    )

    with real_session_local() as check_db:
        rows = check_db.query(ClaudeApiCall).all()
        assert len(rows) == 1
        assert rows[0].model == "claude-sonnet-4-6"
        # sonnet: (100*3.0 + 50*15.0) / 1_000_000 = 0.00105
        assert rows[0].cost_usd == pytest.approx(0.00105)
        assert rows[0].repo_id == 1
        assert rows[0].user_id == 1
