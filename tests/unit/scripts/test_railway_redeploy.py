"""실패한 Railway 배포를 다시 거는 스크립트 — 에이전트가 혼자 쓰는 유일한 배포 경로 (회고 원장 L02, A안).
The only deploy path the agent may run alone: retry a failed deployment after mechanical checks.

판정(`decide`)은 순수 함수로 표를 돌리고, `main` 은 가짜 실행기로 «조건이 하나라도 안 맞으면 재배포 명령이 한 번도
나가지 않는다» 와 «맞으면 정확히 한 번 나간다» 를 잰다. 실제 railway · gh · git 은 부르지 않는다.
decide() is table-tested; main() is wired against a fake runner (no real CLI calls).
"""
import json

import pytest

from scripts import railway_redeploy as rr

_SHA = "a" * 40
_OTHER = "b" * 40


def _state(**over):
    state = {
        "main_sha": _SHA,
        "newest": {"id": "dep-1", "status": "FAILED", "commit": _SHA, "branch": "main"},
        "check_runs": [{"name": "test-and-analyze", "status": "completed", "conclusion": "success"},
                       {"name": "e2e", "status": "completed", "conclusion": "skipped"}],
        "check_runs_total": 2,
        "statuses": [{"context": "codecov/patch", "state": "success", "creator": "codecov[bot]"},
                     {"context": "xzawed - SCAManager", "state": "failure", "creator": "railway-app[bot]"}],
        "marker_age_hours": None,
    }
    state.update(over)
    return state


# --- 1. 판정 — 다시 걸어도 되는 때 ----------------------------------------------


def test_failed_build_of_main_head_with_green_ci_may_be_retried():
    """11-09 꼴: main 최신 커밋의 배포가 실패했고 CI 는 초록 — 다시 건다. Railway 자신의 배포 상태(failure)는 뺀다.
    The 11-09 shape: retry; Railway's own deployment status is excluded from the CI check."""
    assert rr.decide(_state(), "redeploy") == []


def test_skipped_deploy_with_green_ci_may_be_redeployed():
    """CI 재실행으로 초록이 된 뒤의 SKIPPED — 자동 배포와 같은 결과다 / a SKIPPED deploy whose CI is now green."""
    newest = {"id": "dep-1", "status": "SKIPPED", "commit": _SHA, "branch": "main"}
    assert rr.decide(_state(newest=newest), "redeploy") == []


def test_crashed_deploy_may_be_restarted():
    """CRASHED 는 재시작(빌드 없이) / a crashed deployment may be restarted."""
    newest = {"id": "dep-1", "status": "CRASHED", "commit": _SHA, "branch": "main"}
    assert rr.decide(_state(newest=newest), "restart") == []


def test_stale_rotation_marker_is_ignored():
    """48시간이 지난 표지만 효력이 없다 — 나이를 못 재면(NaN) 막는다(Grok 반례 a9bf7844).
    Only a marker at least 48 hours old stops blocking; an unmeasurable age (NaN) still blocks."""
    assert rr.decide(_state(marker_age_hours=49.0), "redeploy") == []
    assert rr.decide(_state(marker_age_hours=float("nan")), "redeploy"), "NaN 나이가 표지를 무효로 만들었다"


# --- 2. 판정 — 막아야 하는 때 ---------------------------------------------------


@pytest.mark.parametrize("over,needle", [
    # 비밀번호 교체 중 — 재시도가 성공하면 사용자가 곧바로 SQL 을 실행해야 한다
    ({"marker_age_hours": 1.0}, "교체"),
    # 이미 성공 · 진행 중 · 지워짐 — 다시 걸 이유가 없거나 자동 배포를 방해한다
    ({"newest": {"id": "d", "status": "SUCCESS", "commit": _SHA, "branch": "main"}}, "SUCCESS"),
    ({"newest": {"id": "d", "status": "BUILDING", "commit": _SHA, "branch": "main"}}, "BUILDING"),
    ({"newest": {"id": "d", "status": "WAITING", "commit": _SHA, "branch": "main"}}, "WAITING"),
    ({"newest": {"id": "d", "status": "REMOVED", "commit": _SHA, "branch": "main"}}, "REMOVED"),
    # main 최신 커밋이 아닌 배포 · main 이 아닌 브랜치
    ({"newest": {"id": "d", "status": "FAILED", "commit": _OTHER, "branch": "main"}}, "main 최신"),
    ({"newest": {"id": "d", "status": "FAILED", "commit": _SHA, "branch": "feature"}}, "main 최신"),
    # CI — 실패 · 끝나지 않음 · 취소 · 다 못 읽음 · 비어 있음
    ({"check_runs": [{"name": "t", "status": "completed", "conclusion": "failure"}], "check_runs_total": 1}, "CI"),
    ({"check_runs": [{"name": "t", "status": "in_progress", "conclusion": None}], "check_runs_total": 1}, "CI"),
    ({"check_runs": [{"name": "t", "status": "completed", "conclusion": "cancelled"}], "check_runs_total": 1}, "CI"),
    ({"check_runs_total": 150}, "다 읽지"),
    ({"check_runs": [], "check_runs_total": 0}, "다 읽지"),
    # Grok 반례(a9bf7844) — 목록은 있는데 total 이 0 · 없음: 어긋난 응답은 «다 읽음» 이 아니다
    # Grok counterexample: a non-empty list with total 0 or missing is not a complete read
    ({"check_runs_total": 0}, "다 읽지"),
    ({"check_runs_total": None}, "다 읽지"),
    # Railway 가 아닌 커밋 상태의 실패 · 대기
    ({"statuses": [{"context": "codecov/patch", "state": "failure", "creator": "codecov[bot]"}]}, "커밋 상태"),
    ({"statuses": [{"context": "codecov/patch", "state": "pending", "creator": "codecov[bot]"}]}, "커밋 상태"),
    # 못 읽은 값 — 막는 쪽
    ({"main_sha": None}, "읽지 못했다"),
    ({"newest": None}, "읽지 못했다"),
])
def test_refuses_when_any_condition_fails(over, needle):
    """조건이 하나라도 안 맞으면 거부하고 그 사유를 말한다 / refuse with the reason when any check fails."""
    reasons = rr.decide(_state(**over), "redeploy")
    assert reasons, f"거부해야 했다: {over}"
    assert any(needle in reason for reason in reasons), reasons


@pytest.mark.parametrize("status", ["FAILED", "SUCCESS", "SKIPPED"])
def test_restart_is_only_for_crashed(status):
    """재시작은 CRASHED 일 때만 — 빌드 실패에 재시작은 소용이 없다 / restart only for a crash."""
    newest = {"id": "d", "status": status, "commit": _SHA, "branch": "main"}
    assert rr.decide(_state(newest=newest), "restart")


def test_crashed_is_not_redeployed():
    """CRASHED 는 재배포가 아니라 재시작으로 / a crash is restarted, not rebuilt."""
    newest = {"id": "d", "status": "CRASHED", "commit": _SHA, "branch": "main"}
    assert rr.decide(_state(newest=newest), "redeploy")


# --- 3. 배선 — 가짜 실행기 -------------------------------------------------------


class _FakeRun:
    """명령 → 출력. 재배포 명령이 나간 횟수를 센다 / maps commands to outputs and records redeploys."""

    def __init__(self, deployments_sequence, check_runs=None, statuses=None, main_sha=_SHA):
        self.calls = []
        self._deployments = list(deployments_sequence)
        self._check_runs = check_runs if check_runs is not None else [
            {"name": "t", "status": "completed", "conclusion": "success"}]
        self._statuses = statuses if statuses is not None else []
        self._main_sha = main_sha

    def __call__(self, args):
        self.calls.append(list(args))
        joined = " ".join(args)
        if args[:2] == ["git", "ls-remote"]:
            return f"{self._main_sha}\trefs/heads/main\n"
        if "deployment list --json" in joined:
            current = self._deployments[0] if len(self._deployments) == 1 else self._deployments.pop(0)
            return json.dumps(current)
        if "check-runs" in joined:
            return json.dumps({"total_count": len(self._check_runs), "check_runs": self._check_runs})
        if "/statuses" in joined:
            return json.dumps(self._statuses)
        if "logs" in args:
            return "INFO started\nERROR something\n"
        return ""

    def actions(self):
        return [c for c in self.calls if "redeploy" in c or "restart" in c]


def _dep(dep_id, status, commit=_SHA):
    return {"id": dep_id, "status": status, "meta": {"commitHash": commit, "branch": "main"}}


def _main(fake, argv, marker_age=None, tmp_path=None):
    marker = tmp_path / "rotation-in-progress"
    if marker_age is not None:
        marker.write_text("x", encoding="utf-8")
    return rr.main(argv, run=fake, sleep=lambda _s: None,
                   now=lambda: marker.stat().st_mtime + marker_age * 3600 if marker_age is not None else 0.0,
                   marker=marker, railway_exe="railway")


def test_check_mode_never_redeploys(tmp_path):
    """`--check` 는 조건만 본다 — 조건이 맞아도 명령을 내지 않는다 / --check never acts."""
    fake = _FakeRun([[_dep("dep-1", "FAILED")]])
    assert _main(fake, ["--check"], tmp_path=tmp_path) == 0
    assert fake.actions() == []


def test_refused_state_never_redeploys(tmp_path):
    """🔴 거부되면 재배포 명령이 한 번도 나가지 않는다 / a refusal never sends the redeploy."""
    fake = _FakeRun([[_dep("dep-1", "FAILED")]],
                    check_runs=[{"name": "t", "status": "completed", "conclusion": "failure"}])
    assert _main(fake, [], tmp_path=tmp_path) == 1
    assert fake.actions() == []


def test_rotation_marker_blocks_the_redeploy(tmp_path):
    """🔴 교체 진행 중 표지가 있으면 재배포 명령이 나가지 않는다 / the rotation marker blocks the redeploy."""
    fake = _FakeRun([[_dep("dep-1", "FAILED")]])
    assert _main(fake, [], marker_age=2.0, tmp_path=tmp_path) == 1
    assert fake.actions() == []


def test_green_failed_build_is_redeployed_once_and_watched(tmp_path):
    """조건이 맞으면 `redeploy --from-source -y` 를 정확히 한 번 내고, 새 배포가 SUCCESS 가 될 때까지 본다.
    Exactly one `redeploy --from-source -y`, then watch the new deployment to SUCCESS."""
    fake = _FakeRun([
        [_dep("dep-1", "FAILED")],                               # 판정 / decide
        [_dep("dep-2", "BUILDING"), _dep("dep-1", "FAILED")],    # 감시 1 / watch 1
        [_dep("dep-2", "SUCCESS"), _dep("dep-1", "FAILED")],     # 감시 2 / watch 2
    ])
    assert _main(fake, [], tmp_path=tmp_path) == 0
    assert fake.actions() == [["railway", "redeploy", "--from-source", "-y"]]


def test_failed_retry_reports_failure(tmp_path):
    """다시 건 배포도 실패하면 exit 2 — 성공으로 접지 않는다 / a failed retry exits 2."""
    fake = _FakeRun([
        [_dep("dep-1", "FAILED")],
        [_dep("dep-2", "FAILED"), _dep("dep-1", "FAILED")],
    ])
    assert _main(fake, [], tmp_path=tmp_path) == 2


def test_crash_is_restarted_not_rebuilt(tmp_path):
    """`--restart` 는 `railway restart -y` 를 한 번 낸다 / --restart sends one `railway restart -y`."""
    fake = _FakeRun([
        [_dep("dep-1", "CRASHED")],
        [_dep("dep-1", "SUCCESS")],
    ])
    assert _main(fake, ["--restart"], tmp_path=tmp_path) == 0
    assert fake.actions() == [["railway", "restart", "-y"]]


def test_log_errors_counts_only_and_never_acts(tmp_path, capsys):
    """`--log-errors` 는 가장 새 배포의 오류 부류를 개수만 찍는다 — 재배포 · 재시작을 내지 않고, 줄 내용을 찍지 않는다.
    --log-errors prints per-class counts for the newest deployment; it never acts and never prints a log line."""
    fake = _FakeRun([[_dep("dep-9", "SUCCESS")]])
    assert _main(fake, ["--log-errors"], tmp_path=tmp_path) == 0
    assert fake.actions() == []
    out = capsys.readouterr().out
    assert "ERROR 1" in out and "SUCCESS" in out
    assert "something" not in out, "로그 줄 내용이 찍혔다 / a log line was printed"
    assert ["railway", "logs", "dep-9", "--deployment", "--lines", "500"] in fake.calls


def test_log_errors_tool_failure_exits_3(tmp_path):
    def broken(args):
        raise rr.CommandFailed(args, 1)
    marker = tmp_path / "rotation-in-progress"
    assert rr.main(["--log-errors"], run=broken, sleep=lambda _s: None, now=lambda: 0.0, marker=marker,
                   railway_exe="railway") == 3


def test_tool_failure_is_fail_closed(tmp_path):
    """git · gh · railway 가 실패하면 막는다(exit 3) — 못 잰 것을 통과로 접지 않는다 / tool failure → exit 3."""
    def broken(args):
        raise rr.CommandFailed(args, 1)
    marker = tmp_path / "rotation-in-progress"
    assert rr.main([], run=broken, sleep=lambda _s: None, now=lambda: 0.0, marker=marker,
                   railway_exe="railway") == 3
