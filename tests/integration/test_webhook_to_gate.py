"""Integration tests: HTTP webhook → BackgroundTask → pipeline → gate.

실제로 실행하는 것: run_analysis_pipeline, _regate_pr_if_needed, DB(SQLite), 서명 검증
Mock 대상: get_pr_files/get_push_files, review_code, analyze_file, run_gate_check, build_notification_tasks
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.analyzer.ai_review import AiReviewResult
from src.database import Base, FailoverSessionFactory
from src.github_client.diff import ChangedFile
from src.main import app
from src.models.analysis import Analysis
from src.models.repository import Repository

SECRET = "test_secret"  # tests/conftest.py:7 과 일치


def _sign(payload: bytes) -> str:
    mac = hmac.new(SECRET.encode(), payload, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def _fake_ai_review() -> AiReviewResult:
    return AiReviewResult(
        commit_score=15,
        ai_score=15,
        test_score=7,
        summary="테스트 리뷰",
        suggestions=[],
        status="success",
    )


@pytest.fixture()
def integration_db():
    """SQLite in-memory DB(StaticPool)를 pipeline·router 양쪽 SessionLocal에 주입한다.

    StaticPool: 모든 연결이 동일한 in-memory DB 커넥션을 공유 → 세션 간 테이블 가시성 보장.
    FailoverSessionFactory에 Engine 객체를 직접 전달(database.py:88 지원).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    factory = FailoverSessionFactory(engine)  # Engine 객체 직접 전달

    with patch("src.worker.pipeline.SessionLocal", factory), \
         patch("src.webhook.router.SessionLocal", factory):
        yield factory._primary_maker  # 테스트 assertions용 sessionmaker 반환


@pytest.fixture()
def mock_deps(monkeypatch):
    """외부 I/O 의존성을 모두 차단한다. run_gate_check mock을 반환한다."""
    changed = [ChangedFile(filename="a.py", content="x = 1", patch="+x = 1")]
    monkeypatch.setattr("src.worker.pipeline.get_pr_files", MagicMock(return_value=changed))
    monkeypatch.setattr("src.worker.pipeline.get_push_files", MagicMock(return_value=changed))
    monkeypatch.setattr("src.worker.pipeline.review_code", AsyncMock(return_value=_fake_ai_review()))
    monkeypatch.setattr(
        "src.worker.pipeline.analyze_file",
        lambda filename, content: __import__(
            "src.analyzer.static", fromlist=["StaticAnalysisResult"]
        ).StaticAnalysisResult(filename=filename),
    )
    gate_mock = AsyncMock()
    monkeypatch.setattr("src.worker.pipeline.run_gate_check", gate_mock)
    monkeypatch.setattr("src.worker.pipeline.build_notification_tasks", lambda *a, **kw: ([], []))
    return gate_mock


def _push_payload(repo: str, sha: str) -> dict:
    return {
        "repository": {"full_name": repo},
        "after": sha,
        "commits": [{"message": "test: push commit"}],
        "head_commit": {"message": "test: push commit"},
    }


def _pr_payload(repo: str, sha: str, pr_number: int, action: str = "opened") -> dict:
    return {
        "action": action,
        "number": pr_number,
        "repository": {"full_name": repo},
        "pull_request": {
            "head": {"sha": sha, "ref": "feature/test"},
            "title": "test PR",
            "body": "",
        },
    }


def _post_webhook(client: TestClient, event: str, payload: dict) -> None:
    payload_bytes = json.dumps(payload).encode("utf-8")
    client.post(
        "/webhooks/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": _sign(payload_bytes),
            "Content-Type": "application/json",
        },
    )


# ---------------------------------------------------------------------------
# 시나리오 1: push 먼저 → 동일 SHA PR opened → re-gate
# ---------------------------------------------------------------------------

def test_push_then_pr_regate(integration_db, mock_deps):
    """push 이벤트 후 동일 SHA로 PR 이벤트 도착 시 Analysis 1건 + run_gate_check 1회."""
    repo = "owner/repo-regate"
    sha = "abc1234"
    pr_num = 42

    client = TestClient(app)

    # 1. push 이벤트 → Analysis 생성 (pr_number=None)
    _post_webhook(client, "push", _push_payload(repo, sha))

    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        assert db_repo is not None, "Repository 미생성"
        analyses = session.query(Analysis).filter_by(repo_id=db_repo.id).all()
        assert len(analyses) == 1
        assert analyses[0].pr_number is None
        assert analyses[0].commit_sha == sha
    finally:
        session.close()

    # 2. PR opened 이벤트 → _regate_pr_if_needed 경로
    _post_webhook(client, "pull_request", _pr_payload(repo, sha, pr_num))

    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        analyses = session.query(Analysis).filter_by(repo_id=db_repo.id).all()
        assert len(analyses) == 1, "Analysis가 중복 생성되면 안 됨"
        assert analyses[0].pr_number == pr_num, "pr_number가 업데이트되어야 함"
    finally:
        session.close()

    assert mock_deps.call_count == 1, "run_gate_check는 정확히 1회 호출되어야 함"


# ---------------------------------------------------------------------------
# 시나리오 2: 신규 SHA PR opened → 정상 분석 + gate
# ---------------------------------------------------------------------------

def test_new_pr_analysis_and_gate(integration_db, mock_deps):
    """PR opened 첫 이벤트: Analysis 1건 생성, pr_number 저장, run_gate_check 1회."""
    repo = "owner/repo-new-pr"
    sha = "def5678"
    pr_num = 7

    client = TestClient(app)
    _post_webhook(client, "pull_request", _pr_payload(repo, sha, pr_num))

    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        assert db_repo is not None
        analyses = session.query(Analysis).filter_by(repo_id=db_repo.id).all()
        assert len(analyses) == 1
        assert analyses[0].pr_number == pr_num
        assert analyses[0].commit_sha == sha
        assert analyses[0].score is not None
    finally:
        session.close()

    assert mock_deps.call_count == 1


# ---------------------------------------------------------------------------
# 시나리오 3: 잘못된 서명 → 401, 파이프라인 미실행
# ---------------------------------------------------------------------------

def test_invalid_signature_returns_401(integration_db, mock_deps):
    """HMAC 서명 불일치 시 401 응답, Analysis 미생성, 파이프라인 미호출."""
    repo = "owner/repo-invalid-sig"
    sha = "ghi9012"
    payload_bytes = json.dumps(_push_payload(repo, sha)).encode("utf-8")

    client = TestClient(app)
    response = client.post(
        "/webhooks/github",
        content=payload_bytes,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=invalidsignature",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    mock_deps.assert_not_called()

    session = integration_db()
    try:
        count = session.query(Analysis).count()
        assert count == 0, "서명 실패 시 Analysis가 생성되면 안 됨"
    finally:
        session.close()
