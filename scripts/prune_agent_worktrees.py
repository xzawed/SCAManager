#!/usr/bin/env python3
"""에이전트 격리 worktree 자동 정리 — **깨끗한 것만** 지운다.

2026-08-17 실측: Grok 위임이 남긴 worktree 41개가 쌓여 브랜치를 잠그고 있었다
(`git branch -D` 가 "used by worktree" 로 거부). 규율로 두면 지켜지지 않으므로 기전으로 둔다.

계약: 미커밋 변경이 하나라도 있으면 **건드리지 않는다**. exit 0 (advisory).
Removes only clean agent worktrees; anything dirty is left alone.
"""
from __future__ import annotations

import subprocess  # nosec B404
import sys
from pathlib import Path

# 에이전트 도구가 만드는 격리 worktree 만 대상. 사람이 만든 worktree 는 건드리지 않는다.
# Only worktrees created by agent tooling; never a human's.
_AGENT_DIRS = (".grok-build/worktrees/", "/scratchpad/wt")


def _git(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=60,
    )


def agent_worktrees(root: Path) -> list[str]:
    """`git worktree list` 에서 에이전트 격리 worktree 경로만 (주 worktree 제외)."""
    out = _git("worktree", "list", "--porcelain", cwd=str(root)).stdout
    paths = [line[9:] for line in out.split("\n") if line.startswith("worktree ")]
    return [p for p in paths[1:] if any(m in p.replace("\\", "/") for m in _AGENT_DIRS)]


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).

    🔴 standalone 실행이라 공유 헬퍼를 import 할 수 없어 검증된 4줄 관용구를 복제한다
    (정책 16 최소 추상화). 누락은 `tests/unit/scripts/test_stdout_encoding_guard.py` 가 잡는다 —
    실제로 이 스크립트의 초판이 그 가드 없이 `UnicodeEncodeError` 로 죽었다.
    Duplicated 4-line idiom; scripts run standalone. A regression guard asserts no script is unguarded.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def main(root: Path | None = None) -> int:
    """`root` 는 테스트 주입용 — 기본은 이 스크립트가 사는 리포.

    🔴 인자로 받는 이유: 테스트가 `Path.resolve` 를 패치하면 **전역**이라 pytest 내부까지
    깨진다(실측: 이 테스트 초판이 그렇게 멈췄다). 주입 지점을 만드는 쪽이 싸다.
    Injected for tests; patching Path.resolve is global and hangs pytest.
    """
    _make_stdout_safe()
    root = root or Path(__file__).resolve().parents[1]
    targets = agent_worktrees(root)
    if not targets:
        return 0

    removed, kept = [], []
    for path in targets:
        status = _git("-C", path, "status", "--porcelain")
        # 🔴 상태를 못 읽으면 지우지 않는다 — 모르는 것을 깨끗하다고 읽지 않는다.
        # Undecidable status is never treated as clean.
        if status.returncode != 0 or status.stdout.strip():
            kept.append(path)
            continue
        if _git("worktree", "remove", path, cwd=str(root)).returncode == 0:
            removed.append(path)
        else:
            kept.append(path)

    _git("worktree", "prune", cwd=str(root))
    print(f"🧹 에이전트 worktree — 정리 {len(removed)}개 · 미커밋 변경이 있어 보존 {len(kept)}개")
    for path in kept:
        print(f"   보존: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
