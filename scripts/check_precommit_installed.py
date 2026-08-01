#!/usr/bin/env python3
"""로컬 pre-commit 계층이 실제로 살아 있는지 — 관측면 (backlog R23, 2026-08-01).

## 왜 만드나 (실측)

`.pre-commit-config.yaml` 에 시크릿 훅 4종(gitleaks · commit-msg-secrets · env-not-staged ·
secrets-in-diff)이 정의돼 있는데, **설치돼 있지 않으면 하나도 실행되지 않는다.** 그리고
그 사실을 관측하는 면이 리포 전체에 없었다 — 회고 2026-07-31 실측: 창 22 커밋 내내
**0회 실행**. `.git/hooks/pre-commit` 이 없으면 `git commit` 은 아무 말 없이 성공한다.

🔴 CI 의 TruffleHog 는 이 계층을 **대체하지 못한다** — `--only-verified` 라 검증된 시크릿만
보고, 무엇보다 **커밋이 이미 원격에 올라간 뒤**다. pre-commit 의 값은 "올라가기 전에 막는 것"
이고, 그 값은 설치돼 있을 때만 존재한다.

## 계약 (advisory — 정책 17 안정성)

- 이 스크립트는 **exit 0** 이다. 로컬 환경 상태는 리포가 강제할 수 없고, 차단하면 새 PC·CI·
  타 개발자 환경에서 세션 시작 자체가 막힌다(가드 자살).
- 대신 **loud** 하게 알린다. SessionStart 훅 stdout 은 Claude 컨텍스트에 주입되므로,
  "설치돼 있지 않다" 가 매 세션 관측된다 — 관측면 0 이던 것을 관측 가능하게 만드는 것이 전부다.
- 🔴 **이것이 "보호" 가 아니라 "관측" 임을 명시한다.** advisory 를 보호로 읽으면 그 자체가
  observer-lie 다(AGENTS.md 불변식 1).

Observability only: reports whether the local pre-commit layer is actually installed. Always
exits 0 — the repo cannot enforce local machine state, and blocking would break fresh clones/CI.
CI's TruffleHog does not substitute: it runs after the push and only on verified secrets.
"""
from __future__ import annotations

import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]


def git_hooks_dir(root: Path) -> Path | None:
    """이 작업트리의 실제 훅 디렉토리 — worktree 는 `.git` 이 파일이라 rev-parse 로 물어본다.
    Resolve the real hooks dir; in a worktree `.git` is a file, so ask git."""
    try:
        proc = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(root), timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return (root / proc.stdout.strip()).resolve()


def hook_is_precommit(hooks_dir: Path | None) -> bool:
    """`pre-commit` 훅 파일이 실재하고 **pre-commit 이 설치한 것**인지.

    존재만 보면 안 된다 — 다른 도구가 남긴 훅일 수 있다. pre-commit 이 생성한 스크립트는
    자기 식별 문자열을 담는다.
    Existence alone is not enough; another tool may own the hook. pre-commit self-identifies.
    """
    if hooks_dir is None:
        return False
    hook = hooks_dir / "pre-commit"
    if not hook.is_file():
        return False
    try:
        return "pre-commit" in hook.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def pre_push_gate_installed(hooks_dir: Path | None) -> bool:
    """`.git/hooks/pre-push` 가 실재하고 **이 리포의 게이트 러너를 부르는지**.

    🔴 존재만 보면 안 된다 — 다른 도구가 남긴 훅일 수 있고 빈 파일일 수도 있다. 배선 판정이므로
    `scripts/pre_push_gate.py` 호출까지 확인한다.

    🔴 이 훅은 **git 이 추적하지 않는다**(머신 고유). 리포는 그 존재를 강제할 수 없고 **관측만**
    할 수 있으므로 그 한계를 출력에 명시한다. `.pre-commit-config.yaml` 에 `stages: [pre-push]`
    를 적는 방식은 pre-commit 이 그 훅 타입을 **따로 설치**해야 동작하므로, 미설치 머신에서는
    한 번도 안 도는 가드가 된다 — 2026-08-01 Grok 설계 검토(`019fbc8e`)가 그 안을 기각했다.
    Local hooks are untracked, so the repo can only observe this, never enforce it.
    """
    if hooks_dir is None:
        return False
    hook = hooks_dir / "pre-push"
    if not hook.is_file():
        return False
    try:
        return "pre_push_gate.py" in hook.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def main() -> int:
    """관측 결과를 보고한다 — **항상 exit 0**(advisory)."""
    binary = shutil.which("pre-commit")
    installed = hook_is_precommit(git_hooks_dir(_ROOT))

    # 🔴 pre-push 게이트는 **별개 축**이다 — pre-commit 이 살아 있어도 이건 없을 수 있다.
    #    없으면 `pre_push_gate.py` 를 사람이 기억해서 돌려야 하고, 기억 의존은 이 리포가
    #    반복해 고쳐 온 실패 클래스다. 다만 로컬 훅은 추적 불가라 **관측만** 한다.
    # Separate axis: the pre-push gate can be absent even when pre-commit is healthy.
    if not pre_push_gate_installed(git_hooks_dir(_ROOT)):
        print(
            "ℹ️ pre-push 게이트 훅이 없습니다 — push 전 13 가드가 **자동 실행되지 않습니다**.\n"
            "   No pre-push hook: the local CI-guard runner will not run automatically.\n"
            "   수동 / manual  : `py -3 scripts/pre_push_gate.py`\n"
            "   자동화 / automate: `.git/hooks/pre-push` 에 그 명령을 넣고 실행 권한 부여\n"
            "   ⚠️ 로컬 훅은 git 이 추적하지 않아 리포가 강제할 수 없습니다 — 관측만 합니다."
        )

    if binary and installed:
        print("✅ pre-commit 계층 활성 — 시크릿 훅 4종이 커밋 시 실행됩니다")
        return 0

    print(
        "🔴 로컬 pre-commit 계층이 내려가 있습니다 — 시크릿 훅이 **커밋 시 실행되지 않습니다**.\n"
        "   Local pre-commit layer is down; the secret hooks do not run on commit.\n"
        f"   pre-commit 실행파일 / binary : {'있음' if binary else '없음 (PATH 부재)'}\n"
        f"   .git/hooks/pre-commit       : {'설치됨' if installed else '없음'}\n"
        "   대상 훅 / affected: gitleaks · check-commit-msg-secrets · check-env-not-staged ·\n"
        "                       check-secrets-in-diff (+ 문서·가드 훅 다수)\n"
        "   해결 / Fix: `pip install pre-commit && pre-commit install`\n"
        "   🔴 CI 의 TruffleHog 는 대체가 아닙니다 — `--only-verified` 이고 **push 이후**입니다.\n"
        "   ⚠️ 이 검사는 advisory(비차단)입니다 — 관측면일 뿐 보호가 아닙니다."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
