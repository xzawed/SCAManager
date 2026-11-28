#!/usr/bin/env python3
"""공개 쓰기 전에 비밀값 · 개인정보 꼴을 센다 — 값은 찍지 않는다 (회고 원장 #1917 M02 P2-6).

리포는 공개다. Issue · PR 본문 · 댓글은 올리는 순간 공개되고 편집 이력에 남는다. 그래서 올리기 **전에** 잰다.

- 파일 검사: `py -3 scripts/scan_publish.py <파일>...` — 파일마다 꼴별 개수를 찍고, 하나라도 있으면 exit 1.
- 훅: `.claude/settings.json` PreToolUse(`if: Bash(gh *)` · `PowerShell(gh *)` — gh 명령에만 뜬다 · `onFailure: "block"`).
  명령 글자 전체와 그 명령이 가리키는 본문 파일(`--body-file` · `-F` · `--notes-file` · api 의 `key=@파일` · `--input`)을 재고,
  꼴이 있으면 deny 한다(종류 · 개수만 알린다). 경로를 못 풀거나 파일을 못 읽으면 막는다(못 재면 red). 게시될 인라인 글
  (`--body` · `--title` · api 필드 · gist 설명 · 머지 제목)의 변수도 같은 명령 안의 글자 대입으로 못 풀면 막는다.

꼴(`_KINDS`)은 이름 · 개수로만 쓰인다 — 맞은 글자는 어디에도 찍지 않는다. 시험 = `tests/unit/scripts/test_scan_publish.py`.
Count secret / personal-data shapes before a public write; values are never printed.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

# 꼴 — 종류 이름 → 정규식. DB 주소 꼴은 `.pre-commit-config.yaml` 의 `check-db-url-in-diff` 와 같은 식이다(시험이 대조한다).
# Shapes: kind → regex. The DB URL shape is the same expression as the pre-commit `check-db-url-in-diff` hook.
_KINDS = {
    "anthropic-key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "openai-key": r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{32,}",
    "github-token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}",
    "db-url-with-password": (
        r"postgres(?:ql)?(?:\+\w+)?://[^:/\s\"'@]+:"
        r"(?!(?:\$?\{[^}]*\}|<[^>]*>|\*+|x+|\.\.\.)@)[^@\s\"'/]+@"
        r"(?!(?:localhost|127\.0\.0\.1|host|db|postgres|<[^>]*>|\$?\{[^}]*\}"
        r"|[^/:?#\s\"',;)>\]]*\.example\.(?:com|org|net))(?::[0-9]*)?"
        r"(?:,(?:localhost|127\.0\.0\.1|host|db|postgres|<[^>]*>|\$?\{[^}]*\}"
        r"|[^/:?#\s\"',;)>\]]*\.example\.(?:com|org|net))(?::[0-9]*)?)*"
        r"(?:[/?#\"'\s;)>\]]|,(?=[\s\"')]|$)|$))"
        r"(?:[^/?#\s\"']+|(?=[/?]))"
    ),
    "jwt": r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}",
    "telegram-bot-token": r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b",
    "slack-token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "aws-key": r"\bAKIA[0-9A-Z]{16}\b",
    "private-key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    # 이름 «안에» 비밀 낱말이 든 대입(`SESSION_SECRET=…` · `"SMTP_PASS": "…"`) — 접두 이름을 놓쳤다(원장 #1940 M03 P1-14).
    # 값은 숫자가 든 16자 이상이거나, 한 가지 대소문자 글자만 16자 이상이다(Gmail 앱 비밀번호 · 패스프레이즈) — 템플릿
    # 자리표시자(`your_webhook_secret_here`) · 코드 이름(`settings.x` · camelCase 호출 `getApiToken()`)은 값이 아니다.
    # 굽은 따옴표도 따옴표다(Grok M03 1 · 2차 반례).
    # A value holds a digit, or is 16+ single-case letters; placeholders and code names (dotted, camelCase calls) are not.
    "assigned-secret": (r"(?i)(?<![A-Za-z0-9])[A-Z0-9_]*(?:SECRET|TOKEN|PASS|API_KEY|ENCRYPTION_KEY)[A-Z0-9_]*[\"'“”‘’]?"
                        r"\s*[=:]\s*[\"'“”‘’]?(?:(?=[A-Za-z0-9+/_-]*\d)[A-Za-z0-9+/_-]{16,}"
                        r"|(?-i:[a-z]{16,}|[A-Z]{16,})(?![A-Za-z0-9+/_(-]|\.[A-Za-z0-9_]))"),
    # 사람 주소 — 공개용 주소(noreply · 예시 · git SSH)는 아래 `_PUBLIC_EMAIL` 이 뺀다.
    "email": r"(?<![\w.+%-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b",
    # 개인 홈 경로(사용자 이름이 든다) — CI 러너 경로(Linux `runner` · Windows `runneradmin`)는 사람 것이 아니다. 대소문자를
    # 가리지 않는 것은 Windows 쪽뿐이다 — 통째로 가리지 않으면 API 경로 `/api/users/me` 가 macOS 홈으로 읽혔다.
    # CI runner homes are not personal; case-insensitive on the Windows side only (else `/api/users/me` read as a home).
    "local-home-path": (r"\b[A-Za-z]:[\\/]+(?i:users)[\\/]+(?!(?i:runneradmin)\b)[^\\/\s\"'`]+"
                        r"|(?<![A-Za-z]:)/Users/(?!runner\b)[^/\s\"'`]+|/home/(?!runner\b)[^/\s\"'`]+"),
}
# 경계(`\b` · `\w`)는 ASCII 로 본다 — 유니코드로 보면 값 앞뒤에 붙은 한글(조사 · 낱말)이 낱말 글자라 경계가 사라져 놓쳤다
# (원장 #1940 M03 P1-16). / Boundaries are ASCII: Hangul glued to a value erased a Unicode `\b`.
_COMPILED = {kind: re.compile(rx, re.ASCII) for kind, rx in _KINDS.items()}
# 공개해도 되는 주소 — 커밋 서명용 noreply · 예시 도메인 · git SSH 원격.
# Public addresses: noreply signatures, example domains, the git SSH remote.
_PUBLIC_EMAIL = re.compile(r"(?i)^(?:noreply@anthropic\.com|[^@]+@users\.noreply\.github\.com|[^@]+@example\.(?:com|org|net)"
                           r"|git@github\.com)$")

_MAX_BYTES = 2_000_000


# URL 의 사용자 자리(`scheme://user:pass@` · `scheme://user@`) 바로 뒤의 `…@호스트` 는 사람 주소가 아니다.
# The `…@host` right after a URL user-info is not a personal address.
_URL_USERINFO_BEFORE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/@]*$")


def count_kinds(text: str, only: tuple[str, ...] | None = None, skip: tuple[str, ...] = ()) -> dict[str, int]:
    """꼴별 개수(0 은 뺀다) — 맞은 글자는 돌려주지 않는다. / Per-kind counts, zeros omitted; never the matches."""
    text = text or ""
    counts = {}
    for kind, rx in _COMPILED.items():
        if kind in skip or (only is not None and kind not in only):
            continue
        if kind == "email":
            hits = [m for m in rx.finditer(text) if not _PUBLIC_EMAIL.match(m.group(0))
                    and not _URL_USERINFO_BEFORE.search(text[max(0, m.start() - 300):m.start()])]
        else:
            hits = rx.findall(text)
        if hits:
            counts[kind] = len(hits)
    return counts


def _add(total: dict[str, int], more: dict[str, int]) -> None:
    for kind, n in more.items():
        total[kind] = total.get(kind, 0) + n


def _summary(counts: dict[str, int]) -> str:
    return " · ".join(f"{kind} {n}" for kind, n in sorted(counts.items()))


# --- 훅: gh 명령이 가리키는 본문 ------------------------------------------------------------------------------
# --- hook: the bodies a gh command points at ---

# heredoc 본문은 게시될 글이다 — 따로 꺼내 재고, 낱말로 나눌 때는 본문 · 끝 표시만 표지로 바꾼다(그 안의 따옴표가 나누기를
# 깨뜨린다). 여는 줄의 나머지(`<<'EOF' --title …` · `| gh …`)는 그 명령의 인자 · 다음 단계라 남긴다. 끝 표시는 bash 처럼
# 낱말 전체(`END-MARK` 는 `END` 가 아니다)가 그 줄에 정확히 있어야 끝난다(`<<-` 만 앞 탭을 허용). fd 접두(`3<<`)가 0 이
# 아니면 stdin 이 아니다. 끝 표시에 따옴표가 없으면 bash 가 본문을 펼친다 — 인라인 글과 같은 규칙으로 판정한다.
# Heredoc bodies are published text: replace only body + terminator with a marker (the rest of the operator line is still
# arguments / the next stage). The terminator is the whole word alone on its line (only `<<-` strips leading tabs);
# a non-zero fd prefix is not stdin; an unquoted delimiter means bash expands the body.
_HEREDOC = re.compile(
    r"(?:(?:(?<=[\s;&|(])|^)(?P<fd>\d+|\{[A-Za-z_]\w*\}))?(?<!<)<<(?!<)(?P<dash>-)?[ \t]*(?P<quote>['\"]?)"
    r"(?P<delim>[A-Za-z_]\w*)(?P=quote)(?=[\s;&|<>()]|$)(?P<tail>[^\n]*)\n(?:(?P<body>.*?)\n)??(?(dash)\t*)(?P=delim)"
    r"(?=\n|$)", re.S | re.M)
_HEREDOC_MARK = "<<\0heredoc\0"            # fd 0 의 heredoc / a heredoc on stdin
_OTHER_FD_HEREDOC_MARK = "\0fd-heredoc\0"  # 다른 fd 의 heredoc — stdin 이 아니다 / a heredoc on another fd
# 이 검사가 끝 표시를 못 읽어 남은 heredoc 연산자 — here-string(`<<<`) · 표지는 아니다.
# A heredoc operator left unparsed — neither a here-string (`<<<`) nor the marker.
_UNPARSED_HEREDOC = re.compile(r"(?<!<)<<(?![<\0])")
# stdin 연산자 — 따옴표를 가린 글자에서 찾는다. 숫자 · `{이름}` 접두는 낱말 머리일 때만 fd 다(`x3<f` 의 3 은 낱말 글자).
# `{이름}<…` 은 새 fd 를 열어 이름에 담는다 — stdin 이 아니다.
# stdin operators, searched in quote-masked text; a digit or `{name}` prefix is an fd only at the start of a word.
_FD_PREFIX = r"(?:(?:(?<=[\s;&|(])|^)(?P<fd>\d+|\{[A-Za-z_]\w*\})|(?<![<>&}]))"
_HERE_STRING_OP = re.compile(_FD_PREFIX + r"<<<[ \t]*", re.M)
_STDIN_REDIRECT_OP = re.compile(_FD_PREFIX + r"(?<!<)<(?P<op>[&>]?)(?![<(])[ \t]*", re.M)
# 셸 낱말 하나(붙어 있는 따옴표 조각을 이은 것)와 그 조각들. / One shell word (adjacent quoted pieces joined) and its pieces.
_SHELL_WORD = re.compile(r"(?:'[^']*'|\$'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\\.|[^\s;&|<>()'\"\\])+", re.S)
_WORD_PIECE = re.compile(r"'(?P<single>[^']*)'|\$'(?P<ansi>(?:[^'\\]|\\.)*)'|\"(?P<double>(?:[^\"\\]|\\.)*)\""
                         r"|\\(?P<escaped>.)|(?P<bare>[^\s;&|<>()'\"\\]+)", re.S)
_SIMPLE_WORD = re.compile(r"\"[^\"\\]*\"|'[^']*'|[^\s;&|<>()'\"\\]+")
# `cat <<EOF | gh … -` — 파이프 앞 단계가 heredoc 하나만 받는 cat 이면 stdin 은 그 heredoc 본문이다(따로 잰다).
# A previous pipeline stage that is a bare `cat <<EOF` feeds that heredoc body (measured separately).
_CAT_HEREDOC_STAGE = re.compile(r"(?:^|[;&|(\n])[ \t]*cat[ \t]+" + re.escape(_HEREDOC_MARK) + r"[ \t]*\|[ \t]*$")
# gh 호출의 시작 — 명령 낱말이 맨 `gh` · 경로(`/usr/bin/gh` · `$HOME/bin/gh` · `C:/…/gh.exe`) · `\gh` · 따옴표로 감싼 것
# (`"C:/Program Files/GitHub CLI/gh.exe"`)인 자리. 끝은 그 자리부터 따옴표를 가린 글자에서 첫 구분자(`\n` · `;` · `&` · `|`)
# 까지다 — 따옴표 안의 `|`(jq 필터 · 검색어)는 구분자가 아니다. 앞쪽 글자의 따옴표 상태에 휘둘리지 않게 gh 자리부터 새로 가린다.
# Where a gh call starts (bare, path-qualified, backslashed or quoted); it ends at the first unquoted separator.
_GH_WORD = (r"(?:\\?(?:[^\s;&|()<>'\"`]*[/\\])?gh(?:\.exe)?"
            r"|\"(?:[^\"`]*[/\\])?gh(?:\.exe)?\""
            r"|'(?:[^']*[/\\])?gh(?:\.exe)?')")
_GH_START = re.compile(r"(?:^|(?<=[\s;&|(]))" + _GH_WORD + r"\s+")
# 명령 어디든 gh 낱말이 있는가 — 없을 때만 «gh 없음» 이다(경로 · 따옴표 · `$(which gh)` · 인자 안의 gh 모두 «있음»).
# 대소문자를 가리지 않는다 — Windows 는 `GH` 도 gh.exe 로 돌린다(Grok 42e755c9). 호출 판정(`_GH_START`)은 가린다: 제목 속
# «GH Actions» 같은 글자를 호출로 읽지 않게.
# Any gh word anywhere, case-insensitive (Windows runs `GH`); only its absence means no gh call.
_ANY_GH_WORD = re.compile(r"(?<![\w-])gh(?![\w-])", re.I)
# 본문 파일 플래그 — 알아본 gh 호출 밖에 있으면 누가 그 파일을 게시하는지 모른다(`GH … --body-file f` · `bash -c "gh … --body-file f"`).
# A body-file flag outside every recognised gh call: whoever reads that file is unknown.
_BODY_FILE_FLAG = re.compile(r"(?<![\w-])--body-file(?![\w-])")
# gh 를 변수 · 명령 치환으로 부르는 꼴 — 경로를 찾아 쓰거나(`$(which gh)` · `$(command -v gh)` · `(Get-Command gh)`) 변수에
# 담는다(`G=gh` · `G=/usr/bin/gh`). 그 호출의 인자는 낱말로 못 가린다.
# gh reached through a lookup substitution or a variable; its arguments cannot be told apart.
_GH_INDIRECT = re.compile(
    r"(?:\$\(|`|\()\s*(?:which|command\s+-v|type\s+-[pP]|where(?:\.exe)?|Get-Command)\s+[\"']?gh(?:\.exe)?[\"']?\s*[)`]"
    r"|(?<![\w-])[A-Za-z_]\w*=[\"']?(?:[^\s;&|()<>'\"`]*[/\\])?gh(?:\.exe)?[\"']?(?=[\s;&|)]|$)")
_UNQUOTED_SEGMENT = re.compile(r"[^\n;&|]*")
# 셸 변수를 바꾸는 대입 — 대입 낱말뿐인 단순 명령(`B=x;` · `A=1 B=2 &&`)에서만 값을 얻는다. 따옴표 안 글자 · 다른 명령의
# 인자는 대입이 아니고, 앞붙임(`B=x cmd` · `B=x gh …` — 그 명령의 환경에만 든다) · `+=` · 배열 · 첨자는 값을 모른다. 대입과
# gh 사이에 그 밖의 명령이 하나라도 돌면 — 선언 내장(`declare -n/-i/-u` · 따옴표로 감싼 옵션 · 첨자 대입 · 함수 밖 `local`)
# 과 `read B` · `printf -v B` · `source` · 함수 모두 — 이 검사는 값이 바뀌었는지 모른다: 그때까지의 값을 모두 모르는 것으로 본다.
# Values come only from assignment-only simple commands; any other command in between (declarations included) makes
# every value so far unknown.
_ASSIGNMENT_WORD = re.compile(r"(?P<name>[A-Za-z_]\w*)(?P<append>\+?)=(?P<value>.*)", re.S)
# 단순 명령의 경계 — `( ) { }` 는 넣지 않는다: `$(…)` · `${…}` 안을 자르면 값의 조각을 값으로 읽는다. 서브셸 · 묶음 안의
# 대입(`(B=x; …)`)은 명령 낱말 뒤가 되어 값을 모르는 쪽으로 간다(막는다).
# Simple-command breaks; `( ) { }` are left out so `$(…)` / `${…}` are never cut (subshell assignments become unknown).
_COMMAND_BREAK = re.compile(r"&&|\|\||[;&|\n]")
# gh 앞(같은 단순 명령 안)에 와도 인자를 그대로 넘기는 낱말 — 대입과 이 앞붙임 · 키워드뿐이면 gh 가 명령 자리에 있다. 그 밖
# (`xargs` · `find -exec` · 목록 밖 감싸기)이면 다른 명령이 gh 를 돌리며 인자를 바꿀 수 있다.
# Words that pass arguments through unchanged before gh; anything else means another command runs gh.
_TRANSPARENT_PREFIXES = frozenset({"env", "time", "nohup", "command", "exec", "if", "then", "else", "elif", "do",
                                   "while", "until", "!", "{", "("})
_CD = re.compile(r"(?:^|(?<=[\s;&|]))cd\s+(\"[^\"]*\"|'[^']*'|[^\s;&|()]+)")
# 디렉터리를 바꾸지만 이 검사가 따라가지 못하는 꼴 — 그 뒤의 상대 경로 본문은 못 잰다(절대 경로를 요구한다).
# Directory changes this scanner does not model; a relative body path after one is unmeasurable.
_UNMODELLED_DIR_CHANGE = re.compile(
    r"(?i)(?:^|(?<=[\s;&|(]))(?:pushd|popd|set-location|push-location|pop-location|sl|chdir)(?=\s|$)"
    r"|(?:^|(?<=[\s;&|]))cd\s+-(?=\s|$)|\(\s*cd\s")
_VAR = re.compile(r"\$(?:\{(\w+)\}|(\w+))")
# 게시될 인라인 글 안의 셸 변수 참조 — 이름 꼴(`$NAME`)과 `${…}` 전부. `$5` · 홀로 선 `$` 는 변수 이름이 아니다.
# Shell variable references in published inline text: `$NAME` and any `${…}`; `$5` or a lone `$` is not a name.
_TEXT_VAR = re.compile(r"\$(?:\{(?P<braced>[^}]*)\}|(?P<bare>[A-Za-z_]\w*))")
_NAME = re.compile(r"[A-Za-z_]\w*")
# 본문 파일을 받는 플래그(api 밖) · 게시될 글을 받는 플래그(`--subject` 는 `gh pr merge` 의 squash 제목) · api 필드 플래그 ·
# gist 에서 게시될 글을 받는 플래그 · gist 에서 값을 받는(파일이 아닌) 플래그.
# Body-file flags (outside api), published-text flags, api field flags, gist text flags, gist flags whose value is not a file.
_BODY_FILE_FLAGS = ("--body-file", "-F", "--notes-file")
_TEXT_FLAGS = ("--body", "-b", "--title", "-t", "--notes", "-n", "--subject")
_API_FIELD_FLAGS = ("-F", "--field", "-f", "--raw-field")
_GIST_TEXT_FLAGS = ("-d", "--desc")
_GIST_VALUE_FLAGS = _GIST_TEXT_FLAGS + ("-f", "--filename")


def _unquote(word: str) -> str:
    return word[1:-1] if len(word) >= 2 and word[0] == word[-1] and word[0] in "\"'" else word


def _split(rest: str, shell: str) -> list[str] | None:
    try:
        words = shlex.split(rest, posix=shell != "powershell")
    except ValueError:
        return None
    return [_unquote(w) for w in words] if shell == "powershell" else words


def _flag_value(words: list[str], i: int) -> tuple[str | None, str | None]:
    """`--flag=값` · `--flag 값` · `-F값` · `-F 값` 을 (플래그, 값) 으로 맞춘다. 값을 다음 낱말로 받는데 다음 낱말이 없으면
    값은 None — 그 값은 다른 명령(`xargs`)이 덧붙일 수 있다. / Normalize the four flag spellings; a missing value is None."""
    word, nxt = words[i], (words[i + 1] if i + 1 < len(words) else None)
    if word.startswith("--"):
        flag, eq, value = word.partition("=")
        return flag, (value if eq else nxt)
    if len(word) >= 2 and word[0] == "-" and word[1].isalpha():
        return word[:2], (word[2:].removeprefix("=") if len(word) > 2 else nxt)
    return None, ""


def _takes_separate_value(word: str, flag: str | None, value_flags: tuple[str, ...]) -> bool:
    """이 낱말이 값을 다음 낱말로 받는 플래그인가(`-d 설명` · `--desc 설명`). / Does the value follow as the next word?"""
    return flag in value_flags and "=" not in word and (word.startswith("--") or len(word) == 2)


def _targets(words: list[str]) -> tuple[list[str | None], list[str | None]]:
    """한 gh 호출 → (본문 파일 경로들 — `-` 는 stdin, 게시될 인라인 글들). 값이 빠진 플래그는 None 이다(못 잰 것).
    (body paths, '-' = stdin; inline texts); None marks a flag whose value is missing."""
    group, action = (words + ["", ""])[:2]
    paths: list[str | None] = []
    texts: list[str | None] = []
    skip_next = False
    for i, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        flag, value = _flag_value(words, i)
        if group == "api":
            if flag in _API_FIELD_FLAGS and value is None:
                texts.append(None)
            elif flag in _API_FIELD_FLAGS and "=" in value:
                field_value = value.split("=", 1)[1]
                (paths if field_value.startswith("@") else texts).append(field_value.removeprefix("@"))
            elif flag == "--input":
                paths.append(value)
        elif group == "gist" and action == "create":
            if i >= 2 and flag is None:
                paths.append(word)
            elif flag in _GIST_TEXT_FLAGS:
                texts.append(value)
            skip_next = _takes_separate_value(word, flag, _GIST_VALUE_FLAGS)
        elif group == "gist" and action == "edit" and flag in ("--add", "-a"):
            paths.append(value)
        elif group == "gist" and action == "edit" and flag in _GIST_TEXT_FLAGS:
            texts.append(value)
        elif flag in _BODY_FILE_FLAGS:
            paths.append(value)
        elif flag in _TEXT_FLAGS:
            texts.append(value)
    return [p for p in paths if p != ""], texts


def _resolve(path: str, assigned: dict[str, str | None], base: Path | None) -> Path | None:
    """대입 · 환경 변수로 경로를 푼다 — 명령 치환 · 못 푼 변수(값을 모르는 대입 포함) · 기준을 모르는 상대 경로는 None.
    Resolve a path from assignments and the environment; unresolvable → None."""
    if "$(" in path or "`" in path:
        return None

    def _lookup(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        if name in assigned:
            return assigned[name] if assigned[name] is not None else "\0"
        return os.environ.get(name, "\0")

    expanded = _VAR.sub(_lookup, path)
    if "\0" in expanded or "$" in expanded:
        return None
    p = Path(os.path.expanduser(expanded))
    if p.is_absolute():
        return p
    return base / p if base is not None else None


def _expand_text(text: str, assigned: dict[str, str | None]) -> str | None:
    """게시될 인라인 글의 변수를 셸 변수를 바꾼 글자 대입으로만 푼다 — 그 밖의 변수 · 값을 모르는 대입 · 매개변수 확장 ·
    치환(`$(…)` · 백틱 · 산술 `$[…]`)이 남으면 None.

    훅의 환경은 명령이 도는 셸의 환경이 아니다(셸 프로필이 덮을 수 있다) — 그래서 게시될 글은 환경에서 풀지 않는다.
    Resolve variables in published inline text from literal assignments only; otherwise None.
    """
    unresolved = False

    def _sub(match: re.Match[str]) -> str:
        nonlocal unresolved
        name = match.group("braced") if match.group("braced") is not None else match.group("bare")
        value = assigned.get(name) if _NAME.fullmatch(name) else None
        if value is None:
            unresolved = True
            return ""
        return value

    expanded = _TEXT_VAR.sub(_sub, text)
    if unresolved or _TEXT_VAR.search(expanded) or any(s in expanded for s in ("$(", "$[", "`")):
        return None
    return expanded


def _assignments(text: str, *, forget: bool = True) -> dict[str, str | None]:
    """`text`(gh 호출 앞 글자)에서 셸 변수를 바꾼 글자 대입 — 이름 → 값, 값을 모르면 None. 구분자로 끝나지 않은 마지막
    단순 명령은 뒤따르는 명령의 앞붙임이다. 값은 그때까지의 대입으로 푼다(`A=x; B="$A y"`).

    `forget=False` 는 본문 파일 **경로**용이다 — 사이에 다른 명령이 돌아도 · 앞붙임이 있어도 이름마다 마지막 글자 대입을
    쓴다. 게시되는 것은 그 경로에서 읽은 파일이라 그 파일을 잰다. 게시될 글 자체(기본값)는 사이 명령에서 모두 잊는다.
    Literal assignments that change shell variables; `forget=False` (paths) keeps the last literal value per name.
    """
    masked = _mask_quoted(text)
    assigned: dict[str, str | None] = {}
    start = 0
    for brk in [*_COMMAND_BREAK.finditer(masked), None]:
        end = brk.start() if brk else len(text)
        words = [text[start + m.start():start + m.end()] for m in re.finditer(r"\S+", masked[start:end])]
        start = brk.end() if brk else len(text)
        # `#` 로 시작하는 낱말부터 줄 끝까지는 주석이다 / from a word starting with `#` to the line end is a comment
        words = list(itertools.takewhile(lambda w: not w.startswith("#"), words))
        if not words:
            continue
        leading = list(itertools.takewhile(bool, (_ASSIGNMENT_WORD.fullmatch(w) for w in words)))
        command = words[len(leading):]
        if not command:
            # 대입뿐인 단순 명령 — 구분자로 끝나야 셸 변수다(끝나지 않았으면 뒤따르는 gh 의 앞붙임)
            # An assignment-only command; without a closing break it prefixes the gh call that follows.
            for match in leading:
                _record(assigned, match, keeps=brk is not None)
            continue
        if not forget:
            continue  # 경로용 — 앞붙임 · 사이 명령은 마지막 글자 대입을 지우지 않는다 / paths keep the last literal value
        for match in leading:
            assigned[match.group("name")] = None  # 앞붙임 — 그 명령의 환경에만 든다 / a prefix: that command's env only
        if brk is None:
            continue  # 구분자로 닫히지 않은 머리 — 뒤따르는 명령(gh · heredoc 을 받는 명령) 자신이다 / the following command
        # 그 밖의 명령 — 선언 내장 · 내장 · 함수가 값을 바꿨는지 모른다: 그때까지의 값을 모두 모르는 것으로 본다
        # Any other command may have changed any value (declarations, builtins, functions): forget them all.
        assigned = dict.fromkeys(assigned)
    return assigned


def _runs_gh_directly(before: str) -> bool:
    """gh 가 단순 명령의 명령 자리에 있는가 — 같은 단순 명령 안의 앞 낱말이 대입 · 투명한 앞붙임뿐이면 참.
    Is gh in command position, preceded only by assignments and pass-through prefixes in its simple command?"""
    masked = _mask_quoted(before)
    # gh 를 감싼 치환(`echo "$(gh …)"` · `URL=$(gh …)`) 안이면 gh 의 단순 명령은 그 치환 안에서 시작한다(Cursor Bugbot #1946)
    # Inside a substitution wrapping gh, gh's simple command starts within it.
    events = list(_substitution_events(before, "bash"))
    floor = events[-1][2] if events and events[-1][0] == "unclosed" else 0
    breaks = [brk for brk in _COMMAND_BREAK.finditer(masked) if brk.start() >= floor]
    start = breaks[-1].end() if breaks else floor
    words = [before[start + m.start():start + m.end()] for m in re.finditer(r"\S+", masked[start:])]
    return all(w in _TRANSPARENT_PREFIXES or _ASSIGNMENT_WORD.fullmatch(w) for w in words)


# 같은 명령 안에서 게시하는 gh 앞에 와도 파일을 쓰지도 변수를 다시 묶지도 않는 명령 — 이 밖의 명령(대입을 바꾸는 내장 · 스크립트 ·
# 복사 · 편집기 · 목록 밖 모두)이 돌면 검사가 읽은 본문 파일은 옛 내용일 수 있다(원장 #1940 M03 P1-12 · P1-13).
# Commands that write no file and rebind no variable before a publishing gh; anything else may have rewritten the body.
_NON_WRITING_HEADS = frozenset({"cd", "echo", "test", "[", "[[", "true", "false", ":", "pwd", "ls", "cat", "head", "tail",
                                "wc", "grep", "sleep", "date", "which", "type", "mkdir", "fi", "done", "esac", "}", ")"})
_GIT_NON_WRITING = frozenset({"status", "log", "diff", "show", "rev-parse", "push", "fetch", "ls-remote", "ls-files",
                              "remote", "branch", "describe"})
_LEADING_KEYWORDS = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "{", "(", "time", "nohup"})
# 단순 명령의 경계 — 리디렉션 안의 `&`(`2>&1` · `>&f` · `&>f`) · `>|` 의 `|` 는 경계가 아니다(Cursor Bugbot #1945).
# Simple-command breaks; the `&` of a redirection and the `|` of `>|` are not breaks.
_SIMPLE_COMMAND_BREAK = re.compile(r"&&|\|\||(?<![<>])&(?!>)|(?<!>)\||[;\n]")
# 출력 리디렉션과 그 대상 — `>f` · `>>f` · `2>f` · `&>f` · `>&f` · `>|f` · `n<>f`(읽기-쓰기로 연다). 쓰기가 아닌 것은
# `/dev/null` 과 `&` 가 붙은 연산자의 fd 복제(`2>&1` · `>&2` · `>&-`)뿐이다 — `> 1` 은 파일 `1` 에 쓰고, `NUL` · `$null` 은 bash
# (리눅스 · Codespaces)에서 파일 이름이 될 수 있다(Cursor #1946). 대상이 비면(`> >(…)`) 쓰기로 본다.
# Output redirections; only /dev/null and fd duplication after an `&` operator are not writes.
_OUTPUT_REDIRECT_TARGET = re.compile(r"(?<![<>\\])(?:\d+|&)?(?P<op>>{1,2}&?|<>)\|?[ \t]*(?P<target>[^\s;&|()<>]*)")
_FD_TARGET = re.compile(r"\d+-?|-")


def _harmless_redirect(op: str, target: str) -> bool:
    """버리는 곳(`/dev/null`)이거나 fd 복제인가 / Is this redirection a discard or an fd duplication?"""
    return target == "/dev/null" or (op.endswith("&") and bool(_FD_TARGET.fullmatch(target)))


def _substitution_opener(text: str, i: int, quoted: bool, shell: str) -> int:
    """`text[i]` 에서 여는 치환 표시의 길이(없으면 0) — bash: `$(` · 따옴표 밖 `<(` · `>(`. PowerShell: `$(` · 따옴표 밖 `@(` · `(`
    (인자 자리 그룹도 gh 보다 먼저 돈다 — Cursor #1946). / Length of a substitution opener at `text[i]`, or 0."""
    if text.startswith("$(", i):
        return 2
    if quoted:
        return 0
    if shell == "powershell":
        return 2 if text.startswith("@(", i) else (1 if text[i] == "(" else 0)
    return 2 if text.startswith(("<(", ">("), i) else 0


def _substitution_events(text: str, shell: str):
    """치환을 따라 읽으며 (종류, 여는 자리, 끝, 산술인가) 를 낸다 — "span"(끝 = 닫는 괄호 다음) · "unclosed"(끝 = 안쪽이 시작하는
    자리, 거기서 멈춘다) · "backtick"(bash 의 백틱 치환, 거기서 멈춘다). 작은따옴표 안은 글자 그대로라 뺀다. PowerShell 은 백틱이
    이스케이프다. / Walk the substitutions of `text`, yielding spans, then an unclosed opener or a bash backtick if any."""
    escape = "`" if shell == "powershell" else "\\"
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote == "'":
            quote = None if ch == "'" else quote
        elif ch == escape:
            i += 2
            continue
        elif ch == "`":
            yield "backtick", i, i, False
            return
        elif ch == '"':
            quote = None if quote == '"' else '"'
        elif ch == "'" and quote is None:
            quote = "'"
        elif opener := _substitution_opener(text, i, quote is not None, shell):
            end = _substitution_end(text[i + opener:], shell)
            if end is None:
                yield "unclosed", i, i + opener, False
                return
            yield "span", i, i + opener + end + 1, shell != "powershell" and text.startswith("$((", i)
            i += opener + end + 1
            continue
        i += 1


def _substitution_spans(text: str, shell: str = "bash") -> list[tuple[int, int, bool]] | None:
    """명령 치환 · 프로세스 치환 · 산술 펼침(`$((…))`, bash 만)의 자리 — (여는 표시, 닫는 괄호 다음, 산술인가). bash 의 백틱
    치환 · 닫히지 않은 치환이 있으면 None(안을 모른다).
    Substitution spans; None for a bash backtick or an unclosed one."""
    spans: list[tuple[int, int, bool]] = []
    for kind, start, end, arithmetic in _substitution_events(text, shell):
        if kind != "span":
            return None
        spans.append((start, end, arithmetic))
    return spans


def _substitution_rewriter(text: str, shell: str, spans: list[tuple[int, int, bool]] | None = None) -> str | None:
    """`text` 의 치환 안에서 파일을 쓰거나 변수를 다시 묶을 수 있는 명령 — 치환은 gh 보다 먼저 돈다(그 자리가 gh 의 인자여도).
    백틱 · 닫히지 않은 치환은 안을 모르니 그 자체로 돌려준다. PowerShell 의 치환은 안쪽을 bash 모형으로 재지 않고 그 자체로
    돌려준다(따옴표 · 이스케이프 · 대입이 다르다 — Cursor #1946).
    A rewriting command inside a substitution of `text`; substitutions run before gh, even inside its own arguments."""
    spans = _substitution_spans(text, shell) if spans is None else spans
    if spans is None:
        return "`…`"
    if shell == "powershell":
        return "PowerShell 의 치환 `(…)`" if spans else None
    for start, end, arithmetic in spans:
        inner = f"(( {text[start + 3:end - 2]} ))" if arithmetic else text[start + 2:end - 1]
        found = _rewriting_command(inner + "\n", shell)
        if found:
            return f"$({found})"
    return None
# 산술 명령 안의 대입(`=` · `+=` · `++` · `--`) — 비교(`==` · `!=` · `<=` · `>=`)는 대입이 아니다.
# An assignment inside an arithmetic command; comparisons are not assignments.
_ARITHMETIC_ASSIGNMENT = re.compile(r"(?<![=!<>])=(?!=)|\+\+|--")


def _rewriting_command(before: str, shell: str = "bash") -> str | None:
    """`before`(게시하는 gh 앞 글자)에서 본문 파일을 쓰거나 변수를 다시 묶을 수 있는 첫 단순 명령 — 없으면 None. 출력 리디렉션
    (버리는 곳 · fd 복제 밖)과 치환 안의 명령도 본다. gh 자신의 단순 명령(마지막 구분자 뒤)은 치환만 본다.
    The first command before gh that may rewrite a file or rebind a variable (redirections and substitutions count)."""
    if shell == "powershell":
        # PowerShell 의 따옴표 · 이스케이프(백틱 · `\` 는 글자) · 그룹 · 대입은 이 셸 모형(bash)과 다르다 — gh 앞에 무엇이든
        # 있으면(호출 연산자 `&` 만 빼고) 본문 파일을 못 잰 것으로 본다(나눠 부른다 · Cursor #1946).
        # PowerShell parses differently; anything before gh but the call operator leaves the body unmeasured.
        return "PowerShell 의 앞 명령" if before.strip() not in ("", "&") else None
    events = list(_substitution_events(before, shell))
    if events and events[-1][0] == "unclosed":
        # gh 를 감싼 치환(`URL=$(… gh …)`) — 닫는 괄호는 gh 뒤에 있다. 그 바깥과, 그 안에서 gh 앞에 도는 명령을 따로 잰다
        # (Cursor Bugbot #1946 — «닫히지 않은 치환» 으로 막던 오탐). / gh sits inside this substitution: judge outside and inside.
        _kind, open_at, inner_at, _arithmetic = events[-1]
        return _rewriting_command(before[:open_at], shell) or _rewriting_command(before[inner_at:], shell)
    spans = _substitution_spans(before, shell)
    found = _substitution_rewriter(before, shell, spans)
    if found:
        return found
    # 치환 안은 따로 쟀다 — 바깥 경계 · 낱말 · 리디렉션 판정에서 가린다(`N=$(gh pr view …; true)` 가 한 낱말)
    # Substitutions were judged on their own; mask them so they stay one word outside.
    masked_chars = list(_mask_quoted(before))
    for open_at, end, _arithmetic in spans or ():
        masked_chars[open_at:end] = "_" * (end - open_at)
    masked = "".join(masked_chars)
    start = 0
    for brk in _SIMPLE_COMMAND_BREAK.finditer(masked):
        seg, seg_masked = before[start:brk.start()], masked[start:brk.start()]
        start = brk.end()
        words = [seg[m.start():m.end()] for m in re.finditer(r"\S+", seg_masked)]
        words = list(itertools.takewhile(lambda w: not w.startswith("#"), words))
        words = list(itertools.dropwhile(lambda w: w in _LEADING_KEYWORDS or _ASSIGNMENT_WORD.fullmatch(w), words))
        if not words:
            continue
        # `(( a > b ))` 의 `>` 는 비교다(Cursor Bugbot #1945) — 산술 안의 대입은 변수를 다시 묶는다
        # In `(( … ))` a `>` compares; an assignment there rebinds a variable.
        if words[0].startswith("(("):
            if _ARITHMETIC_ASSIGNMENT.search(seg_masked):
                return "(( … = … ))"
            continue
        # `[[ a > b ]]` 의 `>` 도 비교다 — 리디렉션이 아니다(Grok M03-b 반례) / inside `[[ … ]]` a `>` compares
        for redirect in () if words[0] == "[[" else _OUTPUT_REDIRECT_TARGET.finditer(seg_masked):
            target = seg[redirect.start("target"):redirect.end("target")]
            if not _harmless_redirect(redirect.group("op"), target):
                return f"{words[0]} > …"
        head = _unquote(words[0]).replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
        if head == "git":
            rest = iter(words[1:])
            sub = ""
            for word in rest:
                if word == "-c" or word.startswith("--config-env"):
                    # 설정이 명령을 돌릴 수 있다(`core.fsmonitor` · `core.pager` · 별칭 — Cursor Bugbot #1945)
                    # A config override can run a command.
                    return "git -c"
                if word == "-C":
                    next(rest, None)
                elif not word.startswith("-"):
                    sub = word
                    break
            if sub not in _GIT_NON_WRITING:
                return f"git {sub}".strip()
            # diff · log · show 의 `--output` 은 파일을 쓴다(Cursor Bugbot #1945) / `--output` writes a file
            if any(word == "--output" or word.startswith("--output=") for word in words):
                return f"git {sub} --output"
        elif head == "gh":
            # 받기 · 복제 · 체크아웃 · 동기화는 작업 트리 파일을 바꾼다(`gh pr checkout` — Grok M03-b 반례)
            if any(word in ("download", "clone", "checkout", "sync") for word in words[1:]):
                return "gh"
        elif head == "printf":
            if "-v" in words[1:]:
                return "printf -v"
        elif head not in _NON_WRITING_HEADS:
            return head
    return None


# 아무것도 게시하지 않는 gh — 무리 · 동작이 이 목록이거나 쓰기 필드 · 메서드가 없는 `gh api`. 명령이 이런 gh 만 부르면 그 글자는
# 공개 글이 되지 않는다(원장 #1940 M03 P2-12). 목록 밖(쓰기인지 모르는 하위 명령 포함)은 지금처럼 명령 글자 전체를 잰다.
# gh calls that publish nothing; a command made only of these is not a public write. Unknown subcommands keep the text scan.
_READ_ONLY_GH = {
    "pr": {"view", "list", "checks", "diff", "status"}, "issue": {"view", "list", "status"},
    "run": {"view", "list", "watch"}, "repo": {"view"}, "release": {"view", "list"}, "workflow": {"view", "list"},
    "label": {"list"}, "gist": {"view", "list"}, "auth": {"status"}, "search": None, "status": None,
}
_API_WRITE_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field", "--input"})


def _is_read_only_gh(words: list[str]) -> bool:
    """이 gh 호출이 아무것도 게시하지 않는가 / Does this gh call publish nothing?"""
    group = words[0] if words else ""
    if group == "api":
        for i, word in enumerate(words):
            flag, value = _flag_value(words, i)
            if flag in _API_WRITE_FLAGS:
                return False
            if flag in ("-X", "--method") and (value or "").upper() != "GET":
                return False
        return True
    if group not in _READ_ONLY_GH:
        return False
    allowed = _READ_ONLY_GH[group]
    return allowed is None or (len(words) > 1 and words[1] in allowed)


def _substitution_end(text: str, shell: str = "bash") -> int | None:
    """`$(` 바로 뒤 글자에서 그 치환을 닫는 `)` 의 자리 — 따옴표 · 안쪽 괄호를 따라 센다. 못 찾으면 None(원장 #1940 M03 P2-15).
    PowerShell 은 백틱이 이스케이프(`\\` 는 글자)이고, 블록 주석(`<#`)이 있으면 닫는 괄호를 모르니 None 이다(Cursor #1946).
    Where the `)` closing a `$(` substitution sits, following quotes and nested parens; None when it never closes."""
    escape = "`" if shell == "powershell" else "\\"
    depth, quote, i = 0, None, 0
    while i < len(text):
        ch = text[i]
        if quote == "'":
            quote = None if ch == "'" else quote
        elif ch == escape:
            i += 2
            continue
        elif shell == "powershell" and text.startswith("<#", i):
            return None
        elif quote == '"':
            quote = None if ch == '"' else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return i
            depth -= 1
        i += 1
    return None


def _gh_segments(stripped: str, shell: str) -> list[tuple[int, int, str, list[str] | None]]:
    """명령 글자 속 gh 호출마다 (시작 자리, 끝 자리, 그 호출의 인자 글자, 낱말 또는 None). 끝은 따옴표 밖 첫 구분자 — `$(gh …)`
    안이면 그 치환을 닫는 괄호에서 먼저 자른다. / Each gh call: (start, end, its argument text, words or None)."""
    segments = []
    for seg in _GH_START.finditer(stripped):
        tail = stripped[seg.end():]
        if stripped[:seg.start()].rstrip().endswith("$("):
            end = _substitution_end(tail, shell)
            tail = tail if end is None else tail[:end]
        rest = tail[:_UNQUOTED_SEGMENT.match(_mask_quoted(tail)).end()]
        segments.append((seg.start(), seg.end() + len(rest), rest, _split(rest, shell)))
    return segments


def _inside_a_call(pos: int, segments: list[tuple[int, int, str, list[str] | None]]) -> bool:
    """`pos` 가 알아본 gh 호출(호출 낱말 · 그 인자) 안인가 / Is `pos` inside a recognised gh call?"""
    return any(start <= pos < end for start, end, _rest, _words in segments)


def _every_gh_word_is_a_call(stripped: str, segments: list[tuple[int, int, str, list[str] | None]]) -> bool:
    """명령 글자의 gh 낱말이 모두 알아본 gh 호출 안에 있는가 — 밖에 있으면 알아보지 못한 꼴로 gh 를 부를 수 있다.
    Is every gh word inside a recognised gh call? One outside may be a gh call in an unrecognised form."""
    return all(_inside_a_call(word.start(), segments) for word in _ANY_GH_WORD.finditer(stripped))


def _record(assigned: dict[str, str | None], match: re.Match[str], *, keeps: bool) -> None:
    """대입 낱말 하나를 기록한다 — 셸 변수에 글자 그대로 남는 대입만 값을 쓰고(그때까지의 대입으로 푼다), 나머지는 None.
    Record one assignment word: a value only when it stays literal in the shell variable, else None."""
    value = _word_value(match.group("value"), assigned) if keeps and not match.group("append") else None
    assigned[match.group("name")] = value[0] if value else None


def _count_value(value: str, expanded: bool) -> dict[str, int]:
    """게시될 값의 꼴 — 글자 그대로면 홈 경로만 더 센다(나머지 꼴은 명령 글자에서 이미 쟀다). 변수를 풀어 달라졌으면 모든 꼴을
    다시 잰다 — 조각마다는 꼴이 아니어도 이은 값은 꼴일 수 있다(그때 개수는 겹쳐 셀 수 있다 · 막는 판정은 같다).
    A literal value adds home paths only; an expanded value is re-counted for every kind (joined pieces may form a shape).
    """
    return count_kinds(value) if expanded else count_kinds(value, only=("local-home-path",))


def _join_continuations(text: str) -> str:
    """bash 처럼 작은따옴표 밖의 `\\`+줄바꿈(줄 이음)을 지운다 — 쪼갠 대입 값 · 경로 · 키는 이어진 값으로 쓰인다.
    이스케이프한 백슬래시(`\\\\`) 뒤의 줄바꿈은 진짜 줄바꿈이다. heredoc 본문은 이 함수에 오기 전에 걷는다.
    Remove backslash-newline outside single quotes, as bash does; heredoc bodies are stripped before this."""
    out: list[str] = []
    i, single = 0, False
    while i < len(text):
        ch = text[i]
        if single:
            single = ch != "'"
        elif ch == "\\" and i + 1 < len(text):
            if text[i + 1] != "\n":
                out.append(text[i:i + 2])  # 이스케이프 두 글자 그대로 / an escape pair, kept
            i += 2
            continue
        elif ch == "'" and not _inside_double_quotes(out):
            single = True
        out.append(ch)
        i += 1
    return "".join(out)


def _inside_double_quotes(prefix: list[str]) -> bool:
    """지금까지 쓴 글자가 큰따옴표 안에서 끝나는가 — 작은따옴표 · 이스케이프를 따라 센다. / Is the prefix inside "…"?"""
    quote: str | None = None
    escaped = False
    for ch in "".join(prefix):
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
    return quote == '"'


def _mask_quoted(text: str) -> str:
    """따옴표 안 글자(따옴표 · 이스케이프 포함)를 같은 길이의 `_` 로 가린다 — 연산자는 따옴표 밖에서만 찾는다(위치는 원문과 같다).
    Mask quoted and escaped characters with `_`, keeping positions, so operators are found outside quotes only.
    """
    out: list[str] = []
    quote: str | None = None
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        else:
            out.append(ch)
            continue
        out.append("_")
    return "".join(out)


def _word_value(word: str, assigned: dict[str, str | None]) -> tuple[str, bool] | None:
    """셸 낱말 하나의 값과 «변수를 풀었는가» — 작은따옴표 조각은 글자 그대로, 나머지는 셸 변수를 바꾼 글자 대입으로만 푼다.
    `$'…'`(펼쳐 봐야 안다) · 머리의 `~`(홈 경로로 펼쳐진다) · 치환 · 못 푼 변수 · 조각으로 다 덮이지 않는 낱말은 None.
    The value of one shell word and whether it was expanded; single-quoted pieces are literal.
    """
    if word.startswith("~"):
        return None
    out, pos, expanded = [], 0, False
    for piece in _WORD_PIECE.finditer(word):
        if piece.start() != pos or piece.group("ansi") is not None:
            return None
        pos = piece.end()
        if piece.group("single") is not None:
            out.append(piece.group("single"))
        elif piece.group("escaped") is not None:
            out.append(piece.group("escaped"))
        else:
            text = piece.group("double") if piece.group("double") is not None else piece.group("bare")
            value = None if ("$(" in text or "`" in text) else _expand_text(text, assigned)
            if value is None:
                return None
            expanded = expanded or value != text
            out.append(value)
    return ("".join(out), expanded) if pos == len(word) else None


def _read(path: Path | None) -> str | None:
    try:
        if path is None or path.stat().st_size > _MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _word_at(text: str, pos: int) -> str | None:
    """`pos` 에서 시작하는 셸 낱말 — 낱말 뒤가 공백 · 연산자 · 끝이 아니면(`$(…)` · `$((…))` 로 이어지면) 그 조각은 낱말이
    아니라 None. / The shell word at `pos`; None when it runs on into something this scanner does not read."""
    match = _SHELL_WORD.match(text, pos)
    if match is None:
        return None
    end = match.end()
    return match.group(0) if end == len(text) or text[end] in " \t\n;&|<>" else None


def _measure_stdin(rest: str, before: str, assigned: dict[str, str | None], path_assigned: dict[str, str | None],
                   base: Path | None,
                   counts: dict[str, int], unread: list[str], rewritten_note: str | None = None) -> None:
    """stdin 본문(`-`)을 잰다 — 출처가 정확히 하나일 때만: fd 0 의 heredoc(본문은 따로 잰다) · here-string 낱말 · `<` 파일,
    또는 출처가 없고 파이프 앞 단계가 `cat <<EOF |` 일 때. 출처가 여럿(덮어쓰기) · `<&` 복제 · 못 읽은 heredoc · 모르는 출처는
    못 잰 것이다. 연산자는 따옴표를 가린 글자에서 찾는다(`--title '<<<x'` 는 연산자가 아니다).
    Measure a stdin body only from exactly one known source; several, `<&`, unparsed heredocs or unknown sources are unread.
    """
    masked = _mask_quoted(rest)
    if _UNPARSED_HEREDOC.search(masked):
        unread.append("(heredoc 끝 표시를 읽지 못했다)")
        return
    sources: list[tuple[str, str | None]] = [("heredoc", None)] * masked.count(_HEREDOC_MARK)
    for op in _HERE_STRING_OP.finditer(masked):
        if op.group("fd") in (None, "0"):
            sources.append(("here-string", _word_at(rest, op.end())))
    for op in _STDIN_REDIRECT_OP.finditer(masked):
        if op.group("fd") in (None, "0"):
            sources.append(("dup" if op.group("op") == "&" else "file", _word_at(rest, op.end())))
    if not sources:
        if _CAT_HEREDOC_STAGE.search(before) is None:
            unread.append("(stdin 본문 — 어디서 오는지 모른다)")
        return
    if len(sources) > 1:
        unread.append("(stdin 출처가 여럿이다 — 어느 것이 본문인지 모른다)")
        return
    kind, word = sources[0]
    if kind == "heredoc":
        return  # 본문은 judge_command 머리에서 잰다 / measured at the top of judge_command
    if kind == "here-string":
        value = _word_value(word, assigned) if word else None
        if value is None:
            unread.append("(here-string 본문을 못 잰다)")
        else:
            _add(counts, _count_value(*value))
        return
    if kind == "dup" or not word or not _SIMPLE_WORD.fullmatch(word):
        unread.append("(stdin 이 다른 fd 에서 오거나 파일 이름을 못 풀었다)")
        return
    if rewritten_note:
        unread.append(rewritten_note)  # `<` 파일도 같은 명령이 다시 썼을 수 있다 / the `<` file may have been rewritten too
        return
    raw = _unquote(word)
    text = _read(_resolve(raw, path_assigned, base))
    if text is None:
        unread.append(raw)
        return
    _add(counts, count_kinds(text))


def judge_command(command: str, cwd: str | None, shell: str) -> tuple[dict[str, int], list[str]]:
    """gh 명령 → (꼴별 개수, 못 잰 것들). 명령 글자 · heredoc · 인라인 본문 · 본문 파일을 잰다.

    heredoc 본문은 걷어 따로 모든 꼴로 재고, 남은 명령 글자는 bash 처럼 줄 이음(`\\`+줄바꿈)을 이은 뒤 잰다 — 명령 글자에서는
    홈 경로 꼴만 빼고 잰다(거기 든 경로는 본문 파일 · cd 같은 로컬 인자다). 홈 경로는 게시될 글(heredoc 본문 · 인라인 본문 ·
    본문 파일)에서만 센다. 인라인 본문의 변수는 대입뿐인 단순 명령의 글자 값으로 풀어 잰다 — 그 값은 명령 글자에 있으니
    홈 경로만 더 센다. 못 풀면 못 잰 것이다.
    A gh command → (per-kind counts, what could not be measured).
    """
    unread: list[str] = []
    counts: dict[str, int] = {}
    if not _ANY_GH_WORD.search(command):
        return counts, unread  # gh 낱말이 없으면 gh 로 게시되는 글도 없다(원장 #1940 M03 P2-13) / no gh word, no gh publish
    stripped = _join_continuations(_HEREDOC.sub(
        lambda m: (_HEREDOC_MARK if m.group("fd") in (None, "0") else _OTHER_FD_HEREDOC_MARK) + m.group("tail"), command))
    segments = _gh_segments(stripped, shell)
    if _GH_INDIRECT.search(stripped):
        unread.append("(gh 를 변수 · 명령 치환으로 부른다 — 어떤 인자가 게시되는지 못 잰다 · gh 를 바로 부른다)")
    elif (segments and all(words is not None and _is_read_only_gh(words) for _start, _end, _rest, words in segments)
          and _every_gh_word_is_a_call(stripped, segments)):
        # 읽기만 하는 gh 뿐이고 다른 꼴로 부른 gh 가 없다 — 게시가 아니다(P2-12)
        # Only read-only gh calls and no gh word outside them: nothing is published.
        return counts, unread
    if any(not _inside_a_call(flag.start(), segments) for flag in _BODY_FILE_FLAG.finditer(stripped)):
        unread.append("(알아보지 못한 자리의 --body-file — 그 파일이 게시될 수 있다 · gh 를 바로 부른다)")
    for heredoc in _HEREDOC.finditer(command):
        body = heredoc.group("body") or ""
        if heredoc.group("quote"):
            _add(counts, count_kinds(body))  # 글자 그대로 게시된다 / published verbatim
            continue
        # 따옴표 없는 끝 표시 — bash 가 `\`+줄바꿈을 지운 뒤 펼친다. 그 앞의 글자 대입으로만 풀고, 못 풀면 못 잰 것이다.
        # Unquoted delimiter: bash joins line continuations, then expands; resolve only from earlier literal assignments.
        body = re.sub(r"\\([\\\n])", lambda m: "" if m.group(1) == "\n" else "\\\\", body)
        earlier = _assignments(_join_continuations(_HEREDOC.sub(lambda m: _HEREDOC_MARK + m.group("tail"),
                                                                command[:heredoc.start()])))
        value = None if ("$(" in body or "`" in body) else _expand_text(body, earlier)
        if value is None:
            unread.append("(따옴표 없는 heredoc 본문이 펼쳐진다 — 펼친 값을 못 잰다)")
            continue
        _add(counts, count_kinds(value))
    _add(counts, count_kinds(stripped, skip=("local-home-path",)))
    for seg_start, _seg_end, rest, words in segments:
        if words is None:
            unread.append("(gh 명령을 낱말로 나누지 못했다)")
            continue
        before = stripped[:seg_start]
        assigned = _assignments(before)  # 게시될 글 — 사이 명령에서 잊는다 / published text: forgets on commands
        path_assigned = _assignments(before, forget=False)  # 경로 — 마지막 글자 대입 / paths: last literal value
        base: Path | None = Path(cwd or os.getcwd())
        if _UNMODELLED_DIR_CHANGE.search(before):
            base = None
        else:
            cds = [_unquote(m.group(1)) for m in _CD.finditer(before)]
            if cds:
                base = _resolve(cds[-1], path_assigned, base)
        paths, texts = _targets(words)
        if (paths or texts) and not _runs_gh_directly(before):
            # 게시하는 gh 를 다른 명령(`xargs` · `find -exec` · 목록 밖 감싸기)이 돌린다 — 인자가 바뀌어 실행될 수 있다
            # Another command runs a publishing gh call; its arguments may be rewritten.
            unread.append("(gh 를 다른 명령이 인자로 받아 돌린다 — 인자가 바뀌어 실행될 수 있다)")
            continue
        # 같은 명령에서 gh 앞의 명령이 본문 파일을 다시 쓰거나 경로 변수를 다시 묶을 수 있다 — 검사가 읽은 것은 옛 내용이다(P1-12 · 13)
        # A command before gh may have rewritten the body file or rebound its path variable.
        rewriter = _rewriting_command(before, shell) or _substitution_rewriter(rest, shell)
        rewritten_note = (f"(같은 명령에서 gh 앞의 `{rewriter}` 가 본문 파일을 바꿀 수 있다 — 본문 파일을 만드는 명령과 게시를 "
                          "나눠 부른다)") if rewriter else None
        for text in texts:
            if text is None:
                unread.append("(값이 빠진 플래그 — 다른 명령이 덧붙인 값이 게시될 수 있다)")
                continue
            if "$(" in text or "`" in text:
                unread.append("(인라인 본문이 명령 치환이다)")
                continue
            if text.startswith("~"):
                # 낱말 머리의 `~` 는 홈 경로로 펼쳐진다 — 따옴표가 걷힌 뒤라 `"~/x"` 도 같이 막는다(드문 오탐).
                # A leading `~` expands to the home path; quotes are already gone, so `"~/x"` is denied too.
                unread.append("(인라인 본문이 ~ 로 시작한다 — 홈 경로로 펼쳐질 수 있다)")
                continue
            expanded = _expand_text(text, assigned)
            if expanded is None:
                unread.append("(인라인 본문의 변수를 같은 명령 안의 대입으로 풀지 못했다)")
                continue
            _add(counts, _count_value(expanded, expanded=expanded != text))
        if "-" in paths:
            _measure_stdin(rest, before, assigned, path_assigned, base, counts, unread, rewritten_note)
        for raw in paths:
            if raw is None:
                unread.append("(값이 빠진 본문 파일 플래그 — 다른 명령이 덧붙인 파일이 게시될 수 있다)")
                continue
            if raw == "-":
                continue  # stdin — 위에서 한 번 잰다 / measured once above
            if rewritten_note:
                unread.append(rewritten_note)
                continue
            text = _read(_resolve(raw, path_assigned, base))
            if text is None:
                unread.append(raw)
                continue
            _add(counts, count_kinds(text))
    return counts, unread


def _deny(reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=True))
    return 0


# 거부 기록 — credential 훅과 같은 파일 · 같은 꼴(시각 · 종류 · 사유 범주 · 명령 sha256 · 길이, 값 없음). 회고의 훅 정밀도 계기가
# 막는 훅 둘을 다 보게 한다(원장 #1940 M03 P2-14). 못 써도 판정은 그대로다 — 기록은 계기이지 관문이 아니다.
# Value-free denial record shared with the credential hook; a write failure never changes the verdict.
_DENIAL_LOG_ENV = "SCAMANAGER_HOOK_LOG"


def _record_denial(subject: str, category: str) -> None:
    path = os.environ.get(_DENIAL_LOG_ENV) or os.path.join(os.path.expanduser("~"), ".scamanager", "hook-denials.jsonl")
    line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": "publish", "reason": category,
                       "sha256": hashlib.sha256(subject.encode("utf-8", "replace")).hexdigest(), "len": len(subject)},
                      ensure_ascii=True)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def _hook() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        tool = payload.get("tool_name") or ""
        command = (payload.get("tool_input") or {}).get("command") or ""
        cwd = payload.get("cwd")
        if not isinstance(command, str):
            raise TypeError("command")
    except (ValueError, TypeError, AttributeError, RecursionError):
        _record_denial(raw, "판정 불가")
        return _deny("[게시 전 검사] 판정 불가 — 훅 입력을 읽지 못했다. 명령을 다시 시도하세요(scripts/scan_publish.py).")
    if tool == "Monitor" and not _ANY_GH_WORD.search(command):
        # Monitor 는 gh 거름(`if`) 없이 모든 명령에 뜬다 — gh 낱말이 없으면 게시가 아니다(원장 #1940 «정할 것» 7 · 경로 · 치환으로
        # 부른 gh 도 낱말은 있다 — Cursor 보안 검토 #1945). / With no gh word anywhere nothing is published.
        return 0
    counts, unread = judge_command(command, cwd, "powershell" if tool == "PowerShell" else "bash")
    if not counts and not unread:
        return 0
    lines = ["[게시 전 검사] 공개 쓰기를 막았다 — 리포는 공개이고 올린 글은 편집 이력에 남는다."]
    if counts:
        lines.append(f"비밀값 · 개인정보 꼴: {_summary(counts)} (값은 열지 않는다)")
        lines.append("→ 본문에서 그 부분을 지우거나 가린 뒤 다시 올린다. 확인: py -3 scripts/scan_publish.py <본문 파일>")
    if unread:
        lines.append(f"못 읽은 본문 {len(unread)}개 — 경로 · 인라인 글의 변수를 못 풀었거나(명령 치환 · 같은 명령 안에서 대입하지 "
                     "않은 변수) 파일을 못 읽었다. 경로 · 글을 그대로 적거나 본문 파일로 다시 시도한다(못 재면 막는다).")
        lines.extend(note for note in dict.fromkeys(unread) if "나눠 부른다" in note)
    _record_denial(command, "비밀값 · 개인정보 꼴" if counts else "못 읽은 본문")
    return _deny("\n".join(lines))


def _make_stdout_safe() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        return  # 캡처된 stream — reconfigure 미지원 / captured stream


def main(argv: list[str] | None = None) -> int:
    _make_stdout_safe()
    args = sys.argv[1:] if argv is None else argv
    if args == ["--hook"]:
        return _hook()
    if not args:
        print("사용법: py -3 scripts/scan_publish.py <파일>...  (훅: --hook)")
        return 2
    found = False
    for name in args:
        try:
            counts = count_kinds(Path(name).read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            print(f"{name}: 못 읽었다 ({type(exc).__name__}) — 못 재면 실패로 본다")
            found = True
            continue
        print(f"{name}: {_summary(counts) or '꼴 0'}")
        found = found or bool(counts)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
