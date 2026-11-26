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
    "./scripts/railway_config.py": ["railway_config"],  # 실행 비트로 직접 돌린 스크립트 / run directly via its shebang
    # 최종 워크플로 패스(wf_bb53a27d-3cf) 반례 — 여러 줄 SQL 을 여는 줄의 호출 · 주석 속 아포스트로피 뒤의 다음 줄 ·
    # 시간 제한 뒤 직접 돌린 스크립트 / a call that opens a multi-line SQL string, the line after a comment's apostrophe
    "py -3 scripts/observe_db.py \"SELECT id, 'tag' AS t\nFROM analyses\nLIMIT 5\"": ["observe_db"],
    "railway logs # it's the deploy log\nrailway status": ["railway logs", "railway status"],
    "timeout 60 ./scripts/railway_config.py": ["railway_config"],
    # watch 는 인자 글자를 셸로 돌린다 · argparse 는 줄인 긴 옵션을 받는다(`--rest` = `--restart`)
    # watch runs its argument through a shell; argparse accepts an abbreviated long option
    "watch -n 30 'railway status'": ["railway status"],
    "py -3 scripts/railway_redeploy.py --rest": ["railway_redeploy --restart"],
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
             "python scripts/perf_measure.py --local-only",
             # 한 줄 따옴표 안의 `#` 은 따옴표 신뢰를 깨 `&&` 에서 잘린다 — 그 조각을 운영 호출로 적었다(하위 에이전트 재검토)
             # a `#` inside a one-line quoted message made the splitter cut at `&&` and audit the piece
             'git commit -m "feat: audit railway status && railway logs (#1917)"',
             # 최종 워크플로 패스 반례 — 다른 명령의 인자인 `railway`(검색어) · 주석 속 백틱 / an argument, a comment
             "if grep -q railway docs; then echo found; fi",
             "echo done # ran `railway status` earlier",
             "py -3 scripts/railway_redeploy.py --he"]  # 줄인 --help / an abbreviated --help


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
    "Start-Job { railway logs } | Receive-Job -Wait": ["railway logs"],
    # 전체 경로 railway 의 읽기 · 이름만 관용구는 통과하고 기록된다 / full-path reads and the names idiom pass and are audited
    "C:\\Users\\x\\AppData\\Roaming\\npm\\railway.cmd status": ["railway status"],
    "C:\\Users\\x\\AppData\\Roaming\\npm\\railway.cmd variables --kv | cut -d= -f1": ["railway variables"],
    # 한 줄 if/else 의 두 블록은 둘 다 코드다(최종 워크플로 패스) / both blocks of a one-line if/else are code
    "if ($x) { railway status } else { railway logs }": ["railway status", "railway logs"],
    "[string]$s = railway status --service x": ["railway status"],  # 형 제약이 붙은 대입 / a typed assignment
    # here-string 을 여는 줄 뒤의 호출 — 본문이 빠진 뒤 `@"` 가 따옴표를 열면 다음 줄이 따옴표 안으로 보인다
    # a call after a here-string: its dangling opener must not open a quote once the body is gone
    "$sql = @\"\nSELECT 1\n\"@\npy -3 scripts\\observe_db.py $sql": ["observe_db"],
}


# PowerShell 의 언급 — 블록 안 검색어 · 주석 속 괄호. 막지도 기록하지도 않는다(최종 워크플로 패스: 새 블록 머리가 블록 안의
# 아무 `railway` 낱말이나 호출로 읽었다). PowerShell mentions: a search term in a block, parentheses in a comment.
_POWERSHELL_MENTIONS = ["Get-ChildItem | % { Select-String -Path $_ -Pattern railway }",
                        "Write-Host done # see (railway status) docs",
                        "$sb = { railway logs --deployment x }",  # 블록을 정의만 한다 — 돌지 않는다 / only defined
                        # here-string 본문의 괄호는 글자다 — `$(…)` 만 돈다 / parentheses in a here-string body are text
                        "Write-Output @\"\nUse (railway up) to deploy\n\"@"]


@pytest.mark.parametrize("command", _POWERSHELL_MENTIONS)
def test_a_powershell_mention_is_neither_denied_nor_audited(command, logs, monkeypatch, capsys):
    """블록 · 주석 속 언급은 호출이 아니다 / a mention inside a block or a comment is not a call."""
    work, audit, denials = logs
    assert _run(monkeypatch, capsys, _shell(command, work, tool="PowerShell")) == "", command
    assert not audit.exists() and not denials.exists()


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
    ("PowerShell", "Start-Job { railway up } | Receive-Job -Wait"),
    ("PowerShell", "Invoke-Command -ScriptBlock { railway redeploy }"),
    # PowerShell 의 전체 경로 railway — 백슬래시를 이스케이프로 읽어 운영 판정이 railway 를 못 알아봤다(main 때부터 · 변수 쓰기는
    # credential 층이 «덤프» 로 우연히 막고 있었다 · 워크플로 C3 재검토). A full-path railway in PowerShell was unrecognised.
    ("PowerShell", "C:\\Users\\x\\AppData\\Roaming\\npm\\railway.cmd variables --set FOO=bar"),
    ("PowerShell", "C:\\tools\\railway.cmd up"),
    ("PowerShell", 'cmd /c "C:\\tools\\railway.cmd up"'),
    ("Bash", 'timeout 60 bash -c "railway up"'),
    ("Bash", "cmd //c railway up"),
    ("Bash", "x=$(bash <<'EOF'\nrailway up\nEOF\n)"),
    ("Bash", "git commit -m \"$(bash <<'EOF'\nrailway up\nEOF\n)\""),
    # 최종 워크플로 패스 반례(C3) — 바깥 명령이 치환의 출력을 실행한다 · 붙여 쓴 `EOF)` 뒤의 줄은 돈다 · 큰따옴표 안 산술은
    # heredoc 이 아니다 · 한 줄 if/else 의 두 번째 블록 / an outer runner, `EOF)` glued, arithmetic, the else block
    ("Bash", "bash -c \"$(cat <<'EOF'\nrailway up\nEOF\n)\""),
    ("Bash", "eval \"$(cat <<'EOF'\nrailway up\nEOF\n)\""),
    ("Bash", "git commit -m \"$(cat <<'EOF'\nmsg\nEOF)\"\nrailway up"),
    ("Bash", "x=$(cat <<'EOF'\nbody\nEOF)\nrailway up"),
    ("Bash", "echo \"$(( 1 << n ))\"\nrailway up\nn"),
    ("Bash", "echo $(( 1 << n ))\nrailway up\nn"),  # 따옴표 없는 산술 — main 은 `<< n` 을 heredoc 으로 읽었다
    ("PowerShell", "if ($x) { railway status } else { railway up }"),
    # watch · flock -c 는 인자 글자를 셸로 돌린다 · 형 제약이 붙은 대입(main 때부터) / shell text of watch and flock -c,
    # typed PowerShell assignments
    ("Bash", "watch -n 30 'railway up'"),
    ("Bash", "flock /tmp/x -c 'railway up'"),
    ("PowerShell", "[string]$s = railway up"),
    ("PowerShell", "[int[]]$a = railway up"),
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
