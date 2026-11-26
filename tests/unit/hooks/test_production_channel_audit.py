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
    # backfill 의 건식 실행(기본 — SQL 만 출력)은 막지 않고 기록한다. `--apply` 와 observer_setup 은 아래 거부 목록
    # the backfill dry run (its default) is allowed and audited; --apply and observer_setup are denied below
    "python -m scripts.backfill_repository_user_id": ["backfill_repository_user_id"],
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
    # 셋째 워크플로 패스(wf_f04c79d9-042) 반례 — xargs 자리표 `{}` · 겹친 훑는 머리 · 긴 옵션 값 · 주석의 아포스트로피 뒤
    # 치환 · case 갈래 · `$'…'` 뒤 / xargs placeholder, nested scan heads, long option values, comment apostrophe, case arm
    "railway deployment list --json | jq -r '.[].id' | head -3 | xargs -I {} railway logs --deployment {}":
        ["railway deployment list", "railway logs"],
    "if timeout 60 railway status; then echo ok; fi": ["railway status"],
    "timeout 60 npx @railway/cli status": ["railway status"],
    "watch --interval 5 railway status": ["railway status"],
    "# it's a read-only check\nDEP=$(railway status --json | jq -r .id)\necho \"$DEP\"": ["railway status"],
    'case "$ENVN" in prod) railway status ;; esac': ["railway status"],
    "echo $'it\\'s'; railway status": ["railway status"],
    # 감사 heredoc 잠금 — 산술 안 `<<` · `EOF)` 로 닫힌 뒤의 호출 · 치환 안 받는 명령(bash) · 하이픈 구분자 뒤의 호출
    # audit heredoc locks: arithmetic, a call after a glued `EOF)`, a bash receiver inside $(, a hyphenated delimiter
    "echo $(( 1 << n ))\nrailway status\nn": ["railway status"],
    'echo "$(( n << shift ))"\nrailway status': ["railway status"],
    "x=$(cat <<'EOF'\nbody\nEOF)\nrailway status": ["railway status"],
    "x=$(bash <<'EOF'\nrailway status\nEOF\n)": ["railway status"],
    "cat > notes.md <<END-NOTES\nhello\nEND-NOTES\nrailway status": ["railway status"],
    # 큰따옴표 속 `$( … )` 안의 따옴표는 바깥과 따로다 — 안쪽 아포스트로피가 뒤 호출을 홑따옴표 안으로 삼키지 않는다
    # quotes inside "$( … )" are their own; an inner apostrophe does not swallow the call that follows
    'x="$(echo "it\'s")" && railway status': ["railway status"],
    # 넷째 워크플로 패스(wf_410501e1-acb) — 줄 잇기 뒤 플래그 · 주석 속 플래그 이름 · 따옴표 친 Windows 인터프리터 경로 ·
    # printf 로 넘긴 명령 / a flag after a line continuation, flag names in a comment, a quoted Windows interpreter path
    "py -3 scripts/railway_redeploy.py \\\n  --restart": ["railway_redeploy --restart"],
    "py -3 scripts/railway_redeploy.py --check  # if green, --restart next": ["railway_redeploy --check"],
    'py -3 scripts/observe_db.py "SELECT 1"  # -h shows the options': ["observe_db"],
    '"C:\\Users\\me\\venv312\\Scripts\\python.exe" -B scripts/observe_db.py "SELECT 3"': ["observe_db"],
    "printf '%s\\n' 'railway status' | bash": ["railway status"],
    # 둘째 적대 패스(wf_150f221f-097) — 치환 몸 속 따옴표 안 `)` 는 몸을 닫지 않는다 / a quoted `)` does not close the body
    "echo \"now: $(railway status | sed -n 's/^Service: \\([^)]*\\).*/\\1/p'; railway whoami)\"":
        ["railway status", "railway whoami"],
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
             "py -3 scripts/railway_redeploy.py --he",  # 줄인 --help / an abbreviated --help
             "py -3 scripts/observer_setup.py --help",  # 사용자 몫 스크립트의 도움말 / help of a user-only script
             # 워크플로 패스(wf_f44bc84a-458) — `-c` 없는 flock 은 낱말을 바로 실행한다(셸 글자가 아니다) · xargs 는 앞
             # 단계 글자를 stdin 이 아니라 인자로 넘긴다 / flock without -c execs words; xargs passes text as arguments
             'flock /tmp/x.lock git commit -m "docs: 배포 절차; railway up 은 사용자 몫"',
             "git grep -l 'railway up' -- '*.sh' | xargs -n1 bash -n",
             # 큰따옴표 속 `$( … )` 안의 따옴표 글자 · `command -v` 는 이름 찾기 / quotes inside "$( … )", name lookup only
             'x="$(echo "a; railway status later")"',
             "command -v railway status",
             # 셋째 워크플로 패스 — 본문에 큰따옴표가 든 커밋 메시지 heredoc · `EOF)` 로 붙여 쓴 heredoc · `<<\\EOF` ·
             # 이스케이프된 구분자 / a commit-message heredoc with a quote in it, a glued `EOF)`, `<<\\EOF`, an escaped `;`
             "git commit -m \"$(cat <<'EOF'\nfix(hooks): treat \"$(cat <<'EOF' bodies as data\n\n"
             + "railway logs inside such a body is not a call\nEOF\n)\"",
             "NOTES=$(cat <<'EOF'\nrailway status was green\nEOF)\necho \"$NOTES\"",
             "cat > notes.txt <<\\EOF\nrailway status looked fine\nEOF",
             "cat > notes.txt <<\\EOF\n$(railway status)\nEOF",  # `<<\\EOF` 본문의 치환은 글자다 / literal body
             "py -3 scripts/perf_measure.py \\\n  --local-only",  # 줄 잇기 뒤 로컬 측정 / local-only after a continuation
             "echo done \\; railway status",
             # 셋째 패스가 짚은 새 거부(C3) — 판정은 main 그대로라 통과한다 / new false denials of the third pass, now main's
             "if npm ls -g @railway/cli >/dev/null 2>&1; then echo installed; fi",
             "timeout 60 bash -c 'if grep -q railway notes.md; then echo yes; fi'",
             "MSG=$(cat <<'EOF'\nIf railway up fails, retry by hand\nEOF)\ngit commit -m \"$MSG\"",
             "cat > notes.md <<END-NOTES\nIf railway up fails, retry by hand\nEND-NOTES",
             "NOTES=$(cat <<'EOF'\nrailway up was run by the user\nEOF)\necho \"$NOTES\"",
             # 둘째 적대 패스(wf_150f221f-097)의 새 거부 — 갈래 패턴의 `|` · 배열 원소 · 따옴표 속 `| bash` 가 든 제목 뒤
             # heredoc 본문 · `[[ … && … ]]` · 문법만 보는 `bash -n` · 큰따옴표 속 `<(` · 스크립트 파일을 받은 셸의 heredoc
             'case "$f" in scripts/observer_setup.py|scripts/backfill_repository_user_id.py) echo skip ;; *) echo check ;; esac',
             'if true; then case "$f" in scripts/observer_setup.py|*.sh) echo skip ;; esac; fi',
             'files=(scripts/railway_config.py scripts/observer_setup.py); for f in "${files[@]}"; do wc -l "$f"; done',
             "gh pr create --title 'fix(hooks): `… | xargs -n1 bash -n` 을 실행으로 읽지 않는다 (원장 #1917 P1-19)' "
             + "--body-file - <<'EOF'\n## Summary\n- `railway up` · `railway redeploy` 는 그대로 막는다\nEOF",
             "gh release create v1.4.0 --title 'v1.4.0 — curl … | sh 설치 (#1917)' --notes-file - <<'EOF'\n"
             + "- observer 설정: `py -3 scripts/observer_setup.py --host <host>` (사용자)\nEOF",
             "gh pr create --title 'fix(hooks): … | timeout 60 bash 오독 (#1917)' --body \"$(cat <<'EOF'\n## 변경\n"
             + "1) 사용자 몫 스크립트: `py -3 scripts/observer_setup.py`\n2) 그 밖은 그대로\nEOF\n)\"",
             "[[ -f /tmp/stamp && scripts/observer_setup.py -nt /tmp/stamp ]] && echo changed",
             "printf '%s\\n' 'railway up' | bash -n 2>/dev/null && echo syntax-ok",
             'git commit -m "fix(hooks): <(py -3 scripts/observer_setup.py) 프로세스 치환 표기"',
             "timeout 60 bash ./scripts/render.sh <<'EOF'\nrailway up 은 사용자 몫\nEOF",
             # 셋째 적대 패스(wf_b8f2f206-703)의 새 거부 — 여러 줄 배열의 원소 · 따옴표 없는 heredoc 본문의 `<( )`(본문에서
             # 펼쳐지는 것은 `$( )` · 백틱뿐) / multi-line array elements; `<( )` in an unquoted heredoc body is text
             'files=(\n  "scripts/observer_setup.py"\n  "scripts/observe_db.py"\n)\n'
             + 'for f in "${files[@]}"; do py -3 -m py_compile "$f"; done',
             "cat > pr_body.md <<EOF\nHEAD: $(git rev-parse --short HEAD)\n"
             + "- \\`<(py -3 scripts/observer_setup.py)\\` inside double quotes is text now\nEOF",
             "cat > notes.md <<EOF\nBranch: $(git branch --show-current)\n"
             + "It's about \\`diff <(railway up) expected.txt\\` being read as a call\nEOF"]


@pytest.mark.parametrize("command", _MENTIONS)
def test_a_mention_of_a_production_channel_is_not_audited(command, logs, monkeypatch, capsys):
    """언급은 호출이 아니다 — 통과하고, 어떤 기록도 남기지 않는다 / a mention is allowed and leaves no record."""
    work, audit, denials = logs
    assert _run(monkeypatch, capsys, _shell(command, work)) == ""
    assert not audit.exists() and not denials.exists()


# witness-corpus: python 으로 도는 리포 스크립트 가운데 운영에 닿지 않는 것(sqlite · 로컬 계측) — 감사 채널 목록 밖
_UNLISTED_REPO_SCRIPTS = ["py -3 scripts/retro_scope.py --json", "python scripts/analyzer_oracle.py",
                          "py -3 scripts/capture_readme_hero.py", "py -3 scripts/pre_push_gate.py",
                          "python scripts/e2e_budget.py"]


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
    # 셋째 워크플로 패스 — here-string 뒤의 치환 · 블록, 본문 아포스트로피 뒤의 치환, 다음 줄의 foreach 블록, 글자를 받는 iex,
    # 괄호 식의 멤버 / after a here-string, an apostrophe in its body, a next-line block, iex input, a member of (…)
    "$b = @'\nx\n'@\nWrite-Output $(railway status)": ["railway status"],
    "$report = @\"\nRailway's status: $(railway status)\n\"@\nWrite-Output $report": ["railway status"],
    "$note = @'\ndeploy check\n'@\n1..2 | ForEach-Object { railway status }": ["railway status"],
    "foreach ($id in @('a','b'))\n{ railway logs --deployment $id }": ["railway logs"],
    '"railway status" | Invoke-Expression': ["railway status"],
    "$who = (railway whoami).Trim()": ["railway whoami"],
    # 주석 속 짝 없는 괄호가 뒤 블록을 삼키지 않는다 / an unbalanced bracket in a comment does not swallow later blocks
    "Write-Host x # note (\n1..2 | % { railway status }": ["railway status"],
    "$p = Start-Process -FilePath railway -ArgumentList 'logs','--json' -NoNewWindow -Wait -PassThru": ["railway logs"],
    # 넷째 워크플로 패스 — 백틱 줄 잇기 · 주석 속 플래그 · 호출 연산자 · 따옴표 안의 `@'` 는 here-string 이 아니다
    # a backtick continuation, flags in a comment, the call operator, `@'` inside quotes is not a here-string
    "py -3 scripts\\railway_redeploy.py `\n    --check": ["railway_redeploy --check"],
    "py -3 scripts\\backfill_repository_user_id.py  # dry run first, --apply later": ["backfill_repository_user_id"],
    'py -3 scripts\\observe_db.py "SELECT 2"  # -h lists options': ["observe_db"],
    "& 'C:\\x\\railway.cmd' status": ["railway status"],
    "Get-Content docs\\a.md | Select-String -Pattern '@'\nrailway status": ["railway status"],
}


# PowerShell 의 언급 — 블록 안 검색어 · 주석 속 괄호. 막지도 기록하지도 않는다(최종 워크플로 패스: 새 블록 머리가 블록 안의
# 아무 `railway` 낱말이나 호출로 읽었다). PowerShell mentions: a search term in a block, parentheses in a comment.
_POWERSHELL_MENTIONS = ["Get-ChildItem | % { Select-String -Path $_ -Pattern railway }",
                        "Write-Host done # see (railway status) docs",
                        "Write-Host done # never here (railway up)",  # 주석 속 쓰기도 글자다 — main 처럼 통과
                        "$sb = { railway logs --deployment x }",  # 블록을 정의만 한다 — 돌지 않는다 / only defined
                        # here-string 본문의 괄호는 글자다 — `$(…)` 만 돈다 / parentheses in a here-string body are text
                        "Write-Output @\"\nUse (railway up) to deploy\n\"@",
                        # 셋째 워크플로 패스 — 정의만 한 블록 안 · 블록 주석 / inside a block only defined, a block comment
                        "$check = { railway whoami; railway status }",
                        "function Get-DeployStatus {\n    railway status --json\n}",
                        "<#\nrailway logs --deployment X\n#>\nGet-Date",
                        "$sb = { Write-Output $(railway status) }",  # 정의만 한 블록 속 치환 / a substitution in it
                        # 넷째 워크플로 패스 — 따옴표로 시작하는 문장은 글자 식이다(`&` 가 없으면 부르지 않는다)
                        # a statement that starts with a quoted string is an expression, not a call
                        "$script = 'scripts\\railway_redeploy.py'",
                        '$target = "scripts\\railway_redeploy.py"; git log --oneline -5 -- $target',
                        "'scripts/observe_db.py' | ForEach-Object { py -3 -m py_compile $_ }",
                        # 셋째 패스가 짚은 새 거부(C3) — 판정은 main 그대로라 통과한다 / now main's verdict
                        "@'\n## 요약\n- 허용된 운영 채널 호출을 값 없이 기록한다\n'@ | Set-Content -Encoding utf8 pr-body.md\n"
                        + "gh pr create --base main --title 'feat(hooks): 운영 채널 감사 기록 (railway 읽기 · 운영 스크립트)' "
                        + "--body-file pr-body.md",
                        "git log --oneline -20 | ForEach-Object { if ($_ -match 'railway') { $_ } }",
                        "$counts = @{ 'railway' = 0; 'supabase' = 0 }",
                        "$hasRailway = 'railway' -in $tools",
                        "if (Test-Path C:\\Users\\me\\AppData\\Roaming\\npm\\railway.cmd) { Write-Host 'installed' }",
                        "$versions = @{ railway = '4.10'; node = '22' }",
                        "@{ railway = 1; up = 2 } | ConvertTo-Json",  # 해시 테이블 키는 명령이 아니다 / keys, not calls
                        # 워크플로 패스(wf_f44bc84a-458) — switch 라벨 · Set-Item 정의 · 붙여 쓴 `=1` · Start-Process 값 옵션
                        # switch labels, a Set-Item definition, a glued `=1` key, a Start-Process value option
                        "$base = switch ($Target) { railway { 'https://x.up.railway.app' } local { 'http://127.0.0.1:8000' } }",
                        "'railway','local' | ForEach-Object { switch ($_) { railway { 'remote' } default { 'local' } } }",
                        "Write-Output (switch ($t) { railway { 'r' } default { 'l' } })",
                        "Set-Item -Path function:Deploy -Value { railway up }",
                        "$h = @{ railway =1 }",
                        "Start-Process -WorkingDirectory C:\\work\\railway pwsh",
                        # 둘째 적대 패스(wf_150f221f-097) — 띄어 쓴 배열의 도움말 · 줄인 값 매개변수 · class 상속 · 정의 블록 속
                        # "$( )" · 큰따옴표 속 `@(` · 겹친 홑따옴표 · 백틱으로 이스케이프한 따옴표 뒤 here-string
                        "Start-Process py -ArgumentList '-3', 'scripts/observer_setup.py', '--help' -NoNewWindow -Wait",
                        "Start-Process -FilePath py -ArgumentList '-3', 'scripts\\observer_setup.py', '-h' -Wait",
                        "Start-Process railway -ArgumentList 'up', '--help' -NoNewWindow -Wait",
                        "Start-Process -WorkingDir C:\\work\\railway notepad",
                        "class Deployer : Object {\n  [void] Run() { railway up }\n}",
                        'function Setup { Write-Host "$(py -3 scripts/observer_setup.py)" }',
                        'git commit -m "docs: @(py -3 scripts/observer_setup.py) 는 사용자 몫"',
                        "$r = Invoke-Expression 'Write-Host ''build ok; railway up is user-only'''",
                        "Start-Process pwsh -ArgumentList '-NoProfile -Command \"Write-Host ''note; railway up''\"'",
                        "gh pr create --title \"Support 4`\" displays\" --body @'\nit's done\nrailway up\n'@",
                        # 셋째 적대 패스(wf_b8f2f206-703) — 펼치는 here-string 속 `@( )` 는 글자다 · 채널 스크립트 이름의
                        # switch 라벨 / `@( )` in an expandable here-string is text; a script name as a switch label
                        '$body = @"\nBase: $(git rev-parse --short origin/main)\n'
                        + '- @(py -3 scripts/observer_setup.py) inside a double-quoted string is text\n"@\n'
                        + 'gh pr create --title "fix(hooks): array subexpression text" --body $body',
                        "switch ((Split-Path 'scripts\\observer_setup.py' -Leaf)) { observer_setup.py { 'user-only' } "
                        + "default { 'auto' } }"]


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


# 운영 변경 — main 의 판정 순회가 놓치던 꼴까지 명령 자리 순회가 막는다(원장 #1917 P1-19 — PowerShell 대입 · 블록 · 하위 식
# · 전체 경로, 시간 제한 뒤 래퍼, `cmd //c`, heredoc 받는 명령 · 산술 · 붙여 쓴 `EOF)` · 하이픈 구분자, watch · flock, case
# 갈래, 겹친 훑는 머리 뒤 패키지 실행기). 막힌 호출은 감사 기록에 오르지 않는다.
# Production changes main's walk missed are denied by the command-position walk, and never audited.
_PRODUCTION_WRITES = [
    ("PowerShell", "$x = railway up"),
    ("PowerShell", "1..3 | ForEach-Object { railway up }"),
    ("PowerShell", "1..3 | % { railway up }"),
    ("PowerShell", "Write-Output (railway redeploy -y)"),
    ("PowerShell", "[void](railway up)"),
    ("PowerShell", "Measure-Command { railway redeploy }"),
    ("PowerShell", "Start-Job { railway up } | Receive-Job -Wait"),
    ("PowerShell", "Invoke-Command -ScriptBlock { railway redeploy }"),
    ("PowerShell", "C:\\Users\\x\\AppData\\Roaming\\npm\\railway.cmd variables --set FOO=bar"),
    ("PowerShell", "C:\\tools\\railway.cmd up"),
    ("PowerShell", 'cmd /c "C:\\tools\\railway.cmd up"'),
    ("PowerShell", "if ($x) { railway status } else { railway up }"),
    ("PowerShell", "[string]$s = railway up"),
    ("PowerShell", "[int[]]$a = railway up"),
    ("PowerShell", "& 'C:\\x\\railway.cmd' up"),
    ("PowerShell", "try { railway status } catch { railway redeploy -y }"),
    ("PowerShell", "foreach ($s in 1..2) { railway up }"),
    ("PowerShell", "'$x = railway up' | Invoke-Expression"),  # 앞 단계 글자를 돌린다 — main 은 대입 머리를 못 봤다
    ("Bash", 'timeout 60 bash -c "railway up"'),
    ("Bash", "cmd //c railway up"),
    ("Bash", "x=$(bash <<'EOF'\nrailway up\nEOF\n)"),
    ("Bash", "git commit -m \"$(bash <<'EOF'\nrailway up\nEOF\n)\""),
    ("Bash", "x=$(cat <<'EOF'\nbody\nEOF)\nrailway up"),
    ("Bash", "echo $(( 1 << n ))\nrailway up\nn"),
    ("Bash", "cat > notes.md <<END-NOTES\nhello\nEND-NOTES\nrailway up"),
    ("Bash", "watch -n 30 'railway up'"),
    ("Bash", "flock /tmp/x -c 'railway up'"),
    ("Bash", 'case "$ENVN" in prod) railway up ;; esac'),
    ("Bash", "timeout 60 npx @railway/cli up"),
    ("Bash", "railway status; timeout 60 bash -c \"railway redeploy -y\""),
    # 워크플로 패스(wf_f44bc84a-458) — `-I{}` 붙여 쓴 xargs · 줄의 `#` 가 따옴표 분할을 끄던 꼴 · eval · iex 매개변수 ·
    # 재지정 · 재지정 · 훑는 머리 뒤 heredoc 받는 명령 · Start-Process 인자 목록 · 접두어 옵션 · 띄어 쓴 case 갈래 · 주석 속
    # `<<'EOF'` / attached -I{}, a `#` on the line, eval, iex parameters, redirects, heredoc receivers, Start-Process lists
    ("Bash", "xargs -I{} sh -c 'railway redeploy --service {} --yes' < services.txt"),
    ("Bash", "printf '%s\\n' api worker | xargs -I{} bash -c 'railway redeploy --service {} --yes'"),
    ("Bash", 'bash -c "railway up --detach; echo exit=$?" # deploy'),
    ("Bash", "bash -lc \"railway redeploy --yes && echo 'redeployed for #1917'\""),
    ("PowerShell", 'powershell -NoProfile -Command "railway up; exit $LASTEXITCODE" # deploy'),
    ("Bash", 'eval "railway up"'),
    ("PowerShell", 'Invoke-Expression -Command "railway up"'),
    ("PowerShell", "$out = Invoke-Expression -Command 'railway redeploy --yes'"),
    ("PowerShell", 'Invoke-Expression -ErrorAction Stop "railway up"'),
    ("Bash", 'echo "railway up" | bash 2>&1'),
    ("Bash", "printf '%s\\n' 'railway redeploy --service api --yes' | bash > /tmp/redeploy.log"),
    ("PowerShell", '"railway up" | iex 2>&1'),
    ("Bash", "bash 2>&1 <<'EOF'\nrailway up --detach\nEOF"),
    ("Bash", "timeout 600 bash <<'EOF'\nrailway up --detach\nEOF"),
    ("PowerShell", "Start-Process pwsh -ArgumentList '-NoProfile','-Command','railway up' -Wait"),
    ("PowerShell", "Start-Process -ArgumentList 'up' -FilePath railway -Wait"),
    ("Bash", "time -p railway up"),
    ("Bash", 'case "$ENV" in\n  prod ) railway up ;;\nesac'),
    ("Bash", "# 본문은 <<'EOF' heredoc 으로 넘긴다\nrailway up"),
    ("Bash", "echo railway up 2>&1 | bash"),  # 재지정의 `&` 는 구분자가 아니다 — main 은 거기서 나눠 놓쳤다
    # 둘째 적대 패스(wf_150f221f-097) 고침의 대조군 — 갈래 · 배열 · `[[ ]]` 뒤 · 몸 속 따옴표 괄호 · `|&` 로 받는 셸 ·
    # 띄어 쓴 배열 · 겹친 따옴표 / controls for that pass's fixes; `|& bash` was missed by main too
    ("Bash", 'case "$env" in prod|production) railway up ;; esac'),
    ("Bash", 'svc=(api worker); for s in "${svc[@]}"; do railway redeploy --service "$s" -y; done'),
    ("Bash", '[[ -n "$CI" ]] && railway up'),
    ("Bash", "x=$(echo 'a)b'; railway up)"),
    ("Bash", "cat <<'EOF' |& bash\nrailway up\nEOF"),
    ("Bash", "( case $e in prod) railway up ;; esac )"),  # 묶음 안의 case 머리 / a case head inside a group
    ("Bash", "{ case $e in prod|production) railway up ;; esac; }"),
    ("Bash", "echo railway up | xargs bash"),  # bash 는 `railway` 를 PATH 에서 찾아 돌린다 / bash finds it on PATH
    # 셋째 적대 패스(wf_b8f2f206-703) — main 도 놓치던 꼴: 치환 · 따옴표가 든 case 주제와 갈래 · case 갈래 안의 heredoc 받는
    # 명령 · env 뒤의 셸 · 인자 배열 · 백틱 이스케이프 · 매개변수가 붙은 `| iex` · `eval --` · `\n` 이 든 printf ·
    # `bash -c "$(cat)"` · PowerShell 속성 · `${}` · 여러 변수 대입 / shapes main missed as well
    ("Bash", 'case "$(git branch --show-current)" in main) railway up ;; *) echo skip ;; esac'),
    ("Bash", "case `uname -s` in MINGW*) railway up;; esac"),
    ("Bash", 'case "$1 $2" in "prod up") railway up;; esac'),
    ("Bash", "case \"$1\" in\n  deploy) bash -s <<'EOF'\nrailway up\nEOF\n  ;;\nesac"),
    ("Bash", "env RAILWAY_ENVIRONMENT=production bash <<'EOF'\nrailway up\nEOF"),
    ("Bash", "cat <<'EOF' | env bash -s\nrailway up\nEOF"),
    ("Bash", 'echo "railway up" | env RAILWAY_ENVIRONMENT=production bash'),
    ("Bash", 'NOTE="(hotfix) deploy" timeout 600 bash -c "railway up"'),
    ("Bash", "timeout 60 bash -c \"$(cat)\" <<'EOF'\nrailway up\nEOF"),
    ("Bash", 'eval -- "railway up"'),
    ("Bash", "printf 'set -e\\nrailway up\\n' | bash"),
    ("PowerShell", "Start-Process pwsh -ArgumentList @('-NoProfile', '-Command', 'railway up') -Wait"),
    ("PowerShell", "Start-Process bash -ArgumentList @('-c', 'railway up') -NoNewWindow -Wait"),
    ("PowerShell", 'Start-Process pwsh -ArgumentList "-NoProfile -Command `"railway up`"" -Wait'),
    ("PowerShell", 'pwsh -NoProfile -Command "& `"$env:APPDATA\\npm\\railway.cmd`" up"'),
    ("PowerShell", '"railway redeploy --yes" | Invoke-Expression -ErrorAction Stop'),
    ("PowerShell", '"railway up" | Invoke-Expression -Verbose:$false'),
    ("PowerShell", "@'\nrailway up\n'@ | & pwsh -NoProfile -Command -"),
    ("PowerShell", "$result = Invoke-Expression @'\nrailway up\n'@"),
    ("PowerShell", "$r.Output = railway up"),
    ("PowerShell", "${out} = railway up"),
    ("PowerShell", "$a, $b = railway up"),
    ("PowerShell", "Start-Process railway -ArgumentList 'up', '--detach' -NoNewWindow -Wait"),
    ("PowerShell", "$r = Invoke-Expression 'railway up; Write-Host ''done'''"),
]


@pytest.mark.parametrize("tool,command", _PRODUCTION_WRITES)
def test_a_production_change_is_denied_and_never_audited(tool, command, logs, monkeypatch, capsys):
    """🔴 운영 변경은 대입 · 블록 · 하위 식 · 래퍼 · heredoc 안에서도 막는다 — 감사 기록에는 오르지 않는다(채널은 읽기뿐).
    A production change is denied in every shape above and never becomes an audit channel."""
    work, audit, _ = logs
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell(command, work, tool=tool)), command
    assert not audit.exists(), command


# 사용자 몫 운영 스크립트 — 관측 역할 비밀번호 설정 · backfill 적용(11-26 사용자 결정 · 원장 P1-19). 도움말과 backfill
# 건식 실행은 막지 않는다. User-only production scripts are denied; help and the backfill dry run are not.
_USER_ONLY_SCRIPTS = [
    ("Bash", f"py -3 scripts/observer_setup.py --host {_MARKER} --ref r1"),
    ("Bash", "py -3 scripts/observer_setup.py"),
    ("PowerShell", "py -3 scripts\\observer_setup.py"),
    ("Bash", "python -m scripts.backfill_repository_user_id --apply"),
    ("Bash", "py -3 scripts/backfill_repository_user_id.py \\\n  --apply"),
    ("Bash", "timeout 600 py -3 scripts/backfill_repository_user_id.py --apply"),
    ("Bash", "py -3 scripts/backfill_repository_user_id.py --app"),  # argparse 줄임 / an abbreviation
    ("Bash", "py -3 scripts/backfill_repository_user_id.py --a"),  # 그 스크립트에는 `--a` 로 시작하는 옵션이 하나뿐
    ("Bash", "ls *.csv | xargs -I{} sh -c 'py -3 scripts/backfill_repository_user_id.py --apply'"),
    ("Bash", 'eval "py -3 scripts/observer_setup.py"'),
    ("PowerShell", 'Invoke-Expression -Command "py -3 scripts\\observer_setup.py"'),
    ("Bash", 'echo "py -3 scripts/backfill_repository_user_id.py --apply" | bash 2>&1'),
    ("PowerShell", "Start-Process py -ArgumentList '-3','scripts\\observer_setup.py' -Wait -NoNewWindow"),
    ("PowerShell", "Start-Process py -ArgumentList 'scripts\\backfill_repository_user_id.py','--apply' -Wait -NoNewWindow"),
    ("PowerShell", 'Start-Process -FilePath python -ArgumentList "scripts\\observer_setup.py --host h --ref r" -Wait'),
    ("Bash", "python -um scripts.observer_setup"),  # 묶은 짧은 옵션 / clustered short options
    ("PowerShell", "Start-Process py -ArgumentList '-3', 'scripts/observer_setup.py' -Wait"),  # 띄어 쓴 배열
    # 셋째 적대 패스(wf_b8f2f206-703) — case 갈래 · 괄호 배열 · 백틱 이스케이프 · `| iex` 매개변수 · 따옴표 속 `(` 가 든
    # 앞 대입 · 붙여 쓴 `-m` / the same shapes reaching user-only scripts
    ("Bash", 'case "$(git branch --show-current)" in main) py -3 scripts/observer_setup.py;; esac'),
    ("PowerShell", "Start-Process -FilePath py -ArgumentList ('-3', 'scripts\\backfill_repository_user_id.py', '--apply')"),
    ("PowerShell", 'Start-Process py -ArgumentList "-3 `"scripts\\observer_setup.py`"" -Wait'),
    ("PowerShell", "'py -3 scripts\\observer_setup.py' | iex -ErrorAction Stop"),
    ("Bash", 'MSG="(wip) rotate" py -3 scripts/observer_setup.py'),
    ("Bash", "python -mscripts.observer_setup"),
    ("Bash", "py -3 -mscripts.backfill_repository_user_id --apply"),
]


@pytest.mark.parametrize("tool,command", _USER_ONLY_SCRIPTS)
def test_a_user_only_production_script_is_denied(tool, command, logs, monkeypatch, capsys):
    """🔴 사용자가 `!` 로 돌리는 운영 스크립트는 막는다 — 거부 기록에 인자는 남지 않는다.
    A script the user runs with `!` is denied; its arguments never reach the denial record."""
    work, audit, denials = logs
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell(command, work, tool=tool)), command
    assert not audit.exists() and denials.exists()
    assert _MARKER not in denials.read_text(encoding="utf-8")


def test_a_full_path_railway_variable_write_in_powershell_stays_denied(logs, monkeypatch, capsys):
    """🔴 회귀 잠금(검증 검토) — credential 층이 PowerShell 백슬래시를 글자로 읽어 전체 경로 `railway.cmd variables --set` 를
    «쓰기» 로 알아보고 덤프 판정을 비켰는데, main 의 운영 판정은 그 전체 경로를 못 알아봐 변수 쓰기가 통과했다. 쓰기로
    비키는 것은 운영 판정이 그 단계를 막을 때만이다. Regression lock: the write excuse needs the production verdict."""
    work, audit, _ = logs
    command = "C:\\Users\\x\\AppData\\Roaming\\npm\\railway.cmd variables --set FOO=bar"
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell(command, work, tool="PowerShell"))
    assert not audit.exists()


# PowerShell 변수 · 배열 · 굽은 따옴표는 shlex 가 모르는 인자를 만든다 — 백슬래시 경로의 «이름만» 관용구에 `--set` ·
# `--json` 을 숨기면 main 은 막았고(경로를 못 읽어서) 글자 읽기는 이름만으로 비켰다(넷째 워크플로 패스). PowerShell 의
# `prod\ set` 은 두 낱말이라 `set` 이 하위 명령 자리에 선 변수 쓰기 꼴이다 — main 은 Bash 읽기로 서비스 이름에 붙여 통과시켰고
# 명령 자리 순회가 막는다(원장 P1-19). PowerShell variables, arrays and curly quotes smuggle flags past the names-only
# excuse; in PowerShell `prod\ set` is two words, a variable-write shape the command-position walk denies.
_POWERSHELL_VARIABLE_VERDICTS = [
    ("$s = '--set'; C:\\x\\railway.cmd variables $s K=V --kv | cut -d= -f1", "deny"),
    ("C:\\x\\railway.cmd variables --kv --service api,--set,K=V | cut -d= -f1", "deny"),
    ("C:\\x\\railway.cmd variables --kv \u2018--set\u2019 K=V | cut -d= -f1", "deny"),
    ("$f = '--json'; C:\\x\\railway.cmd variables $f --kv | cut -d= -f1", "deny"),
    ("railway variables --kv --environment prod\\ set | wc -l", "deny"),
    ("railway variables --kv --service api\\ set | cut -d= -f1", "deny"),
    ("railway variables --kv --environment prod | wc -l", "allow"),  # 개수만 — main 처럼 / a count only, as on main
    # 쓰기 비킴의 두 갈래 — 정의만 한 블록 속 전체 경로 쓰기는 명령 자리 순회가 보지 않으니 credential 층이 막고(main 처럼),
    # 다른 명령의 인자인 언급은 쓰기 꼴이어도 개수만 중화로 내려가 통과한다(main 처럼)
    # the write excuse: a full-path write inside a defined block stays denied; a mention piped to a count passes
    ("$sb = { C:\\x\\railway.cmd variables --set K=V }", "deny"),
    ("Write-Output railway variables --kv --environment prod\\ set | wc -l", "allow"),
    ("C:\\x\\railway.cmd variables --kv | cut -d= -f1", "allow"),
    ("npx @railway/cli variables --kv | cut -d= -f1", "allow"),  # 패키지 이름의 `@` 는 스플랫이 아니다 / not a splat
]


@pytest.mark.parametrize("command,verdict", _POWERSHELL_VARIABLE_VERDICTS)
def test_powershell_railway_variable_idioms_keep_mains_verdict(command, verdict, logs, monkeypatch, capsys):
    """🔴 이름만 관용구를 글자로 읽어 푸는 것은 PowerShell 이 셸 문법으로 인자를 바꾸지 않을 때만 — 그 밖은 main 의 판정.
    The names-only relaxation applies only when PowerShell syntax cannot change the arguments."""
    work, _, _ = logs
    denied = '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell(command, work, tool="PowerShell"))
    assert denied == (verdict == "deny"), command


# witness-corpus: 손으로 적은 이름 목록 밖의 같은 PowerShell 매개변수 — 문서 별칭(-RSO · -RunAs · -proga) · 앞부분 줄임 · 붙여 쓴 값
_POWERSHELL_PARAMETER_SPELLINGS = {
    "Start-Process -RSO out.txt railway up -Wait": True,  # -RSO = -RedirectStandardOutput — 값을 받는다
    "Start-Process -Arg up -File railway -Wait": True,  # -Arg · -File = -ArgumentList · -FilePath 의 앞부분
    "Start-Process -FilePath:railway -ArgumentList:up": True,  # 붙여 쓴 값 / colon-attached values
    "Start-Process -RunAs $cred railway up": True,  # -RunAs = -Credential
    'Invoke-Expression -ErrorA Stop "railway up"': True,  # -ErrorA = -ErrorAction 의 앞부분
    'Invoke-Expression -proga SilentlyContinue "railway up"': True,  # -proga = -ProgressAction
    'Invoke-Expression -Command:"railway up"': True,
    'Invoke-Expression -wa SilentlyContinue "railway up"': True,  # -wa = -WarningAction 별칭 — 앞부분으로는 -WarningVariable 과 겹친다
    "Start-Process -Work C:\\railway notepad": False,  # -Work = -WorkingDirectory — 그 경로는 실행 파일이 아니다
    "Start-Process -RSO railway.log notepad readme.md": False,
    'Invoke-Expression -ErrorA Stop "Write-Host railway up"': False,
}
# witness-corpus: Bash 의 같은 꼴 — 목록 밖 긴 옵션(sudo --user · time --output) · 표준 출력과 오류를 함께 넘기는 파이프 `|&`
_BASH_OPTION_SPELLINGS = {
    "sudo --user deploy railway up": True,
    "time --output t.log railway up": True,
    'echo "railway up" |& bash': True,
    "printf 'railway redeploy -y\\n' |& sh": True,
    "git log --oneline |& grep railway": False,
    "py -3 scripts/backfill_repository_user_id.py --ap": True,  # argparse 줄임 — 목록 글자 `--apply` 가 없다
    "py -3 scripts/observer_setup.py --he": False,  # 도움말 줄임 / an abbreviated --help
    "py -3 scripts/observer_setup.py -h": False,
}


@pytest.mark.parametrize("tool,command,denied",
                         [("PowerShell", c, d) for c, d in _POWERSHELL_PARAMETER_SPELLINGS.items()]
                         + [("Bash", c, d) for c, d in _BASH_OPTION_SPELLINGS.items()])
def test_an_option_spelled_outside_the_listed_names_reads_like_the_listed_name(tool, command, denied, logs,
                                                                               monkeypatch, capsys):
    """🔴 매개변수 · 옵션 목록은 손으로 적었다 — PowerShell 바인더처럼 별칭 · 유일한 앞부분 · 붙여 쓴 값을 풀고, Bash 의 긴
    옵션 · `|&` 도 같은 자리로 읽는다. Option spellings outside the hand-written lists read like the listed names."""
    work, _, _ = logs
    verdict = '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell(command, work, tool=tool))
    assert verdict == denied, command


def test_script_option_table_matches_each_scripts_argparse():
    """🔴 줄임 플래그를 스크립트마다 푸는 표(`_PROD_SCRIPT_OPTIONS`)는 각 스크립트의 argparse 긴 옵션과 같다 — 스크립트에
    옵션을 더하면 이 시험이 표를 고치라고 알린다(argparse 는 그 스크립트의 옵션으로 줄임을 푼다).
    The per-script option table equals each script's argparse long options."""
    import ast
    for script, channel in hook._PROD_CHANNEL_SCRIPTS.items():
        tree = ast.parse((_ROOT / "scripts" / script).read_text(encoding="utf-8"))
        longs = {arg.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and getattr(node.func, "attr", "") == "add_argument"
                 for arg in node.args if isinstance(arg, ast.Constant) and str(arg.value).startswith("--")}
        assert set(hook._PROD_SCRIPT_OPTIONS[channel]) == longs, (script, longs)


def test_a_command_walk_failure_is_unjudged(logs, monkeypatch, capsys):
    """🔴 명령 자리 순회는 판정이다(원장 P1-19) — 죽으면 main 순회처럼 «판정 불가» 로 가서 운영 표지가 있는 호출은 막힌다.
    감사 기록은 남지 않고, 거부 기록에 예외 글자는 없다. A crash in the command-position walk is unjudged."""
    work, audit, denials = logs

    def broken(*_args, **_kwargs):
        raise RuntimeError(_MARKER)

    monkeypatch.setattr(hook, "_command_walk", broken)
    assert '"permissionDecision": "deny"' in _run(monkeypatch, capsys, _shell("railway status", work))
    assert not audit.exists() and denials.exists()
    assert _MARKER not in denials.read_text(encoding="utf-8")


def test_a_bracket_heavy_powershell_command_is_judged_quickly(logs, monkeypatch, capsys):
    """회귀 잠금(넷째 워크플로 패스) — 감사의 PowerShell 대입 정규식이 괄호 무리마다 두 배로 되짚어, 괄호 31 무리 명령이 훅
    시간 제한(30초 · 넘으면 막음)을 넘겼다. A bracket-heavy PowerShell command must not hit the hook timeout."""
    import time
    work, _, _ = logs
    started = time.monotonic()
    _run(monkeypatch, capsys, _shell("[a]" * 40, work, tool="PowerShell"))
    assert time.monotonic() - started < 5, "감사 정규식이 되짚기로 느려졌다"


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
