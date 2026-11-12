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
        "dependabot_suites": frozenset(),
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

    def __init__(self, deployments_sequence, check_runs=None, statuses=None, main_sha=_SHA, workflow_runs=None):
        self.calls = []
        self._deployments = list(deployments_sequence)
        self._check_runs = check_runs if check_runs is not None else [
            {"name": "t", "status": "completed", "conclusion": "success"}]
        self._statuses = statuses if statuses is not None else []
        self._main_sha = main_sha
        self._workflow_runs = workflow_runs if workflow_runs is not None else []

    def __call__(self, args):
        self.calls.append(list(args))
        joined = " ".join(args)
        if args[:2] == ["git", "ls-remote"]:
            return f"{self._main_sha}\trefs/heads/main\n"
        if "deployment list --json" in joined:
            current = self._deployments[0] if len(self._deployments) == 1 else self._deployments.pop(0)
            return json.dumps(current)
        if "actions/runs" in joined:
            return json.dumps({"total_count": len(self._workflow_runs), "workflow_runs": self._workflow_runs})
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


# --- 4. Dependabot 업데이트 작업 — CI 판정에서 뺀다 ------------------------------------
# Railway 의 «CI 기다림» 은 커밋에 붙은 check suite 를 모두 본다. Dependabot 이 업데이트를 못 만들어(11-12 꼴 =
# security_update_not_possible) 그 작업이 실패하면 CI 가 초록이어도 배포를 건너뛴다. 그 작업은 우리 코드를 재지
# 않으므로 뺀다 — 실행 목록에서 event · path · actor · 커밋이 모두 맞는 실행의 suite 만. check-run 이름은 보지 않는다.
# Railway's wait-for-CI reads every check suite on the commit, so a failed Dependabot update job skips the deploy
# although CI is green. Such jobs do not test our code and are excluded — only via the suite of a run whose event,
# path, actor and commit all match; the check-run name is never used.

_REAL_SHA = "6d0b6145b2fdd0fd71d73efc6dd23d2198c9ea02"
_DEPENDABOT_SUITE = 116944979486
_CI_SUITE = 116944897706

# 그 커밋의 실측 응답(2026-11-12)에서 판정이 읽는 필드만 — (이름, status, conclusion, check suite id)
# Decision-relevant fields of the real responses for that commit — (name, status, conclusion, check suite id)
_REAL_CHECK_RUNS = [
    ("SonarCloud Code Analysis", "completed", "success", 116944893320),
    ("Dockerfile build + analyzer contract", "completed", "success", 116944897706),
    ("PG-only tests (SKIP LOCKED + migration round-trip)", "completed", "success", 116944897706),
    ("E2E (Playwright)", "completed", "success", 116944897706),
    ("pytest + Codecov + SonarCloud", "completed", "success", 116944897706),
    ("Dependabot", "completed", "failure", 116944979486),
    ("Lint changed test files (F401/F841 — C1)", "completed", "skipped", 116944897706),
    ("Repo integrity guards (stdlib backstop)", "completed", "success", 116944897706),
    ("lint-js 공허화 차단 (검사 범위 비면 fail)", "completed", "success", 116944897706),
    ("Static analysis gate (pylint + bandit on src/)", "completed", "success", 116944897706),
    ("TruffleHog secret scan", "completed", "success", 116944897706),
    ("pip-audit (SCA — 의존성 취약점 게이트)", "completed", "success", 116944897706),
    ("Analyze (python)", "completed", "success", 116944897693),
]
_REAL_RUNS = [
    {"event": "dynamic", "path": "dynamic/dependabot/dependabot-updates", "actor": {"login": "dependabot[bot]"},
     "head_sha": _REAL_SHA, "check_suite_id": 116944979486},
    {"event": "push", "path": ".github/workflows/codeql.yml", "actor": {"login": "xzawed"},
     "head_sha": _REAL_SHA, "check_suite_id": 116944897693},
    {"event": "push", "path": ".github/workflows/ci.yml", "actor": {"login": "xzawed"},
     "head_sha": _REAL_SHA, "check_suite_id": 116944897706},
]


def _dependabot_run(**over):
    run = {"event": "dynamic", "path": "dynamic/dependabot/dependabot-updates", "actor": {"login": "dependabot[bot]"},
           "head_sha": _SHA, "check_suite_id": _DEPENDABOT_SUITE}
    run.update(over)
    return run


def _listing(*runs, total="len"):
    return {"total_count": len(runs) if total == "len" else total, "workflow_runs": list(runs)}


def test_dependabot_update_run_is_recognised_by_its_suite():
    """event · path · actor · 커밋이 모두 맞는 실행의 suite 만 Dependabot 으로 본다 / only a fully matching run's suite."""
    assert rr.dependabot_suites(_listing(_dependabot_run()), _SHA) == {_DEPENDABOT_SUITE}


@pytest.mark.parametrize("over", [
    {"event": "push"},                                     # 같은 경로라도 push 실행 / a push run on the same path
    {"event": "pull_request"},
    {"path": "dynamic/dependabot/update-graph"},           # 의존성 그래프 작업 — 이번 완화 밖 / graph job: out of scope
    {"path": "dynamic/github-code-scanning/codeql"},       # 다른 동적 작업 / another dynamic job
    {"path": ".github/workflows/ci.yml"},                  # Dependabot 이 띄운 CI / CI started by Dependabot
    {"path": "dynamic/dependabot/dependabot-updates/x"},   # 접두만 같은 경로 / same prefix only
    {"actor": {"login": "xzawed"}},
    {"actor": {"login": "dependabot"}},                    # [bot] 이 아닌 계정 / not the bot account
    {"actor": None},
    {"actor": "dependabot[bot]"},                          # dict 가 아닌 actor / a malformed actor
    {"head_sha": _OTHER},                                  # 다른 커밋의 실행 / a run of another commit
    {"check_suite_id": None},
    {"check_suite_id": str(_DEPENDABOT_SUITE)},            # 문자열 id / a string id
    {"check_suite_id": True},                              # bool 은 id 가 아니다 / a bool is not an id
])
def test_runs_that_do_not_match_every_field_are_not_dependabot(over):
    """하나라도 어긋나면 빼지 않는다 — 싼 판정(이름 · event 만 · 경로 접두)이 받아들일 것을 심는다.
    Any mismatch keeps the run in CI — plants a cheaper predicate (name, event only, path prefix) would accept."""
    assert rr.dependabot_suites(_listing(_dependabot_run(**over)), _SHA) == frozenset()


@pytest.mark.parametrize("payload", [
    _listing(_dependabot_run(), total=2),          # 총수와 목록이 어긋남 — 다 못 읽음 / incomplete read
    _listing(_dependabot_run(), total=None),       # 총수 없음 / no total
    {"total_count": 1, "workflow_runs": "x"},      # 목록이 아님 / not a list
    {"total_count": 1, "workflow_runs": ["x"]},    # 실행이 dict 가 아님 / a non-dict run
    [_dependabot_run()],                           # 응답이 dict 가 아님 / not a dict
    None,
])
def test_incomplete_or_malformed_listing_excludes_nothing(payload):
    """실행 목록을 다 못 읽으면 아무것도 빼지 않는다(막는 쪽) / an incomplete listing excludes nothing."""
    assert rr.dependabot_suites(payload, _SHA) == frozenset()


def _skipped_state(ci="success", dep_status="completed", dep_conclusion="failure",
                   suites=frozenset({_DEPENDABOT_SUITE})):
    newest = {"id": "dep-1", "status": "SKIPPED", "commit": _SHA, "branch": "main"}
    runs = [{"name": "pytest", "status": "completed", "conclusion": ci, "suite": _CI_SUITE},
            {"name": "Dependabot", "status": dep_status, "conclusion": dep_conclusion, "suite": _DEPENDABOT_SUITE}]
    return _state(newest=newest, check_runs=runs, check_runs_total=2, dependabot_suites=suites)


@pytest.mark.parametrize("dep_status,dep_conclusion", [
    ("completed", "failure"),          # 11-12 꼴 / the 11-12 shape
    ("completed", "cancelled"),
    ("completed", "timed_out"),
    ("completed", "action_required"),
    ("in_progress", None),
    ("queued", None),
])
def test_dependabot_update_job_does_not_block(dep_status, dep_conclusion):
    """새로 도달 가능해진 입력 클래스 — CI 는 초록이고 초록이 아닌 것은 Dependabot 업데이트 작업뿐이면 다시 건다.
    Newly reachable class: CI is green and the only non-green check-run is a Dependabot update job → retry."""
    assert rr.decide(_skipped_state(dep_status=dep_status, dep_conclusion=dep_conclusion), "redeploy") == []


def test_dependabot_named_check_run_outside_a_dependabot_suite_still_blocks():
    """🔴 이름은 상태가 아니다 — 이름 · 실패가 같아도 suite 가 Dependabot 업데이트 실행의 것이 아니면 막는다.
    A check-run named Dependabot whose suite is not a Dependabot update run still blocks."""
    reasons = rr.decide(_skipped_state(suites=frozenset()), "redeploy")
    assert any("CI" in r and "Dependabot" in r for r in reasons), reasons


# witness-corpus: GitHub REST 문서가 열거한 check-run · check-suite conclusion 값 전부(검사 목록에서 뽑지 않았다)
# The conclusion values GitHub's REST docs enumerate for check runs and check suites — not drawn from the check.
_DOCUMENTED_CONCLUSIONS = ["action_required", "cancelled", "failure", "neutral", "success", "skipped", "stale",
                           "timed_out", "startup_failure"]


@pytest.mark.parametrize("ci", [*_DOCUMENTED_CONCLUSIONS, None])
def test_ci_next_to_a_dependabot_job_is_still_judged(ci):
    """Dependabot 작업을 빼도 나머지 CI 판정은 그대로다 — 문서의 결론 가운데 success · skipped · neutral 만 통과하고
    나머지(결론 없음 포함)는 그 CI 검사 이름을 대며 막는다.
    The rest of CI is still judged: only success/skipped/neutral pass; every other documented conclusion blocks."""
    reasons = rr.decide(_skipped_state(ci=ci), "redeploy")
    if ci in ("success", "skipped", "neutral"):
        assert reasons == [], (ci, reasons)
    else:
        assert any("pytest" in r for r in reasons), (ci, reasons)


def test_dependabot_jobs_alone_are_not_a_green_ci():
    """Dependabot 작업만 있고 CI 가 없으면 막는다 — 빼고 남은 빈 목록은 초록이 아니다(못 재면 red).
    Only Dependabot jobs and no CI → refuse; an empty list after the exclusion is not green."""
    newest = {"id": "dep-1", "status": "SKIPPED", "commit": _SHA, "branch": "main"}
    runs = [{"name": "Dependabot", "status": "completed", "conclusion": "success", "suite": _DEPENDABOT_SUITE}]
    assert rr.decide(_state(newest=newest, check_runs=runs, check_runs_total=1,
                            dependabot_suites=frozenset({_DEPENDABOT_SUITE})), "redeploy")


def _real_check_runs():
    return [{"name": n, "status": s, "conclusion": c, "check_suite": {"id": suite}}
            for n, s, c, suite in _REAL_CHECK_RUNS]


def _real_fake(workflow_runs=None, deployments=None):
    return _FakeRun(deployments or [[_dep("70c4c7bc", "SKIPPED", commit=_REAL_SHA)]],
                    check_runs=_real_check_runs(), main_sha=_REAL_SHA,
                    workflow_runs=list(_REAL_RUNS if workflow_runs is None else workflow_runs))


def test_real_dependabot_skip_passes_the_check(tmp_path, capsys):
    """실측 응답 그대로(CI · CodeQL · SonarCloud 초록 + Dependabot 작업 실패 + 배포 SKIPPED) → `--check` 통과.
    The real responses pass --check, and the summary says one Dependabot job was excluded."""
    fake = _real_fake()
    assert _main(fake, ["--check"], tmp_path=tmp_path) == 0
    assert fake.actions() == []
    out = capsys.readouterr().out
    assert "CI 검사 12개" in out and "Dependabot 작업 1개 제외" in out, out


def test_real_shape_redeploys_exactly_once(tmp_path):
    """같은 응답으로 실제 실행하면 `redeploy --from-source -y` 를 정확히 한 번 낸다 / exactly one redeploy."""
    fake = _real_fake(deployments=[
        [_dep("70c4c7bc", "SKIPPED", commit=_REAL_SHA)],
        [_dep("dep-2", "SUCCESS", commit=_REAL_SHA), _dep("70c4c7bc", "SKIPPED", commit=_REAL_SHA)],
    ])
    assert _main(fake, [], tmp_path=tmp_path) == 0
    assert fake.actions() == [["railway", "redeploy", "--from-source", "-y"]]


@pytest.mark.parametrize("workflow_runs", [
    [r for r in _REAL_RUNS if r["event"] != "dynamic"],                                   # 그 실행이 목록에 없음
    [dict(r, actor={"login": "xzawed"}) if r["event"] == "dynamic" else r for r in _REAL_RUNS],  # actor 가 다름
])
def test_real_shape_without_a_vouching_run_refuses(tmp_path, workflow_runs):
    """같은 check-run 이라도 실행 목록이 그 suite 를 Dependabot 업데이트 실행으로 보증하지 않으면 막는다.
    Without a run vouching for that suite, the same check-runs are refused."""
    fake = _real_fake(workflow_runs)
    assert _main(fake, ["--check"], tmp_path=tmp_path) == 1
    assert fake.actions() == []


def test_run_listing_failure_is_fail_closed(tmp_path):
    """실행 목록 조회가 실패하면 exit 3 — 빼지 못한 것을 통과로 접지 않는다 / a listing failure exits 3."""
    fake = _real_fake()

    def run(args):
        if any("actions/runs" in a for a in args):
            raise rr.CommandFailed(args, 1)
        return fake(args)
    marker = tmp_path / "rotation-in-progress"
    assert rr.main(["--check"], run=run, sleep=lambda _s: None, now=lambda: 0.0, marker=marker,
                   railway_exe="railway") == 3
