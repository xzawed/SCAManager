"""AI 폴백 원인이 **실제 DB 행**까지 간다 (#1446 완료 판정).

이슈의 완료 판정은 이렇게 적혀 있다:

> 인위적 400 과 529 가 **같은 분석 행에 서로 다른 값**으로 붙는다.

단위 테스트는 `review_code` 반환값과 `build_analysis_result_dict` 출력까지만 잰다.
그 사이에 **직렬화와 영속화**가 있다 — `Analysis.result` 는 SQLAlchemy `JSON`
컬럼이고, dict 가 맞아도 왕복에서 값이 바뀌거나(정수→문자열) 조용히 사라질 수 있다.
그리고 이 리포는 `SessionLocal` 을 MagicMock 으로 대체한 테스트가 ORM 속성 오류를
못 잡는다는 것을 이미 실측했다(`tests/unit/worker/test_pipeline.py` 의 fixture 가
그 형태다). 그래서 여기서는 **진짜 세션**으로 파이프라인을 끝까지 돌린다.

mock 하는 것: 파일 수집·정적분석·게이트·알림(외부 I/O).
mock 하지 않는 것: **`review_code` 자신** — anthropic 클라이언트만 예외를 던지게 한다.
그래야 `except` → `_default_result` → dict → JSON 컬럼 → SELECT 의 전 구간이 실행된다.

The unit tests stop at the dict; this drives the real save path so a serialization or
ORM-level regression cannot pass unnoticed.
"""
# pylint: disable=redefined-outer-name
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.database import Base, FailoverSessionFactory
from src.github_client.diff import ChangedFile
from src.models.analysis import Analysis

_PUSH = {
    "repository": {"full_name": "owner/repo"},
    "after": "cafe0000000000000000000000000000000000ff",
    "head_commit": {"id": "cafe0000000000000000000000000000000000ff", "message": "feat: x"},
    "commits": [{"id": "cafe0000000000000000000000000000000000ff", "message": "feat: x"}],
}


def _vendor_error(status_code):
    """실제 anthropic 예외 — SDK 가 그 코드에 매핑하는 클래스 그대로."""
    from anthropic import _exceptions  # pylint: disable=import-outside-toplevel

    cls = {400: _exceptions.BadRequestError, 529: _exceptions.OverloadedError}[status_code]
    response = httpx.Response(
        status_code, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    return cls("vendor said no", response=response, body=None)


@pytest.fixture()
def real_db():
    """진짜 SQLite 세션 — MagicMock 이 아니다 (ORM·직렬화 오류를 실제로 만난다)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = FailoverSessionFactory(engine)
    # 🔴 비용 로거는 `src.database.WorkerSessionLocal` 을 **함수 안에서** import 한다
    #    (BYPASSRLS 경로). 같은 DB 로 묶어야 그 write 까지 실제로 실행된다 — 안 묶으면
    #    fail-safe 로 조용히 삼켜져 그 구간이 이 테스트에서 dead 가 된다.
    with patch("src.worker.pipeline.SessionLocal", factory), \
         patch("src.database.WorkerSessionLocal", factory):
        yield factory


@pytest.fixture()
def no_external_io(monkeypatch):
    """외부 I/O 만 차단 — `review_code` 는 **진짜로 돈다**."""
    changed = [ChangedFile(filename="app.py", content="x = 1", patch="+x = 1")]
    monkeypatch.setattr("src.worker.pipeline.get_push_files", MagicMock(return_value=changed))
    monkeypatch.setattr("src.worker.pipeline.get_pr_files", MagicMock(return_value=changed))
    monkeypatch.setattr(
        "src.worker.pipeline._run_static_analysis", AsyncMock(return_value=[]),
    )
    monkeypatch.setattr("src.worker.pipeline.run_gate_check", AsyncMock())
    monkeypatch.setattr("src.worker.pipeline.build_notification_tasks", lambda *a, **kw: ([], []))


async def _run_with_vendor_error(status_code, sha):
    """anthropic 이 주어진 코드로 실패할 때 파이프라인을 끝까지 돌린다."""
    from src.worker.pipeline import run_analysis_pipeline  # pylint: disable=import-outside-toplevel

    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=_vendor_error(status_code))
    data = {**_PUSH,
            "after": sha,
            "head_commit": {"id": sha, "message": "feat: x"},
            "commits": [{"id": sha, "message": "feat: x"}]}
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=client):
        await run_analysis_pipeline("push", data)


def _row(factory, sha):
    with factory() as db:
        row = db.query(Analysis).filter(Analysis.commit_sha == sha).one_or_none()
        assert row is not None, f"분석 행이 저장되지 않았다 (sha={sha}) — 이 테스트가 공허하다"
        return dict(row.result or {})


@pytest.mark.usefixtures("no_external_io")
class TestTheCauseSurvivesPersistence:
    """원인이 JSON 컬럼 왕복을 견디는가."""

    async def test_400_and_529_land_as_different_values_on_their_rows(self, real_db):
        """🔴 이슈 #1446 의 완료 판정 — dict 가 아니라 **행**에서."""
        sha_400 = "a" * 40
        sha_529 = "b" * 40
        await _run_with_vendor_error(400, sha_400)
        await _run_with_vendor_error(529, sha_529)

        bad = _row(real_db, sha_400)
        overloaded = _row(real_db, sha_529)

        assert bad["ai_review_status"] == "api_error"
        assert overloaded["ai_review_status"] == "api_error"
        # 🔴 status 만 보면 두 행은 구별되지 않는다 — 그것이 이 이슈였다.
        assert bad["ai_review_error_status_code"] == 400
        assert overloaded["ai_review_error_status_code"] == 529
        assert bad["ai_review_error_type"] != overloaded["ai_review_error_type"]

    async def test_status_code_survives_json_roundtrip_as_an_integer(self, real_db):
        """🔴 int 로 나가고 int 로 돌아오는가.

        dict 단계 테스트는 파이썬 객체를 본다. JSON 컬럼을 통과하면 타입이
        바뀔 수 있고(예: 문자열화), 그러면 `WHERE ... = 529` 가 조용히 0건이 된다.
        """
        sha = "c" * 40
        await _run_with_vendor_error(529, sha)

        stored = _row(real_db, sha)["ai_review_error_status_code"]
        assert isinstance(stored, int), f"정수가 아니다: {type(stored).__name__} — 숫자 비교 쿼리가 무너진다"
        assert stored == 529

    async def test_the_exception_body_never_reaches_the_row(self, real_db):
        """🔴 금지선 — 저장된 행 전체에 예외 본문이 없어야 한다.

        `analyses.result` 는 대시보드·알림으로 그대로 흐른다. 여기 새면 끝이다.
        """
        import json  # pylint: disable=import-outside-toplevel

        sha = "d" * 40
        await _run_with_vendor_error(400, sha)

        blob = json.dumps(_row(real_db, sha), default=str)
        assert "vendor said no" not in blob, "예외 본문이 분석 행에 저장됐다"
        # 대조군 — 이 행이 실제로 실패를 담고 있어야 위 단언이 공허하지 않다.
        assert "BadRequestError" in blob

    async def test_a_successful_row_carries_the_keys_as_null_not_absent(self, real_db):
        """🔴 성공 행에도 두 키가 **있다**(값 null) — Grok claim-review `01a019d1` V5.

        위 세 축은 실패 행만 본다. 그러면 「키가 없다」가 *"실패가 아니었다"* 와
        *"이 필드 이전의 낡은 행"* 두 가지를 뜻하게 되고, 사후 분류 쿼리는
        `WHERE result ? 'ai_review_error_type'` 로 낡은 행을 걸러야 한다.

        이 모호함은 가정이 아니라 **실측**이다 — 운영 DB 에서 `ai_review_truncated`
        키가 3,475행에 아예 없다(`json_typeof(...) IS NULL`). 같은 것을 새로 만들지
        않는다는 주장을, 그 주장이 성립하는 유일한 경로(성공 저장)에서 확인한다.
        """
        import json  # pylint: disable=import-outside-toplevel

        from src.worker.pipeline import (  # pylint: disable=import-outside-toplevel
            run_analysis_pipeline,
        )

        sha = "e" * 40
        block = MagicMock(type="text", text=json.dumps({
            "commit_message_score": 18, "direction_score": 19, "test_score": 8,
            "summary": "looks fine", "suggestions": [],
        }))
        response = MagicMock(content=[block], stop_reason="end_turn",
                             usage=MagicMock(input_tokens=10, output_tokens=20,
                                             cache_read_input_tokens=0,
                                             cache_creation_input_tokens=0))
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=response)
        data = {**_PUSH, "after": sha,
                "head_commit": {"id": sha, "message": "feat: x"},
                "commits": [{"id": sha, "message": "feat: x"}]}
        with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=client):
            await run_analysis_pipeline("push", data)

        stored = _row(real_db, sha)
        assert stored["ai_review_status"] == "success", (
            "성공 경로가 아니다 — 이 테스트가 검사하려는 축을 못 탔다"
        )
        assert "ai_review_error_type" in stored, "성공 행에 키가 없다 — 「키 없음」이 모호해진다"
        assert "ai_review_error_status_code" in stored
        assert stored["ai_review_error_type"] is None
        assert stored["ai_review_error_status_code"] is None

    async def test_the_cost_row_carries_no_exception_body_either(self, real_db):
        """🔴 두 번째 sink — `claude_api_calls` 도 훑는다 (Grok claim-review `01a019d1` V2).

        위 유출 검사는 `analyses` 행만 본다. 그런데 같은 실패 1건이 **두 곳**에
        기록된다: 분석 행과 비용 행(`log_claude_api_call` 의 `finally`). 한쪽만
        훑으면 「본문을 저장하지 않는다」는 주장이 절반만 참이 된다.
        """
        from src.models.claude_api_call import (  # pylint: disable=import-outside-toplevel
            ClaudeApiCall,
        )

        sha = "f" * 40
        await _run_with_vendor_error(400, sha)

        with real_db() as db:
            calls = db.query(ClaudeApiCall).all()
            assert calls, "비용 행이 없다 — 이 sink 가 이 테스트에서 dead 다"
            for call in calls:
                blob = " ".join(str(v) for v in vars(call).values() if not callable(v))
                assert "vendor said no" not in blob, "예외 본문이 비용 행에 저장됐다"
            # 대조군 — 실패가 실제로 기록됐어야 위 단언이 공허하지 않다.
            assert any(c.error_type == "BadRequestError" for c in calls), (
                f"실패가 비용 행에 안 남았다: {[(c.status, c.error_type) for c in calls]}"
            )
