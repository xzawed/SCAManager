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
from sqlalchemy.pool import StaticPool

from src.analyzer.io.ai_review import AiReviewResult
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
         patch("src.webhook.providers.github.SessionLocal", factory):
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
        lambda filename, content, repo_config=None: __import__(
            "src.analyzer.io.static", fromlist=["StaticAnalysisResult"]
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


def _post_webhook(client: TestClient, event: str, payload: dict):
    """서명된 웹훅 1건 전송 후 응답을 돌려준다(재전송 시나리오가 상태코드를 본다).
    Send one signed webhook and return the response (the redelivery scenario asserts on it)."""
    payload_bytes = json.dumps(payload).encode("utf-8")
    return client.post(
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
# Scenario 3: invalid signature → 401, pipeline must not run.
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


# ---------------------------------------------------------------------------
# 시나리오 4: synchronize 이벤트 — 새 SHA 도착 시 두 번째 Analysis 생성
# ---------------------------------------------------------------------------

def test_pr_synchronize_updates_analysis(integration_db, mock_deps):
    """synchronize 이벤트(새 SHA)가 도착하면 두 번째 Analysis 행이 생성된다."""
    repo = "owner/repo-sync"
    sha1 = "sha_first_0000001"
    sha2 = "sha_second_000002"
    pr_num = 99

    client = TestClient(app)

    # 1. PR opened (sha1)
    _post_webhook(client, "pull_request", _pr_payload(repo, sha1, pr_num, action="opened"))

    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        assert db_repo is not None
        analyses = session.query(Analysis).filter_by(repo_id=db_repo.id).all()
        assert len(analyses) == 1
        assert analyses[0].commit_sha == sha1
    finally:
        session.close()

    # 2. PR synchronize (sha2) → 새 Analysis 행 생성
    _post_webhook(client, "pull_request", _pr_payload(repo, sha2, pr_num, action="synchronize"))

    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        analyses = (
            session.query(Analysis)
            .filter_by(repo_id=db_repo.id)
            .order_by(Analysis.id)
            .all()
        )
        assert len(analyses) == 2, "synchronize 이벤트는 새 SHA 에 대해 새 Analysis 를 생성해야 함"
        shas = {a.commit_sha for a in analyses}
        assert sha1 in shas and sha2 in shas
        second = next(a for a in analyses if a.commit_sha == sha2)
        assert second.pr_number == pr_num
    finally:
        session.close()

    assert mock_deps.call_count == 2, "각 이벤트마다 run_gate_check 1회 — 총 2회"


# ---------------------------------------------------------------------------
# 시나리오 5: gate block — build_notification_tasks 는 gate 결과와 무관하게 호출
# ---------------------------------------------------------------------------

def test_gate_block_triggers_notifier(integration_db, mock_deps):
    """gate check 실행 후 build_notification_tasks 가 항상 호출되는지 검증."""
    repo = "owner/repo-notifier"
    sha = "sha_notifier_test0"
    pr_num = 55

    client = TestClient(app)
    notify_mock = MagicMock(return_value=([], []))

    with patch("src.worker.pipeline.build_notification_tasks", notify_mock):
        _post_webhook(client, "pull_request", _pr_payload(repo, sha, pr_num))

    mock_deps.assert_called_once()
    notify_mock.assert_called_once()
    _, kw = notify_mock.call_args
    assert kw["repo_name"] == repo
    assert kw["pr_number"] == pr_num


# ---------------------------------------------------------------------------
# 시나리오 6: **동일 페이로드 재전송** — GitHub "Redeliver" / 202 이후 지연 재시도
# Scenario 6: identical redelivery — GitHub's "Redeliver" button / a late retry after 202.
#
# 🔴 왜 이 축이 따로 필요한가
#
# 위 5개 시나리오는 전부 **서로 다른 이벤트**를 보낸다(push→PR, 새 PR, 잘못된 서명,
# synchronize=새 SHA, 알림). 같은 서명 페이로드를 **두 번** 보내는 축은 없었다.
# 그런데 재전송은 예외 상황이 아니라 **운영자가 누르는 버튼**이고 GitHub 플랫폼이
# 지연 재시도로도 만든다 — 즉 상시 입력이다.
#
# 재전송을 막는 것은 `pipeline.py` `_regate_pr_if_needed` 의 이른 반환:
#     if existing is None or existing.pr_number == pr_number:
#         return
# 이 한 줄이 단순화되면 같은 SHA 에 대해 게이트가 다시 돌아 **리뷰 코멘트 2회 ·
# auto-merge 2회 · Telegram 승인 프롬프트 2회**가 나간다. SHA 유니크 제약과
# `claim_decision` 은 이 경로를 덮지 않는다 — 자동 승인은 `approve.py` 의 upsert 라
# 재기록될 수 있다.
#
# The five scenarios above all send *different* events; none sends the same signed payload
# twice. Redelivery is a normal, operator-generated input, and the only thing stopping a
# double gate is one early-return in `_regate_pr_if_needed`.
# ---------------------------------------------------------------------------

def test_identical_pr_webhook_redelivery_does_not_regate(integration_db, mock_deps):
    """동일 (repo, sha, pr_number) 이벤트 2회 → 분석 1건 · 게이트 1회 · 알림 1회.

    Identical redelivery must not produce a second Analysis, gate run, or notification.
    """
    repo = "owner/repo-redelivery"
    sha = "sha_redeliver_0001"
    pr_num = 21

    client = TestClient(app)
    notify_mock = MagicMock(return_value=([], []))
    payload = _pr_payload(repo, sha, pr_num)

    with patch("src.worker.pipeline.build_notification_tasks", notify_mock):
        first = _post_webhook(client, "pull_request", payload)
        second = _post_webhook(client, "pull_request", payload)  # 🔴 완전히 동일한 재전송

    # ① 재전송은 인증 실패가 아니다 — 서명은 여전히 유효하므로 202 로 받아야 한다.
    #    (401/500 을 돌려주면 GitHub 배달 로그가 빨개져 운영자가 진짜 장애와 구별 못 한다.)
    #    A replay is not an auth failure; the signature is still valid, so it must be accepted.
    assert first.status_code == 202, f"1차 전송이 202 가 아니다: {first.status_code}"
    assert second.status_code == 202, f"재전송이 202 가 아니다: {second.status_code}"

    # ② 분석 행은 1건, pr_number 는 그대로.
    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        assert db_repo is not None, "재전송 처리 중 리포 행이 사라졌다"
        analyses = session.query(Analysis).filter_by(repo_id=db_repo.id).all()
        assert len(analyses) == 1, (
            f"재전송이 Analysis 를 {len(analyses)}건 만들었다 — 동일 SHA 는 1건이어야 한다"
        )
        assert analyses[0].pr_number == pr_num, "재전송이 pr_number 를 바꿨다"
    finally:
        session.close()

    # ③ 게이트는 1회 — 2회면 리뷰 코멘트·auto-merge·승인 프롬프트가 중복 발사된다.
    assert mock_deps.call_count == 1, (
        f"재전송이 run_gate_check 를 {mock_deps.call_count}회 호출했다 — "
        "중복 리뷰 코멘트·중복 auto-merge·중복 Telegram 승인 프롬프트가 나간다"
    )

    # ④ 알림도 1회 — ③ 이 막혀도 알림 경로가 따로 새면 사용자에겐 2회로 보인다.
    assert notify_mock.call_count == 1, (
        f"재전송이 알림 빌드를 {notify_mock.call_count}회 호출했다 — 사용자에게 중복 통지"
    )


def test_same_sha_different_pr_does_not_steal_the_gate(integration_db, mock_deps):
    """대조군 — 같은 SHA 라도 **다른 PR#** 는 first-writer-wins 로 게이트를 뺏지 못한다.

    ⓷ 이 "2회 호출을 무조건 막는" 것으로 오해되면 안 된다. 막는 근거는 *동일성*이지
    *2회라는 횟수*가 아니다. 이 대조군이 없으면 `_regate_pr_if_needed` 를 통째로
    `return` 으로 바꿔도 위 테스트가 통과한다 — 그건 재전송 방어가 아니라 기능 삭제다.

    Control axis: the guard's basis is *identity*, not *call count*. Without this, stubbing
    the whole function to `return` would satisfy the test above.
    """
    repo = "owner/repo-same-sha-two-prs"
    sha = "sha_two_prs_0001"

    client = TestClient(app)
    _post_webhook(client, "pull_request", _pr_payload(repo, sha, 31))
    _post_webhook(client, "pull_request", _pr_payload(repo, sha, 32))  # 같은 SHA, 다른 PR#

    session = integration_db()
    try:
        db_repo = session.query(Repository).filter_by(full_name=repo).first()
        analyses = session.query(Analysis).filter_by(repo_id=db_repo.id).all()
        assert len(analyses) == 1, "동일 SHA 는 유니크 — 2건이면 제약이 깨진 것"
        assert analyses[0].pr_number == 31, (
            f"두번째 PR #32 가 게이트를 뺏었다(pr_number={analyses[0].pr_number}) — "
            "first-writer-wins 위반, 잘못된 PR 에 게이트 액션이 적용된다"
        )
    finally:
        session.close()
