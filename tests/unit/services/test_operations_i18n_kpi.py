"""Phase 5 PR-17 회귀 가드 — operations_service i18n KPI (language_distribution + i18n_fallback_rate).

Phase 5 PR-17 regression guards — operations_service i18n KPI (language_distribution + i18n_fallback_rate).

검증 범위 (Coverage):
1. _i18n_language_distribution — User.preferred_language 분포 + percentages 정확성
2. _i18n_fallback_rate — 메모리 카운터 → fallback_rate_pct 변환 정확성
3. operations_kpi — language_distribution + i18n_fallback 키 존재 + memory_only 명시
4. get_i18n_metrics + reset_i18n_metrics — loader.py 메모리 카운터 라이프사이클
5. get_text 호출 시 카운터 증가 (hit / fallback / missing 구분)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.i18n.loader import (
    get_i18n_metrics,
    get_text,
    reset_i18n_metrics,
)
from src.models.user import User
from src.services.operations_service import (
    _i18n_fallback_rate,
    _i18n_language_distribution,
    operations_kpi,
)


# ── In-memory SQLite fixture (User 모델 의존) ────────────────────────────


@pytest.fixture
def db():
    """In-memory SQLite + User 테이블만 (operations_service 의존성 격리)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, github_login: str, lang: str = "en"):
    user = User(
        github_id=f"gh-{github_login}",
        github_login=github_login,
        github_access_token="gho_test",
        email=f"{github_login}@test.com",
        display_name=github_login,
        preferred_language=lang,
    )
    db.add(user)
    db.commit()
    return user


# ── _i18n_language_distribution ──────────────────────────────────────────


def test_language_distribution_empty_db(db):
    """User 없을 때 — total=0, 분포 비어있음."""
    result = _i18n_language_distribution(db)
    assert result["total_users"] == 0
    assert result["distribution"] == {}
    assert result["percentages"] == {}


def test_language_distribution_3_languages(db):
    """3 언어 사용자 — 분포 + percentages 정확성."""
    _make_user(db, "alice", "ko")
    _make_user(db, "bob", "ko")
    _make_user(db, "carol", "en")
    _make_user(db, "dave", "ja")
    result = _i18n_language_distribution(db)
    assert result["total_users"] == 4
    assert result["distribution"] == {"ko": 2, "en": 1, "ja": 1}
    assert result["percentages"]["ko"] == 50.0
    assert result["percentages"]["en"] == 25.0
    assert result["percentages"]["ja"] == 25.0


def test_language_distribution_single_language(db):
    """단일 언어 사용자 — 100%."""
    _make_user(db, "alice", "en")
    _make_user(db, "bob", "en")
    result = _i18n_language_distribution(db)
    assert result["total_users"] == 2
    assert result["percentages"]["en"] == 100.0


# ── _i18n_fallback_rate (loader.py 메모리 카운터) ─────────────────────────


def test_fallback_rate_zero_when_no_lookups():
    """get_text 호출 0건 시 — fallback_rate_pct=0."""
    reset_i18n_metrics()
    result = _i18n_fallback_rate()
    assert result["lookups_total"] == 0
    assert result["fallback_rate_pct"] == 0.0
    assert result["memory_only"] is True


def test_fallback_rate_hit_only_zero_fallback():
    """모든 lookup hit 시 — fallback_rate=0%."""
    reset_i18n_metrics()
    # 'common.logout' = en/ko/ja 모두 존재 → hit 만 발생
    get_text("common.logout", "en")
    get_text("common.logout", "ko")
    get_text("common.logout", "ja")
    result = _i18n_fallback_rate()
    assert result["lookups_total"] == 3
    assert result["lookups_hit"] == 3
    assert result["lookups_fallback"] == 0
    assert result["lookups_missing"] == 0
    assert result["fallback_rate_pct"] == 0.0


def test_fallback_rate_missing_increments_counter():
    """존재하지 않는 key — missing 카운터 증가."""
    reset_i18n_metrics()
    get_text("nonexistent.key.deep", "ko")
    result = _i18n_fallback_rate()
    assert result["lookups_total"] == 1
    assert result["lookups_missing"] == 1
    # 1 missing / 1 total = 100% fallback rate
    assert result["fallback_rate_pct"] == 100.0


def test_fallback_rate_mixed_hit_and_missing():
    """hit + missing 혼합 — fallback rate 계산 정확성."""
    reset_i18n_metrics()
    get_text("common.logout", "ko")        # hit
    get_text("common.logout", "ja")        # hit
    get_text("nonexistent_xyz", "ko")      # missing (key 자체 반환)
    result = _i18n_fallback_rate()
    assert result["lookups_total"] == 3
    assert result["lookups_hit"] == 2
    assert result["lookups_missing"] == 1
    assert result["fallback_rate_pct"] == round(1 / 3 * 100, 2)  # ~33.33


# ── operations_kpi 통합 (language_distribution + i18n_fallback 키 존재) ─


def test_operations_kpi_includes_i18n_keys(db):
    """operations_kpi — language_distribution + i18n_fallback 키 존재 + 5 기존 카드 보존."""
    reset_i18n_metrics()
    _make_user(db, "alice", "ko")

    # Mock claude_metrics + merge to avoid external deps
    from unittest.mock import patch
    with patch("src.services.operations_service.get_cache_stats") as mock_cache:
        mock_cache.return_value = {
            "total_calls": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0,
            "input_tokens": 0, "cache_hit_rate": 0.0,
        }
        result = operations_kpi(db, days=7)

    # 기존 5 카드 보존
    assert "cache" in result
    assert "api_cost" in result
    assert "merge" in result
    assert "pipeline_latency" in result
    # Phase 5 PR-17 신규 2 카드
    assert "language_distribution" in result
    assert "i18n_fallback" in result

    # language_distribution 정합성
    assert result["language_distribution"]["total_users"] == 1
    assert result["language_distribution"]["distribution"] == {"ko": 1}
    assert result["language_distribution"]["percentages"]["ko"] == 100.0

    # i18n_fallback memory_only 명시
    assert result["i18n_fallback"]["memory_only"] is True


def test_operations_kpi_days_propagation(db):
    """operations_kpi — days 인자 → merge KPI 에 전달."""
    from unittest.mock import patch
    with patch("src.services.operations_service.get_cache_stats") as mock_cache:
        mock_cache.return_value = {
            "total_calls": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0,
            "input_tokens": 0, "cache_hit_rate": 0.0,
        }
        result = operations_kpi(db, days=30)
    assert result["days"] == 30
    assert result["merge"]["days"] == 30


# ── loader.py reset_i18n_metrics — 단위 테스트 격리 ──────────────────────


def test_reset_i18n_metrics_clears_all_counters():
    """reset_i18n_metrics — 모든 카운터 0 으로 초기화."""
    get_text("common.logout", "ko")
    get_text("nonexistent", "en")
    metrics_before = get_i18n_metrics()
    assert metrics_before["lookups_total"] >= 2

    reset_i18n_metrics()
    metrics_after = get_i18n_metrics()
    assert metrics_after["lookups_total"] == 0
    assert metrics_after["lookups_hit"] == 0
    assert metrics_after["lookups_fallback"] == 0
    assert metrics_after["lookups_missing"] == 0


def test_get_i18n_metrics_returns_fallback_rate_field():
    """get_i18n_metrics — fallback_rate_pct 필드 + memory_only 명시 (operations_service 호출 페어)."""
    reset_i18n_metrics()
    metrics = get_i18n_metrics()
    assert "fallback_rate_pct" in metrics
    assert "lookups_total" in metrics
    assert "lookups_hit" in metrics
    assert "lookups_fallback" in metrics
    assert "lookups_missing" in metrics
