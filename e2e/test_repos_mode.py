"""Dashboard repos 모드 E2E 회귀가드.
E2E regression guard for Dashboard repos mode.
"""
import json
import os

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import _seed_paginated_history, _setup_e2e_db

# 페이지 시드를 넣어 보는 UTC 시각 — 매시 30분, 그리고 날짜 경계 직전.
# UTC hours at which the page seed is placed: every hour at :30, plus just before midnight.
_SWEEP_HOURS = tuple(f"{h:02d}:30:00" for h in range(24)) + ("23:54:00",)
# 시드 곁 «지금» 시각에 쌓일 수 있는 행 수 — 없음 · 하나 · 이 스위트의 실제 최대(8) · 그보다 많을 때(29).
# Rows that can sit at "now" beside the seed: none, one, this suite's real maximum (8), many (29).
_NOW_ROW_COUNTS = (0, 1, 8, 29)


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
            # 🔴 `score_unreliable` 명시 (0046) — 원시 SQL 은 ORM 을 안 거치고 기본값이
            #    true(신뢰 불가·fail-closed) 라, 빠뜨리면 추세 차트가 빈 값을 그린다.
            # 🔴 임포트는 **함수 안**이다 — 모듈 레벨이면 pytest **수집 시점**에
            #    `src.config` 검증이 돌고, e2e conftest 가 env 를 넣기 전이라 수집이 죽는다
            #    (실측: CI 의 e2e 범위 점검이 `SettingsValidationError` 로 exit 2).
            from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415
            trend_result = {"summary": "trend"}
            conn.execute(text("""
                INSERT OR IGNORE INTO analyses
                    (repo_id, commit_sha, commit_message, score, grade, result, author_login,
                     score_unreliable, created_at)
                VALUES
                    (:rid, :sha, 'feat: trend seed', :score, 'B', :res, 'e2e-tester',
                     :unrel, datetime('now', :delta))
            """), {"rid": repo_id, "sha": sha, "score": score,
                   "res": json.dumps(trend_result), "delta": delta,
                   "unrel": score_is_unreliable(trend_result)})
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
def test_paginated_seed_keeps_the_repo_trend_on_two_days_at_any_hour(live_server, tmp_path):
    """🔴 페이지 시드가 하루 중 언제 들어가도 repos 추세는 UTC 날짜 2개 이상이다.

    `repo_score_trend` 는 기간 전체를 UTC 날짜로 묶고, 템플릿은 묶음이 2개 이상일 때만
    `#repoTrendChart` 를 그린다. 시드 시각을 고정해 옮겨 가며 **실제** `repo_score_trend` 로
    날짜 수를 잰다.

    대조군 둘(23:30): 하루에만 있는 «지금» 7건은 날짜 1개로 **잡혀야** 하고, 옛 몰림 모양
    (T-25h ~ T-1h 매시 + «지금» 7건)은 날짜 2개여야 한다 — 추세가 최신 몇 건만 묶으면 이 모양이
    하루로 몰려(#1764) 여기서 걸린다.
    The repo trend must span two UTC days whatever hour the seed lands, measured with the real
    repo_score_trend; a one-day control must read as one date, and the old crowded shape as two.
    """
    from datetime import datetime, timedelta  # noqa: PLC0415

    from sqlalchemy import create_engine, delete, func, select  # noqa: PLC0415
    from sqlalchemy.orm import Session  # noqa: PLC0415

    from src.models.analysis import Analysis  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415
    from src.services.repo_insight_service import repo_score_trend  # noqa: PLC0415

    db_path = str(tmp_path / "trend_sweep.db")
    _setup_e2e_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with Session(engine) as db:
            repo = Repository(full_name="owner/testrepo")
            db.add(repo)
            db.commit()
            repo_id = repo.id

            def reset() -> None:
                db.execute(delete(Analysis).where(Analysis.repo_id == repo_id))
                db.commit()

            def add_rows(times: list, prefix: str, start: int = 0) -> None:
                for n, at in enumerate(times, start=start):
                    db.add(Analysis(repo_id=repo_id, commit_sha=f"{prefix}-{n:03d}", score=70,
                                    grade="C", result={"summary": prefix},
                                    score_unreliable=False, created_at=at))
                db.commit()

            def now_rows(base: datetime, have: int, want: int) -> list:
                # «지금» 시드 — 페이지 시드보다 새것이고 base 와 같은 UTC 날짜다.
                # "Now" rows: newer than the page seed and on base's UTC date.
                return [base - timedelta(seconds=j) for j in range(have, want)]

            def dates_at(base: datetime) -> list[str]:
                trend = repo_score_trend(db, repo_id, 7, now=base + timedelta(minutes=5))
                return [p["date"] for p in trend]

            day = datetime(2026, 10, 21)

            late = day.replace(hour=23, minute=30)
            reset()
            add_rows(now_rows(late, 0, 7), "now")
            one_day = dates_at(late)
            add_rows([late - timedelta(hours=25 - i) for i in range(25)], "old")
            crowded = dates_at(late)
            assert len(one_day) == 1, f"하루에만 있는 행을 날짜 여러 개로 셌다 — 계기가 날짜를 잘못 센다: {one_day}"
            assert len(crowded) == 2, (
                f"옛 몰림 모양이 날짜 하나로 몰렸다 — 추세가 기간 전체가 아니라 최신 몇 건만 묶는다: {crowded}")

            failures = []
            for hhmmss in _SWEEP_HOURS:
                h, m, s = map(int, hhmmss.split(":"))
                base = day.replace(hour=h, minute=m, second=s)
                reset()
                seeded = _seed_paginated_history(db_path, base=base.strftime("%Y-%m-%d %H:%M:%S"))
                stored = db.scalar(select(func.count()).select_from(Analysis)
                                   .where(Analysis.repo_id == repo_id))
                assert seeded == stored == 25, (
                    f"{hhmmss}: 시드가 25건이 아니다(반환 {seeded} · 저장 {stored}) — 재지 못했다")
                have = 0
                for want in _NOW_ROW_COUNTS:
                    add_rows(now_rows(base, have, want), "now", start=have)
                    have = want
                    got = dates_at(base)
                    if len(got) < 2:
                        failures.append(f"{hhmmss} «지금» {want}건 → {got}")
            assert not failures, (
                "페이지 시드가 «오늘» 을 채워 추세가 하루로 몰린다 — 차트가 사라지는 경우: "
                + "; ".join(failures))
    finally:
        engine.dispose()


@pytest.mark.e2e
def test_repo_detail_score_chart_renders(seeded_page: Page, base_url: str):
    """repo_detail(`/repos/{name}`) 의 점수 추이 차트(scoreChart)가 실제로 렌더돼야 한다.

    🔴 운영 사고 회귀(2026-06-18): `I18N` 이 한 `<script>` block(IIFE) 내 `const` 로 격리돼,
    별도 block 의 `buildChart` 가 stats 배지에서 `I18N.chartAvg` 참조 시 `ReferenceError:
    I18N is not defined` → buildChart throw → `new Chart` 미도달 → scoreChart 영구 미표시.
    호출 경로: vendor chart.umd.min.js onload → _repoChartReady → buildChart. 캐시 즉시 로드
    (라이브 immutable)가 onload 를 I18N 정의보다 앞당겨 트리거. window.I18N 전역화 +
    buildChart typeof I18N 가드로 봉인. conftest pageerror trap 이 throw 를, wait_for_function
    이 Chart 인스턴스 부착을 양방향 검증한다(repos 모드 차트와 다른 템플릿/canvas).
    """
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_trend_analyses(db_path)
    seeded_page.goto(f"{base_url}/repos/owner/testrepo")
    expect(seeded_page.locator("#scoreChart")).to_be_visible()
    # Chart.js 로드 후 scoreChart canvas 에 Chart 인스턴스 부착(미부착=I18N throw 로 차트 공백)
    # After Chart.js loads, a Chart instance must be attached to the scoreChart canvas.
    seeded_page.wait_for_function(
        "() => !!(window.Chart && Chart.getChart && Chart.getChart('scoreChart'))",
        timeout=6000,
    )


@pytest.mark.e2e
def test_repo_detail_rows_stay_visible_after_rerender(seeded_page: Page, base_url: str,
                                                       paginated_history: int):
    """🔴 표를 **다시 그린 뒤에도** 행이 보여야 한다 — 사용자에게 「내용 유실」로 보이던 사고.

    `.reveal { opacity: 0 }` 이고 `.visible` 은 IntersectionObserver 가 붙인다. 그 관찰 등록은
    로드 시점과 htmx 이벤트에서만 돌았는데, 리포 상세의 표는 평범한 JS 로 다시 그려진다
    (페이지네이션·정렬·필터·검색). 그래서 재렌더된 행은 DOM 에 있으나 **영원히 opacity 0** 였다.
    실측(수정 전): 2페이지 5/5 · 1페이지 복귀 20/20 · 정렬 20/20 이 전부 안 보임.

    🔴 「행이 존재하는가」로 재지 않는다 — 그것은 사고 당시에도 참이었다. **computed opacity** 를
    본다. 애니메이션이 실패할 때 「안 움직임」이 아니라 「안 보임」이 되던 것이 결함의 본체다.
    Assert computed opacity, not row presence: the rows existed throughout the incident.
    """
    seeded_page.goto(f"{base_url}/repos/owner/testrepo")

    def visible_rows() -> int:
        # 🔴 표를 **화면 안에** 둔다. 맨 아래까지 스크롤하면 표가 화면 위로 밀려 관찰자가
        #    발화하지 않고, 그러면 고쳐진 코드에서도 0 이 나온다(실측 — 이 시험의 첫 판이
        #    그렇게 거짓 red 였다).
        seeded_page.evaluate(
            "() => { const r = document.querySelector('tbody tr.analysis-row');"
            " if (r) r.scrollIntoView({block:'center'}); }"
        )
        seeded_page.wait_for_timeout(900)
        return seeded_page.evaluate(
            "() => Array.from(document.querySelectorAll('tbody tr.analysis-row'))"
            ".filter(r => parseFloat(getComputedStyle(r).opacity) > 0.5).length"
        )

    assert visible_rows() > 0, "최초 렌더부터 행이 보이지 않는다 — 이 시험의 전제가 깨졌다"

    # 🔴 번호 버튼으로 특정한다 — 「›」(다음) 버튼도 1페이지에서는 `data-page="2"` 라
    #    속성만으로 고르면 두 개가 잡힌다(실측: strict mode violation).
    pagination = seeded_page.locator("#pagination")
    page_two = pagination.get_by_role("button", name="2", exact=True)
    expect(page_two).to_be_visible()
    page_two.click()
    assert visible_rows() > 0, "2페이지로 넘긴 뒤 행이 하나도 보이지 않는다"

    pagination.get_by_role("button", name="1", exact=True).click()
    assert visible_rows() > 0, "1페이지로 되돌아온 뒤 행이 하나도 보이지 않는다"

    seeded_page.locator(".sortable-th").first.click()
    assert visible_rows() > 0, "정렬한 뒤 행이 하나도 보이지 않는다"


@pytest.mark.e2e
def test_tall_reveal_element_becomes_visible(seeded_page: Page, base_url: str):
    """🔴 유효 루트보다 10배 넘게 긴 `.reveal` 이 화면에 들어오면 보여야 한다.

    관찰자는 `threshold` 버킷이 **바뀔 때만** 콜백을 받는다. 단일 문턱이 0.1 이면
    intersectionRatio 의 최대값(= 유효 루트 높이 / 요소 높이)이 0.1 에 못 미치는 요소는
    초기 통지(`ratio=0`) 하나만 받고 **다시는 받지 못한다** — `isIntersecting` 은 true 가
    될 수 있었으나 콜백이 안 돌아 `.visible` 이 안 붙는다. `.reveal { opacity: 0 }` 이므로
    실패 모습은 「애니메이션 없음」이 아니라 **「내용 안 보임」**이다.

    실측(수정 전, vh=720 · 요소 8640px): 통지 1건 `{isIntersecting:false, ratio:0}` 으로
    끝나고 opacity 0 에 고착. threshold 0 으로 바꾸면 `{isIntersecting:true, ratio:0.0787}`.

    요소를 **집어넣는다** — 현재 어느 화면도 그만큼 길지 않기 때문이다(실측 최대 1646px).
    검사 대상은 페이지가 아니라 **관찰자의 계약**이다: 화면에 들어온 `.reveal` 은 보인다.
    A `.reveal` scrolled into view must be visible, whatever its height.
    """
    seeded_page.goto(f"{base_url}/repos/owner/testrepo")
    seeded_page.wait_for_timeout(800)
    opacity = seeded_page.evaluate(
        """
        () => new Promise(resolve => {
          const d = document.createElement('div');
          d.className = 'reveal';
          d.style.height = (window.innerHeight * 12) + 'px';
          document.body.appendChild(d);
          setTimeout(() => {
            d.scrollIntoView({block: 'center'});
            setTimeout(
              () => resolve(parseFloat(getComputedStyle(d).opacity)), 1200);
          }, 300);
        })
        """
    )
    assert opacity > 0.5, (
        f"화면 가운데까지 올린 `.reveal` 이 opacity {opacity} 로 남았다 — "
        "긴 요소가 threshold 버킷을 못 넘어 콜백이 영영 안 돈다"
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
