#!/usr/bin/env python3
"""공개 쓰기 전에 비밀값 · 개인정보 꼴을 센다 — 값은 찍지 않는다 (회고 원장 #1917 M02 P2-6).

리포는 공개다. Issue · PR 본문 · 댓글은 올리는 순간 공개되고 편집 이력에 남는다. 그래서 올리기 **전에** 잰다.

- 파일 검사: `py -3 scripts/scan_publish.py <파일>...` — 파일마다 꼴별 개수를 찍고, 하나라도 있으면 exit 1.
- 훅: `.claude/settings.json` PreToolUse(`if: Bash(gh *)` · `PowerShell(gh *)` — gh 명령에만 뜬다 · `onFailure: "block"`).
  명령 글자 전체와 그 명령이 가리키는 본문 파일(`--body-file` · `-F` · `--notes-file` · api 의 `key=@파일` · `--input`)을 재고,
  꼴이 있으면 deny 한다(종류 · 개수만 알린다). 경로를 못 풀거나 파일을 못 읽으면 막는다(못 재면 red).

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

# heredoc 본문은 게시될 글이다 — 따로 꺼내 재고, 낱말로 나눌 때는 걷어 낸다(그 안의 따옴표가 나누기를 깨뜨린다).
# Heredoc bodies are published text: scan them separately and drop them before splitting.
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1[^\n]*\n(?P<body>.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
_GH_SEGMENT = re.compile(r"(?:^|(?<=[\s;&|(]))gh(?:\.exe)?\s+(?P<rest>[^\n;&|]*)")
_ASSIGN = re.compile(r"(?:^|(?<=[\s;&|]))([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]*)")
_CD = re.compile(r"(?:^|(?<=[\s;&|]))cd\s+(\"[^\"]*\"|'[^']*'|[^\s;&|()]+)")
# 디렉터리를 바꾸지만 이 검사가 따라가지 못하는 꼴 — 그 뒤의 상대 경로 본문은 못 잰다(절대 경로를 요구한다).
# Directory changes this scanner does not model; a relative body path after one is unmeasurable.
_UNMODELLED_DIR_CHANGE = re.compile(
    r"(?i)(?:^|(?<=[\s;&|(]))(?:pushd|popd|set-location|push-location|pop-location|sl|chdir)(?=\s|$)"
    r"|(?:^|(?<=[\s;&|]))cd\s+-(?=\s|$)|\(\s*cd\s")
_INPUT_REDIRECT = re.compile(r"(?<![<\d])<(?!<)\s*(\"[^\"]*\"|'[^']*'|[^\s;&|<>()]+)")
_VAR = re.compile(r"\$(?:\{(\w+)\}|(\w+))")
# 본문 파일을 받는 플래그(api 밖) · 게시될 글을 받는 플래그 · api 필드 플래그 · gist 에서 값을 받는(파일이 아닌) 플래그.
# Body-file flags (outside api), published-text flags, api field flags, gist flags whose value is not a file.
_BODY_FILE_FLAGS = ("--body-file", "-F", "--notes-file")
_TEXT_FLAGS = ("--body", "-b", "--title", "-t", "--notes", "-n")
_API_FIELD_FLAGS = ("-F", "--field", "-f", "--raw-field")
_GIST_VALUE_FLAGS = ("-d", "--desc", "-f", "--filename")


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
            skip_next = _takes_separate_value(word, flag, _GIST_VALUE_FLAGS)
        elif group == "gist" and action == "edit" and flag in ("--add", "-a"):
            paths.append(value)
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


def _read(path: Path | None) -> str | None:
    try:
        if path is None or path.stat().st_size > _MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def judge_command(command: str, cwd: str | None, shell: str) -> tuple[dict[str, int], list[str]]:
    """gh 명령 → (꼴별 개수, 못 잰 것들). 명령 글자 · heredoc · 인라인 본문 · 본문 파일을 잰다.

    명령 글자 전체에서는 홈 경로 꼴만 빼고 잰다 — 거기 든 경로는 본문 파일 · cd 같은 로컬 인자다. 홈 경로는 게시될 글
    (heredoc 본문 · 인라인 본문 · 본문 파일)에서만 센다.
    A gh command → (per-kind counts, what could not be measured).
    """
    counts = count_kinds(command, skip=("local-home-path",))
    for heredoc in _HEREDOC.finditer(command):
        _add(counts, count_kinds(heredoc.group("body"), only=("local-home-path",)))
    stripped = _HEREDOC.sub("<<", command)
    unread = []
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
            else:
                _add(counts, count_kinds(text, only=("local-home-path",)))
        for raw in paths:
            if raw == "-":
                if "<<" in rest:
                    continue  # heredoc — 위에서 잰다 / measured above
                redirect = _INPUT_REDIRECT.search(rest)
                if redirect is None:
                    unread.append("(stdin 본문 — 어디서 오는지 모른다)")
                    continue
                raw = _unquote(redirect.group(1))
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
        lines.append(f"못 읽은 본문 {len(unread)}개 — 경로를 못 풀었거나(명령 치환 · 정의 안 된 변수) 파일을 못 읽었다. "
                     "경로를 그대로 적어 다시 시도한다(못 재면 막는다).")
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
