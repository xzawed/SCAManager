#!/usr/bin/env python3
"""PostToolUse(Bash) — 보호 경로가 Bash 로 바뀐 것을 «탐지» 한다. 차단하지 않는다.

## 무엇을 닫는가 (회고 2026-09-07 B)

`check_edit_allowed.py` 는 이 리포의 **유일한 차단 훅**이고 `Write|Edit|MultiEdit` 에만
걸려 있다. 그래서 테스트 불가 환경에서 Bash 로 보호 경로를 고치면 그 차단을 통째로
우회한다 — `.pre-commit-config.yaml` 에도 동등한 검사가 없어 하류에서 다시 보지 않는다.

## 🔴 이 훅이 «하지 못하는» 것 — 이름과 문서가 이것을 감추지 않게 한다

**막지 못한다.** PostToolUse 는 도구가 «끝난 뒤» 불리므로 파일은 이미 바뀌어 있다.
이 축은 그 변경을 **보이게** 만들 뿐이고, 되돌리지도 않는다.

그럼 왜 PreToolUse 로 막지 않는가 — Bash 훅이 받는 것은 «명령 문자열» 이고, 그 안에서
파일 쓰기를 알아내려면 `>`·`>>`·`tee`·`sed -i`·`cp`·`mv`·`install`·`python -c`·heredoc 을
전부 정규식으로 가려야 한다. 우회면이 무한하므로 그런 판정은 «막는다» 고 이름 붙일 수
없다 — 이 리포에는 「거짓 집행자는 부재보다 나쁘다」가 기록돼 있고, 부분 차단을 완전
차단으로 읽히게 두는 것이 정확히 그 형태다.

되돌리기(`git checkout --`)는 불변식을 복원하지만 사용자가 «의도한» 편집도 지운다.
파괴적 동작이라 이 훅은 하지 않는다 — 그 결정은 사람 몫이다.

Detection only: PostToolUse runs after the write, so this cannot prevent anything. Parsing
Bash for writes has an unbounded evasion surface, so it must not be named a block.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HOOKS))

# 🔴 보호 경로 정의와 환경 판정은 **차단 훅과 같은 것을 쓴다.** 복사하면 한쪽만 고쳐지는
#    순간 두 훅이 다른 파일을 보호하게 되고, 그 어긋남은 조용하다.
from check_edit_allowed import can_run_tests, protected_reason  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / ".git" / "protected-bash-write-reported"


def _make_stdout_safe() -> None:
    """Windows cp949 stdout 크래시 방지 — 관용구 복제(정책 16 최소 추상화)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def dirty_protected_paths() -> list[tuple[str, str]]:
    """작업 트리에서 변경된 보호 경로 — [(경로, 사유)]. git 을 못 쓰면 빈 목록."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "-z"], cwd=_ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    found = []
    for entry in out.stdout.split("\0"):
        if len(entry) < 4:
            continue
        path = entry[3:]
        reason = protected_reason(path)
        if reason:
            found.append((path, reason))
    return sorted(set(found))


def _fingerprint(path: str) -> str:
    """작업 트리 파일 «내용» 의 지문 — 같은 경로가 Bash 로 «다시» 바뀌면 다시 알리기 위해.
    지워진 파일은 `absent` 라는 하나의 상태다.
    Content fingerprint of the working-tree file, so a second change to the same path re-reports.
    """
    try:
        return hashlib.sha256((_ROOT / path).read_bytes()).hexdigest()[:16]
    except OSError:
        return "absent"


def already_reported(session: str) -> dict[str, str]:
    """이 세션이 이미 알린 {경로: 지문} — 같은 내용으로 매 Bash 호출마다 떠들지 않게 한다.

    🔴 억제는 «이 세션 · 이 내용» 까지만이다. 종전 판은 알린 경로를 클론 수명 내내 쌓기만 해서,
    그 경로가 커밋·되돌림 뒤 다시 바뀌어도, 다른 세션에서 바뀌어도 다시는 알리지 않았다.
    다른 세션의 기록·옛 형식(줄 목록)은 버린다 — 한 번 더 알리는 쪽이 조용해지는 쪽보다 낫다.
    Suppression is scoped to this session and this content; other sessions' records are dropped.
    """
    try:
        data = json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # 깊은 중첩은 ValueError 가 아니다 / not a ValueError
        return {}
    if not isinstance(data, dict) or data.get("session") != session:
        return {}
    reported = data.get("reported")
    if not isinstance(reported, dict):
        return {}
    return {str(p): str(fp) for p, fp in reported.items()}


def remember(session: str, reported: dict[str, str]) -> None:
    """지금 더러운 경로만 남긴다 — 깨끗해진(커밋·되돌림) 경로는 빠져, 다시 바뀌면 다시 알린다.
    Keep only currently dirty paths; a path that became clean re-reports when it changes again.
    """
    try:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps({"session": session, "reported": reported}, sort_keys=True),
                          encoding="utf-8")
    except OSError:
        pass  # 상태를 못 남기면 다음에 다시 알린다 — 조용해지는 것보다 낫다


def build_message(fresh: list[tuple[str, str]]) -> str:
    lines = [
        "🔴 보호 경로가 Bash 로 변경됐고, 이 환경에서는 테스트로 검증할 수 없습니다.",
        "   (Write/Edit 였다면 `check_edit_allowed` 가 **막았을** 변경입니다)",
    ]
    lines += [f"     - {p} — {r}" for p, r in fresh]
    lines += [
        "   이 훅은 «탐지» 만 합니다 — 이미 바뀐 파일을 막지도 되돌리지도 않습니다.",
        "   검증 가능한 환경에서 다시 보거나, 되돌리려면 직접 `git checkout --` 하세요.",
    ]
    return "\n".join(lines)


def main() -> int:
    _make_stdout_safe()
    try:
        payload = json.load(sys.stdin)  # 세션 id 만 읽는다 — 판정은 작업 트리로 한다
    except (ValueError, RecursionError):
        payload = {}  # 입력이 없거나 깨져도 판정은 작업 트리로 한다 / verdict comes from the tree
    # 비어 있지 않은 문자열 id 만 세션으로 친다. 세션을 모르면 억제를 쓰지 않는다 — 모르는 두 실행을
    # 한 세션으로 합치면 앞 실행의 침묵을 물려받는다(숫자 1 · null 이 «id 없음» 과 합쳐지던 반례).
    # Only a non-empty string id names a session; without one, nothing is suppressed or recorded.
    raw = payload.get("session_id") if isinstance(payload, dict) else None
    session = raw if isinstance(raw, str) and raw else ""
    # 🔴 검증 가능한 환경에서는 차단 훅도 통과시킨다 — 같은 조건을 그대로 쓴다.
    if can_run_tests():
        return 0
    dirty = dirty_protected_paths()
    seen = already_reported(session) if session else {}
    now = {p: _fingerprint(p) for p, _ in dirty}
    fresh = [(p, r) for p, r in dirty if seen.get(p) != now[p]]
    if session and now != seen:
        remember(session, now)
    if fresh:
        print(json.dumps({"systemMessage": build_message(fresh)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
