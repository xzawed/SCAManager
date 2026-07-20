"""PR 신규 CodeQL alert 게이트 정합 (회고 2026-07-19 P1 — note 임계값 미설정 봉인).

🔴 실측 반증 (2026-07-18, alert instances API): 자초 alert #547·#548·#549 는 **PR 시점에 이미
탐지돼 있었다** — 각각 `refs/pull/1081/merge`·`1082`·`1083` 인스턴스 보유. 심각도가 `note` 라
Code scanning 체크가 그대로 SUCCESS 였을 뿐이다. 따라서 근본 원인은 '클래스 게이트 부재'가
아니라 **'임계값 미설정'** 이며, 룰별 stdlib 가드 4종 증축은 이미 잡힌 것을 다시 잡는 대응이었다.
Measured: the self-inflicted alerts each had a `refs/pull/<n>/merge` instance — PR-time CodeQL DID
detect them; the check passed only because `note` severity is below the check-failure threshold.

🔴 타임아웃 = 통과 금지 (fail-OPEN 재발 차단): 분석이 인덱싱되기 전에 alert 를 조회하면 0건이
나온다. '분석 존재 확인 → 그 다음 alert 조회' 순서라야 0건을 신뢰할 수 있다.
Never treat "not indexed yet" as clean — verify the analysis exists for the head SHA first.
"""
import os
from pathlib import Path

from scripts.check_codeql_alerts import (
    analysis_ready,
    format_violations,
    select_new_alerts,
    soft_exit2_allowed,
)


def _alert(number, rule="py/empty-except", severity="note", path="scripts/x.py", line=1):
    return {
        "number": number,
        "state": "open",
        "rule": {"id": rule, "severity": severity},
        "most_recent_instance": {
            "location": {"path": path, "start_line": line},
            "message": {"text": "test message"},
        },
    }


# ── select_new_alerts ────────────────────────────────────────────────────


def test_alert_open_on_pr_but_not_base_is_new():
    """🔴 긍정 통제 — base 에 없는 PR alert 는 신규(차단 대상)."""
    got = select_new_alerts([_alert(547)], base_numbers={1, 2})
    assert [a["number"] for a in got] == [547]


def test_alert_also_open_on_base_is_not_new():
    """base 에 이미 열려 있던 alert 는 이 PR 책임 아님 — 차단하지 않는다(오탐 차단).

    legacy alert 로 무관한 PR 이 영구 차단되는 것을 막는다.
    """
    assert select_new_alerts([_alert(300)], base_numbers={300}) == []


def test_note_severity_is_still_gated():
    """🔴 note 심각도도 차단 — 본 게이트의 존재 이유(자초 alert 3건 전부 note)."""
    got = select_new_alerts([_alert(547, severity="note")], base_numbers=set())
    assert len(got) == 1, "note 를 통과시키면 게이트가 무의미하다"


def test_non_open_alert_ignored():
    """이미 fixed/dismissed 인 alert 는 대상 아님."""
    closed = _alert(547)
    closed["state"] = "fixed"
    assert select_new_alerts([closed], base_numbers=set()) == []


def test_empty_pr_alerts_is_clean():
    assert select_new_alerts([], base_numbers={1}) == []


# ── analysis_ready (인덱싱 완료 확인) ────────────────────────────────────


def test_analysis_ready_when_commit_matches():
    """🔴 head SHA 에 대한 분석이 존재해야 alert 0건을 신뢰할 수 있다."""
    analyses = [{"commit_sha": "abc123", "category": "/language:python"}]
    assert analysis_ready(analyses, "abc123") is True


def test_analysis_not_ready_for_other_commit():
    """🔴 부정 통제 — 다른 커밋의 분석은 근거가 못 된다(타임아웃=통과 금지의 핵심)."""
    analyses = [{"commit_sha": "old999", "category": "/language:python"}]
    assert analysis_ready(analyses, "abc123") is False


def test_analysis_not_ready_when_empty():
    assert analysis_ready([], "abc123") is False


# ── format_violations ────────────────────────────────────────────────────


def test_format_violations_includes_rule_and_location():
    """보고에 룰 ID·경로·라인이 노출 — 조치 가능해야 한다."""
    out = format_violations([_alert(547, rule="py/empty-except", path="scripts/a.py", line=42)])
    assert "py/empty-except" in out
    assert "scripts/a.py:42" in out
    assert "547" in out


# ── CI 배선 메타 가드 (test_check_noqa_sideeffect 선례) ───────────────────


def _codeql_workflow():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    return yaml.safe_load((root / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8"))


def test_codeql_workflow_wires_the_gate():
    """🔴 게이트가 codeql.yml 에 배선 — 미배선이면 스크립트는 dead code 다."""
    steps = _codeql_workflow()["jobs"]["analyze"]["steps"]
    runs = [s.get("run", "") for s in steps if "run" in s]
    assert any("check_codeql_alerts.py" in r for r in runs), "codeql.yml 에 게이트 배선 누락"


def test_gate_uses_merge_commit_sha_not_head_sha():
    """🔴 `github.sha`(머지 커밋) 사용 — head.sha 면 분석을 못 찾아 매번 fail-closed 로 막힌다.

    pull_request 이벤트에서 CodeQL 분석 대상은 refs/pull/N/merge 의 머지 커밋이다.
    """
    steps = _codeql_workflow()["jobs"]["analyze"]["steps"]
    gate = next(s.get("run", "") for s in steps if "check_codeql_alerts.py" in s.get("run", ""))
    code = "\n".join(l for l in gate.splitlines() if not l.strip().startswith("#"))
    assert "github.sha" in code, "머지 커밋 SHA(github.sha) 미전달"
    assert "head.sha" not in code, "head.sha 사용 — 분석 미발견으로 영구 fail-closed"


def test_gate_runs_only_on_pull_request():
    """push(main) 에서는 미실행 — base 대비 신규 판정이 성립하지 않는다."""
    steps = _codeql_workflow()["jobs"]["analyze"]["steps"]
    gate = next(s for s in steps if "check_codeql_alerts.py" in s.get("run", ""))
    assert "pull_request" in gate.get("if", ""), "게이트에 pull_request 조건 누락"


# ── 판정 불가(exit 2) 완화 정책 freeze (2026-07-20 — Dependabot 영구 차단 사고) ──
#
# ## 사고
# `#1097` 게이트는 **판정 불가**(API 실패·분석 미인덱싱)를 **위반과 같은 차단**으로 처리했다.
# Dependabot 은 GitHub 이 read-only 토큰을 주므로 `code-scanning/analyses` 를 읽을 수 없다 —
# 즉 **구조적으로 판정 불가**다. 실측(2026-07-20 PR #1134):
#     🔴 GitHub API 실패 — 게이트 판정 불가: repos/.../code-scanning/analyses?ref=refs/pull/1134/merge
# 게이트 도입(2026-07-19) 후 **첫 Dependabot PR 이 곧바로 막혔고**, 그 상태면 의존성 보안
# 업데이트가 영영 머지되지 않는다 — 보안 게이트가 보안 패치를 막는 상태.
#
# ## 이 freeze 가 잠그는 것
# 완화는 **판정 불가에만** 적용되고, **정확히 dependabot[bot]** 에만, **코드 면을 안 건드릴 때만**
# 허용된다. 되돌리거나 예외가 넓어지면 아래가 red 가 된다.


def test_soft_exit2_requires_exact_actor_match():
    """🔴 actor 는 **정확 일치** — prefix/포함 매칭이면 사칭이 통과한다."""
    assert soft_exit2_allowed("dependabot[bot]", ["requirements.txt"]) is True
    for impostor in ("dependabot", "my-dependabot[bot]", "dependabot[bot]x",
                     "renovate[bot]", "xzawed", ""):
        assert soft_exit2_allowed(impostor, ["requirements.txt"]) is False, (
            f"{impostor!r} 가 완화를 통과했다 — 정확 일치가 아니다"
        )


def test_soft_exit2_refused_when_code_surface_touched():
    """🔴 코드 면을 건드리면 완화하지 않는다 — `.github/**` 포함 의무.

    Dependabot 은 action 버전도 올린다(#1018). 그건 **control-plane** 변경이라
    "의존성이니 안전" 논리가 성립하지 않는다 — 게이트 자신을 약화시킬 수 있는 면이다.
    """
    for path in ("src/main.py", "scripts/x.py", "tests/unit/t.py", "e2e/t.py",
                 "alembic/versions/0001.py", ".github/workflows/ci.yml"):
        assert soft_exit2_allowed("dependabot[bot]", ["requirements.txt", path]) is False, (
            f"{path} 가 바뀌었는데 완화됐다 — 코드/control-plane 면은 하드 유지여야 한다"
        )


def test_soft_exit2_refused_when_paths_unknown():
    """🔴 변경 경로를 못 구하면 완화하지 않는다 — 빈 목록 ≠ '코드 변경 없음'.

    판정 불가를 판정하는 입력이 또 판정 불가일 때 통과시키면 완화가 무조건 통과가 된다.
    """
    assert soft_exit2_allowed("dependabot[bot]", ["<unknown>"]) is False


def test_violation_path_is_never_softened():
    """🔴 **exit 1(신규 alert 발견)은 누구에게도 완화되지 않는다.**

    완화는 `Undecidable` 예외 경로에서만 일어난다. 위반 판정은 그 예외를 거치지 않으므로
    actor 와 무관하게 그대로 1 을 반환해야 한다. 이 단언이 완화의 범위를 못박는다.
    """
    from scripts import check_codeql_alerts as mod

    calls = {"n": 0}

    def fake_api(path):
        calls["n"] += 1
        if "analyses" in path:
            return [{"commit_sha": "deadbeef"}]
        if "ref=refs/pull/" in path:  # PR alerts — 신규 1건
            return [{"state": "open", "number": 999,
                     "rule": {"id": "py/x", "severity": "note"},
                     "most_recent_instance": {"location": {"path": "a.py", "start_line": 1}}}]
        return []  # base alerts

    original = mod._gh_api
    mod._gh_api = fake_api
    try:
        os.environ["GITHUB_ACTOR"] = "dependabot[bot]"  # 완화 대상 actor 로 실행
        rc = mod.main(["x", "owner/repo", "1134", "deadbeef", "refs/heads/main"])
    finally:
        mod._gh_api = original
        os.environ.pop("GITHUB_ACTOR", None)

    assert rc == 1, f"신규 alert 가 있는데 {rc} 를 반환했다 — 위반이 완화됐다"


def test_undecidable_is_a_distinct_exception_not_a_direct_exit():
    """🔴 판정 불가가 `sys.exit(2)` 직접 호출이면 완화 분기 자체가 불가능하다.

    구 구현이 그랬고, 그래서 위반과 판정 불가가 같은 결과로 뭉개졌다.
    """
    from scripts import check_codeql_alerts as mod

    assert issubclass(mod.Undecidable, Exception)
    src = (Path(__file__).resolve().parents[3] / "scripts" / "check_codeql_alerts.py").read_text(
        encoding="utf-8"
    )
    api_block = src[src.index("def _gh_api"):src.index("def _wait_for_analysis")]
    assert "sys.exit(2)" not in api_block, (
        "_gh_api 가 여전히 직접 exit 한다 — 완화 분기가 도달 불가가 된다"
    )
