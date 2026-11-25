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
        r"(?!(?:localhost|127\.0\.0\.1|host|db|postgres|<[^>]*>|\$?\{[^}]*\})(?:[:/\"'\s]|$))"
        r"(?![^/:\s\"']*\.example\.(?:com|org|net)(?:[:/\"'\s]|$))"
        r"[^/:\s\"']+"
    ),
    "jwt": r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}",
    "telegram-bot-token": r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b",
    "slack-token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "aws-key": r"\bAKIA[0-9A-Z]{16}\b",
    "private-key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "assigned-secret": r"(?i)\b(?:SECRET|TOKEN|PASSWORD|API_KEY|ENCRYPTION_KEY)[A-Z_]*\s*[=:]\s*[\"']?[A-Za-z0-9+/_-]{24,}",
    # 사람 주소 — 공개용 주소(noreply · 예시 · git SSH)는 아래 `_PUBLIC_EMAIL` 이 뺀다.
    "email": r"(?<![\w.+:/%-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b",
    # 개인 홈 경로(사용자 이름이 든다) — CI 러너 경로는 사람 것이 아니다.
    "local-home-path": r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"'`]+|/Users/[^/\s\"'`]+|/home/(?!runner/)[^/\s\"'`]+",
}
_COMPILED = {kind: re.compile(rx) for kind, rx in _KINDS.items()}
# 공개해도 되는 주소 — 커밋 서명용 noreply · 예시 도메인 · git SSH 원격.
# Public addresses: noreply signatures, example domains, the git SSH remote.
_PUBLIC_EMAIL = re.compile(r"(?i)^(?:noreply@anthropic\.com|[^@]+@users\.noreply\.github\.com|[^@]+@example\.(?:com|org|net)"
                           r"|git@github\.com)$")

_MAX_BYTES = 2_000_000


def count_kinds(text: str, skip: tuple[str, ...] = ()) -> dict[str, int]:
    """꼴별 개수(0 은 뺀다) — 맞은 글자는 돌려주지 않는다. / Per-kind counts, zeros omitted; never the matches."""
    counts = {}
    for kind, rx in _COMPILED.items():
        if kind in skip:
            continue
        hits = rx.findall(text or "") if kind != "email" else [
            m.group(0) for m in rx.finditer(text or "") if not _PUBLIC_EMAIL.match(m.group(0))]
        if hits:
            counts[kind] = len(hits)
    return counts


def _summary(counts: dict[str, int]) -> str:
    return " · ".join(f"{kind} {n}" for kind, n in sorted(counts.items()))


# --- 훅: gh 명령이 가리키는 본문 ------------------------------------------------------------------------------
# --- hook: the bodies a gh command points at ---

# heredoc 본문은 명령 글자 검사에서 이미 잰다 — 낱말로 나눌 때는 걷어 낸다(그 안의 따옴표가 나누기를 깨뜨린다).
# Heredoc bodies are covered by the full-text scan; drop them before splitting (their quotes break shlex).
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.S)
_GH_SEGMENT = re.compile(r"(?:^|(?<=[\s;&|(]))gh(?:\.exe)?\s+(?P<rest>[^\n;&|]*)")
_ASSIGN = re.compile(r"(?:^|(?<=[\s;&|]))([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]*)")
_CD = re.compile(r"(?:^|(?<=[\s;&|(]))cd\s+(\"[^\"]*\"|'[^']*'|[^\s;&|]+)")
_VAR = re.compile(r"\$(?:\{(\w+)\}|(\w+))")
# 본문 파일을 받는 플래그 — api 밖(issue · pr · release …)에서. api 는 `key=@파일` 필드와 `--input` 을 본다.
# Flags taking a body file outside `gh api`; for api, `key=@file` fields and `--input`.
_BODY_FILE_FLAGS = ("--body-file", "-F", "--notes-file")
_API_FIELD_FLAGS = ("-F", "--field", "-f", "--raw-field")


def _unquote(word: str) -> str:
    return word[1:-1] if len(word) >= 2 and word[0] == word[-1] and word[0] in "\"'" else word


def _split(rest: str, shell: str) -> list[str] | None:
    try:
        words = shlex.split(rest, posix=shell != "powershell")
    except ValueError:
        return None
    return [_unquote(w) for w in words] if shell == "powershell" else words


def _body_paths(words: list[str]) -> list[str]:
    """한 gh 호출의 낱말 → 본문 파일 경로들(`-` 은 stdin 이라 뺀다). / Body-file paths of one gh call ('-' = stdin)."""
    group = words[0] if words else ""
    paths = []
    for i, word in enumerate(words):
        flag, _, inline = word.partition("=")
        value = inline if inline and flag.startswith("--") else (words[i + 1] if i + 1 < len(words) else "")
        if group == "api":
            if flag in _API_FIELD_FLAGS and "=@" in value:
                paths.append(value.split("=@", 1)[1])
            elif flag == "--input":
                paths.append(value)
        elif flag in _BODY_FILE_FLAGS:
            paths.append(value)
    return [p for p in paths if p and p != "-"]


def _resolve(path: str, assigned: dict[str, str], base: Path) -> Path | None:
    """같은 명령 안의 대입 · 환경 변수로 경로를 푼다 — 명령 치환 · 못 푼 변수는 None. / Expand vars; None if unresolvable."""
    if "$(" in path or "`" in path:
        return None
    expanded = _VAR.sub(lambda m: assigned.get(m.group(1) or m.group(2), os.environ.get(m.group(1) or m.group(2), "\0")), path)
    if "\0" in expanded or "$" in expanded:
        return None
    p = Path(os.path.expanduser(expanded))
    return p if p.is_absolute() else base / p


def judge_command(command: str, cwd: str | None, shell: str) -> tuple[dict[str, int], list[str]]:
    """gh 명령 → (꼴별 개수, 못 잰 본문 경로들). 명령 글자 전체 + 가리키는 본문 파일을 잰다.
    A gh command → (per-kind counts, body paths that could not be read)."""
    # 명령 글자에서는 홈 경로 꼴을 재지 않는다 — 거기 든 경로는 본문 파일 · cd 같은 로컬 인자이고 게시되지 않는다.
    # (본문 파일 안의 홈 경로는 아래에서 잰다.) / Home paths in the command are local arguments, not published text.
    counts = count_kinds(command, skip=("local-home-path",))
    stripped = _HEREDOC.sub("<<", command)
    assigned = {m.group(1): _unquote(m.group(2)) for m in _ASSIGN.finditer(stripped)}
    unread = []
    for seg in _GH_SEGMENT.finditer(stripped):
        words = _split(seg.group("rest"), shell)
        if words is None:
            unread.append("(gh 명령을 낱말로 나누지 못했다)")
            continue
        cds = [_unquote(m.group(1)) for m in _CD.finditer(stripped[:seg.start()])]
        base = Path(cwd or os.getcwd())
        if cds:
            cd_dir = _resolve(cds[-1], assigned, base)
            base = cd_dir if cd_dir is not None else base
        for raw in _body_paths(words):
            path = _resolve(raw, assigned, base)
            try:
                if path is None or path.stat().st_size > _MAX_BYTES:
                    raise OSError("unresolved or too large")
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                unread.append(raw)
                continue
            for kind, n in count_kinds(text).items():
                counts[kind] = counts.get(kind, 0) + n
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
