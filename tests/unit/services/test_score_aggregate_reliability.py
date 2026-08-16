"""R46 Axis B — dashboard/analytics averages exclude unreliable scores.

Pin expected numbers as literals. Do not derive expectations from production helpers.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.services.dashboard_service import _kpi_avg
from src.services.repo_insight_service import compute_score_kpi
from src.scorer.reliability import score_is_unreliable


def _row(score, result):
    return SimpleNamespace(score=score, result=result, repo_id=1)


def test_kpi_avg_excludes_cli_and_disabled_scores():
    """Verified 90 + unreliable 45(cli) + unreliable 78(disabled) → avg is 90 only."""
    cur = [
        _row(90, {"source": "pr", "ai_review_status": "success", "breakdown": {}}),
        _row(45, {
            "source": "cli",
            "ai_review_status": "success",
            "static_analysis_incomplete": True,
            "breakdown": {},
        }),
        _row(78, {"source": "push", "ai_review_status": "disabled", "breakdown": {}}),
    ]
    prev = [
        _row(80, {"source": "pr", "ai_review_status": "success", "breakdown": {}}),
    ]
    card = _kpi_avg(cur, prev)
    assert card["value"] == 90.0
    assert card["grade"] == "A"
    assert card["excluded_unreliable"] == 2
    assert card["scored_total"] == 3


def test_kpi_avg_all_unreliable_yields_none_with_exclusion_count():
    cur = [
        _row(45, {
            "source": "cli",
            "static_analysis_incomplete": True,
            "ai_review_status": "success",
        }),
        _row(44, {"ai_review_status": "disabled"}),
    ]
    card = _kpi_avg(cur, [])
    assert card["value"] is None
    assert card["excluded_unreliable"] == 2
    assert card["scored_total"] == 2


def test_kpi_avg_null_scores_do_not_count_as_excluded():
    """score is None rows are already out of averages; not double-counted as excluded."""
    cur = [
        _row(None, {"ai_review_status": "api_error"}),
        _row(70, {"source": "pr", "ai_review_status": "success", "breakdown": {}}),
    ]
    card = _kpi_avg(cur, [])
    assert card["value"] == 70.0
    assert card["excluded_unreliable"] == 0
    assert card["scored_total"] == 1


def test_compute_score_kpi_excludes_unreliable():
    cur = [
        SimpleNamespace(score=100, result={"ai_review_status": "success", "source": "pr"}),
        SimpleNamespace(score=40, result={
            "ai_review_status": "success",
            "breakdown": {"ai_defaults_applied": True},
        }),
    ]
    prev = [
        SimpleNamespace(score=50, result={"ai_review_status": "success", "source": "pr"}),
    ]
    avg, delta, grade = compute_score_kpi(cur, prev)
    assert avg == 100.0
    assert delta == 50.0
    assert grade == "A"


def test_score_is_unreliable_literals_match_aggregate_fixture():
    """Sanity: the fixture rows used above really are classified as intended."""
    assert score_is_unreliable({"source": "cli", "static_analysis_incomplete": True}) is True
    assert score_is_unreliable({"ai_review_status": "disabled"}) is True
    assert score_is_unreliable({"source": "pr", "ai_review_status": "success"}) is False


# ── 🔴 제품 전체에서 평균이 하나의 정의를 쓰는가 (R46 Axis B — 2026-08-15) ──


def test_no_sql_avg_of_score_survives_anywhere_in_src():
    """🔴 **`func.avg(Analysis.score)` 는 어디에도 남아 있으면 안 된다.**

    ## 왜 (실측 사고)

    R46 초판은 `dashboard_service`·`analytics_service`·`repo_insight_service` 만 고쳤고
    `src/ui/routes/overview.py:68` 의 SQL AVG 를 남겼다. 그러면 **같은 제품의 두 평균이
    갈린다** — 대시보드 KPI 는 CLI 무검증 45점을 빼고, 리포 카드는 넣는다. 사용자는
    어느 쪽이 참인지 알 수 없고, 그 불일치는 *숫자가 틀린 것보다 나쁘다*.

    근본 원인은 구조적이다: **신뢰도 판정에 필요한 정보가 `result` JSON 안에 있어
    SQL 로 볼 수 없다.** 그래서 평균은 반드시 Python 으로 접어야 하고, SQL AVG 가
    하나라도 살아 있으면 그 자리는 반드시 옛 정의를 쓴다.

    Any surviving SQL AVG necessarily uses the *old* definition — reliability lives in
    the result JSON, which SQL cannot read.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src"
    # 리터럴로 못박는다 — 피검사 코드에서 유도하면 이름을 바꾸는 순간 공허해진다.
    pattern = re.compile(r"func\.avg\(\s*Analysis\.score\s*\)")
    # 🔴 **주석은 제외한다** — 이 축을 *설명하는* 문장(왜 SQL AVG 를 쓰지 않는가)이 스스로
    #    위반으로 잡힌다. 초판이 정확히 그랬다(실측 2건, 둘 다 해설 주석).
    #    이 리포는 같은 형태를 반복했다: red-budget 의 코드 스팬 · 그리고 여기.
    #    산문 가드는 양방향으로 틀린다(traps B5).
    #    Comments explaining *why* SQL AVG is banned must not count as violations.
    offenders = [
        f"{f.relative_to(root.parent).as_posix()}:{i}"
        for f in root.rglob("*.py")
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line) and not line.lstrip().startswith("#")
    ]
    assert not offenders, (
        "SQL AVG 가 남아 있다 — 그 자리는 신뢰 불가 점수를 검증된 점수와 섞는다:\n  "
        + "\n  ".join(offenders)
        + "\n→ 행을 읽어 `score_is_unreliable(result)` 로 거른 뒤 Python 으로 평균낼 것."
    )
