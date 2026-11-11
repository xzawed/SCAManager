"""운영 접근 차단 — 행위로 가른다 (회고 2026-11-06 원장 L02, P0).
Production access is judged by action, not by SQL verb (2026-11-06 retro ledger L02, P0).

사고(10-25~26): 에이전트가 `railway ssh` 로 운영 컨테이너에서 측정 코드를 앱 워커 자격(BYPASSRLS ·
트랜잭션 풀러)으로 돌렸고, 그 코드의 세션 설정이 풀러 연결에 남아 25시간 동안 워커 쓰기가 막혔다.
재발 방지는 CLAUDE.md 한 줄(«SELECT 자율»)뿐이었다 — 회고는 그 분류 축(SQL 동사)이 틀렸다고 확정했다.
Incident: agent code ran in the production container with the app worker credential and its session
setting stuck on the pooled connection for 25 hours; the only prevention was one prose line.

🔴 bypass 권한 모드에서는 훅의 «ask» 와 settings 의 ask 규칙이 창 없이 통과했다(11-10 실측) — 그래서 이 판정은
   «deny» 만 낸다. 사용자는 `!` 로 직접 실행한다(훅은 에이전트의 도구 호출만 본다).
In bypass mode both a hook "ask" and a settings ask rule were auto-allowed (measured), so this verdict is
"deny" only; the user runs such commands with `!`.

판정 표는 훅 모듈의 판정 함수를 직접 부른다(빠름). 배선 · 출력 계약은 훅을 배선된 방식대로 subprocess 로
실행해 확인한다 — 함수만 재면 main() 이 그 함수를 부르지 않아도 초록이다(«거짓 집행자»).
Tables call the decision functions directly; wiring and the output contract run the real hook process.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.hooks.test_block_credential_dump import pretooluse_commands_for
from tests.unit.scripts._wiring_shape import any_invokes

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"
_SETTINGS = _ROOT / ".claude" / "settings.json"


def _load_hook():
    spec = importlib.util.spec_from_file_location("block_credential_dump_for_prod_tests", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_hook()


def _shell_verdict(command, shell="bash"):
    return _MOD.decide_production_access(command, shell=shell)


# --- 1. 셸 — 읽기는 자율 ------------------------------------------------------
# 배포 목록 · 로그 · 상태 · 지표 · 도움말은 운영을 바꾸지 않는다 — 막으면 확인 절차 자체가 사용자 몫이 된다.
# Reads (deployments, logs, status, metrics, help) never change production; blocking them would push
# every verification onto the user.

_ALLOWED_SHELL = [
    "railway",
    "railway status",
    "railway status --json",
    "railway whoami --json",
    "railway --version",
    "railway --help",
    "railway help",
    "railway ssh --help",
    "railway up -h",
    "railway logs --build --lines 3000 7cf2312f-a1ea-4c55-8a49-5fc6da5c2ae9",
    "railway logs --deployment",
    "railway deployment list --json",
    "railway deployments ls",
    "railway service status",
    "railway service logs",
    "railway domain list",
    "railway environment list",
    "railway env ls",
    # 값을 받는 옵션이 하위 명령 앞에 와도 읽기다(Grok 반례 — 첫 판은 `api` 를 둘째 낱말로 읽어 막았다)
    # A value option before the subcommand keeps it a read (Grok: the first version read `api` as the verb)
    "railway domain -s api list",
    "railway domain --service api list",
    "railway domain -s api status example.com",
    "railway -- status",
    "railway ssh -s api --help",
    # `--` 가 안쪽 명령을 여는 것은 ssh · run · local 뿐 — 그 밖의 `--` 는 옵션 끝, `--help` 는 어디 있든 도움말이다
    # (Grok 재판정 반례). Only ssh/run/local open an inner command at `--`; elsewhere `--help` anywhere is help.
    "railway service -- status",
    "railway domain -- list",
    "railway variable set --help",
    "railway domain --port 3000 list",
    "railway metrics",
    "railway list",
    "railway docs",
    'RAILWAY_CALLER="skill:use-railway@1.7.0" RAILWAY_AGENT_SESSION="s1" railway deployment list --json',
    'cd "D:/Source/SCAManager" && railway logs --lines 50',
    "C:/Users/u/AppData/Roaming/npm/railway.cmd status",
    "railway.exe whoami",
    "RAILWAY STATUS",
    # credential 훅이 안내하는 이름만 보기 — 값 노출은 그 훅이 맡고, 운영 변경은 아니다
    # the names-only idiom the credential hook teaches: not a production change
    "railway variables --kv | cut -d= -f1 | grep -i CRON",
    # railway 를 «언급» 만 하는 명령 — 명령 자리가 아니면 실행이 아니다
    # commands that only mention railway are not invocations
    'grep -n "railway ssh" docs/workflow/deploy.md',
    'echo "railway redeploy needs the user"',
    'git log --oneline --grep="railway up"',
    "py -3 scripts/railway_config.py",
]


@pytest.mark.parametrize("command", _ALLOWED_SHELL)
def test_reads_and_mentions_are_allowed(command):
    """읽기 · 도움말 · 언급은 통과 — 과잉 차단 대조군 / reads, help and mentions pass (over-blocking control)."""
    assert _shell_verdict(command) is None, f"읽기가 막혔다: {command!r}"


# --- 2. 셸 — 운영 접근은 막는다 ------------------------------------------------
# 운영 컨테이너 코드 실행 · 운영 변수 주입 실행 · 배포 · 변수 · 환경 · 서비스 변경. 목록에 없는 하위 명령도
# 막는다(새 하위 명령 · 별칭이 생겨도 새지 않게 — 허용 목록 방식).
# Code in the production container, local runs with production variables, deploy/variable/environment
# changes; unknown subcommands are denied too (allowlist, fail-closed).

_DENIED_SHELL = [
    "railway ssh",
    'railway ssh -- sh -c "echo hi"',
    "railway run py -3 x.py",
    "railway local py -3 x.py",
    "railway run -- py -3 -m pytest --help",
    "railway shell",
    "railway connect",
    "railway dev",
    "railway up",
    "railway up --detach -y",
    "railway deploy",
    "railway deployment up",
    "railway deployment redeploy",
    "railway redeploy --from-source -y",
    "railway restart",
    "railway down",
    "railway variable set FOO=1",
    "railway variables --set FOO=1",
    "railway variable delete FOO",
    "railway environment edit",
    "railway environment delete production",
    "railway environment new staging",
    "railway service delete",
    "railway service redeploy",
    "railway service restart",
    "railway domain",
    "railway domain delete example.com",
    "railway volume delete v1",
    "railway link",
    "railway agent -p why",
    "railway scale",
    "railway delete",
    "railway brand-new-subcommand",
]


@pytest.mark.parametrize("command", _DENIED_SHELL)
def test_production_access_is_denied(command):
    """운영 접근 명령은 막는다 / production access is denied."""
    assert _shell_verdict(command), f"운영 접근이 통과했다: {command!r}"


# 같은 호출의 다른 꼴 — 접두 대입 · 경로 · 확장자 · 대소문자 · cd 뒤 · 래퍼(셸 -c · cmd /c · PowerShell -Command ·
# npx · env) · 명령 치환 · 안전한 세그먼트와 섞기. 정직한 세션이 칠 만한 꼴이다(의도적 우회는 위협 모형 밖).
# The same call in other shapes an honest session would type (deliberate evasion is out of scope).
_DENIED_SHAPES = [
    'RAILWAY_CALLER="x" railway ssh',
    'cd "D:/Source/SCAManager" && railway redeploy -y',
    'bash -c "railway ssh"',
    "sh -c 'railway run env'",
    "bash -lc 'railway up'",
    "cmd /c railway up",
    'powershell -Command "railway ssh"',
    'pwsh -c "railway redeploy"',
    "npx @railway/cli ssh",
    "npx -y @railway/cli@latest up",
    "env FOO=1 railway ssh",
    "echo $(railway ssh -- whoami)",
    "railway.exe up",
    "RAILWAY SSH",
    "C:/Users/u/AppData/Roaming/npm/railway.cmd run env",
    "railway status && railway redeploy",
    "railway logs | tee x.txt; railway up",
    # 셸 키워드 · 실행기 뒤의 호출 — 재시도 루프 · 시간 제한 · Git Bash 의 winpty 가 자연스러운 꼴이다(11-11 Claude 확인)
    # Calls after shell keywords and runners: retry loops, time limits and Git Bash's winpty are natural shapes.
    "for i in 1 2 3; do railway redeploy -y && break; sleep 30; done",
    "if true; then railway up; fi",
    "timeout 300 railway up",
    "winpty railway ssh",
    "xargs -I {} railway redeploy",
    # Grok 반례(11-11, beddf10f) — 안쪽 명령의 `--version` 은 railway 의 도움말이 아니다 · 하위 명령 앞 `--` 는
    # 옵션 끝일 뿐 · npx 의 --package 꼴. Grok counterexamples: the inner command's --version is not railway's,
    # a `--` before the subcommand only ends options, and npx --package.
    "railway ssh node --version",
    "railway run node --version",
    "railway ssh -s api node --version",
    "railway -- redeploy",
    "railway -- domain",
    "npx --package=@railway/cli railway up",
    "npx -p @railway/cli railway up",
    # Grok 재판정 반례(11-11) — npm exec 꼴 · 안쪽 명령을 받지 않는 하위 명령의 `--` 뒤 / npm exec, `--` after a verb
    "npm exec @railway/cli up",
    "npm x @railway/cli redeploy",
    "npm exec -- @railway/cli ssh",
    "railway deployment -- redeploy",
    # Grok 3차 반례 · Claude 확인(11-11) — Windows 실행 파일 이름(.cmd) · 글자 heredoc 을 셸에 파이프로 먹이기
    # Windows shim names (.cmd) and a literal heredoc piped into a shell
    "npm.cmd exec @railway/cli up",
    "npx.cmd @railway/cli ssh",
    "cat <<'EOF' | bash\nrailway up\nEOF",
    # 자동 보안 리뷰(11-11) — 글자를 stdin 으로 셸에 넘기기 · 셸 here-string · 따옴표 안의 `<<'EOF'` · 셸 옵션 값 · env -S
    # Automated security review: text piped into a shell, shell here-strings, a quoted `<<'EOF'`, shell option
    # values and env -S.
    'echo "railway up" | bash',
    "printf '%s\\n' 'railway ssh' | sh",
    'bash <<< "railway redeploy"',
    "echo \"see <<'EOF' in the docs\"\nrailway up\nEOF",
    'bash -o pipefail -c "railway up"',
    "bash -O extglob -c 'railway ssh'",
    'bash +o posix -c "railway up"',
    'bash --rcfile x -c "railway up"',
    'env -S "railway up"',
    'env --split-string="railway ssh"',
    # 자동 보안 리뷰 2차(11-11) 중 정직한 꼴 — 따옴표 없이 넘긴 글자 · 묶음 셸 옵션(`-eo pipefail`) · `bash -s`
    # The honest shapes from the second automated review: unquoted piped words, clustered shell options, bash -s
    "echo railway up | bash",
    'bash -eo pipefail -c "railway up"',
    "bash -euo pipefail -c 'railway ssh'",
    "echo 'railway up' | bash -s foo",
    "echo 'railway up' | bash /dev/stdin",
]


@pytest.mark.parametrize("command", _DENIED_SHAPES)
def test_other_shapes_of_production_access_are_denied(command):
    """다른 꼴도 막는다 / other shapes are denied too."""
    assert _shell_verdict(command), f"다른 꼴의 운영 접근이 통과했다: {command!r}"


# 🔴 heredoc · 따옴표 안의 글자는 실행이 아니다 — 처음 판은 따옴표 구분자 heredoc(`<<'EOF'`) 본문의 백틱을 명령
#    치환으로 읽어 Python heredoc · PR 본문을 막았다(11-11 실측, 원장 R-5 부류). 셸에 먹이는 heredoc · 따옴표 없는
#    heredoc 의 치환 · 큰따옴표 안 치환은 실제로 돈다 — 그쪽은 계속 막는다.
# Heredoc data and single-quoted text are not invocations (the first version blocked a Python heredoc);
# heredocs fed to a shell, substitutions in unquoted heredocs and inside double quotes do run.
_ALLOWED_TEXT = [
    "py -3 - <<'EOF'\nprint('`railway ssh` is denied')\nEOF",
    "cat > notes.md <<'EOF'\nUse `railway ssh` only via the user.\nEOF",
    "gh pr create --body-file - <<\"EOF\"\n- `railway redeploy` needs `!`\nEOF",
    "git commit -F - <<-'MSG'\n\tdocs: `railway up` is user-run\n\tMSG",
    "echo 'run `railway ssh` later'",
    "echo '$(railway ssh)'",
]
_DENIED_TEXT = [
    "bash <<'EOF'\nrailway ssh\nEOF",
    "cat <<EOF\n$(railway ssh -- whoami)\nEOF",
    'echo "$(railway ssh -- whoami)"',
    "echo `railway up`",
]


@pytest.mark.parametrize("command", [
    "git commit -m @'\nrailway ssh 는 사용자가 한다\n'@",
    "$body = @'\nrailway redeploy --from-source\n'@",
])
def test_powershell_literal_here_string_is_allowed(command):
    """PowerShell 홑따옴표 here-string(`@'…'@`) 본문은 글자다 / a literal PowerShell here-string is data."""
    assert _shell_verdict(command, shell="powershell") is None, f"here-string 글자가 막혔다: {command!r}"


@pytest.mark.parametrize("command", [
    "Invoke-Expression @'\nrailway ssh\n'@",
    'git commit -m @"\n$(railway up)\n"@',
    "@'\nrailway up\n'@ | iex",
    "@'\nrailway redeploy\n'@ | Invoke-Expression",
    "'railway up' | iex",
    "Write-Output 'railway ssh' | Invoke-Expression",
    "Write-Output railway redeploy | iex",
    "'railway up' | pwsh -File -",
])
def test_powershell_here_string_that_runs_is_denied(command):
    """Invoke-Expression 에 먹이는 here-string · 큰따옴표 here-string 의 `$(…)` 는 돈다 / these run."""
    assert _shell_verdict(command, shell="powershell"), f"도는 here-string 이 통과했다: {command!r}"


@pytest.mark.parametrize("command", _ALLOWED_TEXT)
def test_text_that_only_mentions_railway_is_allowed(command):
    """heredoc 데이터 · 홑따옴표 글자의 railway 는 통과 / heredoc data and single-quoted text pass."""
    assert _shell_verdict(command) is None, f"글자가 막혔다: {command!r}"


@pytest.mark.parametrize("command", _DENIED_TEXT)
def test_text_that_really_runs_railway_is_denied(command):
    """실제로 도는 heredoc · 치환은 막는다 / heredocs and substitutions that run are denied."""
    assert _shell_verdict(command), f"실제로 도는 운영 접근이 통과했다: {command!r}"


_ALLOWED_LOOPS = [
    'echo "railway status" | bash',
    "echo railway status | bash",
    'bash -o pipefail -c "railway status"',
    "bash -eo pipefail -c 'railway status'",
    "while ! railway status; do sleep 5; done",
    "until railway deployment list --json | grep -q SUCCESS; do sleep 30; done",
    "timeout 60 railway logs --lines 20",
    "command -v railway",
]


@pytest.mark.parametrize("command", _ALLOWED_LOOPS)
def test_reads_inside_loops_and_runners_are_allowed(command):
    """루프 · 실행기 안의 읽기 · 설치 확인은 통과 — 대조군 / reads inside loops and runners pass (control)."""
    assert _shell_verdict(command) is None, f"읽기가 막혔다: {command!r}"


# 셸 묶음 옵션 판정(`"c" in flags` · `"s"` · `"o"`/`"O"`)이 «아니다» 로 가는 쪽 — 그 글자가 없는 묶음은 안쪽 명령을
# 열지 않고 · stdin 을 강제하지 않고 · 다음 낱말을 값으로 먹지 않는다.
# The negative side of the clustered-flag checks: clusters without c/s/o/O.
# witness-corpus: c · s · o · O 가 없는 셸 묶음 옵션 — 첫 위치 낱말은 스크립트, -c 앞에선 안쪽 명령이 그대로 판정, 단독이면 stdin
_FLAGS_WITHOUT_C_S_O = ["-l", "-i", "-v", "-n", "-ilv"]


@pytest.mark.parametrize("flag", _FLAGS_WITHOUT_C_S_O)
def test_shell_flags_without_c_s_o_keep_their_plain_meaning(flag):
    """c · s · o 가 없는 묶음 옵션의 세 갈래를 모두 잰다 / all three branches for flags without c, s, o."""
    # 그 뒤 첫 위치 낱말은 스크립트 파일 — 안쪽 명령도 stdin 도 아니다 / the next positional is a script file
    assert _MOD._prod_shell_scan([flag, "script.sh"]) == (None, False)
    # -c 앞에 와도 안쪽 명령은 그대로 판정된다 / before -c, the inner command is still judged
    assert _shell_verdict(f'bash {flag} -c "railway up"'), f"bash {flag} -c 가 통과했다"
    # 그 옵션만 있는 셸은 stdin 을 명령으로 읽는다 / a shell with only that flag reads stdin
    assert _shell_verdict(f"echo 'railway up' | bash {flag}"), f"| bash {flag} 가 통과했다"


@pytest.mark.parametrize("command", [
    "& railway.cmd redeploy", "& 'C:/npm/railway.cmd' ssh", "RAILWAY SSH",
    'Invoke-Expression "railway ssh"', "iex 'railway up'",
    "Start-Process railway -ArgumentList 'ssh'", "if ($true) { railway up }",
])
def test_powershell_call_operator_is_denied(command):
    """PowerShell 호출 연산자(`&`) · 대소문자 — PowerShell 도구는 이 PC 의 기본 셸이다.
    PowerShell's call operator and case-insensitive names (the PowerShell tool is this PC's default shell)."""
    assert _shell_verdict(command, shell="powershell"), f"PowerShell 꼴이 통과했다: {command!r}"


# --- 3. MCP — 도구 이름으로 가른다 ----------------------------------------------
# Railway MCP 는 읽기 도구만 통과(허용 목록), Supabase MCP 는 SQL · 마이그레이션 · 배포 · 브랜치 조작을 막는다.
# 어느 프로젝트를 가리키는지 훅은 모른다 — DB 를 바꾸거나 SQL 을 돌리는 도구는 운영 DB 접근으로 본다.
# Railway MCP: read tools only (allowlist). Supabase MCP: SQL, migrations, deploys and branch changes are
# denied; the hook cannot tell which project a server points at.

_ALLOWED_MCP = [
    "mcp__railway__list_deployments",
    "mcp__railway__get_logs",
    "mcp__railway__get_service_config",
    "mcp__railway__list_services",
    "mcp__railway__environment_status",
    "mcp__railway__whoami",
    "mcp__railway__docs_search",
    "mcp__plugin_railway_railway__get_logs",
    "mcp__supabase-local__search_docs",
    "mcp__supabase-local__list_tables",
    "mcp__plugin_supabase_supabase__get_advisors",
    # 운영과 무관한 MCP — 이 판정의 대상이 아니다 / unrelated MCP servers are out of scope
    "mcp__plugin_grok_grok-build__grok_build_delegate",
    "mcp__claude_ai_Notion__notion-search",
]

_DENIED_MCP = [
    "mcp__railway__deploy",
    "mcp__railway__set_variables",
    "mcp__railway__update_service",
    "mcp__railway__remove_service",
    "mcp__railway__scale_service",
    "mcp__railway__deploy_template",
    "mcp__railway__brand_new_tool",
    "mcp__plugin_railway_railway__deploy",
    "mcp__supabase-local__execute_sql",
    "mcp__supabase-local__apply_migration",
    "mcp__supabase-local__deploy_edge_function",
    "mcp__plugin_supabase_supabase__execute_sql",
    # claude.ai 커넥터 이름은 대문자로 시작한다 / claude.ai connector names are capitalized
    "mcp__claude_ai_Supabase__execute_sql",
    "mcp__claude_ai_Railway__deploy",
]


@pytest.mark.parametrize("tool", _ALLOWED_MCP)
def test_read_mcp_tools_are_allowed(tool):
    """읽기 MCP 도구 · 무관한 MCP 는 통과 / read MCP tools and unrelated servers pass."""
    assert _MOD.decide_mcp_production_access(tool) is None, f"읽기 MCP 가 막혔다: {tool}"


@pytest.mark.parametrize("tool", _DENIED_MCP)
def test_changing_mcp_tools_are_denied(tool):
    """운영을 바꾸거나 SQL 을 돌리는 MCP 도구는 막는다 / MCP tools that change production or run SQL are denied."""
    assert _MOD.decide_mcp_production_access(tool), f"운영 변경 MCP 가 통과했다: {tool}"


# --- 4. 배선된 훅의 실제 출력 (subprocess) --------------------------------------


def _run(tool_name, command=""):
    payload = {"tool_name": tool_name, "tool_input": {"command": command} if command else {}}
    proc = subprocess.run([sys.executable, str(_HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20, check=False, cwd=str(_ROOT))
    assert proc.returncode == 0, f"훅이 exit {proc.returncode}: {proc.stderr.decode('utf-8', 'replace')}"
    return proc.stdout


def _decision(stdout):
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return None, ""
    out = json.loads(text)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


@pytest.mark.parametrize("tool_name,command", [
    ("Bash", "railway ssh -- sh -c 'echo hi'"),
    ("Bash", 'RAILWAY_CALLER="x" railway redeploy --from-source -y'),
    ("PowerShell", "& railway.cmd up"),
    ("mcp__railway__deploy", ""),
    ("mcp__supabase-local__execute_sql", ""),
])
def test_wired_hook_denies_production_access(tool_name, command):
    """🔴 실제 훅 프로세스가 deny 를 낸다 — 판정 함수가 main() 에 배선돼 있다.
    The real hook process denies: the decision functions are wired into main()."""
    decision, reason = _decision(_run(tool_name, command))
    assert decision == "deny", f"{tool_name} {command!r} 가 통과했다"
    assert "!" in reason and "railway deployment list" in reason, (
        f"차단 사유가 대안(사용자의 `!` 실행 · 자율 읽기)을 알려 주지 않는다: {reason}")


@pytest.mark.parametrize("tool_name,command", [
    ("Bash", "railway status --json"),
    ("Bash", 'RAILWAY_CALLER="x" railway deployment list --json'),
    ("PowerShell", "railway.cmd logs --lines 20"),
    ("mcp__railway__get_logs", ""),
])
def test_wired_hook_allows_reads(tool_name, command):
    """실제 훅 프로세스가 읽기에 침묵한다 — 대조군 / the real hook stays silent on reads (control)."""
    decision, _ = _decision(_run(tool_name, command))
    assert decision is None, f"읽기가 막혔다: {tool_name} {command!r}"


def test_redeploy_denial_points_to_the_checked_script():
    """날 재배포를 막을 때 조건을 확인하는 스크립트를 대안으로 알린다 — 대안 없는 차단은 훅을 끄게 만든다.
    A raw redeploy denial points to the checked script; a block without an alternative gets hooks disabled."""
    decision, reason = _decision(_run("Bash", "railway redeploy --from-source -y"))
    assert decision == "deny" and "scripts/railway_redeploy.py" in reason, reason


@pytest.mark.parametrize("tool_name,command", [
    ("Bash", "railway ssh"),
    ("mcp__supabase-local__execute_sql", ""),
])
def test_db_denial_points_to_the_observer_tool(tool_name, command):
    """운영 DB 로 가는 길을 막을 때 관측 역할 조회 도구를 대안으로 알린다 / a DB-path denial names the observer tool."""
    decision, reason = _decision(_run(tool_name, command))
    assert decision == "deny" and "scripts/observe_db.py" in reason, reason


def test_variable_listing_keeps_the_credential_reason():
    """MCP 변수 목록은 지금처럼 credential 사유로 막는다 — 운영 접근 판정이 그 안내를 덮지 않는다.
    The MCP variable listing keeps its credential reason; the production verdict does not replace it."""
    decision, reason = _decision(_run("mcp__railway__list_variables"))
    assert decision == "deny" and "cut -d= -f1" in reason, reason


def test_production_deny_output_is_ascii():
    """차단 출력이 있고 ASCII 다 — 빈 출력이면 이 시험은 아무것도 재지 않는다(그래서 먼저 확인한다).
    cp949 콘솔에서 훅이 죽어 무음 통과하지 않게 / a non-empty deny that survives cp949 consoles."""
    out = _run("Bash", "railway ssh")
    assert out.strip(), "차단 출력이 비었다 — 잴 것이 없다"
    out.decode("ascii")


@pytest.mark.parametrize("tool", ["mcp__railway__deploy", "mcp__plugin_railway_railway__deploy",
                                  "mcp__supabase-local__execute_sql", "mcp__plugin_supabase_supabase__execute_sql",
                                  "mcp__claude_ai_Supabase__execute_sql", "mcp__claude_ai_Railway__deploy"])
def test_hook_is_wired_for_production_mcp_tools(tool):
    """🔴 settings.json 이 운영 MCP 도구에도 훅을 건다 — 배선이 없으면 MCP 로 같은 변경이 통과한다.
    settings.json wires the hook for production MCP tools too."""
    settings = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    commands = pretooluse_commands_for(settings, tool)
    assert any_invokes(commands, ".claude/hooks/block_credential_dump.py"), (
        f"{tool} 에 훅이 배선돼 있지 않다 — 현재: {commands}")
