"""세션 시작 — 지금 도는 훅 · 설정이 main 의 것인가 (원장 #1917 M01 P1-1 ~ P1-3).

리포 훅은 `${CLAUDE_PROJECT_DIR}`(주 체크아웃)의 파일로 돈다. 주 체크아웃이 기능 브랜치에 머물거나 origin/main 보다
뒤처지면 머지된 훅 · 설정 변경이 이 세션에 적용되지 않는다 — 11-15 ~ 11-21 실제로 10 PR 이 4~6일 꺼져 있었고 아무도
몰랐다. 이 스크립트는 그 상태를 한 줄씩 알린다.

- 네트워크를 쓰지 않는다 — 마지막 fetch 의 `origin/main` 과 비교한다(세션 시작을 늦추지 않는다).
- 늘 exit 0 이다 — 세션 시작 훅이 막히면 세션 자체가 막힌다. git 이 없거나 저장소가 아니면 조용하다.
- 비교 범위는 훅 표면(`.claude/` · `scripts/`)뿐이다 — 앱 코드 차이는 훅과 무관하다.

Session start: say so when the hooks running from the main checkout are not main's (branch or stale surface).
Offline, always exit 0, silent outside a git repository.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 — 고정 인자의 git 만 부른다 / fixed-argument git only
import sys

SURFACE = (".claude", "scripts")
_BASE_REF = "origin/main"


def advice(branch: str, differing: list[str]) -> list[str]:
    """알릴 줄 목록 — 비면 조용하다. branch 는 `git rev-parse --abbrev-ref HEAD` 값(분리되면 «HEAD»)."""
    lines = []
    if branch != "main":
        where = "분리된 HEAD" if branch == "HEAD" else branch
        lines.append(f"🔴 주 체크아웃이 main 이 아니다({where}) — 리포 훅 · 설정은 이 작업 트리의 파일로 돈다. "
                     "작업은 워크트리에서 하고 주 체크아웃은 `git switch main && git pull --ff-only`")
    if differing:
        lines.append(f"🔴 지금 도는 훅 ≠ {_BASE_REF} 의 훅 — {' · '.join(SURFACE)} 에서 {len(differing)} 파일이 다르다"
                     f"(예: {', '.join(differing[:3])}). main 으로 당긴 뒤 세션을 다시 시작해야 등록 변경까지 적용된다")
    return lines


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, encoding="utf-8",  # nosec B603 B607
                          errors="replace", check=False, timeout=10)


def main() -> int:
    try:
        # 🔴 try 안이다 — 지워진 작업 디렉터리에서 os.getcwd() 가 FileNotFoundError 를 낸다(Grok `2c797603` 반례)
        # Inside the try: os.getcwd() raises FileNotFoundError in a deleted working directory.
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        head = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
        if head.returncode != 0:
            return 0  # 저장소가 아니다 / not a repository
        if _git(root, "rev-parse", "--verify", "--quiet", _BASE_REF).returncode != 0:
            return 0  # 비교할 기준이 없다(원격 없음 · fetch 전) / nothing to compare against
        diff = _git(root, "diff", "--name-only", _BASE_REF, "--", *SURFACE)
        differing = [p for p in diff.stdout.splitlines() if p.strip()] if diff.returncode == 0 else []
        for line in advice(head.stdout.strip(), differing):
            print(line)
    except (OSError, subprocess.SubprocessError):
        return 0  # git 이 없거나 멈췄다 — 세션을 막지 않는다 / no git or it hung; never block the session
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            continue
    sys.exit(main())
