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
"""
import fnmatch
import functools
import json
import os
import re
import shlex
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


def _command_words(stage):
    """명령 자리의 (첫 낱말 소문자, 나머지 낱말) — 앞쪽 대입 · 실행 접두어 · 괄호 · 경로 · .exe 를 걷어 낸다.
    (head lower-cased, rest) at the command position; assignments, prefixes, parens, paths and .exe stripped."""
    try:
        toks = shlex.split(stage, posix=True)
    except ValueError:
        toks = stage.split()
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
        if not _is_railway(toks[i]) or toks[i + 1].lower() not in ("ssh", "run", "local"):
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
_REDIRECT_TARGET = re.compile(r">>?\s*(['\"]?)[^\s'\";|&()<>]+\1")
_DOTENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})
_DOTENV_SAFE_HEADS = frozenset({
    "cp", "mv", "ls", "dir", "rm", "del", "touch", "test", "[", "[[", "stat", "chmod", "attrib",
    "test-path", "copy-item", "move-item", "remove-item", "new-item", "get-item", "get-childitem",
    "set-content", "add-content", "out-file",
})
_GIT_SAFE_SUBCOMMANDS = frozenset({"check-ignore", "ls-files", "status"})
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
    are dropped only for commands that really have such options."""
    text = text.replace("\\", "/")
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
        tok = _TOKEN_WRAPPERS.sub("", raw.strip("`"))
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
    """쓰기 대상을 뺀 나머지에 .env 꼴 경로가 있는가 / A .env-like path outside write targets?"""
    return _has_dotenv_path(_REDIRECT_TARGET.sub(" ", stage))


def _reads_dotenv(stage):
    """단계가 .env 내용을 출력할 수 있는가 / Can this stage print .env contents?"""
    if not _mentions_dotenv(stage) or _count_only_grep(stage):
        return False
    head, words = _command_words(_REDIRECT_TARGET.sub(" ", stage))
    if head in _DOTENV_SAFE_HEADS:
        return False
    return not (head == "git" and words and words[0].lower() in _GIT_SAFE_SUBCOMMANDS)


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
_WALK_SKIP = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
                        ".pytest_cache", ".ruff_cache", ".tox"})
# 검색 명령 — 단계의 첫 낱말이 아니어도 찾는다(env · timeout · sudo · if · do · ! 같은 접두 뒤, 14차 반영 중 실측).
# Search commands, found anywhere in the stage (past env, timeout, sudo, if, do, ! and other prefixes).
_SEARCH_COMMANDS = frozenset({"grep", "egrep", "fgrep", "rgrep", "rg", "findstr"})


def _plain_words(text):
    """shlex 낱말 — 백슬래시는 / 로, 괄호 · 치환 껍데기는 벗기고 빈 것은 뺀다.
    shlex words with backslashes as slashes and grouping/substitution wrappers peeled."""
    text = text.replace("\\", "/")
    try:
        toks = shlex.split(text, posix=True)
    except ValueError:
        toks = text.split()
    return [w for w in (_TOKEN_WRAPPERS.sub("", t.strip("`")) for t in toks) if w]


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
    if _unresolvable(target):
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
    words = _plain_words(stage)
    for k, word in enumerate(words):
        name = _command_name(word)
        if name not in _SEARCH_COMMANDS:
            continue
        before = [_command_name(w) for w in words[:k]]
        return ("git-grep" if "git" in before else name), words[k + 1:], words[:k]
    return None


def _search_targets(words):
    """패턴 다음의 위치 인자 = 검색 대상. -e · -f 로 패턴을 주면 첫 위치 인자부터 대상이다.
    Positional arguments after the pattern; with -e/-f every positional argument is a target."""
    positional, skip, pattern_given = [], False, False
    for w in words:
        if skip:
            skip = False
        elif w in _GREP_VALUE_OPTIONS:
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


def _rg_reads(parts, globs, no_ignore, hidden):
    """rg 가 그 파일을 읽는가 — 포함 글롭이 맞으면 무시 · 숨김 규칙을 넘어 읽고(재정의가 가장 먼저), 포함 글롭이
    있는데 안 맞으면 안 읽는다. 제외 글롭이 이름에 맞으면 안 읽는다. 그 밖은 무시 해제일 때만, 숨김(점으로 시작)은
    숨김 포함일 때만 읽는다. 숨김 폴더는 숨김 포함이거나 그 폴더를 집는 포함 글롭이 있을 때만 내려간다.
    .env 꼴은 .gitignore 에 있다고 본다(가정 — 아니면 rg 기본값도 읽는다).
    Would rg read this file? Include globs override ignore and hidden rules; .env-like files are assumed
    to be gitignored."""
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
    return no_ignore and (hidden or not name.startswith("."))


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
    Would a recursive search read a .env-like file under its targets (across every cwd candidate)?"""
    call = _search_call(stage)
    if call is None:
        return False
    name, args, before = call
    if name == "findstr":
        return _findstr_reads_dotenv(args)
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
    for target in _search_targets(args) or ["."]:
        files = _dotenv_files(target)
        if files is None or any(reads(parts) for parts in files):
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
    """이스케이프 · 주석이 없고 따옴표가 모두 닫혔는가 — 주석 속 홑따옴표(`# it's`)를 따옴표로 읽으면 뒤
    명령이 묶인다(보안 리뷰 HIGH). No escapes or comments, and every quote closed?"""
    if "\\" in text or "`" in text or "#" in text:
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
    stages = _split_stages(segment)
    # 🔴 `#` 이 있으면 그 뒤가 주석일 수 있다 — `--kv # | cut -d= -f1` 의 cut 은 실행되지 않는다(Grok G1).
    #    단계 분해는 주석을 모르므로, `#` 이 든 세그먼트에서는 어떤 중화도 인정하지 않는다.
    # A `#` may start a comment («--kv # | cut» never runs the cut), so no neutralizer counts there.
    commented = "#" in segment
    # 나열 → 내용 읽기 파이프라인(`Get-ChildItem [-Recurse] | Select-String`) — 단계 하나로는 안 보인다.
    # A listing piped into a content reader is only visible across stages.
    if len(stages) > 1 and _listing_pipeline_reads_dotenv(stages):
        return "나열 → 내용 읽기 — .env 까지 읽는다", _SAFE_SEARCH
    for i, stage in enumerate(stages):
        for matcher, reason, neutralizers, hint in _BLOCKED:
            hit = matcher(stage)
            # 🔴 .env 를 다루는 «안전한» 명령도 출력이 다음 단계로 넘어가면 읽기다(`ls .env | xargs cat` ·
            #    `Get-Item .env | Get-Content` — 보안 리뷰 지적). 안전은 파이프라인의 마지막 단계일 때만.
            # A "safe" .env command whose output flows to a next stage is a read; safe only as the last stage.
            if not hit and matcher is _reads_dotenv and i + 1 < len(stages) and _mentions_dotenv(stage):
                hit = True
            if hit and (commented or not _neutralized(stages, i, neutralizers)):
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
    for segment in segments:
        _follow_directory_change(segment)
    for segment in segments:
        found = _decide_segment(segment)
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


def _prod_classify(args):
    """railway 인자 → None(읽기 · 도움말) 또는 운영 접근 사유 / None for reads and help, else the reason.
    🔴 Grok 반례(11-11) 세 가지를 막는다: 하위 명령 앞 `--` 는 옵션 끝일 뿐이다(`railway -- redeploy` 도 재배포),
    안쪽 명령의 `--version` 은 railway 의 도움말이 아니다(`railway ssh node --version` 은 운영에서 node 를 돈다),
    `-s api` 같은 옵션 값은 둘째 낱말이 아니다(`railway domain -s api list` 는 읽기).
    Grok counterexamples: a leading `--` only ends options; the inner command's --version is not railway's;
    option values are not the second word."""
    k, lead = 0, []
    while k < len(args) and args[k].startswith("-"):
        lead.append(args[k])
        k += 2 if args[k] in _PROD_VALUE_OPTIONS else 1
    if any(word in _PROD_HELP_FLAGS for word in lead):
        return None
    if k >= len(args):
        return None  # `railway` 홀로 · 옵션만 = 도움말 / bare railway prints help
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
        return None
    if sub in _PROD_READ_SUBCOMMANDS:
        return None
    if sub in _VARIABLE_ALIASES:
        return f"railway {sub} — 서비스 변수 변경" if _prod_variable_writes(args[k:]) else None
    pair = _PROD_READ_PAIRS.get(sub)
    if pair is not None:
        second = rest[positions[0]].lower() if positions else ""
        return None if second in pair else f"railway {sub} {second}".rstrip() + " — 운영 상태 변경"
    return f"railway {sub} — {_PROD_REASONS.get(sub, '운영 접근(허용 목록 밖)')}"


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


def decide_production_access(command, shell=None):
    """명령이 운영에 닿는가 — 사유 또는 None. 세그먼트 · 명령 치환 · 알려진 래퍼 안까지 본다.
    railway 를 «언급» 만 하는 명령(`grep "railway ssh"`)은 명령 자리가 아니라 통과한다.
    🔴 위협 모형은 credential 판정과 같다 — 정직한 세션이 칠 만한 꼴을 막는다. 스크립트 파일 안의 호출 ·
    인코딩된 명령 같은 의도적 우회는 글자 훅 밖이다(원장 R-3 부류).
    Does the command touch production? Mentions are not invocations. Same threat model as the credential
    verdict: honest shapes are covered; calls inside script files or encoded commands are out of reach."""
    if shell is not None:
        _CONTEXT["shell"] = shell
    return _prod_decide_text(command or "", 0)


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


def _emit_production_deny(tool, reason):
    """운영 접근 차단 출력 — 대안(사용자의 `!` 실행 · 자율 읽기)을 늘 함께 알린다.
    Emit the production-access denial, always with the alternative."""
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
        found = decide_with_hint(command, payload.get("cwd"),
                                 "powershell" if tool == "PowerShell" else "bash")
        # credential 판정이 먼저(값 노출엔 더 구체적인 안내가 있다) — 통과한 명령만 운영 접근을 본다
        # The credential verdict first (more specific guidance for value leaks); then production access.
        production = None if found else decide_production_access(command)
        if production:
            return _emit_production_deny(tool, production)
    else:
        production = decide_mcp_production_access(tool)
        return _emit_production_deny(tool, production) if production else 0
    if found is None:
        return 0
    reason, hint = found
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
