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
from scripts.check_codeql_alerts import analysis_ready, format_violations, select_new_alerts


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
