"""허용된 운영 채널 호출의 감사 기록 — 회고가 «읽기 전용 확인» 같은 서술을 기계 기록과 대 본다 (회고 원장 #1917 M02 P2-3 ②).

## 이 파일이 잠그는 것

1. 훅이 허용한 운영 채널 호출(railway 읽기 · 운영 MCP 읽기 도구 · python 으로 돌린 관측 DB 읽기 · 조건부 재배포 · 배포
   설정 읽기)은 감사 기록 한 줄을 남긴다 — 시각 · 종류 · 채널(고정 어휘) · 명령 sha256 · 길이만. 명령 글자와 인자(SQL ·
   배포 ID)는 남기지 않는다.
2. 계기 뒤집기 — 낱말 `railway` · `observe_db` 를 «언급» 만 하는 명령(검색 · 스크립트 읽기 · echo)은 기록하지 않고, 명령
   글자가 없는 MCP 도구 호출과 대소문자 · 확장자가 다른 실행 파일 이름은 기록한다(부분 문자열 판정이면 둘 다 틀린다).
3. 막힌 호출은 감사 기록이 아니라 거부 기록에만 간다. 운영과 무관한 명령은 아무 기록도 남기지 않는다.
4. 기록을 못 써도 판정은 그대로다 · 시험은 실제 홈의 기록을 건드리지 않는다(conftest).
"""
import hashlib
import io
import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

import block_credential_dump as hook  # noqa: E402

_MARKER = "SYNTHETIC_AUDIT_MARKER"


@pytest.fixture
def logs(tmp_path, monkeypatch):
    """감사 · 거부 기록을 임시 자리로, 작업 폴더는 그 옆에 / both logs in a scratch folder, plus a workdir."""
    work = tmp_path / "work"
    (work / "docs").mkdir(parents=True)
    (work / "docs" / "a.md").write_text("text\n", encoding="utf-8")
    (work / "scripts").mkdir()
    (work / "scripts" / "observe_db.py").write_text("print('x')\n", encoding="utf-8")
    audit, denials = tmp_path / "allows.jsonl", tmp_path / "denials.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_AUDIT_LOG", str(audit))
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(denials))
    return work, audit, denials


def _run(monkeypatch, capsys, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    return capsys.readouterr().out


def _shell(command, cwd, tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


# 허용되는 운영 채널 호출과 감사 기록에 남을 채널 — 인자(배포 ID · SQL)는 채널에 없다. 마지막 줄은 계기 뒤집기의
# `claimed\cheap` 심음이다: 대소문자 · 확장자가 다른 실행 파일 이름(부분 문자열 `railway ` 로는 못 잡는다).
# Allowed production-channel calls and the channel each records; arguments never reach the channel.
_ALLOWED = {
    "railway status": ["railway status"],
    f"railway logs 4f2c-{_MARKER}": ["railway logs"],
    "railway deployment list --json": ["railway deployment list"],
    "railway variables --kv | cut -d= -f1": ["railway variables"],
    'echo "$(railway status)"': ["railway status"],
    f'py -3 scripts/observe_db.py "SELECT {_MARKER} FROM t"': ["observe_db"],
    "py -3 scripts/railway_redeploy.py --check": ["railway_redeploy --check"],
    "python scripts/railway_config.py": ["railway_config"],
    # 사용자 몫인데 훅이 막지 않는 운영 DB 스크립트 — 에이전트가 돌리면 기록에 남아야 회고가 본다 / user-run DB scripts
    f"py -3 scripts/observer_setup.py --host {_MARKER} --ref r1": ["observer_setup"],
    "python -m scripts.backfill_repository_user_id --apply": ["backfill_repository_user_id --apply"],
    "python scripts/perf_measure.py --prod-only": ["perf_measure --prod-only"],
    "Railway.EXE status": ["railway status"],
    # 교차 검토(하위 에이전트 · 워크플로 wf_8b259a5e-212) 반례 — 시간 제한 · 반복문 · 조건문 안의 스크립트, 값을 받는
    # 인터프리터 옵션(`-X utf8`), 로그만 읽는 재배포 스크립트 / scripts under wrappers, loops, conditionals; -X values.
    'timeout 120 python scripts/observe_db.py "SELECT 1"': ["observe_db"],
    'for i in 1 2; do py -3 scripts/observe_db.py "SELECT 1"; done': ["observe_db"],
    "if py -3 scripts/railway_redeploy.py --check; then py -3 scripts/railway_redeploy.py --restart; fi":
        ["railway_redeploy --check", "railway_redeploy --restart"],
    'py -3 -X utf8 scripts/observe_db.py "SELECT 1"': ["observe_db"],
    'python -W ignore scripts/observe_db.py "SELECT 1"': ["observe_db"],
    "py -3 scripts/railway_redeploy.py --log-errors": ["railway_redeploy --log-errors"],
}


@pytest.mark.parametrize("command", sorted(_ALLOWED))
def test_an_allowed_production_call_leaves_a_value_free_audit_record(command, logs, monkeypatch, capsys):
    """🔴 허용된 운영 채널 호출은 감사 기록 한 줄 — 시각 · 종류 · 채널 · sha256 · 길이만. 명령 글자 · 인자는 없다."""
    work, audit, denials = logs
    assert _run(monkeypatch, capsys, _shell(command, work)) == "", "허용돼야 할 호출이 막혔다"
    records = _records(audit)
    assert len(records) == 1, records
    record = records[0]
    assert set(record) == {"ts", "kind", "channels", "sha256", "len"}, record
    assert record["kind"] == "production-allowed"
    assert record["channels"] == _ALLOWED[command]
    assert record["sha256"] == hashlib.sha256(command.encode("utf-8")).hexdigest()
    assert record["len"] == len(command)
    assert _MARKER not in audit.read_text(encoding="utf-8"), "명령 인자가 감사 기록에 남았다"
    assert not denials.exists(), "허용된 호출이 거부 기록에 남았다"


def test_an_allowed_production_mcp_read_is_audited_too(logs, monkeypatch, capsys):
    """계기 뒤집기 `claimed\\cheap` — MCP 도구 호출에는 명령 글자가 없다(글자를 훑는 판정은 못 본다). 읽기 도구는 허용되고 기록된다.
    An MCP read has no command text, yet it is a production channel: allowed and audited."""
    _, audit, _ = logs
    for tool in ("mcp__railway__get_logs", "mcp__supabase__list_tables"):
        assert _run(monkeypatch, capsys, {"tool_name": tool, "tool_input": {"deploymentId": _MARKER}}) == ""
    assert [r["channels"] for r in _records(audit)] == [["Railway MCP get_logs"], ["Supabase MCP list_tables"]]
    assert _MARKER not in audit.read_text(encoding="utf-8")


# 계기 뒤집기 `cheap\claimed` — 운영 낱말을 «언급» 만 하는 명령: 검색 · 스크립트 파일 읽기 · echo. 실행이 아니다.
# Mention-only commands: a search, reading the script file, echo. None of them runs a production channel.
_MENTIONS = ['grep -n "railway status" docs/a.md', "cat scripts/observe_db.py", "echo railway logs",
             # 교차 검토 반례 — 커밋 메시지(따옴표 안 명령 치환 속 heredoc · 따옴표 안 여러 줄)의 언급, 다른 명령의 인자인
             # `railway`, 운영에 닿지 않는 도움말 · 로컬 측정 / mentions in commit messages, arguments, help, local runs
             "git commit -m \"$(cat <<'EOF'\nfix: x\n\nrailway status is a read\nEOF\n)\"",
             'git commit -m "docs: line one\nrailway logs is read-only"',
             "git ls-files | xargs grep -l railway",
             "if command -v railway; then echo ok; fi",
             "py -3 scripts/observe_db.py --help",
             "python scripts/perf_measure.py --local-only"]


@pytest.mark.parametrize("command", _MENTIONS)
def test_a_mention_of_a_production_channel_is_not_audited(command, logs, monkeypatch, capsys):
    """언급은 호출이 아니다 — 통과하고, 어떤 기록도 남기지 않는다 / a mention is allowed and leaves no record."""
    work, audit, denials = logs
    assert _run(monkeypatch, capsys, _shell(command, work)) == ""
    assert not audit.exists() and not denials.exists()


# witness-corpus: python 으로 도는 리포 스크립트 가운데 운영에 닿지 않는 것(sqlite · 로컬 계측) — 감사 채널 목록 밖
_UNLISTED_REPO_SCRIPTS = ["py -3 scripts/retro_scope.py --json", "python scripts/analyzer_oracle.py",
                          "py -3 scripts/capture_readme_hero.py"]


@pytest.mark.parametrize("command", _UNLISTED_REPO_SCRIPTS)
def test_a_repo_script_that_never_reaches_production_is_not_audited(command, logs, monkeypatch, capsys):
    """대조군 — 목록 밖 리포 스크립트는 운영 채널이 아니다(통과 · 기록 없음) / not a production channel."""
    work, audit, denials = logs
    assert _run(monkeypatch, capsys, _shell(command, work)) == ""
    assert not audit.exists() and not denials.exists()


# witness-corpus: 운영 MCP 도구 가운데 읽기 목록 밖(배포 · SQL) — 감사가 아니라 거부 기록으로 간다
_UNLISTED_PRODUCTION_MCP_TOOLS = ["mcp__railway__deploy", "mcp__supabase__execute_sql"]


@pytest.mark.parametrize("tool", _UNLISTED_PRODUCTION_MCP_TOOLS)
def test_a_production_mcp_tool_outside_the_read_list_is_denied_not_audited(tool, logs, monkeypatch, capsys):
    """읽기 목록 밖 운영 MCP 도구는 막히고 감사 기록에는 오르지 않는다 / denied, never audited."""
    _, audit, denials = logs
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, {"tool_name": tool, "tool_input": {}})
    assert not audit.exists() and [r["kind"] for r in _records(denials)] == ["production"]


def test_a_denied_production_call_goes_to_the_denial_log_only(logs, monkeypatch, capsys):
    """막힌 운영 호출(`railway up` · 배포 MCP)은 거부 기록에만 — 감사 기록은 «허용된» 호출의 기록이다."""
    work, audit, denials = logs
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell("railway up", work))
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, {"tool_name": "mcp__railway__deploy", "tool_input": {}})
    assert not audit.exists()
    assert [r["kind"] for r in _records(denials)] == ["production", "production"]


def test_an_unrelated_command_leaves_no_record(logs, monkeypatch, capsys):
    """운영과 무관한 명령 · 운영과 무관한 리포 스크립트는 아무 기록도 남기지 않는다."""
    work, audit, denials = logs
    for command in ("git status", "ls docs", "py -3 scripts/retro_scope.py --json"):
        assert _run(monkeypatch, capsys, _shell(command, work)) == "", command
    assert not audit.exists() and not denials.exists()


# PowerShell 의 운영 채널 호출 — 대입(`$x = …`) · ForEach-Object · 괄호 하위 식 · 백슬래시 경로 · 블록 안 스크립트.
# PowerShell production-channel calls: assignment, ForEach-Object, subexpressions, backslash paths, scripts in blocks.
_POWERSHELL_ALLOWED = {
    'railway status; py -3 scripts\\observe_db.py "SELECT 1"': ["railway status", "observe_db"],
    "$s = railway status": ["railway status"],
    "$deps = railway deployment list --json | ConvertFrom-Json": ["railway deployment list"],
    "1..3 | ForEach-Object { railway logs }": ["railway logs"],
    '$r = py -3 scripts\\observe_db.py "SELECT 1"': ["observe_db"],
    "$id = (railway deployment list --json | ConvertFrom-Json)[0].id; railway logs $id":
        ["railway deployment list", "railway logs"],
    'foreach ($q in $queries) { py -3 scripts\\observe_db.py $q }': ["observe_db"],
}


@pytest.mark.parametrize("command", sorted(_POWERSHELL_ALLOWED))
def test_powershell_production_reads_are_audited(command, logs, monkeypatch, capsys):
    """PowerShell(기본 셸)에서도 같다 / the same in PowerShell, the default shell."""
    work, audit, _ = logs
    assert _run(monkeypatch, capsys, _shell(command, work, tool="PowerShell")) == ""
    assert [r["channels"] for r in _records(audit)] == [_POWERSHELL_ALLOWED[command]]


# 교차 검토가 짚은 막히지 않던 운영 변경(main 때부터) — PowerShell 대입 · ForEach-Object · `%` · 괄호 하위 식 · Measure-Command,
# 시간 제한 안의 셸 래퍼, Git Bash 의 `cmd //c`, 따옴표 안 명령 치환 속 셸 heredoc. Production changes that slipped through.
_UNBLOCKED_PRODUCTION_WRITES = [
    ("PowerShell", "$x = railway up"),
    ("PowerShell", "1..3 | ForEach-Object { railway up }"),
    ("PowerShell", "1..3 | % { railway up }"),
    ("PowerShell", "Write-Output (railway redeploy -y)"),
    ("PowerShell", "[void](railway up)"),
    ("PowerShell", "Measure-Command { railway redeploy }"),
    ("Bash", 'timeout 60 bash -c "railway up"'),
    ("Bash", "cmd //c railway up"),
    ("Bash", "x=$(bash <<'EOF'\nrailway up\nEOF\n)"),
    ("Bash", "git commit -m \"$(bash <<'EOF'\nrailway up\nEOF\n)\""),
]


@pytest.mark.parametrize("tool,command", _UNBLOCKED_PRODUCTION_WRITES)
def test_a_production_change_inside_a_wrapper_or_assignment_is_denied(tool, command, logs, monkeypatch, capsys):
    """🔴 운영 변경은 대입 · 블록 · 하위 식 · 래퍼 · heredoc 안에서도 막는다 — 감사 기록도 남지 않는다.
    A production change is denied inside assignments, blocks, subexpressions, wrappers and heredocs."""
    work, audit, _ = logs
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell(command, work, tool=tool)), command
    assert not audit.exists()


def test_a_powershell_find_regex_escape_keeps_its_meaning(logs, monkeypatch, capsys):
    """회귀 잠금(워크플로 C3 반례) — PowerShell 에서 명령 낱말의 백슬래시를 모두 / 로 바꾸면 find 의 정규식 `\\.` 가
    `/.` 가 되어 .env 를 고르는 find 가 통과했다. 명령 자리 해석은 main 과 같게 둔다.
    Regression lock: rewriting every backslash turned find's regex escape into a path and let a .env read through."""
    work, _, _ = logs
    (work / ".env").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    out = _run(monkeypatch, capsys, _shell("find . -regex '.*/\\.env$' -exec cat {} +", work, tool="PowerShell"))
    assert '"permissionDecision": "deny"' in out


def test_a_broken_audit_log_never_changes_the_verdict(tmp_path, monkeypatch, capsys):
    """기록은 계기이지 관문이 아니다 — 감사 기록을 못 써도(폴더 자리에 파일) 허용은 허용이다."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("SCAMANAGER_HOOK_AUDIT_LOG", str(blocker / "allows.jsonl"))
    assert _run(monkeypatch, capsys, _shell("railway status", tmp_path)) == ""


def test_the_suite_never_writes_the_real_audit_log():
    """🔴 시험은 실제 홈의 감사 기록을 건드리지 않는다 — 회고가 그 파일로 서술을 대 본다(conftest 가 임시 자리로 돌린다)."""
    log = os.environ.get("SCAMANAGER_HOOK_AUDIT_LOG", "")
    real = os.path.join(os.path.expanduser("~"), ".scamanager")
    assert log and not os.path.abspath(log).startswith(os.path.abspath(real)), log
