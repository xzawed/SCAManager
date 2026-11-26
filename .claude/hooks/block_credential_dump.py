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

🔴 운영 접근(회고 2026-11-06 원장 L02, P0) — 같은 훅이 그 «사전 승인» 을 기계로 집행한다. 운영은 SQL 동사가
아니라 행위로 가른다: railway 는 읽기(배포 목록 · 로그 · 상태 · 지표 · 도움말)만 통과시키는 허용 목록이고,
운영 컨테이너 코드 실행 · 운영 변수를 넣은 실행 · 배포 · 변수 · 환경 변경과 Railway · Supabase MCP 의 변경 ·
SQL 도구는 막는다 — 사용자가 `!` 로 직접 실행한다. 훅을 하나 더 띄우지 않고 이 파일에 둔 것은 셸 명령마다
드는 훅 고정 비용 때문이다(회고 L11) — 해석기(세그먼트 · 단계 · 명령 자리)도 같이 쓴다.
The same hook enforces that prior approval: production is judged by action (railway reads only; code in
the production container, runs with production variables, deploy/variable/environment changes and the
changing or SQL MCP tools are denied — the user runs them with `!`). Kept in this file to avoid a second
hook process per shell call; it reuses the same parser.

🔴 판정하지 못한 호출 — 훅 프로세스가 시작하지 못하거나 · 0/2 밖의 코드로 끝나거나 · 시간을 넘기면 settings 의
`onFailure: "block"` 이 그 호출을 막는다. 판정 중 예외 · JSON 객체가 아닌 입력은 «판정 불가» 로 받아 운영 · 자격 표지
(`_UNJUDGED_MARKERS`)가 있는 호출만 deny 하고, 나머지는 막지 않되 판정 불가를 알린다(`_emit_unjudged` ·
시험 = `test_credential_hook_failure_contract.py`).
Unjudged calls: a hook process that cannot start, exits outside 0/2 or times out is blocked by
`onFailure: "block"`; an exception in the verdict or a non-object payload denies only marked calls and
reports the rest.
"""
import fnmatch
import functools
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time

# 판정하는 셸 도구 / shell tools this hook judges
_SHELL_TOOLS = ("Bash", "PowerShell")
# 셸을 거치지 않는 같은 덤프 — Railway MCP `list_variables` 는 «KEY=VALUE 쌍을 반환» 한다(도구 설명).
# 값 개수만 내는 `get_service_config` 는 대상이 아니다.
# The same dump without a shell: Railway MCP list_variables returns KEY=VALUE pairs.
_MCP_DUMP_TOOLS = re.compile(r"mcp__.*railway.*__list_variables")

# railway 낱말 — 경로 · 대소문자 · npm shim 확장자(.cmd .exe .ps1) · 따옴표와 무관하게 본다(보안 리뷰 지적).
# PowerShell 은 명령 이름 대소문자를 가리지 않고, Windows 의 npm 설치본은 railway.cmd / railway.ps1 shim 이다.
# The railway word regardless of path, case, npm shim extension or quotes.
# 패키지 실행기로 부른 꼴(`npx @railway/cli variables` · `pnpm dlx @railway/cli@4 …`)도 같은 실행 파일이다 — `railway` 바로
# 뒤에 공백을 요구해 그 꼴의 변수 덤프가 판정을 비켜 갔다(워크플로 wf_8b259a5e-212 C3 렌즈 · main 때부터).
# The package-runner spelling is the same executable; requiring whitespace right after `railway` let its dump through.
_RW = r"(?:@railway/cli(?:@[\w.^~-]+)?|\brailway(?:\.(?:cmd|exe|ps1))?)[\"']?"


def _is_railway(tok):
    """토큰이 railway 실행 파일인가(경로 · 확장자 · 대소문자 무관) / Is this token the railway executable?"""
    base = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".cmd", ".exe", ".ps1"):
        if base.endswith(ext):
            base = base[: -len(ext)]
    return base == "railway"


def _is_railway_cli(tok):
    """`_is_railway` 에 패키지 실행기 이름 `@railway/cli` 를 더한 판정 — credential 층(변수 덤프 · 안쪽 명령)만 쓴다. 운영
    판정 순회는 main 그대로 `_is_railway` 를 쓴다(이것을 거기 쓰면 `if npm ls -g @railway/cli` 가 막혔다 — 워크플로 셋째 패스).
    `_is_railway` plus the `@railway/cli` package name; the credential layer only."""
    if tok.lower().startswith("@railway/cli"):
        return True
    base = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".cmd", ".exe", ".ps1"):
        if base.endswith(ext):
            base = base[: -len(ext)]
    return base == "railway"


_SAFE_IDIOM = 'railway variables --kv | cut -d= -f1 | grep -i CRON'
_SAFE_CONFIG = "py -3 scripts/railway_config.py"
_SAFE_ENV = "$env:NAME  (YAML 의 env: 키를 찾는 grep 이면 콜론을 빼고: grep -n 'env' <파일>)"
_SAFE_DOTENV = "grep -c NAME .env  (있는지만 센다 — 값은 열지 않는다)"
_SAFE_SEARCH = "Grep 도구 · git grep KEY · grep -rn --exclude='.env*' --exclude='*.env' KEY <폴더>"

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
# 개수만 내는 grep 단계 — cut 관용구처럼 **단계 통째** 가 이 꼴일 때만: 안전한 플래그(개수 c · 존재 q · 이름 l 중 하나는
# 반드시)와 패턴 하나, 파일 · 앞뒤 군더더기 없음(`} grep -c K` · `grep -c K .env` 는 아니다 — 커밋 보안 검토).
# A count-only grep stage, matched whole like the cut idiom: safe flags (one of c/q/l required), one pattern, no files.
_COUNT_ONLY_GREP_STAGE = re.compile(
    r"""\s*grep(?:\s+-(?=[A-Za-z]*[cql])[EFGPiwxvnHhsIcql]+|\s+-[EFGPiwxvnHhsI]+)*?(?:\s+-(?=[A-Za-z]*[cql])[EFGPiwxvnHhsIcql]+)"""
    r"""(?:\s+-[EFGPiwxvnHhsIcql]+)*(?:\s+(?:'[^']*'|"[^"$`\\]*"|[^\s'"|;&<>()$`{}\\]+))?\s*"""
)
# 개수만 내는 wc — 개수 플래그뿐일 때만. `--files0-from=-` 는 stdin 을 파일 이름으로 읽어 오류에 그 줄(값)을 찍는다.
# A count-only wc: count flags only (`--files0-from=-` reads stdin as file names and echoes them in errors).
_WC_COUNT_ONLY = re.compile(r"\s*wc(?:\s+(?:-[lcwmL]+|--(?:lines|bytes|words|chars|max-line-length)))*\s*")
# 줄 머리의 이름만 고르는 grep -o — 패턴이 `^[이름 글자]*=` 꼴(글자 모임에 `=` 이 없다)이고 플래그는 o · i · E · P · w 뿐.
# `^` 가 없으면 값 속의 `NAME=` 조각까지 고른다. A grep -o that picks only the leading name: `^[name chars]*=`.
#   끝의 `=` 를 요구하고, 글자 모임은 펼쳐서 이름 글자(영문 · 숫자 · `_` · `-`)뿐인지 본다 — `[0-z]` 같은 범위는 `=` 를
#   품어 값 조각까지 고른다(커밋 보안 검토 HIGH).
#   The trailing `=` is required and the class is expanded: a range such as `[0-z]` spans `=` and picks value pieces.
_NAMES_ONLY_GREP = re.compile(
    r"""\s*grep(?=(?:\s+-[oiEPw]+)*?\s+-[iEPw]*o)(?:\s+-[oiEPw]+)+\s+(?P<q>['"]?)\^\[(?P<body>[A-Za-z0-9_-]+)\][*+]=(?P=q)\s*"""
)
_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def _class_chars(body):
    """글자 모임 본문의 글자 집합 — `X-Y` 범위를 펼친다(앞뒤 `-` 는 글자). 거꾸로 된 범위는 None.
    Characters of a bracket-class body with X-Y ranges expanded; None for a reversed range."""
    chars, i = set(), 0
    while i < len(body):
        if i + 2 < len(body) and body[i + 1] == "-":
            lo, hi = ord(body[i]), ord(body[i + 2])
            if lo > hi:
                return None
            chars.update(chr(c) for c in range(lo, hi + 1))
            i += 3
        else:
            chars.add(body[i])
            i += 1
    return chars


def _names_only_grep(stage):
    """줄 머리의 이름만 고르는 grep -o 인가 — 모임을 펼친 글자가 이름 글자뿐일 때만.
    Is this a grep -o that keeps only the leading name (class expands to name characters only)?"""
    m = _NAMES_ONLY_GREP.fullmatch(stage)
    chars = _class_chars(m.group("body")) if m else None
    return chars is not None and chars <= _NAME_CHARS
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


def _railway_variable_call(stage, main_reading=False):
    """단계 안 `railway variable` 호출의 (쓰기인가, 플래그 집합) — 없거나 못 읽으면 None. main_reading 이면 main 그대로
    읽는다(PowerShell 백슬래시도 이스케이프 · `@railway/cli` 는 railway 가 아니다).
    (is_write, flags) of the `railway variable` call in this stage, or None; main_reading reads it as main did."""
    # 백틱은 PowerShell 에선 이스케이프(`x` set` = 인자 하나), Bash 에선 명령 치환 — shlex 가 모른다.
    # A backtick escapes in PowerShell and substitutes in Bash; shlex knows neither, so never neutralize.
    if "`" in stage:
        return None
    try:
        toks = shlex.split(stage if main_reading else _ps_literal_backslashes(stage), comments=True, posix=True)
    except ValueError:
        return None
    is_railway = _is_railway if main_reading else _is_railway_cli
    for i in range(len(toks) - 1):
        if not is_railway(toks[i]) or toks[i + 1].lower() not in _VARIABLE_ALIASES:
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


def _command_words(stage, ps_literal=False):
    """명령 자리의 (첫 낱말 소문자, 나머지 낱말) — 앞쪽 대입 · 실행 접두어 · 괄호 · 경로 · .exe 를 걷어 낸다.
    ps_literal 이면 PowerShell 에서 백슬래시를 글자로 읽는다 — 감사 채널의 스크립트 경로(`scripts\\observe_db.py`) 전용이다.
    판정에 쓰면 안 된다: 낱말의 백슬래시를 모두 바꾸면 find 의 정규식 이스케이프(`\\.`)가 `/.` 가 되어 .env 를 고르는 find 가
    통과했다(워크플로 wf_8b259a5e-212 C3 렌즈).
    (head lower-cased, rest) at the command position; assignments, prefixes, parens, paths and .exe stripped.
    ps_literal reads PowerShell backslashes literally, for the audit's script paths only — never for verdicts."""
    text = _ps_literal_backslashes(stage) if ps_literal else stage
    try:
        toks = shlex.split(text, posix=True)
    except ValueError:
        toks = text.split()
    words = [w for w in (t.strip("(){}") for t in toks) if w]
    i = 0
    while i < len(words) and (words[i].lower() in _LISTING_PREFIXES or _ASSIGNMENT.fullmatch(words[i])):
        i += 1
    if i >= len(words):
        return "", []
    # PowerShell · Windows 의 명령 찾기는 대소문자를 가리지 않는다(`ENV` 도 env.exe) — 소문자로 비교한다.
    # Command lookup is case-insensitive in PowerShell / on Windows; compare lower-cased.
    head = words[i].replace("\\", "/").rsplit("/", 1)[-1].lower()
    head = head[:-4] if head.endswith(".exe") else head
    return head, words[i + 1:]


def _lists_environment(stage):
    """단계가 환경 전체를 찍는가 / Does this stage list the whole environment?"""
    head, rest = _command_words(stage)
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
        if not _is_railway_cli(toks[i]) or toks[i + 1].lower() not in ("ssh", "run", "local"):
            continue
        # 옵션 값 개수를 세지 않는다 — ssh 는 -d · -i · --session[=값] 처럼 옵션마다 달라 셈이 틀리면 안쪽 명령을
        # 놓친다(보안 리뷰 지적). 안쪽 토큰의 모든 접미 구간을 본다(막는 쪽).
        # Do not count option arity (it differs per option); test every suffix of the inner tokens.
        inner = toks[i + 2:]
        return any(_lists_environment(" ".join(shlex.quote(t) for t in inner[k:]))
                   for k in range(len(inner)))
    return False


# ── .env 읽기 — 판정을 뒤집는다: .env 꼴 경로가 나오면 막고, 안전한 꼴만 통과 ──────────────────
# 🔴 읽기 도구를 열거하면 늘 빠진다(cat · type → grep · head → diff · base64 · tac · cut …, 보안 리뷰 지적 2회).
#    경로 변형(.env.local · .env.production.local · .env-old · prod.env)도 같다. 그래서 «.env 꼴 경로가 남아
#    있으면 읽기» 로 보고, 안전한 꼴만 통과시킨다:
#    - 값 없는 템플릿 — 마지막 경로 이름이 정확히 .env.example · .env.sample · .env.template
#    - .env 가 쓰기 대상(`>` · `>>`)으로만 나오는 꼴
#    - 개수 · 존재 · 파일 이름만 내는 grep 계열(-c · -q · -l) — 사용자 관행(값은 열지 않는다)
#    - 옮기기 · 지우기 · 정보 보기 · 쓰기 명령(아래 목록) · git 의 상태 확인
#    - 바로 다음 단계의 `cut -d= -f1`(이름만) — 중화 판정이 맡는다
# Inverted: any .env-like path counts as a read unless the form is known safe.
_PATHISH = re.compile(r"[^\s'\";|&()<>]+")
# 쓰기 리디렉션의 대상 — 이스케이프한 `\>`(글자) · 읽기-쓰기 `<>`(읽는다)의 `>` 는 아니다(AntiGravity 2차).
# A write redirection target; an escaped `\>` (a literal) and the read-write `<>` (it reads) are not writes.
_REDIRECT_TARGET = re.compile(r"(?<![\\<])>>?\s*(['\"]?)[^\s'\";|&()<>]+\1")
# 출력 리디렉션 통째(앞 fd 번호 · `&>` · `>&2` 포함) — 검색 대상을 셀 때 걷는다. 입력(`<`)은 읽기라 남긴다.
# A whole output redirection (fd number, &>, >&N); stripped before counting search targets. Input `<` stays.
_OUTPUT_REDIRECT = re.compile(r"(?:(?<=\s)\d+|&)?(?<![\\<])>>?(?:&\d+|\s*(['\"]?)[^\s'\";|&()<>]+\1)")
# 입력 리디렉션이 읽는 낱말(`<` · `<>` 바로 뒤 · 따옴표로 감싸도) / the word an input redirection reads
_REDIRECT_READ_TARGET = re.compile(r"""<>?\s*(['"]?)([^\s'"<>|;&()]+)\1""")
# 백슬래시 — 짝(`\\`)이거나 따옴표 글자 앞이 아닌 것. 따옴표 앞의 것(`\"`)은 Bash 의 이스케이프라 / 로 바꾸지 않는다.
# A backslash pair, or a backslash not before a quote; in Bash `\"` is an escape and stays.
_SLASHABLE = re.compile(r"\\\\|\\(?!['\"])")


def _slashed(text):
    """백슬래시를 / 로(Windows 경로). Bash 에서는 따옴표 글자 앞의 것(`\\"`)이 이스케이프라 남긴다 — 바꾸면
    `-e "K=\\"" .env -e "S=\\""` 의 따옴표 짝이 뒤집혀 .env 가 따옴표 안으로 삼켜진다(AntiGravity 2차). PowerShell 의
    백슬래시는 이스케이프가 아니라(백틱이 이스케이프다) 전부 바꾼다 — 남기면 `"docs\\" , .env , "src\\"` 의 짝이 거꾸로
    뒤집힌다(3차). Backslashes become slashes; in Bash a backslash before a quote is an escape and stays, in
    PowerShell a backslash is never an escape."""
    if _CONTEXT["shell"] == "powershell":
        return _ps_literal_backslashes(text)
    return _SLASHABLE.sub(lambda m: "/" * len(m.group()), text)


def _ps_literal_backslashes(text):
    """PowerShell 에서는 백슬래시가 이스케이프가 아니다 — shlex(Bash 규칙)에 넘기기 전에 / 로 바꿔 따옴표 짝 · 경로를
    지킨다(`"docs\\"` 는 그 셸에서 닫힌 문자열 · `scripts\\x.py` 는 경로). Bash 모드는 그대로 — 그 셸에서는 이스케이프다.
    쓰는 곳은 `_slashed` · `_railway_variable_call` 과 감사 순회(`_audit_words` · `_command_words(ps_literal=True)`)다 —
    판정용 명령 자리 해석에는 쓰지 않는다(find 정규식 이스케이프가 바뀐다 · 워크플로 C3).
    In PowerShell a backslash is never an escape; Bash text is returned unchanged. Not used for verdict tokenizing."""
    return text.replace("\\", "/") if _CONTEXT["shell"] == "powershell" else text


def _unquoted_lt(text):
    """따옴표 밖 `<` 의 자리 — 따옴표를 믿을 수 없으면 모든 `<`(막는 쪽). Positions of `<` outside quotes."""
    if not _quotes_trustworthy(text):
        return [i for i, ch in enumerate(text) if ch == "<"]
    found, quote = [], None
    for i, ch in enumerate(text):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "<":
            found.append(i)
    return found


def _input_redirect_targets(text):
    """따옴표 밖 입력 리디렉션(`<` · `0<` · `<>` — 붙여 써도: `cat<.env.local` · `grep -i<.env K`)이 읽는 낱말.
    `<<` · `<<<`(글자를 넘긴다) · `<(`(프로세스 치환 — 안쪽은 따로 판정한다)은 아니다. 따옴표 안의 `<`(`'<.env.local'`
    패턴)는 리디렉션이 아니다(교차 검토 2 · 3차). Words read by unquoted input redirections, attached or not."""
    targets = []
    for i in _unquoted_lt(text):
        if text.startswith(("<<", "<("), i) or (i and text[i - 1] == "<"):
            continue
        m = _REDIRECT_READ_TARGET.match(text, i)
        if m:
            targets.append(m.group(2))
    return targets
_DOTENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})
_DOTENV_SAFE_HEADS = frozenset({
    "cp", "mv", "ls", "dir", "rm", "del", "touch", "test", "[", "[[", "stat", "chmod", "attrib",
    "test-path", "copy-item", "move-item", "remove-item", "new-item", "get-item", "get-childitem",
    "set-content", "add-content", "out-file",
})
# 파일 내용을 내지 않는 git 하위 명령 — 상태 확인과, ref 이름 · 패턴만 받는 명령(branch · for-each-ref · show-ref:
# `git branch --list "x/*"` 의 글롭은 ref 이름과 맞출 뿐 파일을 읽지 않는다). tag 는 `-F 파일` 로 파일을 읽고, ls-remote 는
# `--upload-pack` 으로 명령을 돌리므로 넣지 않는다. / git subcommands that print no file contents.
_GIT_SAFE_SUBCOMMANDS = frozenset({"check-ignore", "ls-files", "status", "branch", "for-each-ref", "show-ref"})
# 글롭 값을 받는 옵션. 제외 글롭의 값만 경로 후보에서 뺀다 — 포함 글롭(`--include=.env` · `-Filter .env`)의
# 값은 그 파일을 읽겠다는 뜻이라 후보로 남긴다(보안 리뷰 HIGH). rg 의 -g/--glob/--iglob 은 `!` 가 붙으면 제외.
# 🔴 `-exclude` 는 PowerShell 매개변수다 — grep 에선 `-e xclude`(패턴) 라 뒤 토큰이 읽을 파일이 된다(14차 HIGH).
# Glob-valued options: only exclusion values leave the path candidates; inclusion values stay (they select
# files to read). rg's -g/--glob/--iglob exclude when prefixed with `!`. `-exclude` is PowerShell-only:
# for grep it parses as `-e xclude`, so the next token is a file to read.
_GREP_EXCLUDE_OPTIONS = frozenset({"--exclude", "--exclude-dir"})
_PS_EXCLUDE_OPTIONS = frozenset({"-exclude"})
_RG_GLOB_OPTIONS = frozenset({"-g", "--glob", "--iglob"})

# 훅 입력의 작업 폴더 후보와 셸 — decide_with_hint 가 정한다. 경로 · 와일드카드를 실제 폴더에 대 볼 때 쓴다.
# 🔴 작업 폴더는 «하나» 가 아니라 «후보 전부» 다 — 처음 폴더 + 명령 안의 모든 cd 대상(서브셸 · 조건부 포함).
#    cd 추적이 틀려도 판정이 느슨해지지 않도록, 상대 경로는 후보 모두에서 깨끗해야 통과한다(13차 HIGH).
# Session cwd candidates and shell from the hook input. The cwd is a SET: the starting folder plus every cd
# target in the command (subshells and conditionals too), so a wrong guess about cd can never loosen a verdict.
_CONTEXT = {"cwds": [None], "shell": "bash", "dotglob": False}
_MAX_CWDS = 8
# Bash 의 `*` 가 점 파일을 집게 하는 설정 — 명령에 있으면 셸별 규칙을 PowerShell 처럼 본다(14차).
# Settings that make Bash `*` match dot-files; when present, treat globs like PowerShell's.
_DOTGLOB = re.compile(r"dotglob|globdots|GLOBIGNORE", re.IGNORECASE)


def _bases():
    """작업 폴더 후보들(None = 훅 프로세스의 cwd) / candidate working directories."""
    return [cwd or os.getcwd() for cwd in _CONTEXT["cwds"]]


def _resolve_all(path):
    """작업 폴더 후보마다의 절대 경로 / Absolute path against every cwd candidate."""
    path = os.path.expanduser(path)
    return [path] if os.path.isabs(path) else [os.path.join(base, path) for base in _bases()]


def _cwd_unknown():
    """작업 폴더 후보 중에 훅이 모르는 것이 있는가 / Is any cwd candidate unknown to the hook?"""
    return any(_unresolvable(base) for base in _bases())


def _unresolvable(path):
    """셸이 펼칠 값(`$VAR` · `%VAR%` · `~user` · 폴더 부분의 와일드카드)이라 훅이 실제 경로를 알 수 없는가.
    Does the path hold something only the shell can expand (variables, ~user, a wildcard in a folder part)?"""
    folder = path.replace("\\", "/").rpartition("/")[0]
    return bool(re.search(r"[$%]|^~[^/]", path) or any(ch in folder for ch in "*?["))


def _star_hits_dotfiles(pattern):
    """와일드카드가 점 파일을 집는가 — PowerShell · dotglob 이면 늘, Bash 는 패턴이 점으로 시작할 때만.
    Does the glob match dot-files? Always in PowerShell or with dotglob; in Bash only for a leading dot."""
    return _CONTEXT["shell"] == "powershell" or _CONTEXT["dotglob"] or pattern.startswith(".")


def _name_glob_may_hit_dotenv(pattern):
    """폴더를 읽을 수 없을 때의 막는 쪽 판정 — 이름 와일드카드가 .env 꼴 이름을 집을 수 있는가.
    Fail-closed fallback when the folder cannot be read: could this name glob match a .env-like name?"""
    pattern = pattern.lower()
    dot_ok = _star_hits_dotfiles(pattern)
    return any(fnmatch.fnmatchcase(probe, pattern) for probe in (".env", ".env.local", "prod.env")
               if dot_ok or not probe.startswith("."))


def _is_dotenv_name(comp):
    """마지막 경로 이름이 .env 꼴인가(템플릿 제외 · NTFS 스트림 접미 제거) / Is this name .env-like?"""
    comp = re.sub(r"^[a-z]:", "", comp).split(":", 1)[0]  # 드라이브 · `.env::$DATA` 스트림 접미 제거
    if not comp or comp in _DOTENV_TEMPLATES:
        return False
    return comp == ".env" or comp.startswith((".env.", ".env-", ".env_")) or comp.endswith(".env")


def _glob_matches(norm):
    """와일드카드 경로가 실제로 집는 항목(절대 경로, 작업 폴더 후보 전부) — Bash 의 `*` 는 점 파일을 집지 않고
    PowerShell 의 `*` 는 집는다. 어느 후보에도 그 폴더가 없거나 읽을 수 없으면 None(호출자가 막는 쪽으로).
    Entries a glob really matches across every cwd candidate; None when no candidate has a readable folder."""
    folder, _, pattern = norm.rpartition("/")
    if _cwd_unknown() and not os.path.isabs(os.path.expanduser(folder or ".")):
        return None
    dot_ok = _star_hits_dotfiles(pattern)
    found, readable = [], False
    for base in _resolve_all(folder or "."):
        if not os.path.isdir(base):
            continue  # 이 후보엔 그 폴더가 없다 — 셸이 거기 있지 않았다 / not this candidate
        try:
            names = os.listdir(base)
        except OSError:
            return None  # 못 읽음 — 호출자가 막는 쪽으로 판정한다 / unreadable: callers fail closed
        readable = True
        found.extend(os.path.join(base, name) for name in names
                     if fnmatch.fnmatchcase(name.lower(), pattern.lower())
                     and (dot_ok or not name.startswith(".")))
    return found if readable else None


# 옵션이 글롭 값을 받는 명령 — 그 명령에서만 제외 글롭 값을 경로로 보지 않는다(보안 리뷰 지적).
# Commands whose options take glob values; only there are exclusion globs not treated as paths.
_GREP_FAMILY = frozenset({"grep", "egrep", "fgrep", "rgrep"})
_PS_GLOB_OPTION_HEADS = frozenset({"get-childitem", "gci", "select-string", "sls"})
# 괄호 · 치환 껍데기 — `(cat .env)` 의 `.env)` · `$(ls .env)` 의 `$(ls` 를 경로로 읽으려면 벗긴다(14차 반영 중 실측).
# Grouping and substitution wrappers around a token (`.env)`, `$(ls`) are peeled before the path check.
_TOKEN_WRAPPERS = re.compile(r"^(?:[$<>@]?[({])+|[)}]+$")


def _exclude_options_for(head):
    """그 명령에서 제외 글롭 값을 받는 옵션들 / exclusion options that take a glob for this command."""
    if head in _GREP_FAMILY:
        return _GREP_EXCLUDE_OPTIONS
    if head in _PS_GLOB_OPTION_HEADS or (head in ("ls", "dir") and _CONTEXT["shell"] == "powershell"):
        return _PS_EXCLUDE_OPTIONS
    return frozenset()


def _path_tokens(text):
    """명령의 경로 후보 토큰. 백슬래시는 / 로(Windows 경로). 옵션의 `=값` · `KEY=값` 의 값도 후보에 넣는다.
    제외 글롭 값 옵션(grep --exclude · PowerShell -Exclude · rg -g '!…')의 값은 그런 옵션이 있는 명령에서만 뺀다.
    Path-like tokens; `--opt=value` and `KEY=value` values are candidates too. Exclusion-glob option values
    are dropped only for commands that really have such options.
    따옴표 안 글롭 글자의 표지(`_mark_quoted_literals`)는 글자 그대로의 패턴(`[*]`)으로 읽는다.
    Quoted-glob sentinels are read as literal patterns (`[*]`)."""
    text = _slashed(text)
    try:
        toks = shlex.split(text, posix=True)
    except ValueError:
        toks = _PATHISH.findall(text)
    head = _command_words(text)[0]
    excludes = _exclude_options_for(head)
    rg_globs = head == "rg"
    out, skip = [], False
    for raw in toks:
        if skip:
            skip = False
            continue
        tok = _TOKEN_WRAPPERS.sub("", raw.strip("`")).translate(_SENTINEL_LITERALS)
        name, eq, value = tok.partition("=")
        low = name.lower()
        if low in excludes:
            skip = not eq  # `--exclude X` 는 다음 토큰, `--exclude=X` 는 이 토큰 / next token or this one
            continue
        if rg_globs and low in _RG_GLOB_OPTIONS and eq and value.startswith("!"):
            continue  # `--glob=!x` 는 제외 / an excluding rg glob
        if tok.startswith("!"):
            continue  # 부정 글롭(rg -g '!x' 의 값) — 제외 / a negated glob excludes
        if tok and not tok.startswith("-"):
            out.append(tok.rstrip("/"))
        if eq and value:
            out.append(value.rstrip("/"))
    return out


# ── 따옴표 안 글자는 펼치지 않는다 (회고 원장 R-5) ─────────────────────────────────────────
# Bash 는 따옴표 안의 `*` · `?` · `[` 를 펼치지 않는다. 그 글자를 경로 글롭으로 보면 검색 정규식이 .env 를 집는
# 와일드카드로 읽혀 막혔다. 다만 인자를 스스로 펼치는 명령(find · git · tar …)이나 글자를 실행하는 명령이 그 단계거나
# 뒤 단계면 따옴표가 지켜 주지 못한다 — 그래서 펼치지도 실행하지도 않는 글자 처리 명령(`_QUOTED_LITERAL_HEADS`)으로만
# 끝까지 이어진 단계에서, 명령 전체의 따옴표를 Bash 규칙으로 믿을 수 있을 때만 그 글자를 글자 그대로 본다.
# 표지(사용자 영역 문자)로 바꿔 두면 세그먼트 · 단계 분할을 지나도 자리가 유지되고, 경로 후보(`_path_tokens`)만
# 그것을 글자 그대로의 패턴으로 읽는다 — 다른 판정(재귀 검색 · 환경 나열 …)은 원문을 본다.
# PowerShell 은 cmdlet 이 따옴표 안 와일드카드도 펼치므로 적용하지 않는다.
# Quoted glob characters are literal in Bash. They are read literally only in pipeline stages that, to the
# end of the pipeline, are text tools which neither expand nor execute their arguments, and only when the
# whole command's quoting can be trusted. Sentinels keep their place through segment/stage splitting and
# only the path-candidate check reads them literally; every other check sees the original text.
# Never for PowerShell: cmdlets expand wildcards inside quotes.
_QUOTED_LITERAL_HEADS = frozenset({"grep", "egrep", "fgrep", "echo", "printf", "head", "tail", "wc", "cut",
                                   "tr", "uniq", "sort"})
# 그 명령에서 무언가를 실행하거나 변수에 넣는 옵션(앞부분) — 있으면 그 단계는 글자 그대로 보지 않는다.
# Option prefixes that run something or assign a variable; a stage with one is not read literally.
_QUOTED_LITERAL_UNSAFE_OPTIONS = {"sort": ("--co",), "printf": ("-v",)}
# 따옴표 판정을 믿지 않는 꼴 — 치환 · 매개변수 전개 · ANSI-C/로캘 따옴표 · 히어독(주석 · 묶음은 훑으며 본다).
# Constructs that make the quote reading untrustworthy (comments and grouping are caught while scanning).
_QUOTE_SCAN_UNTRUSTED = re.compile(r"\$[('{\"]|`|[<>]\(|<<")
_SCAN_OPERATORS = ("&>>", "&>", "&&", "||", "|&", ">>", ">|", ">&", "<&", "<>", ";", "&", "|", "<", ">", "\n")
_SCAN_SEPARATORS = frozenset({";", "&", "&&", "||", "\n"})
_SCAN_PIPES = frozenset({"|", "|&"})
_SCAN_OUTPUTS = frozenset({">", ">>", ">|", "&>", "&>>", "<>", ">&"})
_GLOB_SENTINELS = {"*": "", "?": "", "[": ""}
_SENTINEL_LITERALS = str.maketrans({"": "[*]", "": "[?]", "": "[[]"})


def _scan_bash(command):
    """Bash 따옴표 규칙으로 낱말 · 연산자를 나눈다 — 낱말은 [(자리, 글자, 따옴표 안?)], 연산자는 문자열.
    믿을 수 없는 꼴(치환 · 히어독 · 주석 · 괄호 · 중괄호 · 닫히지 않은 따옴표)이면 None. 따옴표 밖 백슬래시가
    이스케이프한 글자는 따옴표 안으로 치지 않는다(예전 판정 그대로 — 막는 쪽).
    Words as [(index, char, quoted)] and operator strings; None when the quoting cannot be trusted.
    A backslash-escaped character outside quotes is not counted as quoted (unchanged, fail closed)."""
    if _QUOTE_SCAN_UNTRUSTED.search(command):
        return None
    items, word, started, quote, i = [], [], False, None, 0
    while i < len(command):
        ch = command[i]
        if quote == "'" or (quote == '"' and ch == '"'):
            if ch == quote:
                quote = None
            else:
                word.append((i, ch, True))
            i += 1
            continue
        if quote == '"':
            if ch == "\\" and command[i + 1:i + 2] in ("$", "`", '"', "\\", "\n"):
                i += 1
            word.append((i, command[i], True))
            i += 1
            continue
        if ch in "'\"":
            quote, started = ch, True
            i += 1
            continue
        if ch == "\\":
            if command[i + 1:i + 2] not in ("", "\n"):
                word.append((i + 1, command[i + 1], False))
                started = True
            i += 2
            continue
        if ch in "#(){}":
            return None
        op = next((o for o in _SCAN_OPERATORS if command.startswith(o, i)), None)
        if op or ch in " \t\r":
            # `2>` 의 2 는 리디렉션의 일부다 / the fd number of `2>` belongs to the redirection
            fd_number = op and op[0] in "<>" and word and all(c.isdigit() and not q for _, c, q in word)
            if started and not fd_number:
                items.append(word)
            word, started = [], False
            if op:
                items.append(op)
            i += len(op) if op else 1
            continue
        word.append((i, ch, False))
        started = True
        i += 1
    if quote:
        return None
    if started:
        items.append(word)
    return items


def _scan_pipelines(items):
    """낱말 · 연산자 → 파이프라인 목록 — 단계 = {"words": 낱말들, "outputs": [(연산자, 대상 낱말)]}.
    대상 없는 리디렉션이면 None. Pipelines of stages with their words and output redirections."""
    pipelines, stages, stage, pending = [], [], {"words": [], "outputs": []}, None
    for item in items:
        if isinstance(item, list):
            if pending in _SCAN_OUTPUTS:
                stage["outputs"].append((pending, item))
            elif pending is None:
                stage["words"].append(item)
            pending = None
            continue
        if pending is not None:
            return None
        if item in _SCAN_SEPARATORS or item in _SCAN_PIPES:
            stages.append(stage)
            stage = {"words": [], "outputs": []}
            if item in _SCAN_SEPARATORS:
                pipelines.append(stages)
                stages = []
        else:
            pending = item
    if pending is not None:
        return None
    stages.append(stage)
    pipelines.append(stages)
    return pipelines


def _word_text(word):
    return "".join(ch for _, ch, _ in word)


def _literal_stage(stage):
    """이 단계의 따옴표 안 글자를 글자 그대로 볼 수 있는가 — 앞쪽 대입 뒤 명령이 글자 처리 명령이고, 무언가를
    실행하는 옵션이 없고, 파일로 내보내지 않는다(`/dev/null` · 파일 기술자 복제는 된다).
    Can this stage's quoted characters be read literally? A text tool after any leading assignments, no
    option that runs something, and no output to a file (/dev/null and fd duplication are fine)."""
    words = stage["words"]
    k = 0
    while k < len(words) and _ASSIGNMENT.fullmatch(_word_text(words[k])) \
            and not any(q for _, _, q in words[k][:_word_text(words[k]).index("=") + 1]):
        k += 1
    if k >= len(words) or any(q or ch in "*?[" for _, ch, q in words[k]):
        return False
    head = _command_name(_word_text(words[k]))
    if head not in _QUOTED_LITERAL_HEADS:
        return False
    unsafe = _QUOTED_LITERAL_UNSAFE_OPTIONS.get(head)
    if unsafe and any(_word_text(w).startswith(unsafe) for w in words[k + 1:]):
        return False
    for op, target in stage["outputs"]:
        text = _word_text(target)
        if not (text == "/dev/null" or (op == ">&" and re.fullmatch(r"\d+|-", text))):
            return False
    return True


def _mark_quoted_literals(command):
    """Bash 에서 글자 처리 단계의 따옴표 안 글롭 글자를 표지로 바꾼 명령 — 바꿀 곳이 없거나 믿을 수 없으면 원문.
    The command with quoted glob characters of literal-safe Bash stages replaced by sentinels; else unchanged."""
    if _CONTEXT["shell"] != "bash":
        return command
    items = _scan_bash(command)
    pipelines = _scan_pipelines(items) if items is not None else None
    if not pipelines:
        return command
    chars = list(command)
    for stages in pipelines:
        literal = [_literal_stage(stage) for stage in stages]
        for k, stage in enumerate(stages):
            if all(literal[k:]):  # 이 단계부터 파이프라인 끝까지 / this stage through the end of the pipeline
                for word in stage["words"]:
                    for index, ch, quoted in word:
                        if quoted and ch in _GLOB_SENTINELS:
                            chars[index] = _GLOB_SENTINELS[ch]
    return "".join(chars)


def _has_dotenv_path(text):
    """.env 꼴 경로가 있는가(템플릿 제외 · 와일드카드는 실제 항목) / Is there a .env-like path?"""
    for tok in _path_tokens(text):
        comp = tok.rsplit("/", 1)[-1].lower()
        if any(ch in comp for ch in "*?["):
            matches = None if _unresolvable(tok) else _glob_matches(tok)
            if matches is None:
                if _name_glob_may_hit_dotenv(comp):  # 못 읽으면 이름으로 — 막는 쪽 / unreadable: by name
                    return True
            elif any(_is_dotenv_name(os.path.basename(m).lower()) for m in matches):
                return True
        elif _is_dotenv_name(comp):
            return True
    return False


def _mentions_dotenv(stage):
    """쓰기 대상을 뺀 나머지에 .env 꼴 경로가 있는가 — 따옴표 밖 입력 리디렉션이 읽는 낱말(붙여 쓴 `cat<.env.local` 도)을
    더해 본다(낱말 나누기는 `<` 에서 끊지 않는다 · AntiGravity 2 · 3차).
    A .env-like path outside write targets, plus what unquoted input redirections read (attached ones too)."""
    return (_has_dotenv_path(_REDIRECT_TARGET.sub(" ", stage))
            or any(_has_dotenv_path(target) for target in _input_redirect_targets(stage)))


def _pattern_positions(args, valued):
    """검색 인자에서 «패턴» 자리 — 다음 낱말로 받은 -e/--regexp 의 값, 그것이 없으면 첫 위치 인자. -f(패턴 파일)의
    값은 파일이라 넣지 않는다. 짧은 옵션 묶음은 `_short_flags` 와 같은 규칙으로 읽는다(`-exclude` = `-e xclude` —
    패턴이 낱말 안에 있으니 뒤의 위치 인자는 전부 대상이다).
    Pattern slots in search args: -e/--regexp values given as the next word, else the first positional."""
    picks, positional, given, take, options_done = [], [], False, None, False
    for i, w in enumerate(args):
        if take is not None:
            if take == "e":
                picks.append(i)
            take = None
            continue
        if options_done or w == "--":
            # `--` 뒤는 전부 위치 인자다 — `grep -- -e .env` 의 `-e` 는 패턴 글자, `.env` 는 읽힐 파일이다.
            # Everything after `--` is positional (`grep -- -e .env` reads .env with the pattern "-e").
            if options_done:
                positional.append(i)
            options_done = True
            continue
        if w.startswith("--"):
            opt = w.split("=", 1)[0]
            # GNU 는 겹치지 않는 앞부분도 받는다(`--reg` = `--regexp`) — 그 꼴도 패턴을 준 것으로 본다(커밋 보안 검토 HIGH).
            # GNU accepts unambiguous prefixes (--reg = --regexp); treat them as giving the pattern.
            full = next((f for f in ("--regexp", "--file") if len(opt) >= 5 and f.startswith(opt)), None)
            if full:
                given = True
                take = ("e" if full == "--regexp" else "value") if "=" not in w else None
                continue
            if opt not in _KNOWN_SEARCH_LONGS:
                return []  # 모르는 긴 옵션 — 어느 낱말이 패턴인지 모른다: 아무것도 빼지 않는다 / unknown: drop nothing
            if "=" not in w and w in _GREP_VALUE_OPTIONS:
                take = "value"
            continue
        if w.startswith("-") and w != "-":
            for k, ch in enumerate(w[1:], 1):
                if ch in valued:
                    given = given or ch in "ef"
                    take = ch if k == len(w) - 1 else None
                    break
            continue
        positional.append(i)
    return picks if given else picks + positional[:1]


# 패턴을 뺀 뒤 다시 이어 붙여도 같은 낱말로 읽히는 인자 — 공백 · 따옴표 · 리디렉션 · 파이프 · 묶음 · 치환 · 주석 글자가 없다.
# An argument that reads back as the same word after re-joining: no whitespace, quote, redirect, pipe, grouping,
# substitution or comment character.
_REJOINABLE_ARG = re.compile(r"[^\s'\"<>|;&()$`{}#]+")


def _without_search_pattern(stage):
    """검색 명령이면 패턴 인자를 뺀 낱말로 — 패턴은 경로가 아니다(`grep "\\.env" 문서` 는 .env 를 읽지 않는다 ·
    원장 #1917 P1-5). 🔴 확신할 때만 뺀다 — 그 밖은 단계를 그대로 돌려줘 원래 판정(막는 쪽)을 받는다(AntiGravity 교차 검토):
    - 검색 명령이 명령 자리(첫 낱말 · `git grep`)에 있을 때만 — `git diff rg .env` 의 rg 는 인자다.
    - 입력 리디렉션이 없을 때만 — `grep <.env KEY` 의 `<.env` 는 패턴 자리에 선 읽기다. 출력 리디렉션은 먼저 걷는다.
    - 빈 낱말을 버리지 않는다 — `grep "" .env` 의 패턴은 빈 낱말이고, 버리면 .env 가 패턴 자리로 밀린다.
    - 남는 낱말이 다시 이어 붙여도 같은 낱말일 때만 — `--label "x >"` 를 풀어 쓰면 `> .env` 가 쓰기로 읽힌다.
    - 따옴표를 믿을 수 있을 때만(`\\"` · 백틱 · `#` 이 없다) — 따옴표 짝을 잘못 읽으면 .env 가 «패턴» 안으로 삼켜진다.
    findstr 은 제 문법이라 그대로 둔다. Drop the pattern argument of a search only when certain; otherwise return
    the stage unchanged so the original (fail-closed) verdict applies."""
    text = _OUTPUT_REDIRECT.sub(" ", stage)
    if not _quotes_trustworthy(text) or _unquoted_lt(text):
        return stage
    try:
        words = shlex.split(_slashed(text), posix=True)
    except ValueError:
        return stage
    name = _command_name(words[0]) if words else ""
    if name in _SEARCH_COMMANDS and name != "findstr":
        head, args = words[:1], words[1:]
    elif name == "git" and len(words) > 1 and words[1] == "grep":
        name, head, args = "git-grep", words[:2], words[2:]
    else:
        return stage
    drop = set(_pattern_positions(args, _RG_VALUED_SHORTS if name == "rg" else _GREP_VALUED_SHORTS))
    kept = [*head, *(w for i, w in enumerate(args) if i not in drop)]
    if not drop or not all(_REJOINABLE_ARG.fullmatch(w) for w in kept):
        return stage
    return " ".join(kept)


def _reads_dotenv(stage):
    """단계가 .env 내용을 출력할 수 있는가 — 검색 패턴은 경로로 보지 않는다 / Can this stage print .env contents?"""
    if not _mentions_dotenv(_without_search_pattern(stage)) or _count_only_grep(stage):
        return False
    head, words = _command_words(_REDIRECT_TARGET.sub(" ", stage))
    if head in _DOTENV_SAFE_HEADS:
        return False
    # 내용을 안 내는 git 하위 명령도 stdin 으로 받은 줄은 낸다 — `show-ref --exclude-existing` 은 ref 가 아닌 줄을,
    # `check-ignore --stdin -n -v` 는 모든 줄을 찍는다(Grok · AntiGravity 교차 검토). 입력 리디렉션이 있으면 면제하지 않는다.
    # Even content-free git subcommands echo lines read from stdin; no exemption with an input redirect.
    return not (head == "git" and words and words[0].lower() in _GIT_SAFE_SUBCOMMANDS and "<" not in stage)


# ── 재귀 검색 · 나열 파이프라인이 .env 를 읽는가 (회고 원장 R-4) ─────────────────────────────
# 🔴 grep -r · findstr /s · Get-ChildItem | Select-String 은 .gitignore 를 보지 않아 .env 의 일치 줄을 값째 낸다.
#    rg 는 숨김 · .gitignore 파일을 기본으로 건너뛰지만, 무시 해제(-u)는 숨김 아닌 .env 꼴(prod.env)을, 숨김까지
#    풀면(-uu) 전부를, 포함 글롭(-g X)은 그 규칙들을 넘어 맞는 파일을 읽는다. 명령 글자로는 «그 폴더에 어떤 .env 꼴
#    파일이 있는가» 를 알 수 없어 파일 시스템을 본다 — 실제로 있는 파일마다 그 검색의 포함 · 제외 규칙에 대 본다
#    (고정 표본 이름에 대 보면 prod.env 를 놓친다, 14차). 큰 폴더는 2초 · 2만 파일에서, 못 읽는 하위 폴더는 바로
#    멈추고 «있다» 로 본다(막는 쪽). 개수만 · 파일 이름만 내는 검색은 통과.
# Recursive searches ignore .gitignore; the hook enumerates the .env-like files really on disk and checks each
# against the search's own include/exclude rules (bounded, fail closed).
_GREP_VALUE_OPTIONS = frozenset({"-e", "-f", "-m", "-A", "-B", "-C", "-d", "-D", "--regexp", "--file",
                                 "--max-count", "--context", "--after-context", "--before-context",
                                 "--exclude", "--include", "--exclude-dir", "--label", "-g", "--glob",
                                 "--iglob", "-t", "-T", "--type", "--type-not", "-j", "--threads"})
# rg 만의 값 옵션(rg 도움말) — grep 의 `-E` 는 플래그지만 rg 의 `-E` 는 인코딩 값을 받는다. `-r ""`(바꿀 글자)의 빈 값이
# 검색 대상으로 읽혔다(교차 검토 4차). rg-only options that take a value; rg's -E takes an encoding, grep's -E does not.
_RG_VALUE_OPTIONS = _GREP_VALUE_OPTIONS | {"-r", "--replace", "-E", "--encoding", "-M", "--max-columns", "--max-depth",
                                           "--max-filesize", "--path-separator", "--pre", "--pre-glob", "--sort",
                                           "--sortr", "--colors", "--engine", "--type-add", "--ignore-file"}
# 패턴 자리를 셀 때 아는 긴 옵션 — 이 밖의 긴 옵션이 있으면 패턴을 빼지 않는다(값을 받는지 모른다).
# Long options known when locating the pattern; any other long option means nothing is dropped.
_KNOWN_SEARCH_LONGS = _GREP_VALUE_OPTIONS | {
    "--count", "--ignore-case", "--no-ignore-case", "--line-number", "--recursive", "--dereference-recursive",
    "--extended-regexp", "--fixed-strings", "--perl-regexp", "--basic-regexp", "--word-regexp", "--line-regexp",
    "--files-with-matches", "--files-without-match", "--only-matching", "--quiet", "--silent", "--no-messages",
    "--with-filename", "--no-filename", "--invert-match", "--color", "--colour", "--null", "--null-data", "--text",
    "--binary-files", "--hidden", "--no-ignore", "--files", "--smart-case", "--case-sensitive", "--no-heading",
    "--heading", "--column", "--count-matches", "--max-depth", "--follow", "--untracked", "--no-index", "--cached",
    "--exclude-standard", "--no-exclude-standard", "--and", "--or", "--not", "--all-match", "--name-only",
    "--full-name"}
_WALK_SKIP = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
                        ".pytest_cache", ".ruff_cache", ".tox"})
# 검색 명령 — 단계의 첫 낱말이 아니어도 찾는다(env · timeout · sudo · if · do · ! 같은 접두 뒤, 14차 반영 중 실측).
# Search commands, found anywhere in the stage (past env, timeout, sudo, if, do, ! and other prefixes).
_SEARCH_COMMANDS = frozenset({"grep", "egrep", "fgrep", "rgrep", "rg", "findstr"})


def _plain_words(text, keep_slots=False):
    """shlex 낱말 — 백슬래시는 / 로(Bash 의 따옴표 앞 이스케이프는 남긴다), 괄호 · 치환 껍데기는 벗기고 껍데기뿐이던
    낱말은 뺀다. keep_slots 면 앞뒤 끝(묶음 `( … )` · `{ …`)의 것만 빼고 가운데 것은 빈 낱말로 남긴다 — 검색 인자의
    자리를 셀 때 `""` · `"{}"` · 따옴표 없는 `{}` 도 한 자리다(`grep -rn "{}" . 문서` 의 `.` 은 대상이다 · 교차 검토
    2 · 3차). 그 밖의 호출처(cd 추적 등)는 빈 낱말을 받지 않는다 — `cd $( … )` 의 빈 낱말이 «지금 폴더» 로 풀렸다(4차).
    shlex words with wrappers peeled and wrapper-only words dropped; keep_slots keeps the middle ones as empty
    words so a search argument slot is never lost. Other callers (cd tracking) never see empty words."""
    text = _slashed(text)
    try:
        toks = shlex.split(text, posix=True)
    except ValueError:
        toks = text.split()
    words = [_TOKEN_WRAPPERS.sub("", t.strip("`")) for t in toks]
    if not keep_slots:
        return [w for w in words if w]
    start, end = 0, len(words)
    while start < end and not words[start]:
        start += 1
    while end > start and not words[end - 1]:
        end -= 1
    return words[start:end]


def _command_name(word):
    """경로 · .exe 를 걷은 소문자 이름 / lower-cased base name without path or .exe."""
    name = word.rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _walk_dotenv(root, recursive):
    """폴더 아래 .env 꼴 파일의 상대 경로 조각들 — 너무 크거나 오래 걸리거나 못 읽은 하위 폴더가 있으면 None.
    recursive=False 면 바로 아래만 본다. Relative path parts of .env-like files under a folder; None when
    too big, too slow or partly unreadable. Only the top level when not recursive."""
    deadline, seen, found, errors = time.monotonic() + 2.0, 0, [], []
    for dirpath, dirnames, filenames in os.walk(root, onerror=errors.append):
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        prefix = () if rel == "." else tuple(rel.split("/"))
        dirnames[:] = [d for d in dirnames if d not in _WALK_SKIP] if recursive else []
        found.extend(prefix + (name,) for name in filenames if _is_dotenv_name(name.lower()))
        seen += len(filenames)
        if seen > 20000 or time.monotonic() > deadline:
            return None
    return None if errors else found


def _dotenv_files(target, recursive=True):
    """대상(파일 · 폴더 · 와일드카드) 아래 .env 꼴 파일의 상대 경로 조각들 — 작업 폴더 후보 전부에서. 셀 수 없으면
    None(막는 쪽): 셸만 아는 경로 · 모르는 작업 폴더 · 어느 후보에도 없는 대상 · 너무 큰 폴더.
    .env-like files under the target across every cwd candidate, or None when they cannot be enumerated."""
    # 빈 대상(`grep -rn K "" 문서` 의 `""`)은 «지금 폴더» 가 아니다 — 셈하지 않고 막는 쪽 / an empty target is not the cwd
    if not target or _unresolvable(target):
        return None
    if any(ch in target for ch in "*?["):
        matches = _glob_matches(target)
        if matches is None:
            return None
        found = []
        for match in matches:
            sub = _dotenv_files(match, recursive)
            if sub is None:
                return None
            found.extend(sub)
        return found
    if _cwd_unknown() and not os.path.isabs(os.path.expanduser(target)):
        return None
    roots = list(dict.fromkeys(os.path.normpath(r) for r in _resolve_all(target) if os.path.exists(r)))
    if not roots:
        return None  # 어느 후보에도 없는 대상 — 막는 쪽 / missing under every candidate: fail closed
    found = []
    for root in roots:
        if os.path.isdir(root):
            sub = _walk_dotenv(root, recursive)
            if sub is None:
                return None
            found.extend(sub)
        elif _is_dotenv_name(os.path.basename(root).lower()):
            found.append((os.path.basename(root),))
    return found


def _search_call(stage):
    """단계 안의 검색 명령 → (이름, 인자, 앞 낱말들). `git … grep` 은 git 의 하위 명령이라 «git-grep» 으로 낸다.
    The search command in a stage as (name, args, preceding words); `git … grep` is reported as git-grep."""
    words = _plain_words(stage, keep_slots=True)
    for k, word in enumerate(words):
        name = _command_name(word)
        if name not in _SEARCH_COMMANDS:
            continue
        before = [_command_name(w) for w in words[:k]]
        return ("git-grep" if "git" in before else name), words[k + 1:], words[:k]
    return None


def _search_targets(words, value_options=None):
    """패턴 다음의 위치 인자 = 검색 대상. -e · -f 로 패턴을 주면 첫 위치 인자부터 대상이다. value_options 는 값을
    받는 옵션(기본 grep · rg 공통 — rg 는 `_RG_VALUE_OPTIONS`).
    Positional arguments after the pattern; with -e/-f every positional argument is a target."""
    value_options = _GREP_VALUE_OPTIONS if value_options is None else value_options
    positional, skip, pattern_given = [], False, False
    for w in words:
        if skip:
            skip = False
        elif w in value_options:
            skip = True
            pattern_given = pattern_given or w in ("-e", "-f", "--regexp", "--file")
        elif w.startswith("-"):
            pattern_given = pattern_given or w.startswith(("--regexp=", "--file="))
        else:
            positional.append(w)
    return positional if pattern_given else positional[1:]


def _recurse_value(value):
    """grep 의 디렉터리 동작 값이 recurse 인가 — GNU 는 겹치지 않는 앞부분(rec)도 받는다.
    Is a grep directories action `recurse`? GNU accepts unambiguous prefixes (rec)."""
    return len(value) >= 3 and "recurse".startswith(value)


def _grep_is_recursive(name, args):
    """grep 계열이 재귀인가 — rgrep · -r/-R(붙여 쓴 꼴 포함) · --recursive · --dereference-recursive 와 그 줄임
    (GNU 는 겹치지 않는 앞부분을 받는다: --rec · --der, 13차) · -d recurse · --directories=recurse(--di 줄임).
    Is this grep recursive? Bundled short flags, GNU long-option abbreviations, -d/--directories recurse."""
    if name == "rgrep":
        return True
    for i, w in enumerate(args):
        nxt = args[i + 1] if i + 1 < len(args) else ""
        opt, eq, value = w.partition("=")
        if not w.startswith("--"):
            if re.match(r"-[A-Za-z]*[rR]", w) or (re.fullmatch(r"-[A-Za-z]*d", w) and _recurse_value(nxt)):
                return True
            continue
        if len(opt) >= 5 and ("--recursive".startswith(opt) or "--dereference-recursive".startswith(opt)):
            return True
        if len(opt) >= 4 and "--directories".startswith(opt) and _recurse_value(value if eq else nxt):
            return True
    return False


def _grep_filters(args):
    """grep 의 파일 거르개 [(종류, 글롭)] — 순서대로(마지막 일치가 이긴다) / grep file filters, in order."""
    filters, take = [], None
    for w in args:
        if take:
            filters.append((take, w))
            take = None
            continue
        opt, eq, value = w.partition("=")
        if opt in ("--include", "--exclude", "--exclude-dir"):
            if eq:
                filters.append((opt, value))
            else:
                take = opt
    return filters


def _grep_reads(parts, filters):
    """grep -r 이 그 파일을 읽는가 — --exclude-dir 는 폴더 이름, --include/--exclude 는 파일 이름에 대고 마지막 일치가
    이긴다. 아무것도 안 맞으면 첫 거르개가 --include 일 때만 건너뛴다(GNU 규칙). 포함은 대소문자 무시(넓게), 제외는
    구분(좁게) — 막는 쪽. Would grep -r read this file? GNU last-match-wins; with no match the file is skipped
    only when the first filter is --include. Includes match case-insensitively, excludes case-sensitively."""
    *dirs, name = parts
    if any(kind == "--exclude-dir" and fnmatch.fnmatchcase(d, glob) for kind, glob in filters for d in dirs):
        return False
    verdict = None
    for kind, glob in filters:
        if kind == "--include" and fnmatch.fnmatchcase(name.lower(), glob.lower()):
            verdict = True
        elif kind == "--exclude" and fnmatch.fnmatchcase(name, glob):
            verdict = False
    if verdict is not None:
        return verdict
    first = next((kind for kind, _glob in filters if kind != "--exclude-dir"), None)
    return first != "--include"


def _rg_globs(args):
    """rg 의 -g/--glob/--iglob 값들(`!` 는 제외) / rg glob values (`!` excludes)."""
    globs, take = [], False
    for w in args:
        if take:
            globs.append(w)
            take = False
            continue
        opt, eq, value = w.partition("=")
        if opt in _RG_GLOB_OPTIONS:
            if eq:
                globs.append(value)
            else:
                take = True
    return globs


def _include_glob_hits(glob, parts):
    """rg 포함 글롭이 맞는가 — 넓게: 대소문자 무시, `/` 가 있으면 상대 경로 전체(앞의 `**/` 는 없어도 맞음), 없으면
    마지막 이름. Does an rg include glob match? Broadly: case-insensitive, whole relative path when it has `/`."""
    glob = glob.lower().lstrip("/")
    rel = "/".join(parts).lower()
    if "/" not in glob:
        return fnmatch.fnmatchcase(parts[-1].lower(), glob)
    return fnmatch.fnmatchcase(rel, glob) or (glob.startswith("**/") and fnmatch.fnmatchcase(rel, glob[3:]))


def _rg_reads(parts, globs, no_ignore, hidden, ignored=frozenset()):
    """rg 가 그 파일을 읽는가 — 포함 글롭이 맞으면 무시 · 숨김 규칙을 넘어 읽고(재정의가 가장 먼저), 포함 글롭이
    있는데 안 맞으면 안 읽는다. 제외 글롭이 이름에 맞으면 안 읽는다. 그 밖은 숨김(점으로 시작)이면 숨김 포함일 때만,
    git 이 무시하는 파일(`ignored` — 호출자가 git 에 물어 넘긴다)이면 무시 해제일 때만 읽는다. 숨김 폴더는 숨김 포함이거나
    그 폴더를 집는 포함 글롭이 있을 때만 내려간다. .env 꼴이 .gitignore 에 있다고 가정하지 않는다 — 무시되지 않은
    prod.env 는 rg 기본값도 읽는다(Grok 교차 검토 반례 `rg -e .env -e KEY .`).
    Would rg read this file? Include globs override ignore and hidden rules; otherwise hidden files need --hidden
    and files git ignores (as git reports them) need --no-ignore."""
    *dirs, name = parts
    includes = [g for g in globs if not g.startswith("!")]
    excludes = [g[1:] for g in globs if g.startswith("!")]
    if not hidden and any(d.startswith(".") and not any(_include_glob_hits(g, [d]) for g in includes)
                          for d in dirs):
        return False
    if any(_include_glob_hits(g, parts) for g in includes):
        return True
    if includes:
        return False
    if any("/" not in g and fnmatch.fnmatchcase(name, g) for g in excludes):
        return False
    return (hidden or not name.startswith(".")) and (no_ignore or tuple(parts) not in ignored)


# 대상 폴더 바로 아래의 있을 리 없는 이름 — 이것까지 무시되면 폴더 자체가 무시된 것이다 / a name no folder holds
_GIT_IGNORE_SENTINEL = "scamanager-hook-ignore-probe-3f9c"


def _git_ignored_parts(target, hits):
    """대상 폴더 아래 .env 꼴 파일 가운데 git 이 무시하는 것 — `git check-ignore --no-index`(추적 여부와 상관없이 규칙만,
    rg 와 같다)로 묻는다. 그 파일이 있는 작업 폴더 후보 모두에서 무시될 때만 무시로 본다. git 이 없거나 · 저장소 밖이거나
    (rg 도 저장소 밖에서는 .gitignore 를 보지 않는다) · 2초를 넘기거나 · 파일 대상(rg 는 이름을 준 파일을 무시 규칙과
    상관없이 읽는다)이면 무시 안 됨 — 막는 쪽.
    Hits git ignores in every cwd candidate holding them; anything unknown counts as not ignored (fail closed)."""
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    checked, unignored = set(), set()
    for root in dict.fromkeys(os.path.normpath(r) for r in _resolve_all(target) if os.path.isdir(r)):
        present = ["/".join(parts) for parts in hits if os.path.exists(os.path.join(root, *parts))]
        if not present:
            continue
        try:
            done = subprocess.run(["git", "-C", root, "check-ignore", "--no-index", "-z", "--stdin"],
                                  input="".join(p + "\0" for p in [*present, _GIT_IGNORE_SENTINEL]).encode("utf-8"),
                                  env=env, capture_output=True, timeout=2, check=False)
            listed = set(done.stdout.decode("utf-8", "replace").split("\0")) if done.returncode in (0, 1) else set()
        except (OSError, subprocess.SubprocessError):
            listed = set()
        # 없는 이름(표지)까지 무시되면 대상 폴더 자체(또는 그 위)가 무시된 것이다 — rg 는 이름을 준 폴더 안을 그래도
        # 읽으므로 git 의 답을 믿지 않는다(AntiGravity 2차 — `rg KEY secrets` 에 `.gitignore` 의 `secrets/`).
        # If even a made-up name is ignored, the root itself is ignored; rg still searches a folder it is given.
        if _GIT_IGNORE_SENTINEL in listed:
            listed = set()
        checked.update(present)
        unignored.update(p for p in present if p not in listed)
    return frozenset(parts for parts in hits if "/".join(parts) in checked - unignored)


# 값을 받는 짧은 옵션 글자 — 묶음에서 이 글자 뒤는 그 값이다(grep 도움말 · rg 도움말).
# Short options that take a value; in a bundle, everything after such a letter is its value.
_GREP_VALUED_SHORTS = "efmABCdD"
_RG_VALUED_SHORTS = "efgtTjmABCrEMd"


def _short_flags(words, valued):
    """짧은 옵션 묶음의 플래그 글자 — 값을 받는 글자를 만나면 묶음의 나머지(없으면 다음 낱말)는 그 값이다.
    `-exclude` 는 `-e xclude` 라 c · l 이 플래그가 아니다(14차 반영 중 실측 — «개수만» 으로 오판했다).
    Flag letters of short-option bundles; after a value-taking letter the rest (or the next word) is its value."""
    flags, skip = set(), False
    for w in words:
        if skip:
            skip = False
            continue
        if w.startswith("--"):
            skip = "=" not in w and w in _GREP_VALUE_OPTIONS
            continue
        if not w.startswith("-") or w == "-":
            continue
        for i, ch in enumerate(w[1:], 1):
            flags.add(ch)
            if ch in valued:
                skip = i == len(w) - 1
                break
    return flags


def _count_only_words(head, words):
    """검색이 개수 · 존재 · 파일 이름만 내는가 — 플래그를 토큰으로 읽는다(대소문자 구분).
    문맥 · 일치 부분 출력 플래그(-A · -B · -C · -o 등)가 하나라도 있으면 아니다(보안 리뷰 지적 — 첫 판은
    대소문자를 무시해 `-C` 문맥 출력을 «개수만» 으로 읽었다). rg 의 -L 은 «링크 따라가기» 라 제외.
    Count/existence/filename-only search, flags read as tokens (case-sensitive); any context or
    match-output flag disqualifies it. rg's -L means follow links."""
    if head not in _SEARCH_COMMANDS and head != "git-grep":
        return False
    shorts = _short_flags(words, _RG_VALUED_SHORTS if head == "rg" else _GREP_VALUED_SHORTS)
    longs = {w.split("=", 1)[0] for w in words if w.startswith("--")}
    if any(ch in "ABCo" for ch in shorts) or longs & {
            "--after-context", "--before-context", "--context", "--only-matching",
            "--passthru", "--passthrough", "--json", "--replace", "--vimgrep"}:
        return False
    quiet = "cql" if head == "rg" else "cqlL"
    return any(ch in quiet for ch in shorts) or bool(longs & {
        "--count", "--count-matches", "--quiet", "--silent", "--files-with-matches", "--files-without-match",
        "--name-only", "--files"})


def _count_only_grep(stage):
    """단계의 grep 계열이 개수 · 존재 · 파일 이름만 내는가 / count/filename-only grep at the command position."""
    head, words = _command_words(stage)
    return _count_only_words(head, words)


def _findstr_reads_dotenv(args):
    """findstr /s 는 «파일 패턴» 을 그 폴더 아래 전부에 적용한다 — 실제 .env 꼴 파일 이름이 패턴에 맞으면 읽기.
    Windows 의 `*` 는 점 파일도 집는다. /m(파일 이름만)은 통과. 스위치를 붙여 써도(`/si`) 재귀다.
    findstr /s applies its file patterns recursively; /m (file names only) passes."""
    switches = [w for w in args if re.fullmatch(r"/[a-z]+(?::.*)?", w, re.IGNORECASE)]
    if not any(re.fullmatch(r"/[a-z]*s[a-z]*", w, re.IGNORECASE) for w in switches):
        return False
    if any(re.fullmatch(r"/[a-z]*m[a-z]*", w, re.IGNORECASE) for w in switches):
        return False
    pattern_given = any(w.lower().startswith(("/c:", "/g:")) for w in switches)
    rest = [w for w in args if w not in switches]
    for pat in (rest if pattern_given else rest[1:]) or ["*"]:
        folder, _, glob = pat.rpartition("/")
        files = _dotenv_files(folder or ".")
        if files is None or any(fnmatch.fnmatchcase(parts[-1].lower(), glob.lower()) for parts in files):
            return True
    return False


def _reads_any(_parts):
    """거르개 없이 다 읽는다(.gitignore 를 끈 git grep) / reads everything (git grep with .gitignore off)."""
    return True


def _recursive_search_reads_dotenv(stage):
    """재귀 검색이 실제로 읽을 .env 꼴 파일이 검색 대상 아래에 있는가(작업 폴더 후보 전부에서).
    출력 리디렉션(`2>/dev/null` · `2>&1` · `> 파일`)은 검색 대상이 아니라 먼저 걷는다 — 남기면 «없는 대상» 으로
    읽혀 막는다(원장 #1917 P1-5).
    Would a recursive search read a .env-like file under its targets (across every cwd candidate)?"""
    call = _search_call(_OUTPUT_REDIRECT.sub(" ", stage))
    if call is None:
        return False
    name, args, before = call
    if name == "findstr":
        return _findstr_reads_dotenv(args)
    ask_git = False  # rg 가 git 의 무시 규칙을 따르는가 — rg 갈래가 정한다 / does rg follow git's ignore rules here?
    if name == "git-grep":
        # git grep 은 기본으로 추적 파일만 본다. --no-index(--exclude-standard 없이)와 --no-exclude-standard 는
        # .gitignore 를 무시한다(git 문서). git grep searches tracked files unless .gitignore is switched off.
        lows = [w.lower() for w in args]
        if not ("--no-exclude-standard" in lows or ("--no-index" in lows and "--exclude-standard" not in lows)):
            return False
        reads = _reads_any
    elif name == "rg":
        u_count = (sum(w.count("u") for w in args if re.match(r"-[A-Za-z.]", w))
                   + sum(w == "--unrestricted" for w in args))
        no_ignore = u_count >= 1 or any(w.startswith("--no-ignore") for w in args)
        hidden = u_count >= 2 or "--hidden" in args or any(re.match(r"-[A-Za-z]*\.", w) for w in args)
        reads = functools.partial(_rg_reads, globs=_rg_globs(args), no_ignore=no_ignore, hidden=hidden)
        ask_git = not no_ignore
    else:
        if not _grep_is_recursive(name, args):
            return False
        reads = functools.partial(_grep_reads, filters=_grep_filters(args))
    if _count_only_words(name, args):
        return False
    # 앞 낱말이 작업 폴더를 바꾸면(`env -C 폴더` · `--chdir`) 그 폴더를 모른다 — 막는 쪽.
    # A prefix that changes directory (env -C / --chdir) leaves the cwd unknown: fail closed.
    if any(w == "-C" or w.startswith("--chdir") for w in before):
        return True
    for target in _search_targets(args, _RG_VALUE_OPTIONS if name == "rg" else None) or ["."]:
        files = _dotenv_files(target)
        if files is None:
            return True
        hits = [parts for parts in files if reads(parts)]
        # rg 는 git 이 무시하는 파일을 건너뛴다 — 가정하지 않고 git 에 물어, 무시되는 것만 뺀다(무시 해제면 묻지 않는다).
        # rg skips what git ignores: ask git and drop only the ignored hits (not needed with --no-ignore).
        if hits and ask_git:
            ignored = _git_ignored_parts(target, hits)
            hits = [parts for parts in hits if reads(parts, ignored=ignored)]
        if hits:
            return True
    return False


_PS_LISTERS = frozenset({"get-childitem", "gci", "ls", "dir"})
_PS_READERS = frozenset({"select-string", "sls", "get-content", "gc", "cat", "type"})
# 나열한 파일 객체를 받아도 내용을 읽지 않는 단계 — 속성만 고르거나 세거나 줄 세운다. 읽기 cmdlet 을 열거하면
# 스크립트 블록 안의 .NET 읽기를 놓친다(14차) — 그래서 안전한 단계를 열거하고 나머지를 읽기로 본다.
# Stages that take file objects without reading content; everything else after a listing counts as a read.
_PS_PROPERTY_STAGES = frozenset({"select-object", "select", "measure-object", "measure", "sort-object", "sort",
                                 "format-table", "ft", "format-list", "fl", "format-wide", "fw", "where-object",
                                 "where", "?", "group-object", "group", "out-null", "out-host", "out-string"})
_PS_DOTNET_READ = re.compile(r"\[(?:system\.)?io\.file\]|readall|opentext|openread|streamreader", re.IGNORECASE)


def _ps_stage_reads_nothing(stage):
    """나열 뒤 단계가 파일 내용을 읽지 않는가 — 속성 단계이고 안에 읽기 명령 · .NET 읽기가 없을 때만.
    Does a stage after a listing leave file contents alone?"""
    head, _words = _command_words(stage)
    if head not in _PS_PROPERTY_STAGES or _PS_DOTNET_READ.search(stage):
        return False
    return not any(tok.strip("{}()$;") in _PS_READERS for tok in stage.lower().split())


def _ps_listing_params(words):
    """Get-ChildItem 매개변수 → (대상, 포함 글롭, 제외 글롭, 재귀인가). 매개변수 이름은 앞부분만 써도 된다(`-Rec`).
    -Depth 도 재귀로 본다(막는 쪽). Get-ChildItem parameters; unique name prefixes count, -Depth recurses."""
    targets, incl, excl, take, recurse = [], [], [], None, False
    for w in words:
        low = w.lower()
        if take == "target":
            targets.extend(p for p in w.split(",") if p)
        elif take in ("incl", "excl"):
            (incl if take == "incl" else excl).extend(g for g in low.split(",") if g)
        if take:
            take = None
        elif low in ("-path", "-literalpath"):
            take = "target"
        elif low in ("-filter", "-include"):
            take = "incl"
        elif low == "-exclude":
            take = "excl"
        elif low == "-r" or (len(low) >= 3 and "-recurse".startswith(low)):
            recurse = True
        elif len(low) >= 3 and "-depth".startswith(low):
            recurse, take = True, "skip"
        elif low == "-attributes":
            take = "skip"
        elif not w.startswith("-"):
            targets.append(w)
    return targets, incl, excl, recurse


def _listing_pipeline_reads_dotenv(stages):
    """PowerShell `Get-ChildItem [-Recurse] [경로] | …` — 나열한 파일 객체를 뒤 단계가 읽는가. 뒤 단계가 모두 속성
    단계가 아니면 읽기다(`% { [IO.File]::ReadAllText($_) }` 도). 재귀가 아니어도 나열한 폴더 바로 아래의 .env 는
    읽힌다(`Get-ChildItem | Select-String KEY`, 14차 반영 중 실측). Bash 의 ls 는 이름 글자만 내보내 대상 아님.
    In PowerShell, listed file objects count as read unless every later stage is property-only; a
    non-recursive listing still exposes the .env right under the folder. Bash ls emits names only."""
    if _CONTEXT["shell"] != "powershell":
        return False
    for i, stage in enumerate(stages[:-1]):
        head, words = _command_words(stage.replace("\\", "/"))
        if head not in _PS_LISTERS or all(_ps_stage_reads_nothing(s) for s in stages[i + 1:]):
            continue
        targets, incl, excl, recurse = _ps_listing_params(words)
        for target in targets or ["."]:
            files = _dotenv_files(target, recursive=recurse)
            if files is None:
                return True
            for parts in files:
                low = parts[-1].lower()
                if (not incl or any(fnmatch.fnmatchcase(low, g) for g in incl)) \
                        and not any(fnmatch.fnmatchcase(low, g) for g in excl):
                    return True
    return False


# ── find 가 찾은 파일을 읽게 넘기는가 (회고 원장 R-3) ──────────────────────────────────────
# 경로 판정은 낱말을 Bash 점 규칙 · 그 폴더로 대 본다. find 의 이름 패턴은 그와 달리 `*` 가 점 파일도 집고 find 는 아래
# 폴더까지 내려가므로 따로 본다 — find 가 찾은 파일을 실행 술어로 넘기거나 이름만 다루는 명령이 아닌 뒤 단계로 넘길 때,
# 시작 경로 아래의 실제 .env 꼴 파일에 find 의 패턴을 find 처럼 대 본다. 이름만 내보내는 find 는 대상이 아니다(ls 처럼
# 이름 글자뿐).
# find's `*` matches dot-files and find descends; when find hands its matches to a command (-exec …) or to a
# later stage that is not name-only, match its patterns the way find does against the real .env-like files.
_FIND_PATTERN_PRIMARIES = frozenset({"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename"})
# 정규식 시험은 전체 경로에 대 본다(파이썬 re 로 — emacs 와 뜻이 갈리는 글자가 있으면 막는 쪽).
# 링크 대상 시험은 대 보지 않는다 — 있으면 전부 고른다고 본다(막는 쪽).
# Regex tests are matched against the whole path; link-target tests are not modelled (select everything).
_FIND_REGEX_PRIMARIES = frozenset({"-regex", "-iregex"})
_FIND_UNMODELLED_TESTS = frozenset({"-lname", "-ilname"})
_FIND_RUN_PRIMARIES = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
# 받은 이름을 글자로만 다루는 뒤 단계 — 닫힌 허용 목록이다. 목록 밖(xargs · 반복문 · 처음 보는 명령)은 읽기로 본다.
# Later stages that treat the names as text only; a closed allowlist — anything else counts as a read.
_NAME_ONLY_CONSUMERS = frozenset({"head", "tail", "wc", "sort", "uniq", "grep", "egrep", "fgrep", "cut", "tr",
                                  "cat"})
_FIND_GLOBAL_OPTIONS = frozenset({"-h", "-l", "-p"})


def _find_call(stage):
    """명령 자리의 find → (시작 경로들, [(시험, 패턴)], 전부 고른다고 볼 것인가, 실행 술어가 있나) — find 가 아니면 None.
    낱말은 셸 규칙으로 나눈다 — `\\(` · `\\;` 를 경로 구분자로 바꾸면 시작 경로를 잘못 읽는다(Grok 반례 검토 중 실측).
    부정 · 링크 대상 시험이 있으면 전부 고른다고 본다(막는 쪽).
    find at the command position as (start paths, [(test, pattern)], select-all?, runs a command?); words are
    split with shell rules — turning `\\(` into a path separator misread the start paths."""
    head, words = _command_words(stage)
    if head != "find":
        return None
    i = 0
    while i < len(words) and (words[i].lower() in _FIND_GLOBAL_OPTIONS or re.fullmatch(r"-O\d*", words[i])):
        i += 1
    starts = []
    while i < len(words) and not words[i].startswith(("-", "!", ",")):
        starts.append(words[i])
        i += 1
    tests, select_all, runs = [], False, False
    expression = words[i:]
    for k, word in enumerate(expression):
        if word in _FIND_PATTERN_PRIMARIES | _FIND_REGEX_PRIMARIES and k + 1 < len(expression):
            tests.append((word, expression[k + 1]))
        select_all = select_all or word in ("!", "-not") or word in _FIND_UNMODELLED_TESTS
        runs = runs or word in _FIND_RUN_PRIMARIES
    return starts or ["."], tests, select_all, runs


def _find_regex_selects(pattern, path, ignore_case):
    """find 정규식(기본 emacs 문법)이 경로를 고르는가. emacs 와 파이썬의 뜻이 갈리는 꼴이면 막는 쪽이다 — `|` · 괄호 ·
    중괄호, POSIX 클래스(`[:`), 글자 그대로를 뜻하는 이스케이프(`\\.` · `\\*` …) 밖의 백슬래시 구문(emacs `\\'` 는 끝 고정
    인데 파이썬에선 따옴표 글자다 — Grok claim-review bdd00182).
    Does a find regex select the path? Constructs whose meaning differs between emacs and Python fail closed:
    `|`, parentheses, braces, POSIX classes, and any backslash escape other than a literal-punctuation one."""
    if any(ch in pattern for ch in "|(){}") or "[:" in pattern or re.search(r"\\(?![.*+?\[\]^$\\/-])", pattern):
        return True
    # emacs 의 `^` · `$` 는 맨 앞 · 맨 끝에서만 고정이고 가운데선 글자다 — 파이썬은 늘 고정(Grok claim-review af786686).
    # In emacs `^`/`$` anchor only at the very start/end and are literal elsewhere; Python always anchors.
    if "^" in pattern[1:] or "$" in pattern[:-1]:
        return True
    try:
        return re.fullmatch(pattern, path, re.IGNORECASE if ignore_case else 0) is not None
    except re.error:
        return True


def _find_may_select(files, start, tests, select_all):
    """find 의 시험(점 파일 포함 · 경로 · 정규식은 시작 경로부터)이 .env 꼴 파일 하나라도 고르는가. 전부 고른다고 볼
    때나 시험이 없으면 고른다. Would find's tests select any of these .env-like files?"""
    if select_all or not tests:
        return bool(files)
    for parts in files:
        path = "/".join((start.rstrip("/"), *parts))
        for primary, pattern in tests:
            if primary in _FIND_REGEX_PRIMARIES:
                if _find_regex_selects(pattern, path, primary == "-iregex"):
                    return True
                continue
            target = parts[-1] if primary in ("-name", "-iname") else path
            if primary.startswith("-i"):
                target, pattern = target.lower(), pattern.lower()
            if fnmatch.fnmatchcase(target, pattern):
                return True
    return False


def _find_reads_dotenv(stages):
    """find 가 찾은 파일을 실행 술어나 «이름만 다루지 않는» 뒤 단계로 넘기고, 그 find 가 .env 꼴 파일을 고를 수 있는가.
    Does a find hand its matches to a command or a non-name-only later stage, and could it select a .env file?"""
    for i, stage in enumerate(stages):
        call = _find_call(stage)
        if call is None:
            continue
        starts, tests, select_all, runs = call
        hands_over = runs or any(_command_words(s)[0] not in _NAME_ONLY_CONSUMERS for s in stages[i + 1:])
        if not hands_over:
            continue
        for start in starts:
            files = _dotenv_files(start)
            if files is None or _find_may_select(files, start, tests, select_all):
                return True
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
    (re.compile(r"\bprintenv\b", re.IGNORECASE).search,
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
    (_reads_dotenv,
     ".env 읽기 — 시크릿 파일 직접 열람", (_NAMES,), _SAFE_DOTENV),
    (_recursive_search_reads_dotenv,
     "재귀 검색 — .gitignore 를 무시해 .env 까지 읽는다", (), _SAFE_SEARCH),
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
# 🔴 구분자는 **따옴표 밖**에서만 나눈다 — `grep -rniE "A|B" src/` 의 정규식 교대를 단계로 쪼개면, 잘린 앞 조각이
#    검색 대상을 잃고 «현재 폴더» 로 읽혀 오판한다(R-4 시험에서 실측). 따옴표가 닫히지 않으면 나누지 않는다
#    (나뉘지 않은 쪽은 중화를 받기 어려워 막는 쪽이다).
# Split only on separators outside quotes; an unclosed quote stops splitting (the fail-closed side).
_SEGMENT_SEPARATORS = ("&&", "||", ";", "\n", "&")
# 이스케이프(Bash `\` · PowerShell 백틱)나 닫히지 않은 따옴표가 있으면 따옴표 인식 분할을 믿지 않고 예전의 무조건
# 분할로 돌아간다 — `echo \"; env` 의 `\"` 를 따옴표로 읽으면 `; env` 가 앞 세그먼트에 묶인다(보안 리뷰 HIGH).
# With escapes or an unclosed quote, fall back to the unconditional split (an escaped quote must not glue segments).
# 구분자 목록에서 만든다 — 정규식 글자에 `|` 교대를 직접 쓰면 증거집합 가드가 조각(`[` 등)을 증거로 센다.
# Built from the separator list; a literal `|` alternation would feed fragments to the witness guard.
_NAIVE_SEGMENT_SPLIT = re.compile("|".join(re.escape(s) for s in _SEGMENT_SEPARATORS))


def _quotes_trustworthy(text):
    """백틱 · 주석이 없고, 백슬래시가 따옴표 글자 바로 앞에 오지 않으며, 따옴표가 모두 닫혔는가 — 주석 속
    홑따옴표(`# it's`)를 따옴표로 읽으면 뒤 명령이 묶인다(보안 리뷰 HIGH).

    백슬래시는 따옴표 글자 앞에서만 따옴표 구조를 바꾼다(`\\"` · `\\'` — 셸은 글자로 읽는데 이 분할은 따옴표로 읽어,
    `echo \\"; env` 의 `; env` 를 앞에 묶는다). `\\|` · `\\.` · `\\*` 같은 정규식 이스케이프는 구조를 바꾸지 않는다 —
    그것까지 믿지 않으면 큰따옴표 안 교대(`"a\\|b"`)를 단계로 쪼개 «대상 없는 재귀 검색» 으로 오판한다(원장 #1917 P1-5).
    PowerShell 의 백슬래시는 이스케이프가 아니라(백틱이 이스케이프다) 그 셸에서는 `\\"` 를 따지지 않는다 — `"docs\\"`
    는 거기서 닫힌 문자열이다(교차 검토 4차).
    No backtick or comment, no backslash right before a quote character (Bash only), and every quote closed?"""
    if "`" in text or "#" in text or (_CONTEXT["shell"] != "powershell" and re.search(r"\\['\"]", text)):
        return False
    quote = None
    for ch in text:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
    return quote is None


def _split_segments(command):
    """세그먼트 분할 — 줄바꿈은 늘 나누고, 줄 안은 따옴표를 믿을 수 있을 때만 따옴표 밖에서.
    Always split on newlines; within a line, quote-aware only when quotes can be trusted."""
    parts = []
    for line in command.split("\n"):
        parts.extend(_split_unquoted(line, _SEGMENT_SEPARATORS) if _quotes_trustworthy(line)
                     else _NAIVE_SEGMENT_SPLIT.split(line))
    return parts


def _split_stages(segment):
    """단계 분할 — 따옴표를 믿을 수 있을 때만 따옴표 밖에서 / Split pipeline stages (quote-aware only when safe)."""
    if _quotes_trustworthy(segment):
        return _split_unquoted(segment, ("|",))
    return segment.split("|")


def _split_unquoted(text, separators):
    """따옴표 밖의 구분자로만 나눈다(긴 구분자 먼저) / Split on separators outside quotes (longest first)."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if quote or ch in "'\"":
            quote = None if ch == quote else (quote or ch)
            buf.append(ch)
            i += 1
            continue
        sep = next((s for s in separators if text.startswith(s, i)), None)
        if sep:
            parts.append("".join(buf))
            buf = []
            i += len(sep)
        else:
            buf.append(ch)
            i += 1
    parts.append("".join(buf))
    return parts


# 🔴 리디렉션(`>&2` · `> 파일` · `<`)과 괄호(명령·프로세스 치환 `$(` · `<(` · `>(` · 서브셸 · extglob `@(a|b)`)가 든
#    단계는 중화하지 않는다 — 출력이 cut 을 비켜 가거나 쓰기 명령 안에서 읽기가 돌고, extglob 안의 `|` 는 파이프가
#    아니다(보안 리뷰 · AntiGravity 교차 검토).
# A stage with redirection or any parenthesis (substitution, subshell, extglob) is never neutralized: output can
# bypass the cut, a read can run inside a write, and a `|` inside `@(a|b)` is no pipe.
_UNREADABLE_STAGE = re.compile(r"[<>()]")


def _neutralized(stages, i, neutralizers):
    """i 번째 단계의 덤프가 중화됐는가 / Is the dump at stage i neutralized?"""
    stage = stages[i]
    if _UNREADABLE_STAGE.search(stage):
        return False
    # 이 단계와 다음 단계를 가른 `|` 가 이스케이프(`\|`)였으면 파이프가 아니다 — 셸은 `printenv \| grep -c KEY` 를
    # `printenv '|' grep -c KEY` 로 돌려 KEY 의 값을 찍는다(커밋 보안 검토). 다음 단계로는 무엇도 중화하지 않는다.
    # An escaped `\|` is not a pipe: the shell runs `printenv '|' grep -c KEY` and prints KEY's value.
    if (len(stage) - len(stage.rstrip("\\"))) % 2 == 1:
        return False
    # `${X:-|}` · `$'…'` 안의 `|` 도 셸에겐 파이프가 아니다 — 확장 · ANSI 문자열이 든 덤프 단계는 중화하지 않는다(커밋 보안 검토).
    # A `|` inside `${…}` or `$'…'` is not a pipe either: never neutralize a dump stage holding one.
    if "${" in stage or "$'" in stage:
        return False
    is_variable = _WRITE in neutralizers  # railway variable 항목만 쓰기 중화를 가진다
    call = _railway_variable_call(stage) if is_variable else None
    # 한 단계에 railway variable 호출이 둘 이상이면 쓰기로 덮지 않는다 / never excuse two calls in one stage
    single = len(re.findall(_RW + r"\s+(?:variables?|vars?)\b", stage, re.IGNORECASE)) == 1
    if is_variable and single and call is not None and call[0]:
        # 쓰기는 운영 판정이 막는다 — main 의 읽기(Bash 이스케이프)로도 쓰기일 때만 덤프 판정을 비킨다. PowerShell 의 전체 경로
        # `railway.cmd` 는 백슬래시를 글자로 읽으면 쓰기지만 main 의 운영 판정은 railway 로 못 알아봐, 비키면 변수 쓰기가
        # 통과했다(검증 검토). A write is excused only when main's reading sees the same write.
        as_main = _railway_variable_call(stage, main_reading=True)
        return as_main is not None and as_main[0]
    if _NAMES not in neutralizers or i + 1 >= len(stages):
        return False
    nxt = stages[i + 1]
    # 바로 다음 단계가 개수만(grep -c · -q · -l · wc) 내면 값이 나오지 않는다(원장 #1917 P1-5 — `env | grep -c X` 오탐).
    # A very next stage that prints only counts prints no value.
    if _COUNT_ONLY_GREP_STAGE.fullmatch(nxt) or _WC_COUNT_ONLY.fullmatch(nxt):
        return True
    # 🔴 이름만 자르는 단계(cut 관용구 · `grep -o '^[A-Z_]*='`)는 덤프 **바로 다음** 이고 덤프가 KEY=VALUE 줄을 낼 때만 —
    #    사이 단계(`tee /dev/stderr` 등)는 값을 복제하고, `printenv 이름` 은 값만 내서 «`=` 앞» 이 곧 값이다(AntiGravity
    #    교차 검토 — cut 은 main 때부터 샜다). railway variable 은 KEY=VALUE(--kv · -k, --json 없음) 출력일 때만 — 토큰으로 본다.
    # A names-only stage must be the very next one and the dump must print KEY=VALUE lines (printenv NAME prints the
    # bare value). For railway variable it needs --kv/-k without --json, read as tokens.
    if not (_CUT_IDIOM.fullmatch(nxt) or _names_only_grep(nxt)) or _prints_bare_values(stage):
        return False
    if is_variable:
        return call is not None and bool({"--kv", "-k"} & call[1]) and "--json" not in call[1]
    return True


def _prints_bare_values(stage):
    """덤프 단계가 KEY=VALUE 가 아니라 값만 내는가 — `printenv 이름…` 은 그 변수들의 값만 한 줄씩 낸다.
    Does the dump print bare values (printenv with names) instead of KEY=VALUE lines?"""
    words = _plain_words(stage)
    for k, word in enumerate(words):
        if _command_name(word) == "printenv":
            return any(not w.startswith("-") for w in words[k + 1:])
    return False


def _decide_segment(segment, marked=None):
    """단일 명령(파이프라인 포함)에 대한 판정 — 차단 사유와 안내를 내거나 None. `marked` 는 따옴표 안 글롭 글자에
    표지를 단 같은 세그먼트(R-5) — .env 경로 판정만 그것을 본다.
    Verdict for one command (pipeline included): (reason, hint) or None. `marked` is the same segment with
    quoted-glob sentinels; only the .env path check reads it."""
    stages = _split_stages(segment)
    path_stages = _split_stages(marked) if marked and marked != segment else stages
    if len(path_stages) != len(stages):
        path_stages = stages  # 나뉨이 어긋나면 표지를 쓰지 않는다 / never trust a misaligned split
    # 🔴 `#` 이 있으면 그 뒤가 주석일 수 있다 — `--kv # | cut -d= -f1` 의 cut 은 실행되지 않는다(Grok G1).
    #    단계 분해는 주석을 모르므로, `#` 이 든 세그먼트에서는 어떤 중화도 인정하지 않는다. 따옴표를 믿을 수 없을
    #    때(`\"` · 백틱)도 같다 — 분할이 따옴표 안의 `|` 로 나눠, `printenv K '\"|wc -l|'` 의 wc 는 printenv 의 인자일
    #    뿐이다(AntiGravity 교차 검토).
    # A `#` may start a comment («--kv # | cut» never runs the cut), and untrusted quotes split on quoted bars:
    # no neutralizer counts in either case.
    unneutralizable = "#" in segment or not _quotes_trustworthy(segment)
    # 나열 → 내용 읽기 파이프라인(`Get-ChildItem [-Recurse] | Select-String`) — 단계 하나로는 안 보인다.
    # A listing piped into a content reader is only visible across stages.
    if len(stages) > 1 and _listing_pipeline_reads_dotenv(stages):
        return "나열 → 내용 읽기 — .env 까지 읽는다", _SAFE_SEARCH
    # find 가 찾은 파일을 읽게 넘긴다 — find 의 `*` 는 점 파일도 집고 아래 폴더까지 내려간다(R-3).
    # find hands its matches to a reader; its `*` matches dot-files and it descends.
    if _find_reads_dotenv(stages):
        return "find → 내용 읽기 — find 가 고른 .env 까지 읽는다", _SAFE_SEARCH
    for i, stage in enumerate(stages):
        for matcher, reason, neutralizers, hint in _BLOCKED:
            hit = matcher(path_stages[i] if matcher is _reads_dotenv else stage)
            # 🔴 .env 를 다루는 «안전한» 명령도 출력이 다음 단계로 넘어가면 읽기다(`ls .env | xargs cat` ·
            #    `Get-Item .env | Get-Content` — 보안 리뷰 지적). 안전은 파이프라인의 마지막 단계일 때만.
            # A "safe" .env command whose output flows to a next stage is a read; safe only as the last stage.
            if (not hit and matcher is _reads_dotenv and i + 1 < len(stages)
                    and _mentions_dotenv(_without_search_pattern(path_stages[i]))):
                hit = True
            if hit and (unneutralizable or not _neutralized(stages, i, neutralizers)):
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


def decide_with_hint(command, cwd=None, shell="bash"):
    """(사유, 안내) 또는 None / (reason, hint) or None.
    cwd · shell 은 훅 입력의 작업 폴더와 셸 — 경로 · 와일드카드 · 재귀 검색 대상을 실제 폴더에 대 볼 때 쓴다.
    먼저 명령 안의 모든 cd 를 따라 작업 폴더 후보를 모은 뒤(줄이지 않는다), 세그먼트마다 그 후보 전부로 판정한다.
    cwd and shell come from the hook input. Every cd in the command first grows the cwd candidates (never
    shrinks them); then each segment is judged against all of them."""
    _CONTEXT.update(cwds=[os.path.normpath(cwd or os.getcwd())], shell=shell,
                    dotglob=bool(command and _DOTGLOB.search(command)))
    if not command:
        return None
    segments = _all_segments(command)
    marked = _mark_quoted_literals(command)
    marked_segments = _all_segments(marked) if marked != command else segments
    if len(marked_segments) != len(segments):
        marked_segments = segments  # 나뉨이 어긋나면 표지를 쓰지 않는다 / never trust a misaligned split
    for segment in segments:
        _follow_directory_change(segment)
    for segment, marked_segment in zip(segments, marked_segments):
        found = _decide_segment(segment, marked_segment)
        if found:
            return found
    return None


def _all_segments(command):
    """세그먼트 + 명령 · 프로세스 치환 안의 세그먼트. 따옴표 안의 치환(`"$(cat .env)"`)을 한 토큰으로 묶으면 안의
    읽기를 놓친다(13차 HIGH) — 그래서 치환 안 글자를 따로 떼어 같은 판정을 거친다. 괄호 짝을 세고(닫히지 않으면
    끝까지), Bash 는 백틱 치환 · `<(…)` · `>(…)` 도, PowerShell 은 `$(…)` · `@(…)` 를 본다.
    Segments plus those inside command/process substitutions, so a substitution inside quotes is judged
    as a command of its own."""
    segments = _split_segments(command)
    powershell = _CONTEXT["shell"] == "powershell"
    opener = re.compile(r"[$@]\(" if powershell else r"[$<>]\(")
    for match in opener.finditer(command):
        depth, j = 1, match.end()
        while j < len(command) and depth:
            depth += {"(": 1, ")": -1}.get(command[j], 0)
            j += 1
        segments.extend(_split_segments(command[match.end(): j - 1 if depth == 0 else j]))
    if not powershell:
        for body in re.findall(r"`([^`]*)`", command):
            segments.extend(_split_segments(body))
    return segments


_CD_HEADS = frozenset({"cd", "pushd", "set-location", "sl", "chdir"})
_UNKNOWN_CWD = "$UNKNOWN-CWD"  # `_unresolvable` 이 잡는 표지 — 뒤 판정이 막는 쪽으로 간다 / fail-closed marker


def _add_cwd(path):
    """작업 폴더 후보를 더한다 — 너무 많으면 «모름» 으로(막는 쪽) / add a cwd candidate; too many → unknown."""
    cwds = _CONTEXT["cwds"]
    if path not in cwds:
        cwds.append(path if len(cwds) < _MAX_CWDS else _UNKNOWN_CWD)


def _follow_directory_change(segment):
    """cd 를 따라 작업 폴더 후보를 늘린다 — 줄이지 않는다. 서브셸 · 조건부 · 루프 안의 cd(`(cd x; …)` · `if cd x` ·
    `do cd $d`)도 후보에 넣어, 셸이 실제로 어디서 돌든 그 폴더가 후보에 있게 한다(13차 HIGH — 서브셸 cd 를 건너뛰면
    판정이 느슨해졌다). 셸만 아는 대상(`cd $X`) · 되돌아가기(`cd -` · popd) · 어느 후보에서도 없는 폴더는 «모름» 을
    더해 뒤의 파일 시스템 판정이 막는 쪽으로 가게 한다.
    Grow (never shrink) the cwd candidates with every cd, including those in subshells, conditionals and
    loops; unknown targets add an unknown marker so later checks fail closed."""
    words = _plain_words(segment)
    for k, word in enumerate(words):
        name = _command_name(word)
        if name == "popd":
            _add_cwd(_UNKNOWN_CWD)
            return
        if name not in _CD_HEADS:
            continue
        rest = words[k + 1:]
        if rest and rest[0] == "-":
            _add_cwd(_UNKNOWN_CWD)
            return
        target = next((w for w in rest if not w.startswith("-")), "~")
        if _unresolvable(target):
            _add_cwd(_UNKNOWN_CWD)
            return
        found = [os.path.normpath(p) for p in _resolve_all(target) if not _unresolvable(p) and os.path.isdir(p)]
        for path in found or [_UNKNOWN_CWD]:
            _add_cwd(path)
        return


# ── 운영 접근 — 행위로 가른다 (회고 2026-11-06 원장 L02, P0) ─────────────────────────────
# 🔴 10-25 사고: 에이전트 측정 코드가 운영 컨테이너에서(`railway ssh`) 앱 워커 자격으로 돌며 세션 설정을 풀러
#    연결에 남겨 25시간 워커 쓰기를 막았다. 위임 규칙은 «SELECT 자율» 이었다 — 위험은 SQL 동사가 아니라 운영
#    런타임의 코드 실행 · 운영 변수를 쓴 실행 · 운영 상태 변경이다. 그래서 railway 는 **허용 목록**으로 본다:
#    배포 목록 · 로그 · 상태 · 지표 · 도움말만 자율, 그 밖(새 하위 명령 · 별칭 포함)은 사용자가 `!` 로 실행한다.
#    bypass 권한 모드에서는 훅의 «ask» 와 settings 의 ask 규칙이 창 없이 통과했다(11-10 실측) — 그래서 deny 만 낸다.
# Production access is judged by action. railway is an allowlist: reads only; everything else (new
# subcommands too) is run by the user with `!`. In bypass mode "ask" was auto-allowed, so only deny.
_PROD_READ_SUBCOMMANDS = frozenset({"status", "whoami", "list", "ls", "logs", "metrics", "docs", "help",
                                    "completion", "check_updates", "check-updates"})
# 두 번째 낱말까지 봐야 읽기인 명령 — 그 밖의 짝은 운영 변경이다(`railway domain` 홀로는 도메인을 새로 만든다).
# Reads only with these second words; a bare `railway domain` generates a new domain.
_PROD_READ_PAIRS = {
    "deployment": frozenset({"list", "ls"}), "deployments": frozenset({"list", "ls"}),
    "service": frozenset({"list", "ls", "status", "logs"}),
    "domain": frozenset({"list", "ls", "status"}),
    "environment": frozenset({"list", "ls"}), "env": frozenset({"list", "ls"}),
}
# 도움말 · 판 출력 — `--` 뒤는 안쪽 명령의 인자라 보지 않는다 / help and version flags (before any `--`)
_PROD_HELP_FLAGS = frozenset({"--help", "-h", "--version", "-V"})
_PROD_REASONS = {
    "ssh": "운영 컨테이너에서 코드 실행", "run": "운영 변수를 넣은 로컬 실행", "local": "운영 변수를 넣은 로컬 실행",
    "shell": "운영 변수를 넣은 셸", "dev": "운영 변수를 넣은 로컬 실행", "connect": "운영 DB 셸",
    "up": "배포", "deploy": "템플릿 배포", "redeploy": "재배포", "restart": "재시작", "down": "배포 제거",
    "agent": "Railway Agent(운영 조작 가능)",
}
# 안쪽 명령을 받는 하위 명령 — 이것들만 `--` 와 첫 위치 낱말 뒤가 안쪽 명령의 인자다
# Verbs that take an inner command; only for them do `--` and the first positional start its arguments.
_PROD_INNER_COMMAND = frozenset({"ssh", "run", "local"})
_PROD_SHELL_WRAPPERS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_PROD_PS_WRAPPERS = frozenset({"powershell", "pwsh"})
_PROD_PKG_RUNNERS = frozenset({"npx", "bunx", "pnpx"})
# 셸 키워드 · 실행기 · PowerShell 블록 머리 — 이 뒤에서는 첫 railway 낱말부터를 호출로 본다. 재시도 루프
# (`for …; do railway redeploy; done`) · 시간 제한(`timeout 300 railway up`) · Git Bash 의 `winpty` 가 자연스러운 꼴이다.
# Shell keywords, runners and PowerShell block heads: the first railway word after them starts the call.
_PROD_SCAN_HEADS = frozenset({
    "if", "then", "else", "elif", "do", "while", "until", "!",
    "timeout", "gtimeout", "nice", "ionice", "stdbuf", "winpty", "unbuffer", "xargs", "watch", "setsid", "flock",
    "elseif", "foreach", "for", "switch", "try", "finally", "start-process", "saps", "start",
})
_PROD_MAX_DEPTH = 4
# 읽기 MCP 도구 — Railway 는 이것만 통과(허용 목록). Supabase 는 SQL · 마이그레이션 · 배포 · 브랜치 조작을 막는다
# (어느 프로젝트를 가리키는지 훅은 모른다 — DB 를 바꾸거나 SQL 을 도는 도구는 운영 DB 접근으로 본다).
# Read-only MCP tools (allowlists); the hook cannot tell which project a server points at.
_PROD_RAILWAY_MCP_READS = frozenset({
    "list_deployments", "get_logs", "environment_status", "list_services", "list_projects", "list_workspaces",
    "whoami", "docs_search", "docs_fetch", "http_error_rate", "http_requests", "http_response_time",
    "service_metrics", "get_service_config", "domain_status", "list_domains", "list_tcp_proxies",
    "get_tcp_proxy", "private_network_status", "search_templates", "authenticate", "complete_authentication",
})
_PROD_SUPABASE_MCP_READS = frozenset({
    "search_docs", "list_tables", "list_extensions", "list_migrations", "get_advisors", "get_project_url",
    "get_publishable_keys", "query_logs", "list_branches", "list_edge_functions", "get_edge_function",
    "generate_typescript_types", "list_notebooks", "get_notebook", "authenticate", "complete_authentication",
})
# 감사 기록에 그대로 적어도 되는 railway 낱말 — 이 밖의 하위 명령 자리 낱말은 «?» 로 적는다(명령에서 온 글자다).
# railway words safe to write into the audit record; any other word in the subcommand slot is written as "?".
_PROD_KNOWN_WORDS = _PROD_READ_SUBCOMMANDS | frozenset(_PROD_READ_PAIRS) | frozenset(_PROD_REASONS) | _VARIABLE_ALIASES
# python 으로 돌리면 운영에 닿는 리포 스크립트 → 감사 기록의 채널 이름. 정책이 에이전트에게 허용한 것(관측 역할 DB 읽기 ·
# 조건부 재배포 · 배포 설정 읽기)과, 사용자 몫인데 훅이 막지 않는 것(관측 역할 설정 · 백필 — 에이전트가 돌리면 회고가 봐야
# 한다) · 운영 측정을 함께 둔다. 인자(SQL · 호스트 · 서비스 이름)는 채널에 넣지 않고 아래 고정 플래그만 붙인다.
# Repo scripts that reach production when run by python; only the fixed flags below are appended, never arguments.
_PROD_CHANNEL_SCRIPTS = {"observe_db.py": "observe_db", "railway_redeploy.py": "railway_redeploy",
                         "railway_config.py": "railway_config", "observer_setup.py": "observer_setup",
                         "backfill_repository_user_id.py": "backfill_repository_user_id",
                         "perf_measure.py": "perf_measure"}
_PROD_SCRIPT_FLAGS = ("--check", "--restart", "--log-errors", "--apply", "--audit", "--prod-only")
# 운영에 닿지 않는 호출 — 도움말, 로컬만 재는 perf_measure. 감사 기록에 올리지 않는다 / calls that never reach production
_PROD_SCRIPT_NO_REACH = ("--help", "-h")
# 값을 받는 python 인터프리터 옵션 — 그 값(`-X utf8` 의 utf8)은 스크립트 이름이 아니다 / interpreter options taking a value
_PYTHON_VALUE_OPTIONS = ("-X", "-W")
_PYTHON_HEAD = re.compile(r"py|python(?:3(?:\.\d+)?)?")
_PROD_SAFE_READS = "railway deployment list --json · railway logs <id> · railway status · railway metrics"
_PROD_SAFE_REDEPLOY = "py -3 scripts/railway_redeploy.py [--restart]"
_PROD_SAFE_DB_READ = 'py -3 scripts/observe_db.py "SELECT ..."'


def _prod_variable_writes(args):
    """`railway variable …` 인자가 쓰기(설정 · 삭제)인가 — 값을 받는 옵션의 값은 하위 명령이 아니다.
    Do these `railway variable` arguments write? Values of value-taking options are not subcommands."""
    k, sub = 1, None
    while k < len(args):
        tok = args[k]
        name = tok.split("=", 1)[0] if tok.startswith("--") else tok
        if name in _VARIABLE_SET_OPTIONS:
            return True
        if name in _VARIABLE_VALUE_OPTIONS:
            k += 1 if "=" in tok else 2
            continue
        if tok == "--":
            break
        if sub is None and not tok.startswith("-"):
            sub = tok.lower()
        k += 1
    return sub in _VARIABLE_WRITE_SUBCOMMANDS


# 값을 받는 옵션 — 그 값은 위치 낱말이 아니다(Grok 3차 반례: `railway domain --port 3000 list` 는 읽기).
# 모르는 값 옵션은 막는 쪽으로 틀린다(읽기가 막혀 사용자가 돌린다).
# Value-taking options; an unknown one errs toward denying a read, never toward allowing a change.
_PROD_VALUE_OPTIONS = _VARIABLE_VALUE_OPTIONS | {"--port"}


def _prod_head(head):
    """Windows 실행 파일 이름(.cmd · .ps1 · .bat)을 뗀다 — `npm.cmd exec …` 도 npm 이다(Grok 3차 반례).
    Strip Windows shim extensions so npm.cmd is npm."""
    for ext in (".cmd", ".ps1", ".bat"):
        if head.endswith(ext):
            return head[: -len(ext)]
    return head


def _prod_positionals(tokens):
    """위치 낱말의 자리 — 옵션과, 값을 받는 옵션(`-s api`)의 값은 뺀다 / positions of positional words."""
    out, k = [], 0
    while k < len(tokens):
        tok = tokens[k]
        if tok.split("=", 1)[0] in _PROD_VALUE_OPTIONS:
            k += 1 if "=" in tok else 2
            continue
        if not tok.startswith("-"):
            out.append(k)
        k += 1
    return out


def _prod_classify(args, channels=None):
    """railway 인자 → None(읽기 · 도움말) 또는 운영 접근 사유 / None for reads and help, else the reason.
    🔴 Grok 반례(11-11) 세 가지를 막는다: 하위 명령 앞 `--` 는 옵션 끝일 뿐이다(`railway -- redeploy` 도 재배포),
    안쪽 명령의 `--version` 은 railway 의 도움말이 아니다(`railway ssh node --version` 은 운영에서 node 를 돈다),
    `-s api` 같은 옵션 값은 둘째 낱말이 아니다(`railway domain -s api list` 는 읽기).
    channels 를 주면 허용한 호출의 채널(`railway logs` 처럼 고정 어휘만 — 인자는 넣지 않는다)을 거기 더한다(감사 기록).
    Grok counterexamples: a leading `--` only ends options; the inner command's --version is not railway's;
    option values are not the second word. With channels, the allowed call's static channel is appended."""

    def allow(*words):
        # 도움말은 운영에 닿지 않는다 — 감사 기록에 올리지 않는다(교차 검토: 다른 명령의 인자인 `railway` 가 «도움말» 로 남았다)
        # help never reaches production, so it is not audited
        if channels is not None and "help" not in words:
            channels.append(" ".join(("railway", *words)))
        return None

    k, lead = 0, []
    while k < len(args) and args[k].startswith("-"):
        lead.append(args[k])
        k += 2 if args[k] in _PROD_VALUE_OPTIONS else 1
    if any(word in _PROD_HELP_FLAGS for word in lead):
        return allow("help")
    if k >= len(args):
        return allow("help")  # `railway` 홀로 · 옵션만 = 도움말 / bare railway prints help
    sub = args[k].lower()
    rest = args[k + 1:]
    if sub in _PROD_INNER_COMMAND:
        # 안쪽 명령을 받는 하위 명령 — `--` 다음과 첫 위치 낱말부터는 안쪽 명령의 인자다(그 `--version` 은 node 것)
        # verbs that take an inner command: after `--` or the first positional word, arguments belong to it
        rest = rest[:rest.index("--")] if "--" in rest else rest
        positions = _prod_positionals(rest)
        help_zone = rest[:positions[0]] if positions else rest
    else:
        # 그 밖의 `--` 는 옵션 끝일 뿐이고 `--help` 는 어디 있든 도움말이다(Grok 재판정 반례 — `railway service -- status`
        # 는 읽기, `railway variable set --help` 는 도움말) / elsewhere `--` only ends options and --help anywhere is help
        rest = [word for word in rest if word != "--"]
        positions = _prod_positionals(rest)
        help_zone = rest
    if any(word in _PROD_HELP_FLAGS for word in help_zone):
        return allow(sub if sub in _PROD_KNOWN_WORDS else "?", "help")
    if sub in _PROD_READ_SUBCOMMANDS:
        return allow(sub)
    if sub in _VARIABLE_ALIASES:
        return f"railway {sub} — 서비스 변수 변경" if _prod_variable_writes(args[k:]) else allow("variables")
    pair = _PROD_READ_PAIRS.get(sub)
    if pair is not None:
        second = rest[positions[0]].lower() if positions else ""
        return allow(sub, second) if second in pair else f"railway {sub} {second}".rstrip() + " — 운영 상태 변경"
    return f"railway {sub} — {_PROD_REASONS.get(sub, '운영 접근(허용 목록 밖)')}"


def _prod_script_channel(head, rest):
    """python 으로 돌린 운영 채널 스크립트의 감사 채널(`observe_db` · `railway_redeploy --check` …) — 아니면 None.
    스크립트 파일을 읽기만 하는 명령(`cat scripts/observe_db.py`)은 python 이 아니라 해당하지 않는다. 인자(SQL)는 넣지 않는다.
    The audit channel of a production-channel script run by python, or None; arguments are never included."""
    if not _PYTHON_HEAD.fullmatch(head):
        return None
    k = 0
    while k < len(rest) and rest[k].startswith("-") and rest[k] not in ("-m", "-c"):
        # `py -3` · `python -u` 의 인터프리터 옵션 — `-X utf8` · `-W ignore` 는 값까지(교차 검토: utf8 을 스크립트로 읽었다)
        # interpreter options; -X / -W take a value
        k += 2 if rest[k] in _PYTHON_VALUE_OPTIONS else 1
    if k + 1 < len(rest) and rest[k] == "-m":
        name, args = rest[k + 1].rsplit(".", 1)[-1] + ".py", rest[k + 2:]  # `python -m scripts.observe_db`
    elif k < len(rest) and rest[k] != "-c":
        name, args = rest[k].replace("\\", "/").rsplit("/", 1)[-1].lower(), rest[k + 1:]
    else:
        return None  # 인터프리터만 · `-c` 의 글자 코드는 스크립트가 아니다 / no script (bare interpreter or -c code)
    channel = _PROD_CHANNEL_SCRIPTS.get(name)
    flags = _prod_script_flags(args)
    if channel is None or flags & set(_PROD_SCRIPT_NO_REACH):
        return None
    if channel == "perf_measure" and "--local-only" in flags:
        return None  # 로컬만 잰다 — 운영에 닿지 않는다 / local only
    return " ".join([channel, *(flag for flag in _PROD_SCRIPT_FLAGS if flag in flags)])


def _prod_script_flags(args):
    """인자 가운데 고정 어휘 플래그 — 여섯 스크립트는 argparse 라 줄인 긴 옵션(`--rest` = `--restart` · `--he` = `--help`)도
    받는다. 어휘의 한 플래그로만 풀리는 앞부분은 그 플래그로 센다(최종 워크플로 패스: `--rest` 가 플래그 없이 적혔다).
    The fixed-vocabulary flags present, resolving argparse abbreviations against the vocabulary."""
    vocabulary = (*_PROD_SCRIPT_FLAGS, *_PROD_SCRIPT_NO_REACH, "--local-only")
    found = set()
    for arg in args:
        name = arg.split("=", 1)[0]
        if name in vocabulary:
            found.add(name)
        elif name.startswith("--") and len(name) > 2:
            matches = [flag for flag in vocabulary if flag.startswith(name)]
            if len(matches) == 1:
                found.add(matches[0])
    return found


def _prod_railway_args(head, rest):
    """railway 호출이면 그 인자(npx @railway/cli 포함), 아니면 None.
    The railway arguments when this stage invokes railway (npx @railway/cli included), else None."""
    if _is_railway(head):
        return rest
    # `pnpm dlx` · `yarn dlx` · `npm exec` · `npm x` 도 패키지 실행기다(Grok 재판정 반례 — `npm exec @railway/cli up`)
    # package runner subcommands too (Grok re-judgment counterexample: npm exec @railway/cli up)
    runner_sub = bool(head in ("pnpm", "yarn", "npm") and rest and rest[0] in ("dlx", "exec", "x"))
    words = rest[1:] if runner_sub else rest
    if head in _PROD_PKG_RUNNERS or runner_sub:
        k = 0
        while k < len(words) and words[k].startswith("-"):
            # `-p/--package <pkg>` 의 값은 실행할 명령이 아니다 — `npx -p @railway/cli railway up` 은 railway 를 돈다
            # the value of -p/--package is not the command (Grok counterexample: npx --package=@railway/cli railway up)
            k += 2 if words[k] in ("-p", "--package") else 1
        if k < len(words) and (words[k] == "@railway/cli" or words[k].startswith("@railway/cli@")):
            return words[k + 1:]
        if k < len(words) and _is_railway(words[k]):
            return words[k + 1:]
    return None


def _prod_shell_scan(rest):
    """셸 래퍼 인자 → (안쪽 `-c` 명령 또는 None, stdin 을 명령으로 읽는가). unwrap 과 stdin 판정이 같은 해석을 쓴다.
    - 값을 받는 옵션(`-o pipefail` · 묶음 `-eo pipefail` · `-O extglob` · `+o posix` · `--rcfile x`)의 값은 스크립트가 아니다.
    - `-s` 는 위치 인자가 있어도 stdin 을 읽고, 스크립트 자리의 `-` · `/dev/stdin` 도 stdin 이다.
    - `<<<` 는 글자를 명령으로 먹인다(자동 보안 리뷰 11-11 두 차례).
    Shell wrapper arguments → (inline -c command or None, reads stdin?), shared by unwrap and the stdin check."""
    k, from_stdin = 0, False
    while k < len(rest):
        word = rest[k]
        if word.startswith("<<<"):
            return (word[3:] or (rest[k + 1] if k + 1 < len(rest) else None)), False
        if word in ("--rcfile", "--init-file"):
            k += 2
            continue
        if word.startswith("--"):
            k += 1
            continue
        if word[:1] in ("-", "+") and len(word) > 1:
            flags = word[1:]
            if word[0] == "-" and "c" in flags:
                return (rest[k + 1] if k + 1 < len(rest) else None), False
            from_stdin = from_stdin or (word[0] == "-" and "s" in flags)
            k += 2 if ("o" in flags or "O" in flags) else 1
            continue
        # 첫 위치 인자 — 스크립트 파일(글자 훅 밖)이거나 `-s` 뒤의 위치 매개변수
        # the first positional: a script file (beyond a text hook) or positional parameters after -s
        return None, from_stdin or word in ("-", "/dev/stdin")
    return None, True


def _prod_unwrap(head, rest):
    """알려진 래퍼 안쪽의 명령 글자 — 셸 `-c` · `cmd /c` · PowerShell `-Command` · `env`. 없으면 None.
    The command text inside a known wrapper (shell -c, cmd /c, PowerShell -Command, env), or None."""
    if head in _PROD_SHELL_WRAPPERS:
        return _prod_shell_scan(rest)[0]
    if head == "cmd":
        for k, word in enumerate(rest):
            if word.lower() in ("/c", "/k", "/r"):
                return " ".join(rest[k + 1:])
        return None
    if head in _PROD_PS_WRAPPERS:
        for k, word in enumerate(rest):
            if word.lower() in ("-command", "-c", "-commandwithargs", "-cwa"):
                return " ".join(rest[k + 1:])
        return None
    if head == "env":
        k = 0
        while k < len(rest) and (rest[k].startswith("-") or _ASSIGNMENT.fullmatch(rest[k])):
            word = rest[k]
            # `-S` · `--split-string` 의 값은 실행할 명령 한 줄이다 / the value of -S is the command line itself
            if word in ("-S", "--split-string"):
                return rest[k + 1] if k + 1 < len(rest) else None
            if word.startswith("--split-string="):
                return word.split("=", 1)[1]
            if word.startswith("-S") and len(word) > 2:
                return word[2:]
            k += 2 if word in ("-u", "--unset", "-C", "--chdir") else 1
        return " ".join(shlex.quote(word) for word in rest[k:]) if k < len(rest) else None
    if head in ("invoke-expression", "iex"):
        return " ".join(rest) or None
    return None


# heredoc 연산자 — 구분자가 따옴표로 싸였는지(본문이 글자인지)를 1번 묶음이 담는다
# A heredoc operator; group 1 holds the quote that makes the body literal.
_PROD_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_PROD_PS_HERESTRING = re.compile(r"@(['\"])[ \t]*$")


def _prod_receiver(prefix):
    """heredoc 을 받는 명령의 첫 낱말 / the head of the command that receives a heredoc."""
    segments = _split_segments(prefix) or [""]
    stages = _split_stages(segments[-1]) or [""]
    return _prod_head(_command_words(stages[-1])[0])


def _prod_runs_text(head):
    """그 명령이 받은 글자를 명령으로 실행하는가(셸 · PowerShell · cmd · iex · railway) / does it execute its text?"""
    return (head in _PROD_SHELL_WRAPPERS or head in _PROD_PS_WRAPPERS or head == "cmd"
            or head in ("invoke-expression", "iex") or _is_railway(head))


def _prod_pipes_into_runner(text):
    """뒤 파이프 단계가 글자를 실행하는 명령인가 — `cat <<'EOF' | bash` · `'@ | iex` 는 글자 heredoc 이라도 돈다
    (Grok 3차 반례 · Claude 확인). Does a later pipeline stage execute the text?"""
    return any(_prod_runs_text(_prod_head(_command_words(stage)[0])) for stage in _split_stages(text)[1:])


def _prod_reads_stdin(head, rest):
    """파이프 뒤에서 stdin 을 명령으로 읽는가 — `bash` · `sh -s` · `powershell -` · 인자 없는 `iex` · `cmd`.
    스크립트 파일을 받거나 `-c` · `-Command` 로 명령을 받으면 stdin 이 아니다(그쪽은 unwrap 이 본다).
    Does this stage read its commands from stdin? A script file or an inline -c/-Command is not stdin."""
    if head in _PROD_SHELL_WRAPPERS:
        inner, from_stdin = _prod_shell_scan(rest)
        return inner is None and from_stdin
    if head in _PROD_PS_WRAPPERS:
        lowered = [word.lower() for word in rest]
        for k, word in enumerate(lowered):
            if word in ("-file", "-f"):
                return k + 1 < len(lowered) and lowered[k + 1] == "-"  # `-File -` 는 stdin / -File - reads stdin
        for k, word in enumerate(lowered):
            if word in ("-command", "-c"):
                return k + 1 < len(lowered) and lowered[k + 1] == "-"
        return True
    if head in ("invoke-expression", "iex"):
        return not rest
    if head == "cmd":
        return not any(word.lower() in ("/c", "/k", "/r") for word in rest)
    return False


def _prod_find_heredoc(line):
    """따옴표 밖의 heredoc 연산자 — 따옴표 안의 `<<'EOF'` 는 글자다(자동 보안 리뷰 11-11: 그것을 heredoc 으로 읽으면
    다음 줄의 실제 명령이 «본문» 으로 빠진다). `<<<` 는 heredoc 이 아니다.
    The heredoc operator outside quotes (a quoted one would swallow the real commands that follow)."""
    quote, i = None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == quote:
                quote = None
            elif ch == "\\" and quote == '"':
                i += 1
        elif ch in "'\"":
            quote = ch
        elif ch == "\\":
            i += 1
        elif line.startswith("<<<", i):
            i += 3
            continue
        elif line.startswith("<<", i):
            match = _PROD_HEREDOC.match(line, i)
            if match:
                return match
        i += 1
    return None


def _prod_substitutions(text):
    """실제로 도는 명령 · 프로세스 치환의 몸 — Bash 는 홑따옴표 안이 글자라 빼고 백슬래시 뒤 글자를 건너뛴다.
    PowerShell 은 `$(…)` · `@(…)` 만(백틱은 이스케이프).
    Bodies of substitutions that actually run: Bash single quotes are literal and a backslash escapes the
    next character; PowerShell only has $() and @() (its backtick is an escape)."""
    powershell = _CONTEXT["shell"] == "powershell"
    openers = ("$(", "@(") if powershell else ("$(", "<(", ">(")
    bodies, i, quote = [], 0, None
    while i < len(text):
        ch = text[i]
        if quote == "'":
            quote = None if ch == "'" else quote
            i += 1
        elif ch == "'" and quote is None:
            quote = "'"
            i += 1
        elif ch == '"':
            quote = None if quote == '"' else '"'
            i += 1
        elif ch == "\\" and not powershell:
            i += 2
        elif text.startswith(openers, i):
            depth, j = 1, i + 2
            while j < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            bodies.append(text[i + 2: j - 1 if depth == 0 else j])
            i = j
        elif ch == "`" and not powershell:
            end = text.find("`", i + 1)
            end = len(text) if end < 0 else end
            bodies.append(text[i + 1:end])
            i = end + 1
        else:
            i += 1
    return bodies


def _prod_without_heredoc_data(text):
    """heredoc 본문 중 «데이터» 를 뺀다 — 따옴표 구분자(`<<'EOF'`)면 본문 전체가 글자, 따옴표 없는 구분자면 치환만
    돈다(그 몸만 남긴다). 셸 · PowerShell · cmd · railway 에 먹이는 heredoc 은 본문이 실행되므로 그대로 둔다.
    Drop heredoc data: a quoted delimiter makes the body literal; an unquoted one still runs substitutions
    (only those stay). A heredoc fed to a shell, PowerShell, cmd or railway runs, so it stays whole."""
    powershell = _CONTEXT["shell"] == "powershell"
    lines = text.split("\n")
    kept, i = [], 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        # PowerShell here-string(`@'…'@` 글자 · `@"…"@` 는 `$(…)` 가 돈다) — 닫는 줄은 `'@` · `"@` 로 시작한다
        # PowerShell here-strings: @'…'@ is literal, @"…"@ still runs $(…); the closing line starts with '@ or "@
        here = _PROD_PS_HERESTRING.search(line) if powershell else None
        match = None if here else _prod_find_heredoc(line)
        if not here and not match:
            continue
        runs = (_prod_runs_text(_prod_receiver(line[:(here or match).start()]))
                or (match is not None and _prod_pipes_into_runner(line[match.end():])))
        body = []
        while i < len(lines) and not (lines[i].startswith(here.group(1) + "@") if here
                                      else lines[i].strip() == match.group(2)):
            body.append(lines[i])
            i += 1
        if here and i < len(lines):
            closing_rest = lines[i][2:]
            kept.append(closing_rest)  # 닫는 `'@` 뒤(파이프 등)는 명령이다 / what follows the closing '@ is a command
            runs = runs or _prod_pipes_into_runner(closing_rest)
        i += 1  # 구분자 줄 / the delimiter line
        literal = here.group(1) == "'" if here else bool(match.group(1))
        if runs:
            kept.extend(body)
        elif not literal:
            kept.extend(_prod_substitutions("\n".join(body)))
    return "\n".join(kept)


def _prod_decide_text(text, depth):
    """세그먼트 · 실제로 도는 치환 · 래퍼 안까지 railway 호출을 찾아 판정한다. heredoc 데이터와 홑따옴표 글자는
    실행이 아니라서 보지 않는다 — 처음 판은 `<<'EOF'` 본문의 백틱을 치환으로 읽어 PR 본문을 막았다(원장 R-5 부류).
    Judge every railway call in segments, substitutions that run and known wrappers; heredoc data and
    single-quoted text are not invocations (the first version blocked a PR-body heredoc)."""
    if depth > _PROD_MAX_DEPTH or not text.strip():
        return None
    text = _prod_without_heredoc_data(text)
    for body in _prod_substitutions(text):
        reason = _prod_decide_text(body, depth + 1)
        if reason:
            return reason
    for segment in _split_segments(text):
        stages = _split_stages(segment)
        for index, stage in enumerate(stages):
            head, rest = _command_words(stage)
            head = _prod_head(head)
            if not head:
                continue
            if index and _prod_reads_stdin(head, rest):
                # 앞 단계가 내보내는 글자가 이 명령의 입력이라 실행된다 — 앞 단계의 낱말을 명령으로 본다(자동 보안 리뷰
                # 11-11: `echo "railway up" | bash`). 파일을 내보내는 앞 단계(`cat x.sh | bash`)는 스크립트 파일 부류다.
                # Text from earlier stages is executed here, so judge their words as commands.
                # 낱말 하나씩과 이어 붙인 인자 전체 — `echo railway up | bash` 는 따옴표 없이 두 낱말로 넘긴다
                # each word and the joined arguments (`echo railway up | bash` passes two unquoted words)
                for earlier in stages[:index]:
                    first, more = _command_words(earlier)
                    for piece in [first, *more, " ".join(more)]:
                        reason = _prod_decide_text(piece, depth + 1)
                        if reason:
                            return reason
            args = _prod_railway_args(head, rest)
            if args is None and head in _PROD_SCAN_HEADS:
                first = next((k for k, word in enumerate(rest) if _is_railway(word)), None)
                args = rest[first + 1:] if first is not None else None
            if args is not None:
                reason = _prod_classify(args)
                if reason:
                    return reason
                continue
            inner = _prod_unwrap(head, rest)
            reason = _prod_decide_text(inner, depth + 1) if inner else None
            if reason:
                return reason
    return None


def decide_production_access(command, shell=None, channels=None):
    """명령이 운영에 닿는가 — 사유 또는 None. 세그먼트 · 명령 치환 · 알려진 래퍼 안까지 본다.
    railway 를 «언급» 만 하는 명령(`grep "railway ssh"`)은 명령 자리가 아니라 통과한다. channels(목록)를 주면 허용한
    명령 안의 운영 채널 호출을 감사 순회(`_audit_text`)로 거기 더한다 — 판정에는 쓰지 않는다(원장 #1917 M02 P2-3 ②).
    🔴 위협 모형은 credential 판정과 같다 — 정직한 세션이 칠 만한 꼴을 막는다. 스크립트 파일 안의 호출 ·
    인코딩된 명령 같은 의도적 우회는 글자 훅 밖이다(원장 R-3 부류).
    Does the command touch production? Mentions are not invocations. Same threat model as the credential
    verdict: honest shapes are covered; calls inside script files or encoded commands are out of reach."""
    if shell is not None:
        _CONTEXT["shell"] = shell
    reason = _prod_decide_text(command or "", 0)
    if reason is None and channels is not None:
        _audit_text(command or "", 0, channels)
    return reason


# ── 감사 순회 — 허용된 운영 채널 호출의 채널만 모은다(원장 #1917 M02 P2-3 ②) ──────────────────────────────────
# 판정은 위 순회(main 그대로)가 한다. 이 순회는 그 판정이 허용한 명령에만 돌고 결과는 감사 기록뿐이다 — 판정 순회를 고쳐
# 감사를 얹었더니 고칠 때마다 main 이 막던 꼴을 풀거나 언급을 새로 막았다(워크플로 적대 패스 세 번). 판정 순회의 구멍
# (PowerShell 블록 · 대입 · 전체 경로 · 시간 제한 뒤 래퍼 등)은 원장의 후속 항목이다.
# The audit walk only collects channels for commands the walk above (main's, unchanged) already allowed.


def _audit_text(text, depth, channels):
    """허용된 명령 안에서 명령 자리에 선 운영 채널 호출의 채널을 channels 에 더한다 — railway 읽기(쓰기는 적지 않는다) ·
    운영 채널 스크립트. 따옴표 · 주석 · heredoc 데이터 · 정의만 한 PowerShell 블록 안에서 시작하는 단계는 세지 않는다.
    Collect the channels of production-channel calls at command positions in an allowed command; never a verdict."""
    if depth > _PROD_MAX_DEPTH or not text.strip():
        return
    text = _audit_without_heredoc_data(text)
    mask = _audit_mask(text)
    for start, body in _audit_substitutions(text):
        if mask[start:start + 1] in ("c", "d"):
            _audit_text(body, depth + 1, channels)
    offset = 0
    for line in text.split("\n"):
        line_start, offset = offset, offset + len(line) + 1
        for seg_at, segment in _audit_parts(_split_segments(line), line):
            stages = _split_stages(segment)
            for index, (stage_at, stage) in enumerate(_audit_parts(stages, segment)):
                if seg_at is None or stage_at is None:
                    continue
                at = line_start + seg_at + stage_at + len(stage) - len(stage.lstrip())
                if mask[at:at + 1] == "c":
                    _audit_stage(stage, stages[:index], depth, channels)


def _audit_parts(parts, text):
    """분할 조각마다 (text 안의 자리, 조각) — 분할기는 text 의 부분 문자열을 순서대로 낸다. 못 찾았거나 이스케이프된
    구분자(`\\;` · `\\|`) 뒤의 조각은 자리 None 이다(셸은 거기서 나누지 않는다 — 워크플로 셋째 패스).
    Each split part with its offset in text; None when not found or after an escaped separator."""
    escape = "`" if _CONTEXT["shell"] == "powershell" else "\\"
    located, cursor = [], 0
    for n, part in enumerate(parts):
        at = text.find(part, cursor)
        run = 0
        while n and cursor - run - 1 >= 0 and text[cursor - run - 1] == escape:
            run += 1
        located.append((None if at < 0 or run % 2 else at, part))
        cursor = cursor if at < 0 else at + len(part)
    return located


def _audit_stage(stage, earlier, depth, channels):
    """단계 하나의 감사 — 대입 · case 패턴 · 훑는 머리를 벗긴 명령 자리에서 railway 읽기 · 운영 채널 스크립트 · 래퍼 안을 본다.
    Audit one stage at its command position (assignment, case pattern and scan heads peeled off)."""
    stage = _audit_without_prefix(stage)
    if stage is None:
        return
    head, rest = _audit_peel(stage)
    if not head:
        return
    if earlier and _prod_reads_stdin(head, rest):
        # 앞 단계가 내보내는 글자를 이 명령이 돌린다 — `echo railway status | bash` · `"railway status" | iex`
        # earlier stages' text is executed here
        for prior in earlier:
            first, more = _command_words(prior, ps_literal=True)
            _audit_text(" ".join(more) if more else first, depth + 1, channels)
    args = _prod_railway_args(head, rest)
    if args is not None:
        _prod_classify(args, channels)
        return
    if head in _PROD_CHANNEL_SCRIPTS:
        script = _prod_script_channel("python", [head, *rest])  # `./scripts/x.py` — 머리가 곧 스크립트다 / run directly
    else:
        script = _prod_script_channel(head, rest)
    if script:
        channels.append(script)
        return
    inner = _audit_unwrap(head, rest)
    if inner:
        _audit_text(inner, depth + 1, channels)


# PowerShell 대입 — `$x = 명령` · 형 제약 `[string]$x = 명령` 의 오른쪽 명령은 돈다 / an assignment still runs its command
_PS_ASSIGNMENT = re.compile(r"^\s*(?:\[[\w.\[\], ]*\]\s*)*\$[\w:]+\s*[-+*/]?=(?!=)\s*")
# Bash case 갈래 — `case x in` 머리와 `prod)` · `a|b)` 패턴 / a Bash case head and arm pattern
_AUDIT_CASE_HEAD = re.compile(r"^\s*case\s+.+?\s+in\s+")
_AUDIT_CASE_PATTERN = re.compile(r"^\s*\(?[^\s()|;]+(?:\s*\|\s*[^\s()|;]+)*\)\s*")


def _audit_without_prefix(stage):
    """명령 자리 앞의 것을 걷는다 — PowerShell 대입의 왼쪽, Bash case 머리 · 갈래 패턴. PowerShell 에서 블록 · 괄호 식으로
    시작하는 단계는 None(그 몸은 블록 순회가 본다 — `$who = (railway whoami).Trim()` 의 괄호 몸).
    Strip what precedes the command position; None for a PowerShell stage that starts with a block or parentheses."""
    if _CONTEXT["shell"] == "powershell":
        stage = _PS_ASSIGNMENT.sub("", stage, count=1)
        return None if stage.lstrip().startswith(("{", "(", "@(", "$(", "@{")) else stage
    return _AUDIT_CASE_PATTERN.sub("", _AUDIT_CASE_HEAD.sub("", stage, count=1), count=1)


# PowerShell 의 블록 낱말 — 뒤는 조건 · 블록이라 명령 자리가 아니다(블록 몸은 블록 순회가 본다) / PowerShell block keywords
_PS_BLOCK_KEYWORDS = frozenset({"if", "elseif", "else", "foreach", "for", "switch", "while", "until", "do", "try",
                                "catch", "finally"})
# 훑는 머리가 명령 앞에 받는 위치 인자 수 · 값을 받는 옵션 / positionals before the command and value-taking options
_AUDIT_SCAN_POSITIONALS = {"timeout": 1, "gtimeout": 1, "flock": 1}
_AUDIT_SCAN_VALUE_OPTIONS = {
    "timeout": ("-s", "-k", "--signal", "--kill-after"), "gtimeout": ("-s", "-k", "--signal", "--kill-after"),
    "nice": ("-n", "--adjustment"), "ionice": ("-c", "-n", "-p", "--class", "--classdata", "--pid"),
    "xargs": ("-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a", "--max-args", "--max-procs", "--max-lines",
              "--delimiter", "--eof", "--max-chars", "--arg-file"),
    "watch": ("-n", "--interval"), "flock": ("-w", "-E", "--timeout", "--wait", "--conflict-exit-code"),
    "stdbuf": ("-i", "-o", "-e", "--input", "--output", "--error"),
}
# 명령 자리의 낱말을 이어 셸로 돌리는 훑는 머리 / scan heads that run their command words as shell text
_AUDIT_SHELL_TEXT_HEADS = frozenset({"watch", "flock"})


def _audit_words(stage):
    """감사용 낱말 — PowerShell 백슬래시는 글자로 읽고, 앞 대입 · 실행 접두어 · 무리 여는 글자(`{` · `(` · `!`)를 건너뛴다.
    낱말 양끝 괄호는 떼지만 괄호만인 낱말(`{}` — xargs 자리표)은 남긴다(워크플로 셋째 패스: `-I {}` 의 값이 사라졌다).
    Audit words: PowerShell backslashes literal, leading assignments, prefixes and group openers skipped."""
    text = _ps_literal_backslashes(stage)
    try:
        toks = shlex.split(text, posix=True)
    except ValueError:
        toks = text.split()
    words = [tok.strip("(){}") or tok for tok in toks]
    i = 0
    while i < len(words) and (words[i] in ("{", "(", "!") or words[i].lower() in _LISTING_PREFIXES
                              or _ASSIGNMENT.fullmatch(words[i])):
        i += 1
    return words[i:]


def _audit_command_index(head, rest):
    """훑는 머리(`timeout 60` · `if` · `xargs -I {}`)가 돌리는 명령 낱말의 자리 — 옵션 · 그 값 · 앞 위치 인자 · `!` · 실행
    접두어 · `env` · 대입을 건너뛴다. 없으면 None. Where the command a scan head runs starts in rest, or None."""
    values = _AUDIT_SCAN_VALUE_OPTIONS.get(head, ())
    positionals = _AUDIT_SCAN_POSITIONALS.get(head, 0)
    k = 0
    while k < len(rest):
        word = rest[k]
        if (word == "!" or word.lower() in _LISTING_PREFIXES or word.lower() == "env" or _ASSIGNMENT.fullmatch(word)
                or (word.startswith("-") and len(word) > 1)):
            k += 2 if word in values else 1
        elif positionals:
            positionals, k = positionals - 1, k + 1
        else:
            return k
    return None


def _audit_peel(stage):
    """단계의 명령 자리 (머리, 나머지) — 훑는 머리를 겹쳐도 벗긴다(`if timeout 60 railway status` — 워크플로 셋째 패스).
    watch · flock 은 남은 낱말을 셸 글자로 돌리므로 (`sh`, [`-c`, 글자]) 로 낸다. PowerShell 의 블록 낱말 뒤는 명령 자리가
    아니다. The (head, rest) at a stage's command position, nested scan heads peeled."""
    words = _audit_words(stage)
    while words:
        head, rest = _prod_head(_command_name(words[0])), words[1:]
        if head not in _PROD_SCAN_HEADS:
            return head, rest
        if _CONTEXT["shell"] == "powershell" and head in _PS_BLOCK_KEYWORDS:
            return "", []
        k = _audit_command_index(head, rest)
        if k is None:
            return "", []
        if head in _AUDIT_SHELL_TEXT_HEADS:
            return "sh", ["-c", " ".join(rest[k:])]
        words = rest[k:]
    return "", []


def _audit_unwrap(head, rest):
    """래퍼 안쪽 명령 글자 — `_prod_unwrap` 에 Git Bash 의 `cmd //c` 를 더한다 / the wrapped command text."""
    if head == "cmd":
        for k, word in enumerate(rest):
            if word.lower() in ("/c", "/k", "/r", "//c", "//k", "//r"):
                return " ".join(rest[k + 1:])
        return None
    return _prod_unwrap(head, rest)


# 감사의 heredoc 구분자 — 셸은 하이픈 · 점이 든 낱말도 받는다(`<<END-NOTES`), 앞 백슬래시는 따옴표와 같다(`<<\EOF`)
# heredoc delimiters for the audit: any word, a leading backslash quotes it
_AUDIT_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)(\\?[^\s'\"<>|&;()`]+)\1")
_ARITH = "arith"  # `_audit_find_heredoc` 의 산술 괄호 표지 / the arithmetic marker


def _audit_find_heredoc(line):
    """따옴표 밖이거나 명령 치환 안인 heredoc 연산자와, 치환 안이면 그 몸이 시작하는 자리 — (match, 자리 또는 None) 또는
    None. 큰따옴표 속 `$(` 안도 명령이라 센다(커밋 메시지 `"$(cat <<'EOF'` 의 본문은 데이터다). 산술 `$((` · `((` 안의
    `<<` 는 자리 옮김이다. 판정 쪽(`_prod_find_heredoc`, main 그대로)은 따옴표 안을 보지 않는다.
    The heredoc operator outside quotes or inside a command substitution, with that substitution's body start."""
    contexts, i = [], 0  # "'" · '"' · "(" · _ARITH · ("$(", 몸 시작)
    while i < len(line):
        ch = line[i]
        top = contexts[-1] if contexts else None
        if top == "'":
            if ch == "'":
                contexts.pop()
        elif top == '"':
            if ch == '"':
                contexts.pop()
            elif ch == "\\":
                i += 1
            elif line.startswith("$((", i):
                contexts.extend((_ARITH, _ARITH))
                i += 3
                continue
            elif line.startswith("$(", i):
                contexts.append(("$(", i + 2))
                i += 2
                continue
        elif ch in ("'", '"'):
            contexts.append(ch)
        elif ch == "\\":
            i += 1
        elif line.startswith(("$((", "(("), i):
            contexts.extend((_ARITH, _ARITH))
            i += 3 if ch == "$" else 2
            continue
        elif line.startswith("$(", i):
            contexts.append(("$(", i + 2))
            i += 2
            continue
        elif ch == "(":
            contexts.append("(")
        elif ch == ")" and top is not None:
            contexts.pop()
        elif line.startswith("<<<", i):
            i += 3
            continue
        elif line.startswith("<<", i) and _ARITH not in contexts:
            match = _AUDIT_HEREDOC.match(line, i)
            if match:
                starts = [context[1] for context in contexts if isinstance(context, tuple)]
                return match, (starts[-1] if starts else None)
        i += 1
    return None


def _audit_receiver(prefix):
    """heredoc 을 받는 명령의 첫 낱말(PowerShell 백슬래시는 글자) / the head of the command that receives a heredoc."""
    segments = _split_segments(prefix) or [""]
    stages = _split_stages(segments[-1]) or [""]
    return _prod_head(_command_words(stages[-1], ps_literal=True)[0])


def _audit_pipes_into_runner(text):
    """뒤 파이프 단계가 글자를 실행하는가(`cat <<'EOF' | bash` · `'@ | iex`) / does a later stage execute the text?"""
    return any(_prod_runs_text(_prod_head(_command_words(stage, ps_literal=True)[0])) for stage in _split_stages(text)[1:])


def _audit_without_heredoc_data(text):
    """감사용 heredoc · here-string 데이터 빼기 — 판정 쪽(`_prod_without_heredoc_data`, main 그대로)보다 정밀하다. 큰따옴표 속
    명령 치환 안의 heredoc 도 heredoc 이고, 치환 안이면 `EOF)` 로 붙여 쓴 줄에서 닫히며(bash 5.3), 닫는 줄이 없으면 끝까지
    데이터다. 본문을 돌리는 받는 명령(앞부분 전체의 마지막 명령 · 치환 몸의 첫 명령 · 뒤 파이프)이면 본문을 남긴다.
    here-string 을 여는 `@'` · `@"` 는 걷는다 — 남기면 닫히지 않은 따옴표로 보여 뒤가 모두 따옴표 안이 된다(워크플로 셋째 패스).
    Drop heredoc and here-string data for the audit, more precisely than the verdict side."""
    powershell = _CONTEXT["shell"] == "powershell"
    lines = text.split("\n")
    kept, i = [], 0
    while i < len(lines):
        line = lines[i]
        i += 1
        here = _PROD_PS_HERESTRING.search(line) if powershell else None
        found = None if here else _audit_find_heredoc(line)
        match, inner = found if found else (None, None)
        if not here and not match:
            kept.append(line)
            continue
        start = (here or match).start()
        kept.append(line[:start] if here else line)
        runs = (_prod_runs_text(_audit_receiver(line[:start]))
                or (inner is not None and _prod_runs_text(_audit_receiver(line[inner:start])))
                or (match is not None and _audit_pipes_into_runner(line[match.end():])))
        body, closing = [], None
        delimiter = match.group(2).lstrip("\\") if match else None
        while i < len(lines):
            candidate = lines[i]
            if here and candidate.startswith(here.group(1) + "@"):
                closing = candidate[2:]
                break
            if match and candidate.strip() == delimiter:
                closing = ""
                break
            if match and inner is not None and candidate.lstrip("\t").startswith(delimiter + ")"):
                closing = candidate.lstrip("\t")[len(delimiter):]
                break
            body.append(candidate)
            i += 1
        i += 1  # 닫는 줄 / the closing line
        if closing:
            kept.append(closing)  # 닫는 글자 뒤(`)"` · `| iex`)는 명령이다 / what follows the closing mark is a command
            runs = runs or _audit_pipes_into_runner(closing)
        literal = here.group(1) == "'" if here else bool(match.group(1)) or match.group(2).startswith("\\")
        if runs:
            kept.extend(body)
        elif not literal:
            kept.extend(found_body for _, found_body in _audit_substitutions("\n".join(body), string_body=True))
    return "\n".join(kept)


# PowerShell 주석이 시작될 수 있는 앞 글자(낱말 시작) / characters after which `#` begins a PowerShell comment
_PS_COMMENT_AFTER = " \t\n;|&(){}"
# Bash 주석이 시작될 수 있는 앞 글자 / characters after which `#` begins a Bash comment
_BASH_COMMENT_AFTER = " \t\n;|&()<>"


def _audit_substitutions(text, string_body=False):
    """감사용 치환 몸 (자리, 몸) — 판정 쪽(main 그대로)과 달리 주석을 안다: 주석 속 따옴표는 따옴표를 열지 않고 주석 속
    치환은 돌지 않는다(주석의 아포스트로피가 뒤 `$(railway status)` 를 가렸다 — 워크플로 셋째 패스). string_body 면 heredoc ·
    here-string 본문이라 따옴표 · `#` 가 글자다. PowerShell 은 따옴표 · 주석 밖 맨 괄호 · 블록도 낸다(`_ps_code_blocks`).
    Substitution bodies for the audit, comment-aware; in string bodies quotes and `#` are text."""
    powershell = _CONTEXT["shell"] == "powershell"
    openers = ("$(", "@(") if powershell else ("$(", "<(", ">(")
    escape = "`" if powershell else "\\"
    comment_after = _PS_COMMENT_AFTER if powershell else _BASH_COMMENT_AFTER
    bodies, i, quote = [], 0, None
    while i < len(text):
        ch = text[i]
        if quote == "'":
            quote = None if ch == "'" else quote
            i += 1
        elif ch == escape and i + 1 < len(text):
            i += 2
        elif not string_body and quote is None and ch == "'":
            quote = "'"
            i += 1
        elif not string_body and ch == '"':
            quote = None if quote == '"' else '"'
            i += 1
        elif not string_body and quote is None and ch == "#" and (i == 0 or text[i - 1] in comment_after):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif text.startswith(openers, i):
            depth, j = 1, i + 2
            while j < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            bodies.append((i, text[i + 2: j - 1 if depth == 0 else j]))
            i = j
        elif ch == "`" and not powershell:
            end = text.find("`", i + 1)
            end = len(text) if end < 0 else end
            bodies.append((i, text[i + 1:end]))
            i = end + 1
        else:
            i += 1
    if powershell and not string_body:
        bodies.extend(_ps_code_blocks(text))
    return bodies


def _ps_code_blocks(text):
    """PowerShell 의 따옴표 · 주석 밖 맨 바깥 `(…)` · `{…}` 가운데 쓰인 자리에서 도는 것의 (자리, 몸) — 하위 식 · 스크립트
    블록(`Write-Output (railway status)` · `% { railway status }` · if/else 의 블록). 정의만 하는 블록(`$sb = { … }` ·
    `function f { … }`)은 내지 않는다. `$(…)` · `@(…)` 는 위 순회가 내므로 건너뛰고, `${이름}` 은 변수다. 안쪽 블록은 그 몸을
    볼 때 다시 찾는다. Top-level PowerShell (…) and {…} outside quotes and comments that run where written."""
    found, stack, start, i = [], [], 0, 0  # stack — "'" · '"' · "${" · "$(" · "(" · "{"
    closes = {")": ("(", "$("), "}": ("{",)}
    while i < len(text):
        ch = text[i]
        top = stack[-1] if stack else None
        if top == "'":
            if ch == "'":
                stack.pop()
        elif top == "${":
            if ch == "}":
                stack.pop()
        elif ch == "`":
            i += 1  # 이스케이프 — 다음 글자는 글자다 / an escape
        elif top == '"':
            if ch == '"':
                stack.pop()
            elif text.startswith("$(", i):
                stack.append("$(")
                i += 1
        elif ch in ("'", '"'):
            stack.append(ch)
        elif text.startswith("<#", i):
            end = text.find("#>", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        elif ch == "#" and (i == 0 or text[i - 1] in _PS_COMMENT_AFTER):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        elif text.startswith("${", i):
            stack.append("${")
            i += 1
        elif text.startswith(("$(", "@("), i):
            stack.append("$(")
            i += 1
        elif ch in ("(", "{"):
            if not stack:
                start = i
            stack.append(ch)
        elif top is not None and top in closes.get(ch, ()):
            stack.pop()
            if not stack and top in ("(", "{") and _ps_block_runs(text, start):
                found.append((start, text[start + 1:i]))
        i += 1
    if stack and stack[0] in ("(", "{") and _ps_block_runs(text, start):
        found.append((start, text[start + 1:]))  # 닫히지 않은 블록 / an unclosed block runs to the end
    return found


# 블록을 정의만 하는 앞부분 — 대입(`$sb = {`) · 정의(`function f {` · `function f($x) {` · `class C {`)
# what precedes a block that is only defined: an assignment or a definition
_PS_DEFINES_BLOCK = re.compile(
    r"(?i)(?:(?<![=!<>])[-+*/]?=|\b(?:function|filter|workflow|class|enum)\s+[\w:.-]+\s*(?:\([^()]*\))?)\s*$")


def _ps_block_runs(text, start):
    """그 블록이 쓰인 자리에서 도는가 — 정의만 하는 스크립트 블록(`$sb = { … }` · `function f { … }`)이면 False. 해시
    테이블 `@{ … }` 과 괄호 `( … )` 는 만들 때 돈다. Does the block at start run where it is written?"""
    before = text[:start].rstrip(" \t\n")
    return not (text[start] == "{" and not before.endswith("@") and _PS_DEFINES_BLOCK.search(before))


def _audit_mask(text):
    """글자마다의 자리 — c(코드) · s(홑따옴표 · `$'…'`) · d(겹따옴표) · e(겹따옴표 안의 이스케이프된 글자) · m(주석 ·
    PowerShell `<# … #>`) · b(정의만 한 PowerShell 블록 안의 코드). 감사가 단계 · 치환이 코드 자리에서 시작하는지 본다.
    여는 따옴표 글자는 코드 자리다(따옴표로 감싼 실행 파일 경로의 낱말 시작).
    Per-character position for the audit: code, quotes, escaped, comment, code inside a block that is only defined."""
    powershell = _CONTEXT["shell"] == "powershell"
    escape = "`" if powershell else "\\"
    comment_after = _PS_COMMENT_AFTER if powershell else _BASH_COMMENT_AFTER
    states, state, defined, i = [], "c", [], 0  # defined — PowerShell 코드의 `{` 마다 정의만 하는 블록인가
    while i < len(text):
        ch = text[i]
        code = "b" if any(defined) else "c"
        if state == "m":
            state = "c" if ch == "\n" else "m"
            states.append(code if state == "c" else "m")
        elif state == "k":
            if text.startswith("#>", i):
                states.extend("mm")
                state, i = "c", i + 2
                continue
            states.append("m")
        elif state in ("s", "a"):
            if state == "a" and ch == "\\" and i + 1 < len(text):
                states.extend("ss")
                i += 2
                continue
            states.append("s")
            state = "c" if ch == "'" else state
        elif ch == escape and i + 1 < len(text):
            states.extend(("d", "e") if state == "d" else (code, code))
            i += 2
            continue
        elif state == "d":
            states.append("d")
            state = "c" if ch == '"' else "d"
        elif powershell and text.startswith("<#", i):
            states.extend("mm")
            state, i = "k", i + 2
            continue
        elif not powershell and text.startswith("$'", i):
            states.extend((code, code))
            state, i = "a", i + 2
            continue
        elif ch in ("'", '"'):
            states.append(code)
            state = "s" if ch == "'" else "d"
        elif ch == "#" and (i == 0 or text[i - 1] in comment_after):
            states.append("m")
            state = "m"
        elif powershell and ch == "{":
            states.append(code)
            defined.append(not _ps_block_runs(text, i))
        elif powershell and ch == "}" and defined:
            defined.pop()
            states.append("b" if any(defined) else "c")
        else:
            states.append(code)
        i += 1
    return "".join(states)


def decide_mcp_production_access(tool_name):
    """운영 MCP 도구의 운영 접근 사유 — 읽기 도구 · 무관한 서버면 None.
    Production-access reason for a Railway/Supabase MCP tool; None for reads and unrelated servers."""
    if not tool_name.startswith("mcp__") or "__" not in tool_name[5:]:
        return None
    server, tool = tool_name[5:].rsplit("__", 1)
    server = server.lower()
    if "railway" in server:
        return None if tool in _PROD_RAILWAY_MCP_READS else f"Railway MCP `{tool}` — 운영 실행 · 변경"
    if "supabase" in server:
        return None if tool in _PROD_SUPABASE_MCP_READS else f"Supabase MCP `{tool}` — DB SQL · 변경"
    return None


def _mcp_production_channel(tool_name):
    """허용된 운영 MCP 읽기 도구의 감사 채널(`Railway MCP get_logs`) — 운영 MCP 가 아니면 None. 도구 이름은 하네스가
    정한 고정 이름이라 그대로 적고, 도구 입력(배포 ID 등)은 적지 않는다.
    The audit channel of an allowed production MCP read; tool names are fixed identifiers, inputs are never written."""
    if not tool_name.startswith("mcp__") or "__" not in tool_name[5:]:
        return None
    server, tool = tool_name[5:].rsplit("__", 1)
    server = server.lower()
    if "railway" in server and tool in _PROD_RAILWAY_MCP_READS:
        return f"Railway MCP {tool}"
    if "supabase" in server and tool in _PROD_SUPABASE_MCP_READS:
        return f"Supabase MCP {tool}"
    return None


# 거부 기록 — 회고가 정밀도(오탐)를 센다(원장 #1917 M02 P1-5). 값 · 명령 글자는 남기지 않는다: 시각 · 종류 · 사유 ·
# 명령 sha256 · 길이만. 기본 자리는 리포 밖 `~/.scamanager/hook-denials.jsonl`, SCAMANAGER_HOOK_LOG 로 바꾼다.
# Denial records for the retro's precision count: time, kind, reason, command sha256 and length only.
_DENIAL_LOG_ENV = "SCAMANAGER_HOOK_LOG"


def _append_record(env_name, file_name, fields, subject):
    """값 없는 기록 한 줄 — 시각 · fields · 명령 sha256 · 길이. 못 써도 판정은 그대로다(기록은 계기이지 관문이 아니다).
    Append one value-free record (time, fields, command sha256 and length); a write failure never changes the verdict."""
    path = os.environ.get(env_name) or os.path.join(os.path.expanduser("~"), ".scamanager", file_name)
    subject = subject or ""
    line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields,
                       "sha256": hashlib.sha256(subject.encode("utf-8", "replace")).hexdigest(), "len": len(subject)},
                      ensure_ascii=True)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        return  # 기록을 못 써도 판정은 막지도 풀지도 않는다 / logging never decides


def _record_denial(kind, reason, subject):
    """거부 한 줄 / one denial record."""
    _append_record(_DENIAL_LOG_ENV, "hook-denials.jsonl", {"kind": kind, "reason": reason}, subject)


# 감사 기록 — 허용된 운영 채널 호출(railway 읽기 · 운영 MCP 읽기 도구 · 운영 채널 스크립트). 회고가 «읽기 전용 확인» 같은
# 서술을 이 기계 기록과 대 본다(원장 #1917 M02 P2-3 ②). 거부 기록과 같은 값 없는 꼴이고 채널은 고정 어휘뿐이다. 기본 자리는
# 리포 밖 `~/.scamanager/hook-production-allows.jsonl`, SCAMANAGER_HOOK_AUDIT_LOG 로 바꾼다. 막힌 호출은 거부 기록에만 간다.
# Audit records of allowed production-channel calls, so a retro can check narratives against them; value-free.
_AUDIT_LOG_ENV = "SCAMANAGER_HOOK_AUDIT_LOG"


def _record_allowed(channels, subject):
    """허용된 운영 채널 호출 한 줄(채널은 겹치지 않게) / one audit record of an allowed production-channel call."""
    _append_record(_AUDIT_LOG_ENV, "hook-production-allows.jsonl",
                   {"kind": "production-allowed", "channels": list(dict.fromkeys(channels))}, subject)


def _emit_production_deny(tool, reason, subject=""):
    """운영 접근 차단 출력 — 대안(사용자의 `!` 실행 · 자율 읽기)을 늘 함께 알린다.
    Emit the production-access denial, always with the alternative."""
    # 기록에는 « — » 뒤의 정적 범주만 — 앞쪽은 명령 낱말(하위 명령 자리에 온 값 · 둘째 낱말)을 품는다(AntiGravity 교차
    # 검토: `railway --token 값 status` 의 값이 사유째 남았다). 에이전트에게 보이는 사유는 그대로 둔다.
    # The record keeps only the static category after « — »; the part before it embeds command words.
    _record_denial("production", reason.rpartition(" — ")[2], subject or tool)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"[운영 접근] {tool} 실행 차단 — 운영은 행위로 가른다 (CLAUDE.md · 회고 원장 L02)\n\n"
                f"사유: {reason}\n\n"
                "운영 컨테이너 코드 실행 · 운영 변수를 넣은 실행 · 배포 · 변수 · 환경 변경 · 운영 DB 쓰기 SQL 은\n"
                "사용자가 직접 실행한다. 2026-10-25 에 에이전트 측정 코드가 운영 워커 쓰기를 25시간 막았다.\n\n"
                "→ 사용자에게 이 명령과 목적을 보여 주고 `! <명령>` 으로 실행해 달라고 요청하세요.\n"
                f"자율로 되는 읽기: {_PROD_SAFE_READS}\n"
                f"운영 DB 읽기는 관측 역할(허용 컬럼 · 읽기 전용)로 `{_PROD_SAFE_DB_READ}` — 자율.\n"
                "실패한 배포 재시도 · 크래시 재시작은 조건(main 최신 커밋 · CI 초록 · 교체 중 아님)을 확인하는\n"
                f"`{_PROD_SAFE_REDEPLOY}` 로 자율 — `--check` 로 조건부터 본다."
            ),
        }
    }
    print(json.dumps(output, ensure_ascii=True))
    return 0


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


# 판정 불가일 때 막는 표지 — 운영 · 자격에 닿을 수 있는 글자다. 판정이 예외로 끝났거나 입력이 JSON 객체가 아닐 때만 쓴다.
# 부분문자열로 넓게 잡는다 — 틀리면 막는 쪽이고, 막힌 호출은 사유를 보고 사용자 `!` 로 돌린다.
# Markers that deny a call the verdict could not judge (it raised, or the payload was not a JSON object).
# Matched as substrings on purpose: a false hit denies, and the denied call goes to the user's `!`.
#   운영 = railway · supabase · psql · pg_dump · postgres · observe_db · database_url,
#   자격 = env(`.env` · printenv · `Env:` · environ 을 함께 덮는다) · secret · token · password · credential.
_UNJUDGED_MARKERS = ("railway", "supabase", "psql", "pg_dump", "postgres", "observe_db", "database_url",
                     "env", "secret", "token", "password", "credential")


def _emit_unjudged(text, why):
    """판정 불가 — 운영 · 자격 표지가 있으면 deny, 없으면 막지 않고 에이전트(additionalContext) · 사람(systemMessage)에게 알린다.

    훅 고장 하나로 모든 셸이 막히지 않게 표지로 가른다. 훅 프로세스 자체가 죽거나 시간을 넘기면 settings 의
    `onFailure: "block"` 이 그 호출을 막는다. `why` 에는 예외의 이름만 싣는다 — 예외 메시지는 명령 글자를 담을 수 있다.
    The verdict could not be reached: deny when the text carries a production/credential marker, else only say so.
    """
    lowered = (text or "").lower()
    marker = next((m for m in _UNJUDGED_MARKERS if m in lowered), None)
    if marker:
        _record_denial("unjudged", f"판정 불가({why}) · 표지 «{marker}»", text)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"[판정 불가] credential · 운영 접근 훅이 이 호출을 판정하지 못했다({why}) — "
                    f"운영 · 자격 표지 «{marker}» 가 있어 막는다.\n\n"
                    "→ 사용자에게 이 명령과 목적을 보여 주고 `! <명령>` 으로 실행해 달라고 요청하거나, "
                    "훅(.claude/hooks/block_credential_dump.py)을 워크트리에서 고친 뒤 다시 시도하세요."
                ),
            }
        }
    else:
        note = (f"⚠️ credential · 운영 접근 훅이 이 호출을 판정하지 못했다({why}) — 운영 · 자격 표지가 없어 막지 않았다. "
                "훅(.claude/hooks/block_credential_dump.py)을 고쳐야 한다.")
        output = {"systemMessage": note,
                  "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}
    print(json.dumps(output, ensure_ascii=True))
    return 0


def main():
    _make_stdout_safe()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (ValueError, RecursionError):  # JSONDecodeError 포함 · 아주 깊은 중첩은 RecursionError / deep nesting
        payload = None
    if not isinstance(payload, dict):
        return _emit_unjudged(raw, "입력이 JSON 객체가 아니다")
    try:
        return _judge(payload)
    except Exception as exc:  # pylint: disable=broad-exception-caught  # 판정 불가는 표지로 가른다 / unjudged → markers
        # 표지는 받은 글자 그대로에서 찾는다 — 여기서 다시 직렬화하면 그 자체가 또 죽을 수 있다(깊은 중첩).
        # Scan the text as received; re-serializing here could fail again (deep nesting).
        return _emit_unjudged(raw, type(exc).__name__)


def _judge(payload):
    """판정 본체 — 출력(deny JSON)을 내고 0 을 돌려준다. 예외는 main() 이 «판정 불가» 로 받는다.
    The verdict proper; main() turns any exception into an unjudged outcome."""
    tool = payload.get("tool_name") or ""
    if _MCP_DUMP_TOOLS.fullmatch(tool):
        found = ("Railway MCP list_variables — 서비스 변수 값(KEY=VALUE) 덤프", _SAFE_IDIOM)
    elif tool in _SHELL_TOOLS:
        command = (payload.get("tool_input") or {}).get("command") or ""
        found = decide_with_hint(command, payload.get("cwd"),
                                 "powershell" if tool == "PowerShell" else "bash")
        # credential 판정이 먼저(값 노출엔 더 구체적인 안내가 있다) — 통과한 명령만 운영 접근을 본다. 같은 순회에서
        # 허용한 운영 채널 호출을 모아 감사 기록으로 남긴다(원장 #1917 M02 P2-3 ②).
        # The credential verdict first (more specific guidance for value leaks); then production access, whose
        # walk also collects the allowed production-channel calls for the audit record.
        channels = []
        production = None if found else decide_production_access(command, channels=channels)
        if production:
            return _emit_production_deny(tool, production, command)
        if found is None and channels:
            _record_allowed(channels, command)
    else:
        production = decide_mcp_production_access(tool)
        if production:
            return _emit_production_deny(tool, production)
        channel = _mcp_production_channel(tool)
        if channel:
            _record_allowed([channel], tool)
        return 0
    if found is None:
        return 0
    reason, hint = found
    _record_denial("credential", reason, (payload.get("tool_input") or {}).get("command") or tool)
    if hint == _SAFE_CONFIG:
        safe = f"배포 설정은 변수 값을 뺀 읽기로 보세요:\n  {_SAFE_CONFIG}\n\n"
    elif hint == _SAFE_ENV:
        safe = f"변수 하나만 필요하면 그 이름으로 읽으세요:\n  {_SAFE_ENV}\n\n"
    elif hint == _SAFE_DOTENV:
        safe = f".env 는 값 없이 확인하세요:\n  {_SAFE_DOTENV}\n\n"
    elif hint == _SAFE_SEARCH:
        safe = f"재귀 검색은 .env 를 건너뛰는 방법으로:\n  {_SAFE_SEARCH}\n\n"
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
