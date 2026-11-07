"""credential 값 stdout 덤프 차단 훅 — 배선 + 판정 가드 (회고 2026-07-19 P0).

사고: 2026-07-19 세션에서 변수 **이름만** 확인할 의도로 아래를 실행했으나, `CRON` 패턴이
값까지 매칭해 credential 이 평문으로 대화 기록에 남았다.
Incident: a name-only lookup matched a value too, leaking a credential into the transcript.

    railway variables --service SCAManager --kv | grep -iE "...|CRON"

2차 회고(168 에이전트)가 P0 로 확정한 것은 유출 자체가 아니라 **재발 방지책이 산문뿐**이라는
점이다 — 산문 메모만. "credential 유출 벡터(Bash stdout)에 훅 커버리지 0",
"인지 의존 산문 5회차, 자기 진단 1커밋 후 재생산".
The retro's P0 was not the leak but that the only mitigation was prose: zero hook coverage on the
Bash-stdout exfiltration vector, the 5th consecutive cognition-dependent mitigation.

🔴 그래서 이 가드는 산문을 읽지 않는다. (1) `.claude/settings.json` 을 **JSON 으로 파싱**해
   PreToolUse/Bash 배선을 단언하고, (2) 훅을 **subprocess 로 실제 실행**해 stdin→stdout 판정을
   확인한다. 문서 문자열 grep 은 #1094 형('가드가 무력한데 green')을 재생산하므로 금지.
This asserts the execution mechanism: settings.json wiring parsed as JSON, plus a real subprocess
run of the hook. Asserting prose would reproduce the very defect the retro flagged.

🔴 이 파일의 명령 상수는 **명령 문자열일 뿐 실제 키 값을 담지 않는다**. 상수명도 중립 명명
   (`_CMD_*`) 을 쓴다 — #1109 에서 테스트 상수명이 CodeQL `py/clear-text-logging-sensitive-data`
   alert 2건을 자초한 전례.
Command constants hold commands only, never real key material; neutral `_CMD_*` naming avoids the
self-inflicted CodeQL alerts of #1109.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.scripts._wiring_shape import any_invokes

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"

# 훅이 배선돼야 하는 도구 — Bash stdout 이 유출 벡터.
# The tool the hook must gate; Bash stdout is the exfiltration vector.
_TOOL = "Bash"

# --- 명령 상수 (실제 키 값 없음 — 명령 문자열만) ------------------------------

# 🔴 실제 사고 명령 원문. `CRON` 이 이름뿐 아니라 값까지 매칭한 그 형태.
# The verbatim incident command: `CRON` matched values, not just names.
_CMD_INCIDENT = (
    'railway variables --service SCAManager --kv '
    '| grep -iE "SCHEDULER|ENVIRONMENT|LOG_LEVEL|CRON"'
)

# 안전 관용구 — 이름만 추출한 뒤 필터. 훅이 이걸 막으면 사용자가 훅을 끄게 된다.
# The safe idiom; blocking it would push the operator to disable the hook.
_CMD_NAMES_ONLY = "railway variables --kv | cut -d= -f1 | grep -i CRON"


def _payload(command, tool_name=_TOOL):
    return json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})


def _run_hook(command, tool_name=_TOOL):
    """훅을 배선된 방식대로 실제 실행 — import 우회 없이 stdin/stdout 계약 확인.

    Run the hook exactly as wired (subprocess + stdin JSON), not via import.
    """
    assert _HOOK.is_file(), (
        f"훅 파일 부재: {_HOOK.relative_to(_ROOT)}\n"
        "해결 / Fix: PreToolUse(Bash) 훅을 신설하라. 배선 문자열만 맞고 파일이 없으면 "
        "실행 횟수는 0 이다(#1094 형 'green 인데 무력')."
    )
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=_payload(command, tool_name).encode("utf-8"),
        capture_output=True,
        timeout=20,
        check=False,
        cwd=str(_ROOT),
    )


def _decide(command, tool_name=_TOOL):
    """(permissionDecision, reason) 반환. 통과(무출력)면 (None, "").

    Returns the decision pair; (None, "") means the hook stayed silent = allow.
    """
    proc = _run_hook(command, tool_name)
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    # 훅은 무슨 일이 있어도 exit 0 — 비정상 종료는 harness 를 막거나 무음 실패한다.
    # The hook must always exit 0; a crash either blocks the harness or fails silently.
    assert proc.returncode == 0, (
        f"훅이 exit {proc.returncode} 로 종료 — 항상 exit 0 이어야 한다.\n"
        f"stderr: {stderr}"
    )
    if not stdout:
        return None, ""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"훅 stdout 이 JSON 이 아니다 — harness 가 판정을 읽지 못한다.\n"
            f"stdout: {stdout!r}"
        ) from exc
    spec = data.get("hookSpecificOutput", {})
    assert spec.get("hookEventName") == "PreToolUse", (
        f"hookEventName 이 'PreToolUse' 가 아니다 — 판정이 무시된다. 실제: {spec!r}"
    )
    return spec.get("permissionDecision"), spec.get("permissionDecisionReason", "")


# --- 1·3. 차단 대상 (credential 값이 stdout 으로 나오는 명령) -----------------

_BLOCKED = [
    # 🔴 실제 사고 명령 — 이 한 줄이 이 PR 의 존재 이유.
    pytest.param(_CMD_INCIDENT, id="incident-railway-variables-grep"),
    pytest.param("railway variables --service SCAManager --kv", id="railway-variables-kv"),
    pytest.param("railway variables", id="railway-variables-bare"),
    pytest.param("printenv", id="printenv-bare"),
    pytest.param("printenv | sort", id="printenv-piped"),
    pytest.param("cat .env", id="cat-dotenv"),
    pytest.param("cat D:/Source/SCAManager/.env", id="cat-dotenv-abspath"),
    pytest.param("type .env", id="type-dotenv-windows"),
    # 🔴 복합 명령 우회 — 2026-07-26 5+1 회고 P0 실측 원문 4종.
    # `_ALLOWED` 를 명령 **문자열 전체**에 먼저 적용하면, 안전한 세그먼트 하나가 명령 전체를
    # 화이트리스트해 다른 세그먼트의 덤프가 통과한다. 가장 자연스러운 우회 형태가 훅 자신이
    # 가르치는 안전 관용구를 앞에 붙이는 것이라 더 위험하다.
    # 🔴 Compound-command bypasses (measured, retro 2026-07-26 P0): one safe segment must not
    # whitelist the whole command line.
    pytest.param(
        "railway variables --kv | cut -d= -f1; railway variables --kv | grep -i CRON",
        id="bypass-semicolon-after-safe-idiom",
    ),
    pytest.param("printenv | grep KEY; echo a=b | cut -d= -f1", id="bypass-semicolon-before-safe"),
    pytest.param("cat .env; echo a=b | cut -d= -f1", id="bypass-catenv-then-safe"),
    pytest.param("railway variables --set FOO=1 && railway variables --kv", id="bypass-and-after-write"),
    # 🔴 배포 설정 «읽기» 로 문서가 처방했던 명령 — CLI 가 서비스·공유 변수 값을 평문으로 싣는다.
    #    별칭은 CLI 도움말 그대로: environment = env, config = show = info. `--json` 없는 꼴도 막는다 —
    #    지금 판은 개수만 찍지만 판이 바뀌면 조용히 값이 나온다. 안전 대체는 scripts/railway_config.py.
    # The deploy-config "read" the docs prescribed prints raw service/shared variable values.
    # Aliases follow the CLI help; the plain form is blocked too (fail-closed across CLI versions).
    pytest.param("railway environment config --json", id="env-config-json"),
    pytest.param("timeout 60 railway environment config --json 2>&1 | head -c 3000", id="env-config-json-head"),
    pytest.param("railway environment config", id="env-config-plain"),
    pytest.param("railway environment config --environment production --json", id="env-config-flag-between"),
    pytest.param("railway environment --json config", id="env-config-flag-before"),
    pytest.param("railway env config --json", id="env-alias-config"),
    pytest.param("railway environment show --json", id="env-config-alias-show"),
    pytest.param("railway env info", id="env-alias-info"),
    pytest.param(
        'railway environment config --json | py -3 -c "import json,sys; print(json.load(sys.stdin))"',
        id="env-config-piped-to-python",
    ),
    # 🔴 `variable` 의 별칭(variables · vars · var)도 같은 값을 쏟는다 — 종전 패턴은 `variables` 하나만 봤다.
    # Every alias of `variable` dumps the same values; the old pattern knew only `variables`.
    pytest.param("railway variable list --kv", id="variable-singular-list-kv"),
    pytest.param("railway var --kv", id="variable-alias-var"),
    pytest.param("railway vars --json", id="variable-alias-vars-json"),
    pytest.param("railway variable ls --service api --json", id="variable-ls-json"),
    # 🔴 `cut -d= -f1` 은 KEY=VALUE 줄에서만 값을 지운다. 종전 판정은 세그먼트 어디에든 cut 이 있으면
    #    통과시켜, JSON·표 출력(줄에 `=` 없음 → 줄 통째 출력)과 «cut 이 덤프보다 앞» 인 꼴이 새었다.
    #    쓰기 단계도 같은 파이프라인의 다른 단계를 덮지 못한다.
    # cut only strips values from KEY=VALUE lines; a cut anywhere in the segment used to excuse JSON/table
    # dumps and a cut placed *before* the dump. A write stage must not excuse a sibling stage either.
    pytest.param("railway variables --json | cut -d= -f1", id="cut-after-json-dump"),
    pytest.param("railway variables | cut -d= -f1", id="cut-after-table-dump"),
    pytest.param("cut -d= -f1 names.txt | railway variables --kv", id="cut-before-dump"),
    pytest.param("railway variable set A=1 | railway variables --kv", id="write-stage-then-dump-stage"),
    # 🔴 옵션 값이 하위 명령처럼 보여도 읽기다 — 서비스 이름이 `set` 인 목록 조회.
    #    «뒤에 set 글자가 있으면 쓰기» 같은 싼 판정의 대조군 (Grok G1 지적 뒤 추가).
    # An option value that looks like a subcommand is still a read (service named «set»).
    pytest.param("railway variables --service set", id="read-with-service-named-set"),
    pytest.param("railway variable -s delete --kv", id="read-with-service-named-delete"),
    # 🔴 «이름만» 처럼 보이지만 값을 그대로 내는 cut (Grok G1 재검증 반례 — 원래 훅부터 있던 구멍).
    # cut forms that look names-only but still print values (Grok G1 re-review; present since the first hook).
    pytest.param("railway variables --kv | cut -d= -f1-", id="cut-field-range-to-end"),
    pytest.param("railway variables --kv | cut -d= -f1,2", id="cut-field-list"),
    pytest.param("railway variables --kv | cut -d= -f1 --complement", id="cut-complement"),
    pytest.param("printenv | cut -d= -f1-", id="printenv-cut-range"),
    # 🔴 주석 속 쓰기 글자가 읽기를 덮지 못한다 (Grok G1 세 번째 반례).
    # A write-looking word in a comment must not excuse a read (Grok G1 third counterexample).
    pytest.param("railway variables # --set", id="comment-with-legacy-set"),
    pytest.param("railway variables --kv # set FOO=1", id="comment-with-set-subcommand"),
    # 🔴 따옴표 안의 공백·플래그 글자는 옵션 **값**이다 (Grok G1 네 번째 반례).
    #    서비스 이름 `x set` 은 읽기이고, `--kv x` 라는 서비스 이름은 KV 출력이 아니다(표 출력 → cut 무력).
    # Quoted spaces/flags are option VALUES: service «x set» is a read; service «--kv x» is not KV output.
    pytest.param('railway variables --service "x set" --kv', id="quoted-service-value-with-set"),
    pytest.param('railway variables --service "--kv x" | cut -d= -f1', id="quoted-service-value-with-kv"),
    pytest.param('railway variables --service "unbalanced --kv | cut -d= -f1', id="unbalanced-quote"),
    # 🔴 주석 뒤의 cut 은 실행되지 않는다 (Grok G1 다섯 번째 반례) · 사이 단계는 값을 복제할 수 있다 ·
    #    --json 이 함께 있으면 KV 출력이 아니다.
    # A cut after a comment never runs (Grok G1 fifth); a stage in between can copy values; --json wins over --kv.
    pytest.param("railway variables --kv # | cut -d= -f1", id="comment-before-cut"),
    pytest.param("railway variables --kv | tee /dev/stderr | cut -d= -f1", id="tee-between-dump-and-cut"),
    pytest.param("printenv | tee env.log | cut -d= -f1", id="printenv-tee-before-cut"),
    pytest.param("railway variables --kv --json | cut -d= -f1", id="kv-with-json"),
    # 🔴 운영 컨테이너(ssh)나 Railway 변수를 주입한 로컬 실행(run · local)에서 env 를 통째로 찍는 꼴.
    # Dumping the whole env inside the production container (ssh) or a Railway-injected local run.
    pytest.param("railway ssh -- env", id="ssh-env"),
    pytest.param("railway ssh env | grep DATABASE", id="ssh-env-grep"),
    pytest.param("railway run env", id="run-env"),
    pytest.param("railway local -- env | sort", id="local-alias-env"),
    # 🔴 printenv 와 같은 부류 — Bash·cmd 의 env 전체 출력(원래 훅부터 비어 있던 형제).
    # Same class as printenv: whole-env listings in Bash/cmd (siblings missing since the first hook).
    pytest.param("env", id="bare-env"),
    pytest.param("env | grep KEY", id="bare-env-grep"),
    pytest.param("set | grep TOKEN", id="bare-set-grep"),
    pytest.param("export -p", id="export-p"),
    pytest.param("declare -x", id="declare-x"),
    # 🔴 이름 없는 declare 는 -x · -p 만이 아니라 대부분의 플래그에서 값을 나열한다(-f · -F 만 함수).
    # Flags-only declare lists values for most flags, not just -x/-p (only -f/-F print functions).
    pytest.param("declare", id="declare-bare"),
    pytest.param("declare -i", id="declare-integer-listing"),
    pytest.param("typeset -r", id="typeset-readonly-listing"),
    pytest.param("cmd /c set", id="cmd-set"),
    # cmd 의 `set NAME` 은 접두어로 나열한다(`set A` → A 로 시작하는 변수 전부) — 보안 리뷰 지적.
    # cmd's `set NAME` is a prefix listing (security review).
    pytest.param("cmd /c set ANTHROPIC", id="cmd-set-prefix-listing"),
    pytest.param('cmd.exe /c "set"', id="cmd-exe-quoted-set"),
    pytest.param('powershell -c "Get-ChildItem env:"', id="bash-invokes-powershell-env-drive"),
    # 🔴 명령 자리를 토큰으로 본다 — 숫자 플래그(Grok G4) · 접두어 · 경로 · 괄호 · 따옴표 · 앞쪽 대입
    #    (자동 보안 리뷰 네 번째 지적).
    # The command position is read as tokens: digit flags (Grok G4), prefixes, paths, parens, quotes.
    pytest.param("env -0", id="env-null-flag"),
    pytest.param("command env", id="env-command-prefix"),
    pytest.param("/usr/bin/env", id="env-absolute-path"),
    pytest.param("(env) | sort", id="env-in-subshell"),
    pytest.param('"env"', id="env-quoted"),
    pytest.param("FOO=1 env", id="env-after-assignment"),
    pytest.param("sudo env | grep KEY", id="env-sudo"),
    pytest.param("builtin set", id="set-builtin-prefix"),
    pytest.param("railway ssh -- set", id="ssh-inner-set"),
    pytest.param("railway run -- export -p", id="run-inner-export-p"),
    pytest.param("railway ssh -s api -- env", id="ssh-option-value-then-env"),
    pytest.param("cat /proc/self/environ", id="proc-self-environ"),
    pytest.param("tr '\\0' '\\n' < /proc/1/environ", id="proc-pid-environ"),
    # 🔴 리디렉션 · 치환이 든 단계는 중화하지 않는다 — 출력이 cut 을 비켜 가거나 쓰기 안에서 읽기가 돈다.
    # Redirection or substitution in the dump stage defeats neutralization.
    pytest.param("railway variables --kv >&2 | cut -d= -f1", id="kv-redirected-to-stderr-before-cut"),
    pytest.param("printenv > /dev/stderr | cut -d= -f1", id="printenv-redirected-before-cut"),
    pytest.param("railway variable set A=$(railway variables --kv)", id="read-inside-write-substitution"),
    pytest.param("railway variable set A=1 railway variables --kv", id="two-calls-one-stage"),
    # 🔴 railway 낱말의 경로 · 확장자 · 따옴표 · 대소문자(자동 보안 리뷰 다섯 번째 지적).
    # Path, extension, quotes and case of the railway word (fifth automated review).
    pytest.param("railway.cmd variables --kv", id="railway-cmd-shim"),
    pytest.param('"railway" variables --kv', id="railway-quoted"),
    pytest.param("C:\\Users\\me\\AppData\\Roaming\\npm\\railway.cmd environment config --json",
                 id="railway-shim-full-path-config"),
    pytest.param("railway.ps1 env config", id="railway-ps1-shim-config"),
    # 🔴 값을 받는 env 옵션 뒤의 낱말은 명령이 아니다 · ssh/run 옵션 값 개수와 무관하게 안쪽 명령을 본다.
    # A value after an env option is not a command; the inner command is found regardless of option arity.
    pytest.param("env -u FOO", id="env-unset-only"),
    pytest.param("env --unset=FOO | sort", id="env-unset-eq-only"),
    pytest.param("env -C /tmp", id="env-chdir-only"),
    pytest.param("railway ssh --session main env", id="ssh-optional-value-option-then-env"),
    pytest.param("railway ssh -d abc123 -- env", id="ssh-deployment-instance-then-env"),
    pytest.param("railway ssh -i ~/.ssh/id_ed25519 env", id="ssh-identity-file-then-env"),
    # 🔴 .env 를 읽는 다른 도구 · .env 변형(.env.local 등) — 일치 줄이 값째 나온다(자동 보안 리뷰 일곱 번째 지적).
    # Other .env readers and .env variants print matching lines with values (seventh automated review).
    pytest.param("grep DATABASE_URL .env", id="grep-dotenv"),
    pytest.param("rg KEY .env", id="rg-dotenv"),
    pytest.param("head -n 5 .env", id="head-dotenv"),
    pytest.param("tail .env", id="tail-dotenv"),
    pytest.param("awk -F= '{print $2}' .env", id="awk-dotenv-values"),
    pytest.param("sed -n 1p .env", id="sed-dotenv"),
    pytest.param("cat .env.local", id="cat-dotenv-local"),
    pytest.param("grep TOKEN .env.production", id="grep-dotenv-production"),
    # 🔴 판정을 뒤집었다 — .env 꼴 경로가 나오면 막고 안전한 꼴만 통과(자동 보안 리뷰 여덟 번째 지적).
    #    경로 변형(.env.production.local · .env-old · prod.env)과 목록 밖 읽기 도구(diff · base64 · tac · cut 등).
    # Inverted: any .env-like path is denied unless the form is known safe (eighth automated review).
    pytest.param("cat .env.production.local", id="dotenv-double-suffix"),
    pytest.param("cat .env-old", id="dotenv-dash-suffix"),
    pytest.param("cat prod.env", id="dotenv-name-suffix"),
    pytest.param("diff .env .env.example", id="diff-dotenv"),
    pytest.param("base64 .env", id="base64-dotenv"),
    pytest.param("tac .env", id="tac-dotenv"),
    pytest.param("cut -d= -f2 .env", id="cut-values-dotenv"),
    pytest.param("source .env && env", id="source-dotenv-then-env"),
    # 🔴 자동 보안 리뷰 아홉 번째 지적 — 문맥 출력 플래그(-C)를 «개수만» 으로 읽던 결함 · 와일드카드 경로 ·
    #    NTFS 스트림 · 안전한 명령의 출력이 다음 단계로 넘어가는 꼴.
    # Ninth review: context flags read as count-only, glob paths, NTFS streams, safe heads piped onward.
    pytest.param("grep -C 3 KEY .env", id="grep-context-dotenv"),
    pytest.param("grep -c -A2 KEY .env", id="grep-count-with-context-flag"),
    pytest.param("cat .env*", id="dotenv-glob-suffix"),
    pytest.param("cat *.env", id="dotenv-glob-name"),
    pytest.param("ls .env | xargs cat", id="safe-head-piped-to-reader"),
]


@pytest.mark.parametrize("command", _BLOCKED)
def test_credential_dump_is_denied(command):
    """🔴 credential 값을 stdout 으로 쏟는 명령은 deny — 사고 명령 원문 포함."""
    decision, _ = _decide(command)
    assert decision == "deny", (
        f"차단되지 않음: {command!r}\n"
        "이 명령은 credential 값을 대화 기록에 평문으로 남긴다(2026-07-19 사고 재현).\n"
        "해결 / Fix: .claude/hooks/block_credential_dump.py 의 차단 패턴에 추가."
    )


# --- 2·4·5. 통과 대상 (false-positive 방어) -----------------------------------

_ALLOWED = [
    # 안전 관용구 3변형 — 이름만 추출. 막히면 훅이 곧 비활성화된다.
    pytest.param(_CMD_NAMES_ONLY, id="safe-idiom-cut-d-eq"),
    pytest.param("railway variables --kv | cut -d'=' -f1", id="safe-idiom-cut-quoted-single"),
    pytest.param('railway variables --kv | cut -d"=" -f1', id="safe-idiom-cut-quoted-double"),
    pytest.param("printenv | cut -d= -f1", id="safe-idiom-printenv-names"),
    # 쓰기 작업 — 값을 넣는 것이지 꺼내는 것이 아니다.
    pytest.param("railway variables --set FOO=bar", id="write-set"),
    pytest.param("railway variables --set SCHEDULER_ENABLED=1", id="write-set-scheduler"),
    # 🔴 소스에서 CRON 을 grep 하는 정상 작업 — 이게 막히면 일상 작업이 마비된다.
    pytest.param('grep -rn "CRON" src/', id="grep-source-cron"),
    pytest.param('grep -rniE "SCHEDULER|CRON" src/', id="grep-source-alternation"),
    # 무관 명령 일반.
    pytest.param("git status", id="git-status"),
    pytest.param("pytest tests/unit", id="pytest-unit"),
    pytest.param("railway logs", id="railway-logs"),
    pytest.param("railway status", id="railway-status"),
    pytest.param("cat README.md", id="cat-readme"),
    pytest.param("ls -la .claude/hooks/", id="ls-hooks"),
    # ⚠️ 사양 판단: `.env.example` 은 저장소에 커밋된 값 없는 템플릿이고
    # CLAUDE.md 핵심 명령(`cp .env.example .env`)에 등장한다 → 통과 대상으로 본다.
    # Spec call: .env.example is a committed, value-free template — allow it.
    pytest.param("cat .env.example", id="cat-dotenv-example"),
    # 🔴 파이프 보존 대조군 — 세그먼트 분해가 **단일 `|` 까지** 쪼개면 훅이 가르치는 안전
    # 관용구 자체가 막혀 훅이 곧 비활성화된다. 파이프라인은 하류 필터가 상류 덤프를 실제로
    # 중화하지만 `;`/`&&` 는 그렇지 않다 — 이 비대칭이 분해 경계의 근거다.
    # 🔴 Pipes must NOT be split: a downstream filter genuinely neutralizes the upstream dump,
    # unlike `;`/`&&`. Splitting on `|` would block the hook's own documented safe idiom.
    pytest.param(
        "railway variables --kv | cut -d= -f1 | grep -i CRON", id="safe-idiom-three-stage-pipeline",
    ),
    pytest.param("railway variables --set A=1 && git status", id="write-then-benign"),
    pytest.param("git status; ls -la", id="two-benign-segments"),
    # 안전 대체 — 서비스마다 deploy·build 절만 남긴 배포 설정 읽기. 막히면 다시 덤프 꼴로 돌아간다.
    # The safe reader keeps only deploy/build per service; blocking it pushes sessions back to the dump.
    pytest.param("py -3 scripts/railway_config.py", id="safe-config-reader"),
    pytest.param("py -3 scripts/railway_config.py --environment production", id="safe-config-reader-env"),
    # 값을 내지 않는 environment 하위 명령 — «railway environment 면 전부» 같은 과잉 패턴을 잡는 대조군.
    # Value-free environment subcommands: controls against an over-broad «any railway environment».
    pytest.param("railway environment list --json", id="env-list"),
    pytest.param("railway environment link production", id="env-link"),
    pytest.param("railway env", id="env-bare"),
    # 쓰기 하위 명령 — 값을 넣거나 지우는 것이지 꺼내는 것이 아니다.
    # Write subcommands put or remove values; they do not read them out.
    pytest.param("railway variable set FOO=bar --skip-deploys", id="variable-set"),
    pytest.param("railway var delete FOO", id="variable-alias-delete"),
    pytest.param("railway variables --set-from-stdin FOO", id="variable-legacy-set-from-stdin"),
    # 🔴 하위 명령 앞에 `variable` 의 옵션이 와도 쓰기다(Grok G1 반례 — 종전엔 오탐 차단).
    # Options before the subcommand keep it a write (Grok G1 counterexample; was a false deny).
    pytest.param("railway variable --service SCAManager set FOO=bar", id="variable-options-then-set"),
    pytest.param("railway var -s api -e production delete FOO", id="variable-short-options-then-delete"),
    pytest.param("railway variables --service=api --skip-deploys set A=1", id="variable-eq-option-then-set"),
    pytest.param('railway variable --service "my api" set A=1', id="variable-quoted-service-then-set"),
    pytest.param('railway variables --kv --service "a b" | cut -d= -f1', id="safe-idiom-quoted-service"),
    # ssh·run 자체는 막지 않는다 — env 를 통째로 찍는 꼴만. 이름만 자르면 통과.
    # ssh/run themselves stay allowed; only a whole-env dump is blocked, and names-only passes.
    pytest.param("railway variables --kv | cut -f1 -d=", id="safe-idiom-cut-reversed-flags"),
    pytest.param("printenv | cut -d = -f 1", id="safe-idiom-cut-spaced"),
    pytest.param("railway ssh -- ls /app", id="ssh-benign"),
    pytest.param("railway run npm test --env production", id="run-benign-env-flag"),
    pytest.param("railway run -- env | cut -d= -f1", id="run-env-names-only"),
    # 단계 전체가 env 출력 명령일 때만 막는다 — 변수 설정·옵션·이름만 자르기는 통과.
    # Only a stage that is exactly the listing is blocked; setting, options and names-only pass.
    pytest.param("env FOO=1 python x.py", id="env-sets-variable-for-command"),
    pytest.param("set -euo pipefail", id="set-shell-options"),
    pytest.param("export FOO=bar", id="export-assignment"),
    pytest.param("env | cut -d= -f1", id="env-names-only"),
    pytest.param("declare -a arr", id="declare-array"),
    # env 가 «실행기» 인 꼴 — 옵션·대입 뒤에 실행할 명령이 남는다. 그 밖의 낱말 자리 env 도 통과.
    # env as a runner (a command follows options/assignments), and env in a non-command position.
    pytest.param("/usr/bin/env python3 x.py", id="env-shebang-style-runner"),
    pytest.param("env -i python x.py", id="env-empty-environment-runner"),
    pytest.param("command -v env", id="command-v-env"),
    # 따옴표 짝이 안 맞는 조각(`;` 로 잘린 PowerShell 인자 등)에 env 낱말이 있어도 railway 호출이 없으면 통과.
    # An unbalanced fragment mentioning env passes unless it is a railway ssh/run/local call.
    pytest.param("echo 'env", id="unbalanced-quote-without-railway"),
    pytest.param("env -u FOO python x.py", id="env-unset-then-runner"),
    pytest.param('env -S "python x.py"', id="env-split-string-runner"),
    pytest.param("railway.cmd variable set A=1", id="railway-cmd-shim-write"),
    pytest.param("railway run -s api npm test", id="run-service-option-benign"),
    # .env 는 개수·존재만 본다(사용자 관행 — 값은 열지 않는다). 템플릿·쓰기도 통과.
    # Counting/existence checks on .env (the user's practice), templates and writes stay allowed.
    pytest.param("grep -c DATABASE_URL .env", id="grep-count-dotenv"),
    pytest.param("grep -q TOKEN .env", id="grep-quiet-dotenv"),
    pytest.param("rg -l KEY .env", id="rg-files-with-matches-dotenv"),
    pytest.param("grep KEY .env.example", id="grep-dotenv-example"),
    pytest.param("cp .env.example .env", id="copy-template-to-dotenv"),
    pytest.param("ls -la .envrc", id="envrc-not-dotenv"),
    # 안전한 꼴 — 옮기기 · 지우기 · 정보만 보기 · 쓰기 대상으로만 나오는 .env · 템플릿 · 이름만 자르기.
    # Safe forms: move/remove/metadata, .env only as a write target, templates, names-only cut.
    pytest.param("ls -la .env", id="ls-dotenv"),
    pytest.param("test -f .env", id="test-f-dotenv"),
    pytest.param("echo 'A=1' >> .env", id="append-to-dotenv"),
    pytest.param("Test-Path .env", id="test-path-dotenv"),
    pytest.param("cat .env | cut -d= -f1", id="dotenv-names-only"),
    pytest.param("cat config/.env.sample", id="dotenv-sample-template"),
    pytest.param("grep -ci KEY .env", id="grep-count-ignore-case-dotenv"),
    pytest.param("ls .env*", id="ls-dotenv-glob"),
    pytest.param("export PATH=$PATH:/opt/bin", id="export-path-assignment"),
    pytest.param("declare -A map", id="declare-assoc-array"),
    pytest.param("declare -f", id="declare-functions-only"),
    pytest.param("cmd /c set FOO=bar", id="cmd-set-assignment"),
    pytest.param("declare -F", id="declare-function-names-only"),
]


@pytest.mark.parametrize("command", _ALLOWED)
def test_benign_command_is_not_denied(command):
    """정상 명령은 통과 — 특히 소스 grep 과 이름만 추출 관용구(과잉 차단 봉인)."""
    decision, reason = _decide(command)
    assert decision != "deny", (
        f"오탐 차단: {command!r} 는 credential 값을 노출하지 않는다.\n"
        f"훅 사유: {reason}\n"
        "해결 / Fix: 허용 예외(cut -d= -f1 / --set / 비대상 명령)를 넓혀라."
    )


# --- 6. 셸이 아닌 도구는 무조건 통과 -----------------------------------------


@pytest.mark.parametrize("tool_name", ["Read", "Edit", "Write", "Grep", "Glob"])
def test_non_bash_tool_always_passes(tool_name):
    """셸(Bash·PowerShell) 외 도구는 판정 대상 아님 — 오작동 시 전 도구가 마비된다."""
    decision, _ = _decide(_CMD_INCIDENT, tool_name=tool_name)
    assert decision != "deny", (
        f"{tool_name} 도구가 차단됐다 — 이 훅은 셸 명령의 stdout 만 대상으로 한다."
    )


# --- 6-1. PowerShell 도구도 같은 훅을 지난다 ----------------------------------
# 🔴 이 PC 의 기본 셸 도구는 PowerShell 이다. 훅이 Bash 에만 걸려 있던 동안 PowerShell 로는
#    `railway variables --kv` 조차 통과했다. PowerShell 고유의 덤프 꼴(Get-Content .env · env: 드라이브)도
#    Bash 쪽 cat .env · printenv 와 같은 부류로 막는다. 한 변수만 읽는 `$env:NAME` 은 Bash 의
#    `echo $NAME` 처럼 통과 — «env: 가 들어가면 전부» 같은 과잉 패턴을 잡는 대조군이다.
# The PowerShell tool used to bypass the Bash-only hook entirely. Its native dump forms join the same
# classes as cat .env / printenv; reading one `$env:NAME` stays allowed (control for an over-broad «env:»).

_POWERSHELL_BLOCKED = [
    pytest.param("railway variables --kv", id="ps-railway-variables"),
    # 🔴 PowerShell 백틱 이스케이프 — `x` set` 은 서비스 이름 «x set» 하나다(읽기). shlex 는 모른다.
    # PowerShell backtick escape: «x` set» is one service name (a read); shlex cannot tell.
    pytest.param("railway variables --service x` set --kv", id="ps-backtick-escaped-space"),
    pytest.param("railway environment config --json", id="ps-env-config"),
    # PowerShell 은 명령 이름 대소문자를 가리지 않는다 / PowerShell command names are case-insensitive.
    pytest.param("Railway variables --kv", id="ps-railway-capitalized"),
    # PowerShell 의 명령 이름 · Windows 실행 파일 찾기는 대소문자를 가리지 않는다(보안 리뷰 일곱 번째 지적).
    # Command lookup is case-insensitive in PowerShell / on Windows (seventh review).
    pytest.param("Printenv", id="ps-printenv-capitalized"),
    pytest.param("ENV | Sort-Object", id="ps-env-uppercase"),
    pytest.param("Select-String -Path .env -Pattern KEY", id="ps-select-string-dotenv"),
    pytest.param("sls KEY .env", id="ps-sls-dotenv"),
    pytest.param("findstr KEY .env", id="ps-findstr-dotenv"),
    pytest.param("Get-Content .e*", id="ps-get-content-dotenv-glob"),
    pytest.param("Get-Content .env::$DATA", id="ps-get-content-dotenv-ads"),
    pytest.param("Get-Item .env | Get-Content", id="ps-get-item-piped-to-get-content"),
    pytest.param("& 'railway' env config --json", id="ps-call-operator-quoted"),
    pytest.param("Get-Content .env", id="ps-get-content-dotenv"),
    pytest.param("gc D:\\Source\\SCAManager\\.env", id="ps-gc-dotenv-abspath"),
    pytest.param("get-content .env | Select-String KEY", id="ps-get-content-lowercase"),
    pytest.param("Get-ChildItem env:", id="ps-env-drive"),
    pytest.param("gci Env:", id="ps-env-drive-alias-case"),
    pytest.param("dir env: | Sort-Object Name", id="ps-env-drive-dir"),
    pytest.param("[Environment]::GetEnvironmentVariables()", id="ps-dotnet-env-dump"),
    # 🔴 매개변수 · 따옴표 · 와일드카드 · 경로 구분자가 붙은 env: 드라이브 (자동 보안 리뷰 지적).
    # env: drive with a parameter, quotes, a wildcard or a path separator (automated security review).
    pytest.param("Get-ChildItem -Path Env:", id="ps-env-drive-path-param"),
    pytest.param("gci 'env:'", id="ps-env-drive-quoted"),
    pytest.param("Get-Item env:*", id="ps-env-drive-wildcard"),
    pytest.param("dir Env:\\", id="ps-env-drive-backslash"),
    # 🔴 이름 앞부분 + 와일드카드는 여러 변수를 나열한다 (자동 보안 리뷰 두 번째 지적).
    # A name prefix plus a wildcard lists many variables (second automated security review).
    pytest.param("gci env:A*", id="ps-env-drive-prefix-wildcard"),
    pytest.param("Get-ChildItem Env:ANTHROPIC*", id="ps-env-drive-named-wildcard"),
    pytest.param("Get-ChildItem env:[A-Z]*", id="ps-env-drive-bracket-wildcard"),
    pytest.param("dir env:?", id="ps-env-drive-question-wildcard"),
    # 🔴 따옴표로 쪼갠 와일드카드 · 변수 전개 · 공급자 경로 (자동 보안 리뷰 세 번째 지적) — 판정을 뒤집어
    #    «정확히 이름 하나» 만 통과시킨다.
    # Split-quote wildcards, expansion and provider paths (third review); only one exact name passes.
    pytest.param("gci env:A'*'", id="ps-env-drive-single-quoted-wildcard"),
    pytest.param('gci env:A"*"', id="ps-env-drive-double-quoted-wildcard"),
    pytest.param("$p='*'; gci env:$p", id="ps-env-drive-variable-expansion"),
    pytest.param("gci Environment::", id="ps-environment-provider-path"),
    pytest.param("Get-ChildItem Microsoft.PowerShell.Core\\Environment::", id="ps-environment-provider-qualified"),
]

_POWERSHELL_ALLOWED = [
    pytest.param("git status", id="ps-git-status"),
    pytest.param("Get-Content README.md", id="ps-get-content-readme"),
    pytest.param("Get-Content .env.example", id="ps-get-content-env-example"),
    pytest.param("$env:PATH -split ';'", id="ps-single-variable"),
    pytest.param("Get-Item env:PATH", id="ps-single-variable-item"),
    pytest.param("Write-Output ${env:USERPROFILE}", id="ps-single-variable-braced"),
    pytest.param("Get-Item -Path env:TEMP", id="ps-single-variable-path-param"),
    pytest.param("[Environment]::GetEnvironmentVariable('PATH')", id="ps-dotnet-single-variable"),
    pytest.param("py -3 scripts/railway_config.py", id="ps-safe-config-reader"),
]


@pytest.mark.parametrize("command", _POWERSHELL_BLOCKED)
def test_powershell_dump_is_denied(command):
    """🔴 PowerShell 도구로 보낸 덤프 명령도 deny — Bash 만 보던 공백 봉인."""
    decision, _ = _decide(command, tool_name="PowerShell")
    assert decision == "deny", (
        f"PowerShell 에서 차단되지 않음: {command!r}\n"
        "해결 / Fix: 훅이 PowerShell 도구도 판정하고, PowerShell 고유 덤프 꼴을 _BLOCKED 에 둔다."
    )


@pytest.mark.parametrize("command", _POWERSHELL_ALLOWED)
def test_powershell_benign_is_not_denied(command):
    """PowerShell 의 정상 명령은 통과 — 한 변수 읽기와 안전 대체 포함(과잉 차단 봉인)."""
    decision, reason = _decide(command, tool_name="PowerShell")
    assert decision != "deny", (
        f"PowerShell 오탐 차단: {command!r}\n훅 사유: {reason}"
    )


# --- 6-1b. 중화 목록 밖의 실제 덤프 명령 — 넓은 탐지기가 잡아야 한다 ----------------
# 훅의 별칭·옵션·하위 명령 목록은 **중화**(쓰기 · KV 출력) 판정에만 쓴다. 덤프 자체는 넓은 탐지기가
# 잡는다 — 그것을 그 목록이 알아보지 못하는 실제 명령으로 확인한다. 출처: deploy.md 처방을 그대로
# 실행하는 꼴(출력을 head 로 자른 형태) · 07-19 사고 부류 · PowerShell/.NET 공식 문서의 환경 변수 나열 예.
# The alias/option/subcommand catalogues only judge neutralizers; the broad detectors must catch dumps
# those catalogues never see. Sources: the deploy.md prescription as run, the 07-19 class, PowerShell docs.

# witness-corpus: 문서 처방 · CLI 도움말 · 사고 부류 · 공식 문서에서 옮긴 값 덤프 명령 — 중화 목록이 아니라 넓은 탐지기가 잡아야 한다
_REAL_DUMPS = [
    ("Bash", "timeout 60 railway environment config --json 2>&1 | head -c 3000"),
    ("Bash", "railway environment config"),  # CLI 도움말 사용법 줄 / CLI help usage line
    ("Bash", "printenv"),
    ("PowerShell", "dir env:"),  # about_Environment_Variables
    ("PowerShell", "Get-Item Env:*"),
    ("PowerShell", "Get-ChildItem Env:"),
    ("PowerShell", "[Environment]::GetEnvironmentVariables()"),  # .NET 문서 / .NET docs
]


@pytest.mark.parametrize(("tool", "command"), _REAL_DUMPS)
def test_real_dump_commands_are_denied_by_the_broad_detectors(tool, command):
    """🔴 중화 목록이 모르는 실제 덤프 명령도 deny — 목록이 아니라 탐지기가 문지기다."""
    decision, _ = _decide(command, tool_name=tool)
    assert decision == "deny", f"실제 덤프 명령이 통과했다({tool}): {command!r}"


# --- 6-2. Railway MCP 의 변수 목록 도구 --------------------------------------
# 🔴 `list_variables` 는 설명 그대로 «KEY=VALUE 쌍을 반환» 한다 — 셸을 거치지 않는 같은 덤프다.
#    값 개수만 내는 `get_service_config` 는 통과(과잉 차단 대조군).
# Railway MCP `list_variables` returns KEY=VALUE pairs; `get_service_config` (variable count only) stays.

_MCP_LIST = "mcp__railway__list_variables"


def test_railway_mcp_variable_listing_is_denied():
    """🔴 Railway MCP 변수 목록 도구도 deny — 명령 글자가 없어도 도구 이름으로 판정한다."""
    decision, reason = _decide("", tool_name=_MCP_LIST)
    assert decision == "deny", f"{_MCP_LIST} 가 통과했다 — 서비스 변수 값이 그대로 나온다."
    assert "cut -d= -f1" in reason, f"이름만 보는 안전 대안이 사유에 없다: {reason}"


@pytest.mark.parametrize("tool_name", [
    "mcp__railway__get_service_config",
    "mcp__railway__list_services",
    "mcp__railway__get_logs",
])
def test_other_railway_mcp_tools_pass(tool_name):
    """값을 내지 않는 Railway MCP 도구는 통과 — «railway MCP 면 전부» 같은 과잉 판정 대조군."""
    decision, _ = _decide("", tool_name=tool_name)
    assert decision != "deny", f"{tool_name} 가 차단됐다 — 변수 값을 내지 않는 도구다."


# --- 7. 차단 메시지 유용성 ----------------------------------------------------


def test_deny_reason_teaches_the_safe_idiom():
    """🔴 deny 사유가 안전 대안을 제시 — 대안 없는 차단은 우회를 부른다."""
    decision, reason = _decide(_CMD_INCIDENT)
    assert decision == "deny"
    assert "cut -d= -f1" in reason, (
        "차단 사유에 안전 관용구(`cut -d= -f1`)가 없다.\n"
        f"현재 사유: {reason}\n"
        "대안을 알려주지 않는 차단은 사용자가 훅을 끄게 만든다."
    )


def test_config_deny_reason_points_to_the_safe_reader():
    """🔴 배포 설정 덤프를 막을 때는 값 없는 읽기(scripts/railway_config.py)를 안내한다.
    `cut -d= -f1` 은 JSON 설정에 쓸 수 없다 — 대안이 틀리면 대안이 없는 것과 같다."""
    decision, reason = _decide("railway environment config --json")
    assert decision == "deny"
    assert "scripts/railway_config.py" in reason, (
        "배포 설정 차단 사유에 안전 대체(scripts/railway_config.py)가 없다.\n"
        f"현재 사유: {reason}"
    )


def test_deny_output_is_ascii_safe():
    """훅 stdout 이 ASCII — Windows cp949 콘솔에서 UnicodeEncodeError 로 무음 실패 방지.

    선례: `check_edit_allowed.py` 가 `ensure_ascii=True` 를 쓰는 이유, bilingual 훅 cp949 버그.
    """
    proc = _run_hook(_CMD_INCIDENT)
    try:
        proc.stdout.decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssertionError(
            "훅 stdout 에 non-ASCII 바이트 — cp949 콘솔에서 훅이 죽어 무음 통과한다.\n"
            "해결 / Fix: json.dumps(..., ensure_ascii=True)."
        ) from exc


def test_malformed_stdin_does_not_crash():
    """깨진 stdin 에도 exit 0 — 훅이 죽으면 모든 Bash 호출이 막히거나 무음 통과한다."""
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=b"not json at all",
        capture_output=True,
        timeout=20,
        check=False,
        cwd=str(_ROOT),
    )
    assert proc.returncode == 0, (
        f"깨진 stdin 에 exit {proc.returncode} — 훅은 항상 exit 0 이어야 한다."
    )


# --- 8. 배선 단언 (JSON 파싱 — 산문 grep 금지) --------------------------------


def _settings():
    return json.loads(_SETTINGS.read_text(encoding="utf-8"))


def pretooluse_commands_for(settings, tool):
    """지정 도구에 매칭되는 PreToolUse 훅 command 전부.

    matcher 는 `Write|Edit|MultiEdit` 같은 정규식 alternation 이므로 토큰 분해 후 대조.
    Matchers are regex alternations, so split on `|` before comparing.
    """
    out = []
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        tokens = [t.strip() for t in entry.get("matcher", "").split("|")]
        # matcher 토큰은 정규식일 수 있다(`mcp__.*railway.*__list_variables`) — 통째 일치로 본다.
        # Tokens may be regexes; a plain name still fullmatches itself.
        if not any(re.fullmatch(t, tool) for t in tokens if t):
            continue
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if hook.get("args"):
                cmd = f"{cmd} {' '.join(hook['args'])}"
            out.append(cmd)
    return out


def test_extractor_finds_bash_group():
    """🔴 긍정 통제 — 추출기가 Bash 그룹의 command 를 실제로 찾는다."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "python x.py"}]}]}}
    assert pretooluse_commands_for(fake, "Bash") == ["python x.py"]


def test_extractor_handles_alternation_and_args():
    """alternation matcher + `args` 분리 형식도 인식 (스키마 변형 대응)."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Bash|BashOutput", "hooks": [
        {"type": "command", "command": "python", "args": [".claude/hooks/h.py"]}]}]}}
    assert pretooluse_commands_for(fake, "Bash") == ["python .claude/hooks/h.py"]


def test_extractor_matches_regex_tokens_whole():
    """정규식 토큰은 통째 일치 — `mcp__.*railway.*__list_variables` 가 다른 도구를 집지 않는다."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Bash|mcp__.*railway.*__list_variables", "hooks": [
        {"type": "command", "command": "python h.py"}]}]}}
    assert pretooluse_commands_for(fake, "mcp__railway__list_variables") == ["python h.py"]
    assert pretooluse_commands_for(fake, "mcp__railway__list_variables_v2") == []
    assert pretooluse_commands_for(fake, "BashOutput") == []


def test_extractor_ignores_other_tool_groups():
    """🔴 부정 통제 — Write/Edit 그룹은 Bash 로 집계되지 않는다(공허 통과 차단)."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Write|Edit", "hooks": [
        {"type": "command", "command": "python other.py"}]}]}}
    assert pretooluse_commands_for(fake, "Bash") == []


def test_settings_json_is_valid():
    """settings.json 이 유효한 JSON — 깨지면 모든 훅이 조용히 죽는다."""
    assert isinstance(_settings(), dict)


def test_hook_wired_to_pretooluse_bash():
    """🔴 훅이 PreToolUse/Bash 에 배선 — 산문 안내가 아니라 기계 집행면."""
    commands = pretooluse_commands_for(_settings(), _TOOL)
    assert any_invokes(commands, ".claude/hooks/block_credential_dump.py"), (
        "block_credential_dump.py 가 PreToolUse(Bash) 에 미배선 — 차단이 인지 의존으로 회귀한다.\n"
        f"현재 Bash 배선: {commands}\n"
        "해결 / Fix: .claude/settings.json 의 hooks.PreToolUse 에 matcher 'Bash' 그룹 추가."
    )


def test_hook_wired_to_pretooluse_powershell():
    """🔴 PowerShell 도구에도 배선 — Bash 만 배선이면 PowerShell 로 같은 덤프가 통과한다."""
    commands = pretooluse_commands_for(_settings(), "PowerShell")
    assert any_invokes(commands, ".claude/hooks/block_credential_dump.py"), (
        "block_credential_dump.py 가 PreToolUse(PowerShell) 에 미배선.\n"
        f"현재 PowerShell 배선: {commands}\n"
        "해결 / Fix: .claude/settings.json 의 PreToolUse matcher 를 'Bash|PowerShell' 로."
    )


def test_hook_wired_to_railway_mcp_variable_listing():
    """🔴 Railway MCP 변수 목록 도구에도 배선 — 셸 밖의 같은 덤프 경로."""
    commands = pretooluse_commands_for(_settings(), _MCP_LIST)
    assert any_invokes(commands, ".claude/hooks/block_credential_dump.py"), (
        f"block_credential_dump.py 가 PreToolUse({_MCP_LIST}) 에 미배선.\n"
        f"현재 배선: {commands}"
    )


def test_wired_hook_exists_on_disk():
    """배선된 훅이 실재 — 경로 오타 시 훅이 무음 실패한다(#1094 형 차단)."""
    assert _HOOK.is_file(), f"배선된 훅 파일 부재: {_HOOK.relative_to(_ROOT)}"


def test_existing_edit_hooks_survive():
    """기존 Write/Edit 훅 배선이 유지 — Bash 그룹 추가가 기존 보호를 덮어쓰지 않는다."""
    commands = pretooluse_commands_for(_settings(), "Write")
    assert any_invokes(commands, ".claude/hooks/check_edit_allowed.py"), (
        "check_edit_allowed.py 배선이 사라졌다 — 모바일 환경 보호가 무력화된다."
    )
