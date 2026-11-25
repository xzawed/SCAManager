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

import json
import os
import re
import shlex
import sys
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
    "assigned-secret": r"(?i)\b(?:SECRET|TOKEN|PASSWORD|API_KEY|ENCRYPTION_KEY)[A-Z_]*\s*[=:]\s*[\"']?[A-Za-z0-9+/_-]{24,}",
    # 사람 주소 — 공개용 주소(noreply · 예시 · git SSH)는 아래 `_PUBLIC_EMAIL` 이 뺀다.
    "email": r"(?<![\w.+%-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b",
    # 개인 홈 경로(사용자 이름이 든다) — CI 러너 경로는 사람 것이 아니다.
    "local-home-path": r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"'`]+|/Users/[^/\s\"'`]+|/home/(?!runner/)[^/\s\"'`]+",
}
_COMPILED = {kind: re.compile(rx) for kind, rx in _KINDS.items()}
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
    r"(?:(?:(?<=[\s;&|(])|^)(?P<fd>\d+))?(?<!<)<<(?!<)(?P<dash>-)?[ \t]*(?P<quote>['\"]?)(?P<delim>[A-Za-z_]\w*)"
    r"(?P=quote)(?=[\s;&|<>()]|$)(?P<tail>[^\n]*)\n(?:(?P<body>.*?)\n)??(?(dash)\t*)(?P=delim)(?=\n|$)", re.S | re.M)
_HEREDOC_MARK = "<<\0heredoc\0"            # fd 0 의 heredoc / a heredoc on stdin
_OTHER_FD_HEREDOC_MARK = "\0fd-heredoc\0"  # 다른 fd 의 heredoc — stdin 이 아니다 / a heredoc on another fd
# 이 검사가 끝 표시를 못 읽어 남은 heredoc 연산자 — here-string(`<<<`) · 표지는 아니다.
# A heredoc operator left unparsed — neither a here-string (`<<<`) nor the marker.
_UNPARSED_HEREDOC = re.compile(r"(?<!<)<<(?![<\0])")
# stdin 연산자 — 따옴표를 가린 글자에서 찾는다. 숫자 접두는 낱말 머리일 때만 fd 다(`x3<f` 의 3 은 낱말 글자).
# stdin operators, searched in quote-masked text; a digit prefix is an fd only at the start of a word.
_FD_PREFIX = r"(?:(?:(?<=[\s;&|(])|^)(?P<fd>\d+)|(?<![<>&]))"
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
_GH_SEGMENT = re.compile(r"(?:^|(?<=[\s;&|(]))gh(?:\.exe)?\s+(?P<rest>[^\n;&|]*)")
_ASSIGN = re.compile(r"(?:^|(?<=[\s;&|]))([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]*)")
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


def _flag_value(words: list[str], i: int) -> tuple[str | None, str]:
    """`--flag=값` · `--flag 값` · `-F값` · `-F 값` 을 (플래그, 값) 으로 맞춘다. / Normalize the four flag spellings."""
    word, nxt = words[i], (words[i + 1] if i + 1 < len(words) else "")
    if word.startswith("--"):
        flag, eq, value = word.partition("=")
        return flag, (value if eq else nxt)
    if len(word) >= 2 and word[0] == "-" and word[1].isalpha():
        return word[:2], (word[2:].removeprefix("=") if len(word) > 2 else nxt)
    return None, ""


def _takes_separate_value(word: str, flag: str | None, value_flags: tuple[str, ...]) -> bool:
    """이 낱말이 값을 다음 낱말로 받는 플래그인가(`-d 설명` · `--desc 설명`). / Does the value follow as the next word?"""
    return flag in value_flags and "=" not in word and (word.startswith("--") or len(word) == 2)


def _targets(words: list[str]) -> tuple[list[str], list[str]]:
    """한 gh 호출 → (본문 파일 경로들 — `-` 는 stdin, 게시될 인라인 글들). / (body paths, '-' = stdin; inline texts)."""
    group, action = (words + ["", ""])[:2]
    paths, texts = [], []
    skip_next = False
    for i, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        flag, value = _flag_value(words, i)
        if group == "api":
            if flag in _API_FIELD_FLAGS and "=" in value:
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
    return [p for p in paths if p], texts


def _resolve(path: str, assigned: dict[str, str], base: Path | None) -> Path | None:
    """대입 · 환경 변수로 경로를 푼다 — 명령 치환 · 못 푼 변수 · 기준을 모르는 상대 경로는 None. / Unresolvable → None."""
    if "$(" in path or "`" in path:
        return None
    expanded = _VAR.sub(lambda m: assigned.get(m.group(1) or m.group(2), os.environ.get(m.group(1) or m.group(2), "\0")), path)
    if "\0" in expanded or "$" in expanded:
        return None
    p = Path(os.path.expanduser(expanded))
    if p.is_absolute():
        return p
    return base / p if base is not None else None


def _expand_text(text: str, assigned: dict[str, str]) -> str | None:
    """게시될 인라인 글의 변수를 같은 명령 안의 글자 대입으로만 푼다 — 그 밖의 변수 · 매개변수 확장 · 치환이 남으면 None.

    훅의 환경은 명령이 도는 셸의 환경이 아니다(셸 프로필이 덮을 수 있다) — 그래서 게시될 글은 환경에서 풀지 않는다.
    Resolve variables in published inline text from literal assignments in the same command only; otherwise None.
    """
    unresolved = False

    def _sub(match: re.Match[str]) -> str:
        nonlocal unresolved
        name = match.group("braced") if match.group("braced") is not None else match.group("bare")
        if not _NAME.fullmatch(name) or name not in assigned:
            unresolved = True
            return ""
        return assigned[name]

    expanded = _TEXT_VAR.sub(_sub, text)
    if unresolved or _TEXT_VAR.search(expanded) or "$(" in expanded or "`" in expanded:
        return None
    return expanded


def _count_value(value: str, expanded: bool) -> dict[str, int]:
    """게시될 값의 꼴 — 글자 그대로면 홈 경로만 더 센다(나머지 꼴은 명령 글자에서 이미 쟀다). 변수를 풀어 달라졌으면 모든 꼴을
    다시 잰다 — 조각마다는 꼴이 아니어도 이은 값은 꼴일 수 있다(그때 개수는 겹쳐 셀 수 있다 · 막는 판정은 같다).
    A literal value adds home paths only; an expanded value is re-counted for every kind (joined pieces may form a shape).
    """
    return count_kinds(value) if expanded else count_kinds(value, only=("local-home-path",))


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


def _word_value(word: str, assigned: dict[str, str]) -> tuple[str, bool] | None:
    """셸 낱말 하나의 값과 «변수를 풀었는가» — 작은따옴표 조각은 글자 그대로, 나머지는 같은 명령 안의 글자 대입으로만 푼다.
    `$'…'`(펼쳐 봐야 안다) · 치환 · 못 푼 변수 · 조각으로 다 덮이지 않는 낱말은 None.
    The value of one shell word and whether it was expanded; single-quoted pieces are literal.
    """
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


def _measure_stdin(rest: str, before: str, assigned: dict[str, str], base: Path | None,
                   counts: dict[str, int], unread: list[str]) -> None:
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
            word = _SHELL_WORD.match(rest, op.end())
            sources.append(("here-string", word.group(0) if word else None))
    for op in _STDIN_REDIRECT_OP.finditer(masked):
        if op.group("fd") in (None, "0"):
            word = _SHELL_WORD.match(rest, op.end())
            sources.append(("dup" if op.group("op") == "&" else "file", word.group(0) if word else None))
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
    raw = _unquote(word)
    text = _read(_resolve(raw, assigned, base))
    if text is None:
        unread.append(raw)
        return
    _add(counts, count_kinds(text))


def judge_command(command: str, cwd: str | None, shell: str) -> tuple[dict[str, int], list[str]]:
    """gh 명령 → (꼴별 개수, 못 잰 것들). 명령 글자 · heredoc · 인라인 본문 · 본문 파일을 잰다.

    명령 글자 전체에서는 홈 경로 꼴만 빼고 잰다 — 거기 든 경로는 본문 파일 · cd 같은 로컬 인자다. 홈 경로는 게시될 글
    (heredoc 본문 · 인라인 본문 · 본문 파일)에서만 센다. 인라인 본문의 변수는 같은 명령 안의 글자 대입으로 풀어 잰다 —
    그 값은 명령 글자(대입)에 있으니 홈 경로만 더 센다. 못 풀면 못 잰 것이다.
    A gh command → (per-kind counts, what could not be measured).
    """
    counts = count_kinds(command, skip=("local-home-path",))
    unread: list[str] = []
    for heredoc in _HEREDOC.finditer(command):
        body = heredoc.group("body") or ""
        if heredoc.group("quote"):
            _add(counts, _count_value(body, expanded=False))
            continue
        # 따옴표 없는 끝 표시 — bash 가 펼친다. 그 앞의 글자 대입으로만 풀고, 못 풀면 못 잰 것이다.
        # Unquoted delimiter: bash expands the body; resolve only from earlier literal assignments.
        earlier = {m.group(1): _unquote(m.group(2)) for m in _ASSIGN.finditer(command[:heredoc.start()])}
        value = None if ("$(" in body or "`" in body) else _expand_text(body, earlier)
        if value is None:
            unread.append("(따옴표 없는 heredoc 본문이 펼쳐진다 — 펼친 값을 못 잰다)")
            continue
        _add(counts, _count_value(value, expanded=value != body))
    stripped = _HEREDOC.sub(lambda m: (_HEREDOC_MARK if m.group("fd") in (None, "0") else _OTHER_FD_HEREDOC_MARK)
                            + m.group("tail"), command)
    for seg in _GH_SEGMENT.finditer(stripped):
        rest = seg.group("rest")
        words = _split(rest, shell)
        if words is None:
            unread.append("(gh 명령을 낱말로 나누지 못했다)")
            continue
        before = stripped[:seg.start()]
        assigned = {m.group(1): _unquote(m.group(2)) for m in _ASSIGN.finditer(before)}
        base: Path | None = Path(cwd or os.getcwd())
        if _UNMODELLED_DIR_CHANGE.search(before):
            base = None
        else:
            cds = [_unquote(m.group(1)) for m in _CD.finditer(before)]
            if cds:
                base = _resolve(cds[-1], assigned, base)
        paths, texts = _targets(words)
        for text in texts:
            if "$(" in text or "`" in text:
                unread.append("(인라인 본문이 명령 치환이다)")
                continue
            expanded = _expand_text(text, assigned)
            if expanded is None:
                unread.append("(인라인 본문의 변수를 같은 명령 안의 대입으로 풀지 못했다)")
                continue
            _add(counts, _count_value(expanded, expanded=expanded != text))
        if "-" in paths:
            _measure_stdin(rest, before, assigned, base, counts, unread)
        for raw in paths:
            if raw == "-":
                continue  # stdin — 위에서 한 번 잰다 / measured once above
            text = _read(_resolve(raw, assigned, base))
            if text is None:
                unread.append(raw)
                continue
            _add(counts, count_kinds(text))
    return counts, unread


def _deny(reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=True))
    return 0


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
        return _deny("[게시 전 검사] 판정 불가 — 훅 입력을 읽지 못했다. 명령을 다시 시도하세요(scripts/scan_publish.py).")
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
