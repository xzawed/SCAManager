"""Overview score count-up 0 고착 회귀 — IntersectionObserver 미발동 안전망.

운영 사고(2026-06-18): effects.js `setupCountUp` 이 `.repo-card__score` 를 "0" 으로
pre-fill 한 뒤 `onceInView`(IntersectionObserver) 로 0→점수 count-up 한다. hx-boost
body swap race / 특정 타이밍에 IntersectionObserver 콜백이 미발동하면 점수가 "0" 에
고착(등급은 별도 요소라 정상)된다. `onceInView` 의 rAF 안전망이 화면 내 미발동
요소를 강제 실행해 봉인한다.

IntersectionObserver 를 no-op 으로 주입해 "콜백 영구 미발동" 을 결정론적으로 재현한다.
서버 avg_score 는 session-scope 공유 DB(다른 e2e 가 owner/testrepo 에 analysis 삽입)로
값이 가변이므로, 정확 값 대신 "0/100" 고착 여부로 안전망을 검증한다.

Regression: count-up pre-fills score to "0" then animates via an IntersectionObserver;
if the callback never fires (hx-boost swap race) the score sticks at 0. The onceInView
rAF safety net must force in-viewport elements. avg_score varies (shared session DB),
so we assert the "0/100" freeze is gone rather than an exact value.
"""
import os

import pytest
from playwright.sync_api import Page, expect


def _seed_score(db_path: str, score: int = 85) -> None:
    """owner/testrepo 에 score 분석 1건 삽입 (overview avg_score 에 반영)."""
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/testrepo'"
        )).fetchone()
        if row is None:
            raise RuntimeError("_seed_repo must run before _seed_score")
        rid = row[0]
        conn.execute(text(
            "INSERT OR IGNORE INTO analyses "
            "(repo_id, commit_sha, commit_message, score, grade, result, author_login, created_at) "
            "VALUES (:rid,'ov-score-001','seed',:sc,'B','{}','e2e-tester',datetime('now'))"
        ), {"rid": rid, "sc": score})
        conn.commit()
    engine.dispose()


# IntersectionObserver 를 콜백이 영구 미발동하는 no-op 으로 대체 (hx-boost race 결정론적 시뮬)
# Replace IntersectionObserver with a no-op whose callback never fires (deterministic race sim)
_IO_NOOP = (
    "window.IntersectionObserver = function(){ return {"
    " observe:function(){}, unobserve:function(){}, disconnect:function(){},"
    " takeRecords:function(){ return []; } }; };"
)


@pytest.mark.e2e
def test_overview_score_survives_io_miss(seeded_page: Page, base_url: str):
    """IntersectionObserver 콜백이 안 와도 score 가 "0/100" 에 고착되지 않아야 한다.

    🔴 회귀(2026-06-18): IO no-op → onceInView count-up 미발동 → "0" pre-fill 고착.
    onceInView rAF 안전망이 화면 내 요소를 강제 count-up 해 "0/100" 고착을 해제해야 한다.
    """
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_score(db_path, 85)
    seeded_page.add_init_script(_IO_NOOP)
    seeded_page.goto(f"{base_url}/")
    seeded_page.wait_for_selector(".repo-card__score")
    # 안전망 없으면 "0/100" 고착, 있으면 rAF 안전망이 강제 count-up → 서버값(≠ "0/100")
    expect(seeded_page.locator(".repo-card__score").first).not_to_have_text("0/100", timeout=4000)


@pytest.mark.e2e
def test_overview_score_renders_full_load(seeded_page: Page, base_url: str):
    """정상 full load (IntersectionObserver 동작) 시 score count-up 이 "0/100" 에 안 머문다."""
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_score(db_path, 85)
    seeded_page.goto(f"{base_url}/")
    expect(seeded_page.locator(".repo-card__score").first).not_to_have_text("0/100", timeout=4000)
