"""CLI 훅 분석이 full 정적분석을 **가리지 못하게** 하는 봉인 (2026-07-30 감사 결정 ①).

CLI hook analyses must not shadow the webhook's full static analysis.

## 왜 필요한가 (실측 사고)

`src/api/hook.py` 는 `calculate_score([], ...)` 로 정적 45/45 를 **무검증 부여**한다(CLI 훅은
분석기를 한 번도 돌리지 않는다). 그 Analysis 행이 `_ensure_repo`/`_save_and_gate` 의
`find_by_sha` dedup 을 만족시키면:

  1. PR 이벤트가 와도 webhook 의 full 정적분석이 **영영 실행되지 않는다**
  2. `_regate_pr_if_needed` 가 그 무검증 결과에 pr_number 를 붙여 gate 를 돌린다
  3. 즉 CLI 훅을 설치한 리포는 **PR 이 실제 정적분석 없이 확정**된다

`static_analysis_incomplete` 마커(#1243)가 무검증 머지는 막았지만, 그 부작용으로 semi-auto
승인 버튼까지 막혀 사람이 판단할 창구가 사라졌다. 근본 해결 = **CLI 결과를 게이트 입력으로
쓰지 않고 full 분석으로 교체**한다.

## 봉인 계약

- `_is_cli_only` 가 dedup 예외·supersede·regate 회피 **3곳의 단일 출처** (갈라지면 full 분석이
  매번 재계산됐다가 버려진다)
- 교체는 **제자리(in-place)** — row id 유지로 analysis_feedback·gate_decisions FK 보존
- 교체 후 `source` 가 pr/push 가 되므로 다음 이벤트부터 통상 dedup 재개(무한 재분석 없음)
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.worker.pipeline import _ensure_repo, _is_cli_only, _regate_pr_if_needed


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _repo(db) -> Repository:
    repo = Repository(full_name="owner/repo")
    db.add(repo)
    db.flush()
    return repo


def _add(db, repo, sha: str, source: str, pr_number=None) -> Analysis:
    a = Analysis(
        repo_id=repo.id, commit_sha=sha, pr_number=pr_number, score=89, grade="B",
        result={"score": 89, "grade": "B", "source": source, "ai_review_status": "success"},
    )
    db.add(a)
    db.commit()
    return a


# ── _is_cli_only — 3곳이 공유하는 단일 출처 ────────────────────────────────

def test_is_cli_only_true_for_cli_source(db_session):
    repo = _repo(db_session)
    assert _is_cli_only(_add(db_session, repo, "sha_cli", "cli")) is True


@pytest.mark.parametrize("source", ["pr", "push"])
def test_is_cli_only_false_for_webhook_sources(db_session, source):
    repo = _repo(db_session)
    assert _is_cli_only(_add(db_session, repo, f"sha_{source}", source)) is False


def test_is_cli_only_false_when_result_missing(db_session):
    """result=None(구 레코드)은 CLI 로 단정하지 않는다 — 오판 시 무한 재분석."""
    repo = _repo(db_session)
    a = Analysis(repo_id=repo.id, commit_sha="sha_none", result=None)
    db_session.add(a)
    db_session.commit()
    assert _is_cli_only(a) is False


# ── dedup 예외 — CLI 행은 full 분석을 막지 않는다 ──────────────────────────

def test_ensure_repo_does_not_dedup_on_cli_analysis(db_session):
    """🔴 핵심: CLI 행이 있어도 `_ensure_repo` 가 None 을 반환하지 않아야 full 분석이 진행된다."""
    repo = _repo(db_session)
    _add(db_session, repo, "sha_cli", "cli")
    assert _ensure_repo(db_session, "owner/repo", "sha_cli") is not None


def test_ensure_repo_still_dedups_on_webhook_analysis(db_session):
    """대조군 — 통상 dedup 은 그대로 (교체 로직이 멱등성을 깨지 않았는지)."""
    repo = _repo(db_session)
    _add(db_session, repo, "sha_pr", "pr")
    assert _ensure_repo(db_session, "owner/repo", "sha_pr") is None


# ── regate 회피 — CLI 결과로 게이트하지 않는다 ─────────────────────────────

async def test_regate_skips_cli_only_analysis(db_session):
    """CLI 행에는 pr_number 를 붙이지도, gate 를 돌리지도 않는다."""
    repo = _repo(db_session)
    cli = _add(db_session, repo, "sha_cli", "cli")
    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await _regate_pr_if_needed(db_session, "owner/repo", "sha_cli", pr_number=7)
    mock_gate.assert_not_awaited()
    db_session.refresh(cli)
    assert cli.pr_number is None, "CLI 행에 pr_number 가 붙으면 그 SHA 가 무검증으로 확정된다"


async def test_regate_still_gates_push_analysis(db_session):
    """대조군 — push 분석은 기존대로 regate 된다(이 변경이 정상 경로를 막지 않았는지)."""
    repo = _repo(db_session)
    pushed = _add(db_session, repo, "sha_push", "push")
    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await _regate_pr_if_needed(db_session, "owner/repo", "sha_push", pr_number=7)
    mock_gate.assert_awaited_once()
    db_session.refresh(pushed)
    assert pushed.pr_number == 7


# ── supersede 본경로 — Grok claim-review P0 (이전엔 미검증이었다) ──────────

def test_claim_and_supersede_replaces_row_in_place(db_session):
    """🔴 교체가 **제자리**로 일어나 row id 가 유지되는가 (FK 보존의 근거)."""
    from types import SimpleNamespace

    from src.worker.pipeline import _claim_and_supersede_cli

    repo = _repo(db_session)
    cli = _add(db_session, repo, "sha_x", "cli")
    original_id = cli.id

    params = SimpleNamespace(
        commit_sha="sha_x", commit_message="full analysis", pr_number=7,
        score_result=SimpleNamespace(total=42, grade="D"), author_login="dev",
        ai_review=SimpleNamespace(used_model="m", input_tokens=1, output_tokens=2),
    )
    full = {"score": 42, "grade": "D", "source": "pr", "ai_review_status": "success"}
    out = _claim_and_supersede_cli(db_session, cli, params, full, False)

    assert out is not None, "claim 승자는 교체된 행을 반환해야 한다"
    assert out.id == original_id, "row id 가 바뀌면 analysis_feedback·gate_decisions FK 가 깨진다"
    db_session.refresh(out)
    assert out.result["source"] == "pr", "source 가 전환돼야 다음 이벤트 dedup 이 재개된다"
    assert out.score == 42 and out.grade == "D"
    assert out.pr_number == 7
    assert _is_cli_only(out) is False, "교체 후에도 CLI 로 보이면 매 이벤트 재분석 루프가 된다"


def test_claim_returns_none_when_row_already_superseded(db_session):
    """🔴 동시 webhook 2건 중 **패자**는 None 을 받아 이중 gate/notify 로 가지 않는다."""
    from types import SimpleNamespace

    from src.worker.pipeline import _claim_and_supersede_cli

    repo = _repo(db_session)
    cli = _add(db_session, repo, "sha_y", "cli")
    # 승자가 이미 교체를 끝낸 상태를 재현 — source 가 더 이상 cli 가 아니고 점수도 승자 값이다
    cli.result = {"score": 42, "grade": "D", "source": "pr"}
    cli.score, cli.grade = 42, "D"
    db_session.commit()

    params = SimpleNamespace(
        commit_sha="sha_y", commit_message="m", pr_number=7,
        score_result=SimpleNamespace(total=1, grade="F"), author_login=None,
        ai_review=SimpleNamespace(used_model=None, input_tokens=None, output_tokens=None),
    )
    out = _claim_and_supersede_cli(db_session, cli, params, {"source": "pr"}, False)
    assert out is None, "패자가 None 을 못 받으면 gate·notify 가 두 번 실행된다"
    db_session.refresh(cli)
    assert cli.score == 42, "패자가 승자의 결과를 덮어쓰면 안 된다"
