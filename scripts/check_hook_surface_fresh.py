"""세션 시작 — 지금 도는 훅 · 설정이 main 의 것인가 (원장 #1917 M01 P1-1 ~ P1-3).

리포 훅은 `${CLAUDE_PROJECT_DIR}`(주 체크아웃)의 파일로 돈다. 주 체크아웃이 기능 브랜치에 머물거나 origin/main 보다
뒤처지면 머지된 훅 · 설정 변경이 이 세션에 적용되지 않는다 — 11-15 ~ 11-21 실제로 10 PR 이 4~6일 꺼져 있었고 아무도
몰랐다. 이 스크립트는 그 상태를 한 줄씩 알린다.

- 네트워크를 쓰지 않는다 — 마지막 fetch 의 `origin/main` 과 비교한다(세션 시작을 늦추지 않는다).
- 늘 exit 0 이다 — 세션 시작 훅이 막히면 세션 자체가 막힌다. 저장소가 아니거나 origin/main 이 없으면 조용하고,
  git 을 못 부르거나 실패하면 «못 쟀다» 한 줄을 찍는다.
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


def _git(root: str, *args: str) -> str:
    """git 을 돌려 stdout — 실패하면 exit 2(리포 가드 관용구 · `test_guard_git_failclosed`). 빈 결과로 숨기지 않는다.
    Run git and return stdout; exit 2 on failure (the repo's guard idiom) — never hide a failure as an empty result.
    """
    proc = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, encoding="utf-8",  # nosec B603 B607
                          errors="replace", check=False, timeout=10)
    if proc.returncode != 0:
        sys.exit(2)
    return proc.stdout


def _has_repo_and_base(root: str) -> bool:
    """저장소이고 비교 기준(origin/main)이 있는가 — 둘 다 없을 수 있는 정상 상태라 실패로 치지 않는다."""
    for args in (("rev-parse", "--git-dir"), ("rev-parse", "--verify", "--quiet", _BASE_REF)):
        probe = subprocess.run(["git", "-C", root, *args], capture_output=True, check=False, timeout=10)  # nosec B603 B607
        if probe.returncode != 0:
            return False
    return True


def main() -> int:
    try:
        # 🔴 try 안이다 — 지워진 작업 디렉터리에서 os.getcwd() 가 FileNotFoundError 를 낸다(Grok `2c797603` 반례)
        # Inside the try: os.getcwd() raises FileNotFoundError in a deleted working directory.
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        if not _has_repo_and_base(root):
            return 0  # 저장소가 아니거나 비교 기준이 없다(원격 없음 · fetch 전) / nothing to compare against
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
        differing = [p for p in _git(root, "diff", "--name-only", _BASE_REF, "--", *SURFACE).splitlines() if p.strip()]
        for line in advice(branch, differing):
            print(line)
    except (SystemExit, subprocess.SubprocessError, OSError):
        # 🔴 못 재면 조용히 넘기지 않고 알린다 — git 실패 · 시간 초과 · git 을 못 부름 · 작업 디렉터리가 사라짐
        #    (Grok `2c797603` 반례 둘). 세션 시작 훅이라 막지는 않는다(늘 exit 0).
        # Say that it could not be measured (git failed, hung, missing, or the cwd vanished); never block the session.
        print("⚠️ 훅 최신성을 못 쟀다 — git 이 실패했거나 멈췄거나 없다(세션은 그대로 시작한다)")
        return 0
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            continue
    sys.exit(main())
