"""Dockerfile·시작 명령을 **구조로** 읽는 최소 파서 — 배포 계약 테스트 공용.

Minimal structural readers for the Dockerfile and start commands, shared by the deploy-contract tests.

🔴 주석 줄은 버린다. 주석 산문이 설치 검사를 만족시키면 안 된다 — 조달 가드가 한 번
`echo 'WARNING: tsc … disabled'` 산문에 속아, 설치를 지워도 초록이었다.
Comment lines are dropped so prose can never satisfy an install check.
"""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
RAILWAY_TOML = ROOT / "railway.toml"

_DEFAULT_SHELL = ["/bin/sh", "-c"]
_SHELLS = {"sh", "bash", "dash"}
# `$PORT` · `${PORT}` · `${PORT:-8000}` — 셸이 확장하는 형태만.
# Only forms a shell expands.
_PORT_REF = re.compile(r"^\$(?:PORT|\{PORT(?::-\d+)?\})$")
# 명령을 가르는 셸 연산자 — 리다이렉션(`>`)은 명령 경계가 아니다.
# Shell operators that start a new command; redirections do not.
_SEPARATORS = {"&&", "||", "|", ";", "(", ")"}


def instructions(text: str) -> list[tuple[str, str]]:
    """(지시어 대문자, 인자) 목록. 줄 이음(`\\`)을 잇고 주석 줄은 버린다.

    Docker 와 같게 이음 **안쪽**의 주석 줄도 버린다.
    """
    out: list[tuple[str, str]] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#") or (not line and not buf):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        keyword, _, args = buf.strip().partition(" ")
        out.append((keyword.upper(), args.strip()))
        buf = ""
    if buf.strip():
        keyword, _, args = buf.strip().partition(" ")
        out.append((keyword.upper(), args.strip()))
    return out


def run_steps(text: str) -> list[str]:
    """RUN 지시어 인자를 순서대로 — 설치 검사는 이것만 본다(주석·산문 제외)."""
    return [args for keyword, args in instructions(text) if keyword == "RUN"]


def invocations(script: str) -> list[list[str]]:
    """셸 스크립트 한 덩어리에서 **실행되는 명령마다의 argv** 를 순서대로.

    따옴표 안의 `;` 는 명령 경계가 아니다(`python -c "a; b"`) — 그래서 shlex 로 자른다.
    Quoted `;` is not a boundary, so this tokenises with shlex rather than splitting on text.
    """
    lexer = shlex.shlex(script, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    calls: list[list[str]] = [[]]
    for token in lexer:
        if token in _SEPARATORS:
            calls.append([])
        else:
            calls[-1].append(token)
    return [argv for argv in calls if argv]


def start_argv(text: str) -> list[str] | None:
    """이미지 기본 시작 명령의 argv — Docker 가 실제로 exec 하는 형태.

    마지막 CMD 만 유효하다. exec 형(JSON 배열)은 그대로, shell 형은 그 시점의 SHELL
    (기본 `/bin/sh -c`)로 감싼다. CMD 가 없으면 None.
    The last CMD wins; shell form is wrapped in the SHELL in effect at that point.
    """
    shell = list(_DEFAULT_SHELL)
    argv: list[str] | None = None
    for keyword, args in instructions(text):
        if keyword == "SHELL":
            shell = json.loads(args)
        elif keyword == "CMD":
            argv = json.loads(args) if args.startswith("[") else [*shell, args]
    return argv


def shell_script(argv: list[str]) -> str | None:
    """argv 가 셸 래핑(`sh … -c <script>`)이면 그 스크립트, 아니면 None."""
    if not argv or Path(argv[0]).name not in _SHELLS or "-c" not in argv:
        return None
    i = argv.index("-c")
    return argv[i + 1] if i + 1 < len(argv) else None


def uvicorn_argv(argv: list[str]) -> list[str] | None:
    """셸 스크립트 안의 uvicorn 호출 argv(선행 `exec` 제거). 셸 래핑이 아니면 None."""
    script = shell_script(argv)
    if script is None:
        return None
    tokens = shlex.split(script)
    if tokens[:1] == ["exec"]:
        tokens = tokens[1:]
    return tokens if tokens[:1] == ["uvicorn"] else None


def serves_injected_port(argv: list[str] | None) -> bool:
    """🔴 시작 명령이 Railway 가 주입한 `$PORT` 에서 듣는가.

    exec 형은 변수를 확장하지 않는다(Railway 문서) — `$PORT` 가 **글자 그대로** uvicorn 에
    간다. 그래서 셸 래핑이고 그 안의 `--port` 값이 PORT 참조일 때만 참이다.
    Exec form never expands variables, so only a shell-wrapped uvicorn with a PORT ref qualifies.
    """
    tokens = uvicorn_argv(argv or [])
    if tokens is None or "--port" not in tokens:
        return False
    i = tokens.index("--port")
    return i + 1 < len(tokens) and bool(_PORT_REF.match(tokens[i + 1]))


def without_port_value(tokens: list[str]) -> list[str]:
    """`--port` 값만 뺀 uvicorn argv — 두 시작 명령의 나머지 플래그를 대조할 때 쓴다."""
    i = tokens.index("--port")
    return tokens[:i + 1] + tokens[i + 2:]


def all_invocations(text: str) -> list[list[str]]:
    """모든 RUN 의 명령 argv 를 빌드 순서대로 이어 붙인 것."""
    return [argv for script in run_steps(text) for argv in invocations(script)]


def apt_installs(argv: list[str]) -> set[str]:
    """이 argv 가 `apt-get install` 이면 설치 패키지 집합, 아니면 빈 집합."""
    if argv[:2] != ["apt-get", "install"]:
        return set()
    return {w for w in argv[2:] if not w.startswith("-")}


def dockerignore_patterns() -> list[str]:
    """`.dockerignore` 의 유효 패턴(주석·빈 줄 제외)."""
    return [
        line.strip() for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
