"""semgrep 자기 venv 감사 — 그 파일을 바꾼 PR 만 막고, 나머지는 경고 · 주간 감사가 이슈로 알린다 (회고 원장 L09 P2-54 · 사용자 11-16 결정).

## 사고

semgrep 의 정확 전이 핀에 상류 권고가 뜨면 우리 쪽에서 고칠 길이 없는데, required 감사가 늘 막아
창 안에서 권고 3건이 무관한 PR 6건 · main 1회를 빨갛게 했고 예외 PR 이 3번 났다(P2-54).

## 이 파일이 잠그는 것

1. 막는 조건 — PR 이 `requirements-semgrep.txt` 를 바꿨거나 바꿨는지 못 쟀을 때 · 주간 실행(`--always-block`).
2. 막지 않을 때는 감사가 실패해도 exit 0 · `::warning::` · job summary.
3. 주간 실행의 알림은 **정확히 같은 제목**의 열린 이슈에 댓글, 없으면 새 이슈 — 비슷한 제목은 다른 이슈다.
4. 배선 — CI 감사 스텝이 PR base/head 를 넘기고 전체 이력을 받는다 · 주간 워크플로는 늘 초록으로 끝낸다.
5. 예외 목록(`--ignore-vuln`)은 스크립트 한 곳에만 있다.
"""
from __future__ import annotations

import json
import shlex
import subprocess  # nosec B404 — 격리된 임시 리포와 가짜 gh 만
from pathlib import Path

import pytest
import yaml

import scripts.semgrep_audit as mod
from tests.unit.scripts._wiring_shape import invokes

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = "scripts/semgrep_audit.py"
_WEEKLY = _ROOT / ".github" / "workflows" / "semgrep-audit-weekly.yml"


# ── 1. 막는 조건 ────────────────────────────────────────────────────────


@pytest.mark.parametrize(("in_pr", "changed", "always", "want"), [
    (True, True, False, True),      # 그 파일을 바꾼 PR — 권고를 들여오는 자리
    (True, False, False, False),    # 무관한 PR — 경고만
    (True, None, False, True),      # 바꿨는지 못 쟀다 — 못 재면 막는다
    (False, None, False, False),    # main push — 경고만
    (False, None, True, True),      # 주간 실행
    (True, False, True, True),
])
def test_must_block_matrix(in_pr, changed, always, want):
    assert mod.must_block(in_pr=in_pr, changed=changed, always=always) is want


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.strip()


@pytest.fixture()
def history(tmp_path: Path) -> dict[str, object]:
    """커밋 셋 — A(처음) · B(다른 파일만) · C(semgrep 요구 파일)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / mod.REQS).write_text("semgrep==1.0.0\n", encoding="utf-8")
    (repo / "other.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "A")
    a = _git(repo, "rev-parse", "HEAD")
    (repo / "other.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "B")
    b = _git(repo, "rev-parse", "HEAD")
    (repo / mod.REQS).write_text("semgrep==1.0.1\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "C")
    c = _git(repo, "rev-parse", "HEAD")
    return {"repo": repo, "a": a, "b": b, "c": c}


def test_reqs_changed_sees_both_sides(history):
    """계기 뒤집기 — 다른 파일만 바뀐 범위는 False, 그 파일이 바뀐 범위는 True."""
    repo = history["repo"]
    assert mod.reqs_changed(history["a"], history["b"], cwd=repo) is False
    assert mod.reqs_changed(history["b"], history["c"], cwd=repo) is True
    assert mod.reqs_changed(history["a"], history["c"], cwd=repo) is True


def test_a_base_that_moved_ahead_is_not_this_prs_change(history):
    """🔴 base 가 앞서 나가며 semgrep 파일을 바꿨어도(다른 PR), 그 파일을 안 건드린 이 PR 은 «안 바뀜» 이다.

    두 점(`base head`)으로 비교하면 이 경우가 «바뀜» 으로 나와 무관한 PR 을 막는다 — 세 점은 병합 기점에서 잰다.
    """
    repo = history["repo"]
    _git(repo, "checkout", "-q", "-b", "pr", history["a"])
    (repo / "pr.txt").write_text("pr\n", encoding="utf-8")
    _git(repo, "add", "pr.txt")
    _git(repo, "commit", "-q", "-m", "PR")
    pr_head = _git(repo, "rev-parse", "HEAD")
    assert mod.reqs_changed(history["c"], pr_head, cwd=repo) is False
    assert mod.reqs_changed(history["a"], history["c"], cwd=repo) is True     # 대조군 — 바꾼 범위는 그대로 True


def test_reqs_changed_is_unknown_when_git_cannot_find_the_range(history):
    """🔴 얕은 체크아웃처럼 base 가 없으면 «안 바뀜» 이 아니라 «모름» — 호출부가 막는다."""
    assert mod.reqs_changed("0" * 40, history["c"], cwd=history["repo"]) is None


# ── 2. main — 막을 때와 경고만 남길 때 ───────────────────────────────────


@pytest.fixture()
def audit(monkeypatch, tmp_path):
    """감사 · git 대조를 가짜로 — (감사 결과, 바뀜 여부)를 시험마다 정한다."""
    state = {"rc": 1, "changed": False, "summary": tmp_path / "summary.md"}
    monkeypatch.setattr(mod, "run_audit", lambda: (state["rc"], "Name Version ID\nmcp 1.29.0 CVE-2099-0001"))
    monkeypatch.setattr(mod, "reqs_changed", lambda base, head, cwd=None: state["changed"])
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(state["summary"]))
    for key in ("PR_BASE_SHA", "PR_HEAD_SHA"):
        monkeypatch.delenv(key, raising=False)
    return state


def _in_pr(monkeypatch):
    monkeypatch.setenv("PR_BASE_SHA", "a" * 40)
    monkeypatch.setenv("PR_HEAD_SHA", "b" * 40)


def test_a_pr_that_changes_the_semgrep_pin_is_blocked(audit, monkeypatch):
    _in_pr(monkeypatch)
    audit["changed"] = True
    assert mod.main([]) == 1


def test_an_unrelated_pr_only_warns(audit, monkeypatch, capsys):
    """🔴 무관한 PR — 감사가 실패해도 0. 대신 경고 줄과 job summary 에 남는다."""
    _in_pr(monkeypatch)
    audit["changed"] = False
    assert mod.main([]) == 0
    assert "::warning" in capsys.readouterr().out
    assert "semgrep" in audit["summary"].read_text(encoding="utf-8")


def test_a_pr_whose_change_cannot_be_measured_is_blocked(audit, monkeypatch):
    _in_pr(monkeypatch)
    audit["changed"] = None
    assert mod.main([]) == 1


def test_a_half_pr_context_is_treated_as_unmeasured(audit, monkeypatch):
    """SHA 하나만 오면 PR 인데 범위를 못 잰다 — push 로 읽어 경고만 내면 안 된다."""
    monkeypatch.setenv("PR_HEAD_SHA", "b" * 40)
    audit["changed"] = False      # 호출되면 안 된다 — 범위가 없으니 «모름» 이어야 한다
    assert mod.main([]) == 1


def test_main_push_only_warns(audit, capsys):
    assert mod.main([]) == 0
    assert "::warning" in capsys.readouterr().out


def test_the_weekly_run_blocks(audit):
    assert mod.main(["--always-block"]) == 1


def test_the_report_file_carries_the_audit_output(audit, tmp_path):
    """주간 실행의 알림 본문 — 감사 출력이 그대로 파일에 남는다."""
    report = tmp_path / "audit.txt"
    assert mod.main(["--always-block", "--report", str(report)]) == 1
    assert "CVE-2099-0001" in report.read_text(encoding="utf-8")


def test_a_clean_audit_passes_everywhere(audit, monkeypatch):
    audit["rc"] = 0
    assert mod.main(["--always-block"]) == 0
    _in_pr(monkeypatch)
    audit["changed"] = True
    assert mod.main([]) == 0


# ── 3. 주간 알림 — 정확히 같은 제목의 열린 이슈 ─────────────────────────


@pytest.fixture()
def gh(monkeypatch):
    """가짜 gh — 호출을 적고, `issue list` 에는 시험이 정한 목록을 돌려준다."""
    state: dict[str, object] = {"issues": [], "calls": [], "list_rc": 0}

    def _fake(args: list[str]) -> subprocess.CompletedProcess:
        state["calls"].append(args)
        if args[:2] == ["issue", "list"]:
            return subprocess.CompletedProcess(args, state["list_rc"], json.dumps(state["issues"]), "")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(mod, "_gh", _fake)
    return state


def _verbs(state) -> list[list[str]]:
    return [call[:2] for call in state["calls"]]


def test_notify_comments_on_the_open_issue_with_the_same_title(gh, tmp_path):
    gh["issues"] = [{"number": 7, "title": "다른 이슈"}, {"number": 42, "title": mod.ISSUE_TITLE}]
    report = tmp_path / "report.txt"
    report.write_text("mcp 1.29.0 CVE-2099-0001\n", encoding="utf-8")
    assert mod.notify(report) == 0
    assert ["issue", "comment"] in _verbs(gh) and ["issue", "create"] not in _verbs(gh)
    comment = next(call for call in gh["calls"] if call[:2] == ["issue", "comment"])
    assert comment[2] == "42", comment


def test_a_similar_title_is_another_issue(gh, tmp_path):
    """🔴 부분문자열은 같은 이슈가 아니다 — 제목이 정확히 같을 때만 댓글을 단다."""
    gh["issues"] = [{"number": 9, "title": mod.ISSUE_TITLE + " (닫을 것)"},
                    {"number": 10, "title": "옛 " + mod.ISSUE_TITLE}]
    report = tmp_path / "report.txt"
    report.write_text("x\n", encoding="utf-8")
    assert mod.notify(report) == 0
    assert ["issue", "create"] in _verbs(gh) and ["issue", "comment"] not in _verbs(gh)


def test_notify_fails_when_it_cannot_list_issues(gh, tmp_path):
    """🔴 열린 이슈를 못 읽으면 새로 만들지도 않고 red — 중복 이슈를 쌓거나 조용히 넘어가지 않는다."""
    gh["list_rc"] = 1
    assert mod.notify(tmp_path / "report.txt") == 1
    assert _verbs(gh) == [["issue", "list"]]


def test_notify_says_so_when_the_audit_left_no_report(gh, tmp_path, monkeypatch):
    """감사 스텝이 보고서를 못 남겼으면(중단) 그 사실이 본문에 실린다."""
    bodies: list[str] = []
    real = mod._gh

    def _keep(args):
        for i, tok in enumerate(args[:-1]):
            if tok == "--body-file":
                bodies.append(Path(args[i + 1]).read_text(encoding="utf-8"))
        return real(args)
    monkeypatch.setattr(mod, "_gh", _keep)
    assert mod.notify(tmp_path / "absent.txt") == 0
    assert bodies and "감사 출력이 없다" in bodies[0]


# ── 4 · 5. 배선 · 예외 목록 한 곳 ───────────────────────────────────────


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(doc: dict) -> list[dict]:
    return [step for job in doc["jobs"].values() for step in job.get("steps", [])]


def _script_args(run: str) -> list[list[str]]:
    """`run` 안에서 이 스크립트를 실행하는 줄마다 그 뒤 인자 목록."""
    out = []
    for line in run.splitlines():
        if invokes(line, _SCRIPT):
            tokens = shlex.split(line)
            at = next(i for i, tok in enumerate(tokens) if tok.replace("\\", "/").endswith(_SCRIPT))
            out.append(tokens[at + 1:])
    return out


def _ignore_flags(run: str) -> list[str]:
    """명령 줄의 `--ignore-vuln` 토큰 — 주석 줄은 보지 않는다."""
    found = []
    for line in run.splitlines():
        if line.lstrip().startswith("#"):
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()
        found += [tok for tok in tokens if tok == "--ignore-vuln" or tok.startswith("--ignore-vuln=")]
    return found


def test_the_ignore_flag_detector_sees_both_spellings():
    """두 심음 — 두 철자는 잡고, 주석 · 다른 플래그는 무시한다."""
    run = ("python -m pip_audit -r x.txt --ignore-vuln CVE-1 --ignore-vuln=CVE-2\n"
           "# --ignore-vuln CVE-3 은 주석\npython -m pip_audit --desc on\n")
    assert _ignore_flags(run) == ["--ignore-vuln", "--ignore-vuln=CVE-2"]


def test_ci_audit_step_passes_the_pr_range_and_fetches_history():
    """🔴 범위를 못 넘기거나 base 커밋이 없으면 «모름» = 늘 막는다 — 결정한 것과 반대가 된다."""
    job = _workflow(_ROOT / ".github" / "workflows" / "ci.yml")["jobs"]["dependency-audit"]
    steps = [s for s in job["steps"] if _script_args(s.get("run", ""))]
    assert len(steps) == 1, "dependency-audit 잡에 semgrep 감사 스텝이 하나여야 한다"
    step = steps[0]
    assert _script_args(step["run"]) == [[]], "PR 감사는 인자 없이 — `--always-block` 은 주간 실행만"
    passed = step.get("env", {})
    assert "pull_request.base.sha" in str(passed.get("PR_BASE_SHA")), passed
    assert "pull_request.head.sha" in str(passed.get("PR_HEAD_SHA")), passed
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout.get("with", {}).get("fetch-depth") == 0, "base 커밋이 없으면 «모름» 이 되어 늘 막는다"


def test_the_weekly_workflow_audits_and_notifies_without_turning_red():
    doc = _workflow(_WEEKLY)
    on = doc.get(True, doc.get("on"))
    assert on.get("schedule") and on["schedule"][0].get("cron"), "예약이 없다"
    assert "workflow_dispatch" in on
    assert doc.get("permissions") == {"contents": "read", "issues": "write"}
    steps = _steps(doc)
    audit_steps = [s for s in steps
                   if any(args[:1] == ["--always-block"] for args in _script_args(s.get("run", "")))]
    assert len(audit_steps) == 1, "주간 감사 스텝은 `--always-block` 으로 한 번"
    audit_step = audit_steps[0]
    report_args = _script_args(audit_step["run"])[0]
    assert report_args[1:2] == ["--report"] and len(report_args) == 3, report_args
    assert audit_step.get("id"), "알림 스텝이 결과를 읽을 id 가 없다"
    notify = [s for s in steps if any(args[:1] == ["--notify"] for args in _script_args(s.get("run", "")))]
    assert len(notify) == 1, "알림 스텝이 하나여야 한다"
    assert f"steps.{audit_step['id']}.outputs.rc" in str(notify[0].get("if", "")), notify[0].get("if")
    assert "GH_TOKEN" in notify[0].get("env", {}), "gh 가 쓸 토큰이 없다"


def test_the_exception_list_lives_only_in_the_script():
    """🔴 예외 ID 가 여러 곳에 복사되면 하나만 고쳐진다(P2-89) — 워크플로 명령에는 `--ignore-vuln` 이 없다."""
    workflows = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows, "워크플로를 못 찾았다 — 이 판정이 공허하다"
    leaked = {path.name: flags for path in workflows
              for flags in [[f for step in _steps(_workflow(path)) for f in _ignore_flags(step.get("run", ""))]]
              if flags}
    assert leaked == {}, leaked
    argv = mod.audit_argv()
    assert argv[argv.index("-r") + 1] == mod.REQS
    pairs = [argv[i + 1] for i, tok in enumerate(argv) if tok == "--ignore-vuln"]
    assert pairs == list(mod.IGNORED_VULNS) and pairs, argv
