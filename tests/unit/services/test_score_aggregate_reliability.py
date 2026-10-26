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


def test_repo_kpi_excludes_unreliable():
    """리포 KPI 는 기간 전체를 열로 집계한다 — 쓰기 경로처럼 판정 함수로 채운 `score_unreliable` 이 거른다.
    The repo KPI aggregates the window from columns; score_unreliable, filled as the write paths do, filters.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.database import Base
    from src.models.analysis import Analysis
    from src.models.repository import Repository
    from src.services.repo_insight_service import repo_kpi

    now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    rows = [
        (100, {"ai_review_status": "success", "source": "pr"}, timedelta(hours=1)),
        (40, {"ai_review_status": "success", "breakdown": {"ai_defaults_applied": True}}, timedelta(hours=2)),
        (50, {"ai_review_status": "success", "source": "pr"}, timedelta(days=31)),
    ]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        repo = Repository(full_name="owner/r46")
        db.add(repo)
        db.commit()
        for score, result, ago in rows:
            db.add(Analysis(repo_id=repo.id, commit_sha=f"sha-{score}", score=score, grade="B", result=result,
                            score_unreliable=score_is_unreliable(result),
                            created_at=now.replace(tzinfo=None) - ago))
        db.commit()
        kpi = repo_kpi(db, repo.id, 30, now=now)
    engine.dispose()
    assert (kpi["avg_score"], kpi["score_delta"], kpi["grade"]) == (100.0, 50.0, "A")


def test_compute_score_kpi_from_window_scores():
    """카드와 인사이트 페이지가 같이 쓰는 산식 — 검증 점수 합/개수, 직전 기간과의 차, 등급.
    The formula cards and the insights page share: verified sum/count, delta, grade.
    """
    # 함수 안에서 — 모듈 맨 위에 두면 이 이름이 없는 코드에서 파일 전체가 수집부터 멈춘다
    # Imported here: at module top, code without this name stops the whole file at collection
    from src.services.repo_insight_service import WindowScores

    avg, delta, grade = compute_score_kpi(WindowScores(5, 179, 2), WindowScores(1, 50, 1))
    assert (avg, delta, grade) == (89.5, 39.5, "B")
    assert compute_score_kpi(WindowScores(3, 0, 0), None) == (None, None, "?")


def test_score_is_unreliable_literals_match_aggregate_fixture():
    """Sanity: the fixture rows used above really are classified as intended."""
    assert score_is_unreliable({"source": "cli", "static_analysis_incomplete": True}) is True
    assert score_is_unreliable({"ai_review_status": "disabled"}) is True
    assert score_is_unreliable({"source": "pr", "ai_review_status": "success"}) is False


# ── 🔴 제품 전체에서 평균이 하나의 정의를 쓰는가 (R46 Axis B — 2026-08-15) ──


def test_every_sql_avg_of_score_excludes_unreliable_rows():
    """🔴 **`func.avg(Analysis.score)` 는 신뢰도 필터와 함께여야 한다.**

    ## 이 가드의 전제가 바뀌었다 (0046)

    초판은 SQL AVG 를 **전면 금지**했고, 근거는 이랬다:

        「신뢰도 판정에 필요한 정보가 `result` JSON 안에 있어 SQL 로 볼 수 없다.
         그래서 평균은 반드시 Python 으로 접어야 한다.」

    0046 이 `analyses.score_unreliable`(판정의 비정규화 캐시)을 추가하면서 **그 전제가
    거짓이 됐다.** SQL 은 이제 신뢰도를 볼 수 있다. 금지를 유지하면 가드가 옛 사실을
    집행하게 되고, 실측상 그 대가는 컸다 — 블롭 전량 로드 16.2 ms · 33 MB 전송 vs
    SQL 집계 0.45 ms · 4행(로컬 PG17, 운영 동형 5,164행).

    ## 그래도 지켜야 하는 불변식

    R46 사고의 본질은 「SQL AVG 를 썼다」가 아니라 **「같은 제품의 두 평균이 갈렸다」**
    였다. 대시보드 KPI 는 CLI 무검증 45점을 빼는데 리포 카드는 넣었고, 사용자는 어느
    쪽이 참인지 알 수 없었다. 그 불일치는 숫자가 틀린 것보다 나쁘다.

    그래서 금지가 아니라 **동반 강제**로 바꾼다: SQL 로 평균을 내려면 같은 쿼리에서
    신뢰 불가 행을 빼라. 필터 없는 AVG 는 여전히 red 다.

    The ban is replaced by a co-occurrence requirement: a SQL average must exclude
    unreliable rows in the same query. A bare AVG is still a failure.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src"
    bare = []
    total = 0
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        if "func.avg" not in src:
            continue
        tree = ast.parse(src)
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            # `func.avg(Analysis.score)` 호출을 AST 로 찾는다 — 주석은 구조에 없으므로
            # 산문 오탐이 원리적으로 불가능하다(초판은 주석을 위반으로 잡았다).
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "avg"):
                continue
            arg = node.args[0] if node.args else None
            if not (isinstance(arg, ast.Attribute) and arg.attr == "score"
                    and isinstance(arg.value, ast.Name) and arg.value.id == "Analysis"):
                continue
            total += 1
            # 감싸는 함수 전체에서 신뢰도 필터를 찾는다.
            owner = node
            while owner in parents and not isinstance(
                    owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                owner = parents[owner]
            # 🔴 `ast.dump` 부분문자열로 보면 **다른 이름**이 걸린다 — 같은 함수 안의
            #    `_score_unreliable`(다른 판정)이 이 가드를 통과시켰다(Grok `01a02f70` Q5-7).
            #    `Analysis.score_unreliable` 속성 접근을 구조로 찾는다.
            filtered = any(
                isinstance(n, ast.Attribute) and n.attr == "score_unreliable"
                and isinstance(n.value, ast.Name) and n.value.id == "Analysis"
                for n in ast.walk(owner)
            )
            if not filtered:
                bare.append(f"{path.relative_to(root.parent).as_posix()}:{node.lineno}")

    assert total, (
        "`func.avg(Analysis.score)` 를 하나도 못 찾았다 — 이 가드가 공허하다. "
        "SQL 집계를 없앴다면 이 테스트도 함께 지울 것."
    )
    assert not bare, (
        "신뢰도 필터 없는 SQL 평균이 있다 — 그 자리는 CLI 무검증 45점·AI 기본값 44점을 "
        "검증된 점수와 섞고, 같은 화면의 다른 평균과 갈린다:\n  "
        + "\n  ".join(bare)
        + "\n→ 같은 쿼리에 `Analysis.score_unreliable.isnot(True)` 를 넣을 것."
    )
