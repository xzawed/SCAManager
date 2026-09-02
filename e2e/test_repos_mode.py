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


def _seed_two_pages(db_path: str, count: int = 25) -> None:
    """`PAGE_SIZE`(20)를 넘기는 분석 이력을 넣어 페이지네이션이 나타나게 한다."""
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/testrepo'"
        )).fetchone()
        if row is None:
            raise RuntimeError("_seed_repo must run before _seed_two_pages")
        repo_id = row[0]
        from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415
        result = {"summary": "page"}
        for i in range(count):
            conn.execute(text("""
                INSERT OR IGNORE INTO analyses
                    (repo_id, commit_sha, commit_message, score, grade, result, author_login,
                     score_unreliable, created_at)
                VALUES
                    (:rid, :sha, :msg, :score, 'B', :res, 'e2e-tester',
                     :unrel, datetime('now', :delta))
            """), {"rid": repo_id, "sha": f"page-sha-{i:03d}", "msg": f"feat: page seed {i}",
                   "score": 60 + (i * 7) % 35, "res": json.dumps(result),
                   "delta": f"-{count - i} hours",
                   "unrel": score_is_unreliable(result)})
        conn.commit()
    engine.dispose()


@pytest.mark.e2e
def test_repo_detail_rows_stay_visible_after_rerender(seeded_page: Page, base_url: str):
    """🔴 표를 **다시 그린 뒤에도** 행이 보여야 한다 — 사용자에게 「내용 유실」로 보이던 사고.

    `.reveal { opacity: 0 }` 이고 `.visible` 은 IntersectionObserver 가 붙인다. 그 관찰 등록은
    로드 시점과 htmx 이벤트에서만 돌았는데, 리포 상세의 표는 평범한 JS 로 다시 그려진다
    (페이지네이션·정렬·필터·검색). 그래서 재렌더된 행은 DOM 에 있으나 **영원히 opacity 0** 였다.
    실측(수정 전): 2페이지 5/5 · 1페이지 복귀 20/20 · 정렬 20/20 이 전부 안 보임.

    🔴 「행이 존재하는가」로 재지 않는다 — 그것은 사고 당시에도 참이었다. **computed opacity** 를
    본다. 애니메이션이 실패할 때 「안 움직임」이 아니라 「안 보임」이 되던 것이 결함의 본체다.
    Assert computed opacity, not row presence: the rows existed throughout the incident.
    """
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    _seed_two_pages(db_path)
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
