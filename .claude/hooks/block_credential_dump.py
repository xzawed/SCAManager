"""셸 credential 덤프 차단 훅 — 정책 12 위반의 **기계 집행면**(Bash · PowerShell 도구).
PreToolUse hook that blocks shell commands (Bash and PowerShell tools) which dump credential *values*.

🔴 왜 존재하는가 (2026-07-19 회고 P0): Claude 가 정책 12 를 위반해 credential 을 대화
기록에 평문 출력했다. 의도는 변수 **이름만** 보는 것이었으나 grep 패턴이 값까지 매칭했다:

    railway variables --service SCAManager --kv | grep -iE "SCHEDULER|ENVIRONMENT|LOG_LEVEL|CRON"
                                                                                       ^^^^
                                                       INTERNAL_CRON_API_KEY 의 **값**까지 출력

그 뒤 재발 방지책으로 남긴 것은 **산문뿐**이었다(owed 원장 표 셀 + 로컬 메모리). 2차 회고
(168 에이전트)가 이를 P0 로 확정했다 — "credential 유출 벡터(Bash stdout)에 훅 커버리지 0",
"인지 의존 산문 5회차". 이 파일이 그 시정이다.
The recurrence-prevention rule previously existed only as prose; this hook is the enforcement.

🔴 훅은 실행이 아니라 **명령 글자**를 본다. 그래서 같은 값을 쏟는 다른 이름(CLI 별칭 ·
`railway environment config` · PowerShell 고유 명령)은 목록에 없으면 통과한다 — 별칭은 CLI 도움말에서
옮긴다. PowerShell 도구도 같은 판정을 받는다(이 PC 의 기본 셸 도구다). 셸 밖의 같은 덤프인
Railway MCP `list_variables` 는 도구 이름으로 막는다.
The hook reads command text, not execution: every alias that dumps the same values must be listed.
The Railway MCP list_variables tool is denied by name.

🔴 설계 원칙 — **대안 없는 차단은 훅을 무력화시킨다.** 차단 시 반드시 안전한 관용구를
안내한다(이름만 → `cut -d= -f1`, 배포 설정 → `scripts/railway_config.py`). 그래야 다음 세션이 훅을
우회하지 않는다.
Blocking without an alternative gets hooks disabled; every denial teaches the safe idiom.

🔴 위협 모형 — **실수로 값을 찍는 정직한 세션**이다. 그런 세션이 칠 만한 꼴(별칭 · 접두어 · 경로 ·
괄호 · 따옴표 · 파이프라인 · 리디렉션)은 막고, 중화(이름만 자르기 · 쓰기)는 읽을 수 없으면 인정하지
않는다. 의도적 우회(`sh -c` 간접 실행 · 임의 코드 · 파일 경유)는 글자 훅이 망라할 수 없다 — 그 경로는
운영 접근 자체의 사전 승인이 맡는다.
Threat model: an honest session dumping by accident. Deliberate evasion (indirection, arbitrary code)
cannot be enumerated by a text hook; prior approval of production access covers it.
"""
import json
import re
import shlex
import sys

# 판정하는 셸 도구 / shell tools this hook judges
_SHELL_TOOLS = ("Bash", "PowerShell")
# 셸을 거치지 않는 같은 덤프 — Railway MCP `list_variables` 는 «KEY=VALUE 쌍을 반환» 한다(도구 설명).
# 값 개수만 내는 `get_service_config` 는 대상이 아니다.
# The same dump without a shell: Railway MCP list_variables returns KEY=VALUE pairs.
_MCP_DUMP_TOOLS = re.compile(r"mcp__.*railway.*__list_variables")

# railway 낱말 — 경로 · 대소문자 · npm shim 확장자(.cmd .exe .ps1) · 따옴표와 무관하게 본다(보안 리뷰 지적).
# PowerShell 은 명령 이름 대소문자를 가리지 않고, Windows 의 npm 설치본은 railway.cmd / railway.ps1 shim 이다.
# The railway word regardless of path, case, npm shim extension or quotes.
_RW = r"\brailway(?:\.(?:cmd|exe|ps1))?[\"']?"


def _is_railway(tok):
    """토큰이 railway 실행 파일인가(경로 · 확장자 · 대소문자 무관) / Is this token the railway executable?"""
    base = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".cmd", ".exe", ".ps1"):
        if base.endswith(ext):
            base = base[: -len(ext)]
    return base == "railway"


_SAFE_IDIOM = 'railway variables --kv | cut -d= -f1 | grep -i CRON'
_SAFE_CONFIG = "py -3 scripts/railway_config.py"
_SAFE_ENV = "$env:NAME  (YAML 의 env: 키를 찾는 grep 이면 콜론을 빼고: grep -n 'env' <파일>)"

# ── 무엇이 덤프를 «중화» 하는가 ─────────────────────────────────────────────
# What neutralizes a dump.
# - "names": 덤프 **바로 다음** 단계가 정확히 `cut -d= -f1` 이고, 덤프가 KEY=VALUE 줄일 때만.
#   JSON·표 출력에는 `=` 가 없어 cut 이 줄을 통째로 내보낸다.
# - "write": 그 단계 자체가 쓰기(값을 넣거나 지움)일 때만 — 옆 단계를 덮지 않는다.
# - None: 중화 수단 없음(안전 대체로 보낸다).
# "names": the very next stage is exactly `cut -d= -f1`, KEY=VALUE output only. "write": the stage writes.
_NAMES, _WRITE = "names", "write"

# 🔴 파이프라인 단계 **전체**가 정확히 이 관용구일 때만 — `-f1-` · `-f1,2` · `--complement` 는 값을 그대로
#    낸다(Grok G1 반례). 구분자 `=` 의 따옴표 변형과 -d/-f 순서 바꿈만 허용한다.
# The whole stage must be exactly the idiom: -f1-, -f1,2 and --complement still print values.
_CUT_IDIOM = re.compile(
    r"""\s*cut\s+(?:-d\s*(?P<q1>['"]?)=(?P=q1)\s+-f\s*1|-f\s*1\s+-d\s*(?P<q2>['"]?)=(?P=q2))\s*"""
)
# ── `railway variable` 호출을 «토큰으로» 읽는다 — 중화(쓰기 · --kv) 판정 전용 ──────────────────
# 🔴 정규식은 셸의 따옴표·주석을 모른다. `--service "x set" --kv` 의 `set` 을 하위 명령으로,
#    `# --set` 주석을 쓰기로, `--service "--kv x"` 의 `--kv` 를 KV 출력으로 읽었다(Grok G1 반례).
#    그래서 탐지는 넓은 정규식(막는 쪽)으로 두고, **중화**만 shlex 토큰으로 판정한다. 토큰을 못 읽으면
#    (따옴표 불균형) 중화를 인정하지 않는다.
# Regexes do not know shell quoting or comments, so neutralizers (write, --kv) are judged on shlex tokens;
# unreadable tokens never neutralize.
_VARIABLE_ALIASES = frozenset({"variable", "variables", "var", "vars"})
# 값을 받는 옵션(CLI 도움말) / options that take a value
_VARIABLE_VALUE_OPTIONS = frozenset({"-s", "--service", "-e", "--environment", "-p", "--project"})
_VARIABLE_SET_OPTIONS = frozenset({"--set", "--set-from-stdin"})
_VARIABLE_WRITE_SUBCOMMANDS = frozenset({"set", "delete", "rm", "remove"})


def _railway_variable_call(stage):
    """단계 안 `railway variable` 호출의 (쓰기인가, 플래그 집합) — 없거나 못 읽으면 None.
    (is_write, flags) of the `railway variable` call in this stage, or None."""
    # 백틱은 PowerShell 에선 이스케이프(`x` set` = 인자 하나), Bash 에선 명령 치환 — shlex 가 모른다.
    # A backtick escapes in PowerShell and substitutes in Bash; shlex knows neither, so never neutralize.
    if "`" in stage:
        return None
    try:
        toks = shlex.split(stage, comments=True, posix=True)
    except ValueError:
        return None
    for i in range(len(toks) - 1):
        if not _is_railway(toks[i]) or toks[i + 1].lower() not in _VARIABLE_ALIASES:
            continue
        write, flags, sub = False, set(), None
        j = i + 2
        while j < len(toks):
            tok = toks[j]
            name, has_eq = (tok.split("=", 1)[0], "=" in tok) if tok.startswith("--") else (tok, False)
            if name in _VARIABLE_SET_OPTIONS:
                write = write or has_eq or j + 1 < len(toks)
                j += 1 if has_eq else 2
            elif name in _VARIABLE_VALUE_OPTIONS:
                j += 1 if has_eq else 2
            elif tok.startswith("-"):
                flags.add(tok)
                j += 1
            else:
                if sub is None:
                    sub = tok
                    write = write or tok in _VARIABLE_WRITE_SUBCOMMANDS
                j += 1
        return write, flags
    return None


# ── 셸 환경 전체 나열 — 토큰으로 본다 ─────────────────────────────────────────────
# 🔴 단계 전체를 정규식으로 맞추면 `command env` · `/usr/bin/env` · `(env)` · `"env"` · `FOO=1 env` 가
#    빠진다(보안 리뷰 지적). 그래서 명령 자리(앞쪽 대입 · 실행 접두어 · 괄호 · 경로를 걷어 낸 첫 낱말)를
#    토큰으로 읽는다. `env` 는 옵션·대입 뒤에 **실행할 명령이 남을 때만** 실행기다 — 그 밖은 나열이다.
# Whole-environment listings, read as tokens at the command position (leading assignments, exec
# prefixes, parentheses and paths stripped). `env` is a runner only when a command follows.
_LISTING_PREFIXES = frozenset({"command", "builtin", "exec", "sudo", "nohup", "time"})
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def _lists_environment(stage):
    """단계가 환경 전체를 찍는가 / Does this stage list the whole environment?"""
    try:
        toks = shlex.split(stage, posix=True)
    except ValueError:
        toks = stage.split()
    words = [w for w in (t.strip("(){}") for t in toks) if w]
    i = 0
    while i < len(words) and (words[i] in _LISTING_PREFIXES or _ASSIGNMENT.fullmatch(words[i])):
        i += 1
    if i >= len(words):
        return False
    head = words[i].replace("\\", "/").rsplit("/", 1)[-1]
    head = head[:-4] if head.lower().endswith(".exe") else head
    rest = words[i + 1:]
    if head == "env":
        # 값을 받는 옵션(-u/--unset NAME · -C/--chdir DIR)의 값은 명령이 아니다. -S 의 값은 실행할 명령이다.
        # Values of -u/--unset and -C/--chdir are not commands; -S carries the command itself.
        k = 0
        while k < len(rest):
            w = rest[k]
            if w in ("-u", "--unset", "-C", "--chdir"):
                k += 2
            elif w.startswith(("-S", "--split-string")):
                return False
            elif w.startswith("-") or _ASSIGNMENT.fullmatch(w):
                k += 1
            else:
                return False  # 실행할 명령이 남았다 — 실행기 / a command follows: a runner
        return True
    if head == "set":
        return not rest
    if head == "export":
        return not rest or rest == ["-p"]
    if head in ("declare", "typeset"):
        # 이름 없이 플래그만이면 해당 변수들을 **값과 함께** 나열한다(-x · -p 만이 아니라 -i · -r · -a 등도).
        # 함수만 내는 -f · -F 뿐일 때만 나열이 아니다(증거집합 가드 지적 — 첫 판은 x · p 두 글자만 봤다).
        # With flags only, declare lists matching variables WITH values; only -f/-F (functions) do not.
        if not all(w.startswith("-") for w in rest):
            return False
        letters = {ch for w in rest for ch in w.lstrip("-")}
        return not rest or not letters <= {"f", "F"}
    return False


def _railway_inner_lists_environment(stage):
    """`railway ssh|run|local [옵션] [--] <안쪽 명령>` 의 안쪽 명령이 환경 전체를 찍는가.
    Does the inner command of `railway ssh|run|local` list the whole environment?"""
    if not re.search(_RW + r"\s+(?:ssh|run|local)\b", stage, re.IGNORECASE):
        return False
    try:
        toks = shlex.split(stage, posix=True)
    except ValueError:
        # 못 읽으면 나열 낱말이 글자로 있는지로 — 막는 쪽 / unreadable: fall back to the words, failing closed
        return bool(re.search(r"\b(?:env|set|export|declare|typeset)\b", stage))
    for i in range(len(toks) - 1):
        if not _is_railway(toks[i]) or toks[i + 1].lower() not in ("ssh", "run", "local"):
            continue
        # 옵션 값 개수를 세지 않는다 — ssh 는 -d · -i · --session[=값] 처럼 옵션마다 달라 셈이 틀리면 안쪽 명령을
        # 놓친다(보안 리뷰 지적). 안쪽 토큰의 모든 접미 구간을 본다(막는 쪽).
        # Do not count option arity (it differs per option); test every suffix of the inner tokens.
        inner = toks[i + 2:]
        return any(_lists_environment(" ".join(shlex.quote(t) for t in inner[k:]))
                   for k in range(len(inner)))
    return False


# ── credential **값**을 stdout 으로 쏟는 명령: (판정 함수, 사유, 중화 수단, 안내) ──────
# Commands that dump credential values: (matcher, reason, neutralizers, hint).
# 🔴 `.env\b(?!\.)` 부정 lookahead — 커밋된 템플릿 `.env.example` 은 값이 없고
#    CLAUDE.md 핵심 명령(`cp .env.example .env`)에 등장하므로 차단 대상이 아니다.
#    Negative lookahead so the committed, value-free .env.example template stays usable.
_BLOCKED = (
    # `railway variable` 의 별칭은 variables · vars · var (`railway --help`).
    (re.compile(_RW + r"\s+(?:variables?|vars?)\b", re.IGNORECASE).search,
     "railway variable(s) — 서비스 변수 값 덤프", (_NAMES, _WRITE), _SAFE_IDIOM),
    # `environment` = `env`, `config` = `show` = `info` (CLI 도움말). 출력에 서비스·공유 변수 값이
    # 평문으로 실린다. `--json` 없는 꼴도 막는다 — 판이 바뀌면 조용히 값이 나온다.
    # Aliases from the CLI help; the plain form is blocked too so a CLI change cannot leak silently.
    (re.compile(_RW + r"\s+(?:environment|env)\b[^|&;]*?\s(?:config|show|info)\b", re.IGNORECASE).search,
     "railway environment config — 서비스 변수 값까지 평문 출력", (), _SAFE_CONFIG),
    (re.compile(r"\bprintenv\b").search,
     "printenv — 프로세스 env 값 덤프", (_NAMES,), _SAFE_IDIOM),
    # 운영 컨테이너(ssh)나 Railway 변수를 주입한 로컬 실행(run = local)의 **안쪽 명령**이 환경 전체를
    # 찍는 꼴 — 안쪽 명령을 토큰으로 떼어 아래 셸 나열 판정에 넘긴다(`--env production` 인자는 대상 아님).
    # The inner command of ssh/run/local, judged by the same whole-environment listing check.
    (_railway_inner_lists_environment,
     "railway ssh/run env — 운영·주입 env 값 덤프", (_NAMES,), _SAFE_IDIOM),
    # 프로세스 환경 파일(NUL 구분 KEY=VALUE) — `cut` 으로 중화되지 않는다.
    # The process environment file (NUL-separated); a cut does not neutralize it.
    (re.compile(r"/proc/[^\s/]+/environ\b").search,
     "/proc/*/environ — 프로세스 env 값 덤프", (), _SAFE_IDIOM),
    (re.compile(r"\b(?:cat|type|gc|Get-Content)\b[^|&;]*\.env\b(?!\.)", re.IGNORECASE).search,
     "cat/type/Get-Content .env — 시크릿 파일 직접 열람", (_NAMES,), _SAFE_IDIOM),
    # PowerShell 의 printenv — env: 드라이브 경로는 **정확히 변수 이름 하나 + 구분자** 일 때만 통과한다.
    # 그 밖은 전부 덤프로 본다: 빈 경로 · 구분자 · 와일드카드 · 따옴표로 쪼갠 와일드카드(`env:A'*'`) ·
    # 변수 전개(`env:$p`). 덤프 꼴을 열거하는 판정은 세 번 뚫렸다(보안 리뷰 지적 3회).
    # `$env:NAME` · `${env:NAME}` 은 변수 문법이라 대상 아님. YAML 의 `env:` 키를 찾는 grep 도 막히는데,
    # 그때는 콜론을 빼고 찾는다(안내에 적는다).
    # PowerShell's printenv: an env: path passes only as exactly one literal variable name plus a
    # delimiter; everything else (empty, separator, wildcard, split quotes, expansion) is a dump.
    (re.compile(r"(?<![\w$])env:(?![A-Za-z_][A-Za-z0-9_]*(?:[\s;|),}]|$))", re.IGNORECASE).search,
     "env: 드라이브 나열 — 프로세스 env 값 덤프", (), _SAFE_ENV),
    # 공급자 경로(`Environment::` · `Microsoft.PowerShell.Core\Environment::`)와 .NET 전체 조회.
    # Provider-qualified paths and the .NET full read.
    (re.compile(r"\bEnvironment::", re.IGNORECASE).search,
     "Environment:: 공급자 경로 — 프로세스 env 값 덤프", (), _SAFE_ENV),
    (re.compile(r"\[(?:System\.)?Environment\]::GetEnvironmentVariables\b", re.IGNORECASE).search,
     "GetEnvironmentVariables — 프로세스 env 값 덤프", (), _SAFE_ENV),
    # Bash 의 env 전체 출력(env · set · export -p · declare -x) — 명령 자리를 토큰으로 본다
    # (`env FOO=1 cmd` · `/usr/bin/env python x.py` · `set -e` · `export X=1` 은 대상 아님). 출력이 KEY=VALUE
    # 줄이라 바로 다음 단계의 `cut -d= -f1` 이 중화한다.
    # Whole-env listings in Bash, read at the command position; a following exact cut neutralizes.
    (_lists_environment,
     "env/set/export -p — 셸 env 값 덤프", (_NAMES,), _SAFE_IDIOM),
    # cmd 의 `set NAME` 은 그 이름으로 **시작하는** 변수를 전부 나열한다 — 대입(`set A=1`)만 대상 아님(보안 리뷰 지적).
    # cmd's `set NAME` lists every variable starting with NAME; only an assignment is not a dump.
    (re.compile(r"\bcmd(?:\.exe)?\s+/[ck]\s+[\"']?set\b(?!\s*[\"']?\w+=)", re.IGNORECASE).search,
     "cmd /c set — 프로세스 env 값 덤프", (_NAMES,), _SAFE_IDIOM),
)


# ── 세그먼트 분해 경계 (2026-07-26 5+1 회고 P0 — 복합 명령 fail-open 봉인) ──
# 🔴 `;`·`&&`·`||`·`&`·줄바꿈으로 이어진 명령은 서로를 중화하지 못한다 — 안전한 쪽이 위험한 쪽을
# 가려주면 안 된다. 파이프라인(단일 `|`)은 하류 필터가 상류 덤프를 실제로 중화할 수 있으므로 한
# 세그먼트로 두고, 그 안에서 **단계별로** 판정한다(이름만 자르는 cut 은 덤프 바로 다음 단계여야 한다).
# 🔴 `;`/`&&`/`||`/`&` chain independent commands that cannot neutralize one another. A pipeline stays one
# segment and is judged stage by stage — the names-only cut must be the very next stage.
# `||` 는 `[|]{2}` 로 쓴다 — 같은 뜻이고, 증거집합 가드가 교대를 `|` 로 쪼갤 때 빈 조각을 만들지 않는다.
# `||` is written `[|]{2}`: same meaning, and no empty piece when the witness guard splits on `|`.
_SEPARATORS = re.compile(r"&&|[|]{2}|;|\n|&")


# 🔴 리디렉션(`>&2` · `> 파일` · `<`)과 명령·프로세스 치환(`$(` · `<(` · `>(`)이 든 단계는 중화하지 않는다 —
#    출력이 cut 을 비켜 가거나 쓰기 명령 안에서 읽기가 돈다(보안 리뷰 지적).
# A stage with redirection or substitution is never neutralized: output can bypass the cut, or a read
# can run inside a write.
_UNREADABLE_STAGE = re.compile(r"[<>]|\$\(")


def _neutralized(stages, i, neutralizers):
    """i 번째 단계의 덤프가 중화됐는가 / Is the dump at stage i neutralized?"""
    stage = stages[i]
    if _UNREADABLE_STAGE.search(stage):
        return False
    is_variable = _WRITE in neutralizers  # railway variable 항목만 쓰기 중화를 가진다
    call = _railway_variable_call(stage) if is_variable else None
    # 한 단계에 railway variable 호출이 둘 이상이면 쓰기로 덮지 않는다 / never excuse two calls in one stage
    single = len(re.findall(_RW + r"\s+(?:variables?|vars?)\b", stage, re.IGNORECASE)) == 1
    if is_variable and single and call is not None and call[0]:
        return True
    # 🔴 이름만 자르는 cut 은 덤프 **바로 다음** 단계여야 한다 — 사이 단계(`tee /dev/stderr` 등)가 값을
    #    복제할 수 있다. railway variable 은 KEY=VALUE(--kv · -k, --json 없음) 출력일 때만 — 토큰으로 본다.
    # The names-only cut must be the very next stage (a stage in between, e.g. tee, can copy values).
    # For railway variable it needs KEY=VALUE output (--kv/-k without --json), read as tokens.
    if _NAMES in neutralizers and i + 1 < len(stages) and _CUT_IDIOM.fullmatch(stages[i + 1]):
        if is_variable:
            return (call is not None and bool({"--kv", "-k"} & call[1])
                    and "--json" not in call[1])
        return True
    return False


def _decide_segment(segment):
    """단일 명령(파이프라인 포함)에 대한 판정 — 차단 사유와 안내를 내거나 None.
    Verdict for one command (pipeline included): (reason, hint) or None."""
    stages = segment.split("|")
    # 🔴 `#` 이 있으면 그 뒤가 주석일 수 있다 — `--kv # | cut -d= -f1` 의 cut 은 실행되지 않는다(Grok G1).
    #    단계 분해는 주석을 모르므로, `#` 이 든 세그먼트에서는 어떤 중화도 인정하지 않는다.
    # A `#` may start a comment («--kv # | cut» never runs the cut), so no neutralizer counts there.
    commented = "#" in segment
    for i, stage in enumerate(stages):
        for matcher, reason, neutralizers, hint in _BLOCKED:
            if matcher(stage) and (commented or not _neutralized(stages, i, neutralizers)):
                return reason, hint
    return None


def decide(command):
    """차단 사유를 반환하거나, 통과면 None.
    Return a denial reason, or None when the command may proceed.

    🔴 세그먼트 **하나라도** 차단 대상이면 명령 전체를 deny 한다(fail-closed). 예외를 명령 문자열
    **전체**에 먼저 적용하면 안전한 세그먼트 하나가 명령 전체를 화이트리스트한다 — 가장 자연스러운
    우회가 `_SAFE_IDIOM` 을 앞에 붙이는 것이라('이름 먼저 보고 값도 하나 확인' 흐름) 실사용 형태 그대로
    뚫렸다. 같은 이유로 세그먼트 안에서도 중화는 **그 덤프 단계 자신이나 뒤 단계**만 본다.
    🔴 Deny if ANY segment is blocked (fail-closed); inside a segment a neutralizer only covers its own
    stage or a later one.
    """
    found = decide_with_hint(command)
    return found[0] if found else None


def decide_with_hint(command):
    """(사유, 안내) 또는 None / (reason, hint) or None."""
    if not command:
        return None
    for segment in _SEPARATORS.split(command):
        found = _decide_segment(segment)
        if found:
            return found
    return None


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    현재 출력은 `ensure_ascii=True` JSON 뿐이라 크래시 경로가 없지만, 차단 사유 문구를
    한 줄 추가하는 순간 훅이 죽는다 — 그 형태가 실제로 doc_review_gate.py 를 죽였다.
    No crash path today (ASCII-only JSON), but one Korean reason string would introduce one —
    which is exactly what killed doc_review_gate.py.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / captured streams: ignore


def main():
    _make_stdout_safe()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # 입력이 깨져도 작업을 막지 않는다 — 이 훅은 advisory 성격의 안전망이다.
        # Never block on malformed input; this hook is a safety net, not a gate on correctness.
        return 0

    tool = payload.get("tool_name") or ""
    if _MCP_DUMP_TOOLS.fullmatch(tool):
        found = ("Railway MCP list_variables — 서비스 변수 값(KEY=VALUE) 덤프", _SAFE_IDIOM)
    elif tool in _SHELL_TOOLS:
        command = (payload.get("tool_input") or {}).get("command") or ""
        found = decide_with_hint(command)
    else:
        return 0
    if found is None:
        return 0
    reason, hint = found
    if hint == _SAFE_CONFIG:
        safe = f"배포 설정은 변수 값을 뺀 읽기로 보세요:\n  {_SAFE_CONFIG}\n\n"
    elif hint == _SAFE_ENV:
        safe = f"변수 하나만 필요하면 그 이름으로 읽으세요:\n  {_SAFE_ENV}\n\n"
    else:
        safe = f"이름만 필요하면 값을 먼저 잘라내세요:\n  {hint}\n\n"

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"[credential 보호] {tool} 실행 차단 (정책 12)\n\n"
                f"사유: {reason}\n\n"
                "이 명령은 credential **값**을 대화 기록에 평문으로 남깁니다.\n"
                "2026-07-19 에 실제로 발생한 사고입니다 — grep 패턴이 변수 이름뿐 아니라\n"
                "값까지 매칭해 API 키가 그대로 출력됐습니다.\n\n"
                f"{safe}"
                "값이 정말 필요하면 사용자에게 요청하세요 (정책 12: 사전 승인 의무)."
            ),
        }
    }
    # ensure_ascii=True — Windows cp949 콘솔에서 무음 실패하지 않도록.
    # ensure_ascii keeps the payload decodable on Windows cp949 consoles.
    print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
