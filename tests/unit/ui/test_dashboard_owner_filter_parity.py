"""대시보드 route→service owner-filter parity 가드 (회고 2026-07-18 P2#41 — #1074 비대칭 봉인).
Dashboard route→service owner-filter parity guard (retro 2026-07-18 P2#41 — seals the #1074 asymmetry).

#1074: overview 7 형제 집계 중 `feedback_status` 하나만 owner 필터(`user_id`)를 안 받아 타 테넌트
private repo CTA 가 노출됐다(사후 감사로 발견). owner-filter parity 가 문서 규약일 뿐 기계 미강제였다.
이 테스트는 `src/ui/routes/dashboard.py` 의 **모든** `dashboard_service.<집계>` 호출이 `user_id` 를
전달하는지 AST 로 강제한다 — 신규 집계가 owner 스코프 없이 추가되면 CI fail(형제 누락 재발 차단).
#1074: one of the 7 overview aggregations (feedback_status) didn't receive the owner filter, leaking
another tenant's private-repo CTA. This asserts every dashboard_service aggregation call in the route
passes user_id — so a new aggregation added without owner scope fails CI.

직접 호출(`dashboard_service.f(db, user_id=...)`)과 executor 위임(`run_in_threadpool(
dashboard_service.f, db, user_id=...)`) 두 패턴 모두 커버.
Covers both direct calls and run_in_threadpool executor delegation.
"""
import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_ROUTE = _ROOT / "src" / "ui" / "routes" / "dashboard.py"

# owner-스코프(사용자별) 집계 — 각 호출은 user_id 를 받아야 한다(#1074 parity 계약).
# 신규 owner-스코프 집계 도입 시 이 집합에 추가(완전성 가드가 rename/제거를 잡는다).
# Owner-scoped aggregations — each call must pass user_id. Add new ones here (completeness guard).
_OWNER_SCOPED = {
    "dashboard_kpi", "dashboard_trend", "frequent_issues_v2", "auto_merge_kpi",
    "merge_failure_distribution", "repo_insight_cards", "feedback_status",
    "dashboard_security", "dashboard_usage", "insight_narrative",
}


def _is_dashboard_service_attr(node, names):
    """node 가 `dashboard_service.<name>` (name ∈ names) Attribute 면 name, 아니면 None.
    Return <name> if node is `dashboard_service.<name>` with name in names, else None."""
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "dashboard_service" and node.attr in names):
        return node.attr
    return None


def find_owner_scoped_calls(source, owner_scoped):
    """source(파이썬)에서 owner-스코프 dashboard_service 집계 호출을 (name, has_user_id) 로 수집.
    Collect (name, has_user_id) for owner-scoped dashboard_service aggregation invocations.

    두 패턴 / two patterns:
      - 직접 호출: Call.func == dashboard_service.<name>  → user_id ∈ 이 Call 의 keywords
      - executor: run_in_threadpool(dashboard_service.<name>, db, user_id=...) → name 은 인자, user_id 는
        바깥 Call(run_in_threadpool)의 keyword (executor 가 전달)
    """
    tree = ast.parse(source)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kw_names = {kw.arg for kw in node.keywords}
        # 직접 호출 / direct call
        name = _is_dashboard_service_attr(node.func, owner_scoped)
        if name:
            out.append((name, "user_id" in kw_names))
            continue
        # executor 위임 — 위치 인자 중 dashboard_service.<name> 이 있으면 이 Call 의 keyword 로 판정
        # executor delegation — a positional arg is dashboard_service.<name>; judge by this call's keywords
        for arg in node.args:
            aname = _is_dashboard_service_attr(arg, owner_scoped)
            if aname:
                out.append((aname, "user_id" in kw_names))
                break
    return out


def test_every_dashboard_aggregation_passes_user_id():
    """🔴 dashboard.py 의 모든 owner-스코프 집계 호출이 user_id 를 전달 (#1074 parity)."""
    calls = find_owner_scoped_calls(_ROUTE.read_text(encoding="utf-8"), _OWNER_SCOPED)
    missing = [name for name, has_uid in calls if not has_uid]
    assert not missing, (
        f"owner-스코프 집계가 user_id 없이 호출됨(타 테넌트 노출 위험 — #1074 재발): {missing}"
    )


def test_all_owner_scoped_aggregations_are_wired():
    """🔴 완전성 — 알려진 owner-스코프 집계가 전부 route 에서 호출됨(rename/제거 회귀 차단)."""
    calls = find_owner_scoped_calls(_ROUTE.read_text(encoding="utf-8"), _OWNER_SCOPED)
    called = {name for name, _ in calls}
    missing = _OWNER_SCOPED - called
    assert not missing, (
        f"owner-스코프 집계가 dashboard.py 에서 미호출(rename/삭제?) — 집합 갱신 또는 배선 확인: {missing}"
    )


# ── 순수 함수 검증 (합성 소스 — 가드 자체 정합) ──────────────────────────
# Pure-function checks (synthetic source — guard self-integrity)

def test_helper_detects_missing_user_id():
    """user_id 없는 직접 호출을 has_user_id=False 로 검출."""
    src = "x = dashboard_service.feedback_status(db)\n"
    assert find_owner_scoped_calls(src, {"feedback_status"}) == [("feedback_status", False)]


def test_helper_detects_direct_call_with_user_id():
    src = "x = dashboard_service.dashboard_kpi(db, days=days, user_id=uid)\n"
    assert find_owner_scoped_calls(src, {"dashboard_kpi"}) == [("dashboard_kpi", True)]


def test_helper_detects_executor_delegation():
    """run_in_threadpool 위임 패턴에서 바깥 Call 의 user_id 를 인식."""
    src = "y = run_in_threadpool(dashboard_service.dashboard_security, db, user_id=uid)\n"
    assert find_owner_scoped_calls(src, {"dashboard_security"}) == [("dashboard_security", True)]


def test_helper_ignores_non_owner_scoped():
    """집합 밖 함수(전역 지표 등)는 무시 — 오탐 차단."""
    src = "z = dashboard_service.global_metric(db)\n"
    assert find_owner_scoped_calls(src, {"dashboard_kpi"}) == []
