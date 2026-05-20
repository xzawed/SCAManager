"""repo_insight_service + dashboard_service 언어별 프롬프트 생성 검증.

Verifies that the `language` parameter controls the Claude prompt's
response-language instruction for both insight services.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401  side-effect: populate Base.metadata
from src.database import Base
from src.models.repository import Repository
from src.models.user import User


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션.

    Provides an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def repo(db):
    """user + repo 1건 seed — repo_insight_narrative FK 충족용.

    Seeds one user + repo so repo_insight_narrative has valid FK.
    """
    user = User(github_id=77, github_login="langtest", email="lt@x.com", display_name="LT")
    db.add(user)
    db.commit()
    db.refresh(user)
    r = Repository(full_name="owner/langtest", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ─── repo_insight_service 언어 프롬프트 테스트 ─────────────────────────────


def _make_repo_mock_client(text: str) -> AsyncMock:
    """repo_insight_narrative용 AsyncAnthropic 클라이언트 mock 생성 헬퍼.

    Helper that creates an AsyncAnthropic mock for repo_insight_narrative tests.
    """
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=text)]
    mock_msg.usage = MagicMock(input_tokens=10, output_tokens=20)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)
    return mock_client


class TestRepoInsightLanguagePrompt:
    """repo_insight_narrative — language 파라미터가 프롬프트 언어를 제어하는지 검증."""

    @pytest.mark.asyncio
    async def test_prompt_uses_korean_when_language_ko(self, db, repo):
        """language='ko' → 프롬프트에 'Korean' 포함."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_client = _make_repo_mock_client('{"text": "테스트"}')

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
                   return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 3, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
                language="ko",
            )

        # call_args.kwargs["messages"][0]["content"] 에 언어 지시 포함 검증
        # Verify the prompt message contains the language instruction.
        user_prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "Korean" in user_prompt

    @pytest.mark.asyncio
    async def test_prompt_uses_english_when_language_en(self, db, repo):
        """language='en' → 프롬프트에 'English' 포함, 'Korean' 미포함."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_client = _make_repo_mock_client('{"text": "test"}')

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
                   return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 3, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
                language="en",
            )

        user_prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "English" in user_prompt
        assert "Korean" not in user_prompt

    @pytest.mark.asyncio
    async def test_prompt_uses_japanese_when_language_ja(self, db, repo):
        """language='ja' → 프롬프트에 'Japanese' 포함."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_client = _make_repo_mock_client('{"text": "テスト"}')

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
                   return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 3, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
                language="ja",
            )

        user_prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "Japanese" in user_prompt


# ─── dashboard_service 언어 프롬프트 테스트 ───────────────────────────────


class TestDashboardInsightLanguagePrompt:
    """_build_insight_user_prompt — language 파라미터 유무 및 언어 지시 검증."""

    def test_build_prompt_ko_contains_korean_instruction(self):
        """language='ko' → user prompt에 한국어 지시 포함."""
        from src.services.dashboard_service import _build_insight_user_prompt
        prompt = _build_insight_user_prompt(
            days=7, kpi={}, trend=[], frequent=[], auto_merge={}, language="ko",
        )
        assert "Korean" in prompt

    def test_build_prompt_en_contains_english_instruction(self):
        """language='en' → user prompt에 영어 지시 포함, 한국어 지시 미포함."""
        from src.services.dashboard_service import _build_insight_user_prompt
        prompt = _build_insight_user_prompt(
            days=7, kpi={}, trend=[], frequent=[], auto_merge={}, language="en",
        )
        assert "English" in prompt
        assert "Korean" not in prompt

    def test_build_prompt_ja_contains_japanese_instruction(self):
        """language='ja' → user prompt에 일본어 지시 포함."""
        from src.services.dashboard_service import _build_insight_user_prompt
        prompt = _build_insight_user_prompt(
            days=7, kpi={}, trend=[], frequent=[], auto_merge={}, language="ja",
        )
        assert "Japanese" in prompt

    @pytest.mark.asyncio
    async def test_insight_narrative_passes_language_to_cache(self, db):
        """language 파라미터가 get_fresh / upsert 캐시 호출에 전달되는지 검증."""
        from src.services import dashboard_service

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=(
            '{"positive_highlights":["ok"],'
            '"focus_areas":["fix"],'
            '"key_metrics":[{"label":"a","value":"1","delta":"0"},'
            '{"label":"b","value":"2","delta":"0"},'
            '{"label":"c","value":"3","delta":"0"},'
            '{"label":"d","value":"4","delta":"0"}],'
            '"next_actions":["do it"]}'
        ))]
        mock_msg.usage = MagicMock(
            input_tokens=10, output_tokens=20,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        )
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("src.services.dashboard_service.settings") as s, \
             patch("src.services.dashboard_service.anthropic.AsyncAnthropic",
                   return_value=mock_client), \
             patch("src.repositories.insight_narrative_cache_repo.get_fresh",
                   return_value=None) as mock_get_fresh, \
             patch("src.repositories.insight_narrative_cache_repo.upsert") as mock_upsert:
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"

            # dashboard_kpi 등 4 헬퍼도 mock
            # Mock the 4 dashboard helpers so no DB queries are needed.
            with patch.object(dashboard_service, "dashboard_kpi",
                               return_value={"analysis_count": {"value": 5}}), \
                 patch.object(dashboard_service, "dashboard_trend", return_value=[]), \
                 patch.object(dashboard_service, "frequent_issues_v2", return_value=[]), \
                 patch.object(dashboard_service, "auto_merge_kpi", return_value={}):
                await dashboard_service.insight_narrative(
                    db, days=7, user_id=1, language="en",
                )

        # get_fresh에 language="en" 전달됐는지 확인
        # Verify language="en" was forwarded to get_fresh.
        call_kwargs = mock_get_fresh.call_args[1]
        assert call_kwargs.get("language") == "en"
        # upsert에도 language="en" 전달됐는지 확인
        # Verify language="en" was forwarded to upsert.
        upsert_kwargs = mock_upsert.call_args[1]
        assert upsert_kwargs.get("language") == "en"
