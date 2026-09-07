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


def already_reported() -> set[str]:
    """이미 알린 경로 — 같은 파일로 매 Bash 호출마다 떠들지 않게 한다."""
    try:
        return {ln.strip() for ln in _STATE.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def remember(paths: set[str]) -> None:
    try:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text("\n".join(sorted(paths)) + "\n", encoding="utf-8")
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
        json.load(sys.stdin)          # 입력 형태만 소비 — 판정은 작업 트리로 한다
    except (json.JSONDecodeError, ValueError):
        pass  # 입력이 없거나 깨져도 판정은 작업 트리로 한다 / verdict comes from the tree
    # 🔴 검증 가능한 환경에서는 차단 훅도 통과시킨다 — 같은 조건을 그대로 쓴다.
    if can_run_tests():
        return 0
    dirty = dirty_protected_paths()
    if not dirty:
        return 0
    seen = already_reported()
    fresh = [(p, r) for p, r in dirty if p not in seen]
    if not fresh:
        return 0
    remember(seen | {p for p, _ in fresh})
    print(json.dumps({"systemMessage": build_message(fresh)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
