"""Dashboard repos 모드 E2E 회귀가드.
E2E regression guard for Dashboard repos mode.
"""
import json
import os

import pytest
from playwright.sync_api import Page, expect


def _seed_trend_analyses(db_path: str) -> None:
    """owner/testrepo 에 서로 다른 날짜 2건의 Analysis 를 삽입해 score_trend(length>1)를 만든다.

    repo_score_trend 는 created_at 날짜별로 bin 하므로 trend 차트(`| length > 1`)가
    렌더되려면 서로 다른 날짜의 분석 ≥2건이 필요하다.
    Insert 2 analyses on different dates so repo_score_trend returns >1 point and the
    repos-mode score-trend chart (`{% if score_trend | length > 1 %}`) renders.
    """
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/testrepo'"
        )).fetchone()
        if row is None:
            raise RuntimeError("_seed_repo must run before _seed_trend_analyses")
        repo_id = row[0]
        for sha, score, delta in (("trend-sha-001", 70, "-3 days"),
                                  ("trend-sha-002", 90, "-0 days")):
            conn.execute(text("""
                INSERT OR IGNORE INTO analyses
                    (repo_id, commit_sha, commit_message, score, grade, result, author_login, created_at)
                VALUES
                    (:rid, :sha, 'feat: trend seed', :score, 'B', :res, 'e2e-tester',
                     datetime('now', :delta))
            """), {"rid": repo_id, "sha": sha, "score": score,
                   "res": json.dumps({"summary": "trend"}), "delta": delta})
        conn.commit()
    engine.dispose()


@pytest.mark.e2e
def test_repos_mode_score_trend_chart_renders(seeded_page: Page, base_url: str):
    """repos 모드에서 repo 선택 시 점수 트렌드 차트가 실제로 렌더링돼야 한다.

    🔴 회귀(#921 누락): `buildRepoTrendChart()` 가 Chart.js vendor `<script>`(문서 하단)보다
    앞서 실행돼 `Chart is not defined` throw → 점수추이 차트 미표시. typeof Chart 가드 +
    vendor onload 재빌드(_reposChartReady)로 봉인. pageerror trap 이 throw 를, wait_for_function
    이 Chart 인스턴스 부착을 양방향 검증한다.
    Repos-mode score-trend chart must actually render (Chart instance attached to the canvas).
    """
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_trend_analyses(db_path)
    seeded_page.goto(f"{base_url}/dashboard?mode=repos&repo=owner/testrepo")
    expect(seeded_page.locator(".repos-report")).to_be_visible()
    expect(seeded_page.locator("#repoTrendChart")).to_be_visible()
    # Chart.js 로드 후 repoTrendChart canvas 에 Chart 인스턴스가 부착돼야 함 (미부착=차트 공백)
    # After Chart.js loads, a Chart instance must be attached to the repoTrendChart canvas.
    seeded_page.wait_for_function(
        "() => !!(window.Chart && Chart.getChart && Chart.getChart('repoTrendChart'))",
        timeout=6000,
    )


@pytest.mark.e2e
def test_repos_tab_visible(page: Page, base_url: str):
    """repos 탭 링크가 Dashboard에 표시된다."""
    page.goto(f"{base_url}/dashboard")
    expect(page.get_by_role("link", name="Repos")).to_be_visible()


@pytest.mark.e2e
def test_repos_mode_summary_visible(page: Page, base_url: str):
    """repos 모드 진입 시 KPI 카드와 드롭다운이 렌더링된다."""
    page.goto(f"{base_url}/dashboard?mode=repos")
    expect(page.locator(".repos-kpi-grid")).to_be_visible()
    expect(page.locator(".repos-selector")).to_be_visible()


@pytest.mark.e2e
def test_repos_mode_empty_state(page: Page, base_url: str):
    """Repo 미선택 시 레포트 섹션이 없어야 한다."""
    page.goto(f"{base_url}/dashboard?mode=repos")
    expect(page.locator(".repos-report")).not_to_be_visible()
