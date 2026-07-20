#!/usr/bin/env python3
"""PostToolUse pytest 스모크 훅 — src 편집 후 대응 tests/unit 서브영역만 빠르게 실행.
PostToolUse pytest smoke hook — after a src edit, quickly run only the matching tests/unit subarea.

회고 2026-07-18 P1 테마 C: 기존 훅은 `pytest tests/`(전체 5566)를 60s 타임아웃에 돌려 완주 불가 →
SIGTERM → `|| true` 로 삼켜져 **false-green**. 'Hook 신뢰' 필수 원칙의 토대가 붕괴했다. 편집된 src
경로 → 대응 tests/unit 서브디렉토리(없으면 collection 스모크)만 돌리면 실제로 완주하는 신호가 된다.
Retro 2026-07-18 P1 theme C: the old hook ran the full suite in a 60s timeout → SIGTERM → `|| true`
swallow → false-green. Scoping to the affected subarea makes the signal actually finish.

🔴 이 훅은 **best-effort 조기 실패 탐지** — 전체 게이트가 아니다. 전체 게이트는 push-time(6-step ②)로
위임된다. 비차단(advisory·항상 exit 0) — 결과는 배너(✅/❌)로 가시화, edit 을 막지 않음.
This hook is best-effort early-failure detection, NOT the full gate (that stays at push-time 6-step ②).
Non-blocking (always exit 0); the result is shown via a ✅/❌ banner.

사용법 / Usage: PostToolUse 훅 (stdin 으로 tool_input JSON 수신).
"""
import json
import subprocess
import sys
from pathlib import Path

# 스코프 실행 타임아웃(초) — 서브영역 단위라 대개 <30s. 훅 자체는 settings.json timeout 이 상한.
# Scoped-run timeout (s) — a subarea usually runs in <30s; settings.json timeout bounds the hook.
_RUN_TIMEOUT = 75


def _norm(path):
    """경로 정규화 — 백슬래시 → 슬래시.
    Normalize path separators (backslash → slash)."""
    return (path or "").replace("\\", "/")


# 감시 대상 최상위 디렉토리 — src/ 만이 아니다.
# Watched top-level roots — not just src/.
#   🔴 `alembic/` 은 이번 사이클 최다 결함 영역(#1102 fileConfig 가 앱 로깅을 파괴)이고
#      `scripts/` 는 최다 churn(가드 스크립트 다수)인데 둘 다 훅이 **아예 발동하지 않았다**.
#      결함이 가장 많은 곳에 조기탐지가 0이었다.
_WATCHED_ROOTS = ("src", "alembic", "scripts")


def is_watched_file(path):
    """편집 파일이 감시 대상 루트 하위 Python 파일인지.
    Whether the edited file lives under a watched root."""
    p = _norm(path)
    if not p.endswith(".py"):
        return False
    return any(f"/{r}/" in p or p.startswith(f"{r}/") for r in _WATCHED_ROOTS)


def is_src_file(path):
    """하위 호환 별칭 — 기존 호출부/테스트 보존.
    Backwards-compatible alias."""
    p = _norm(path)
    return "/src/" in p or p.startswith("src/")


def _after_src(path):
    """src/ 이후 상대 경로 반환 (src 아니면 '')."""
    p = _norm(path)
    if "/src/" in p:
        return p.split("/src/", 1)[1]
    if p.startswith("src/"):
        return p[len("src/"):]
    return ""


def _root_and_rest(path):
    """감시 루트와 그 이후 상대 경로 — (`"src"`, `"gate/engine.py"`) 형태."""
    p = _norm(path)
    for root in _WATCHED_ROOTS:
        if f"/{root}/" in p:
            return root, p.split(f"/{root}/", 1)[1]
        if p.startswith(f"{root}/"):
            return root, p[len(root) + 1:]
    return None, ""


def derive_test_target(path, repo=None):
    """편집 파일 → 대응 테스트 경로(디렉토리 또는 **파일**). 없으면 None.

    Map an edited file to its test target — a directory OR a specific file.

    · `src/gate/engine.py`  → `tests/unit/gate`            (서브영역 디렉토리)
    · `src/scheduler.py`    → `tests/unit/test_scheduler.py`  🔴 **정확 대응 파일**
    · `scripts/foo.py`      → `tests/unit/scripts/test_foo.py`
    · `alembic/env.py`      → `tests/unit/migrations`

    🔴 **왜 정확 대응 파일까지 보는가 (2026-07-19 회고 P2 D10)**: 이전 판은 `len(parts) < 2`
    이면 무조건 collection 스모크로 **강등**했다. 그런데 `src/` 직속 7파일 중 **6개가 정확히
    대응하는 테스트 파일을 갖고 있다**(config·crypto·database·logging_config·main·scheduler).
    즉 실행 가능한 단언이 있는데 0-단언 수집으로 내려앉고 있었다 — 그중 `logging_config.py` 는
    이 사이클의 토큰 유출 봉인 지점이고 `scheduler.py` 는 cron P0 대체 코어다.
    The previous version demoted every src-direct file to a 0-assertion collection smoke, even
    though 6 of 7 have an exact matching test file.
    """
    root, rest = _root_and_rest(path)
    if root is None:
        return None
    repo = repo or Path(__file__).resolve().parents[2]
    parts = [p for p in rest.split("/") if p]
    if not parts:
        return None

    if root == "alembic":
        return "tests/unit/migrations"

    stem = parts[-1][:-3] if parts[-1].endswith(".py") else parts[-1]
    if stem == "__init__":
        return None

    if root == "scripts":
        exact = f"tests/unit/scripts/test_{stem}.py"
        return exact if (repo / exact).is_file() else "tests/unit/scripts"

    # root == "src"
    if len(parts) >= 2:
        return f"tests/unit/{parts[0]}"
    exact = f"tests/unit/test_{stem}.py"
    return exact if (repo / exact).is_file() else None


def _banner(rc, asserted):
    """결과 배너 — 🔴 **단언을 실행했는지**와 통과 여부를 구별한다.

    Build the result banner, distinguishing "assertions ran" from "collection only".

    🔴 사고 (2026-07-19 회고 P2 D12): 이전 판은 `--co`(수집만, **단언 0건**) 경로에도
    `✅ 스모크 통과` 를 출력했다. 아무것도 검증하지 않은 실행이 검증 통과로 보였다 —
    이 훅이 존재하는 이유였던 false-green 을 훅 자신이 재생산한 것이다.
    수집 성공은 "import 가 깨지지 않았다" 이지 "동작이 옳다" 가 아니다.
    A collection-only run asserts nothing; labelling it "passed" is the very false-green
    this hook was created to eliminate.
    """
    if rc is None:
        return "⚠️ 스모크 미완(타임아웃/오류)"
    if rc != 0:
        return "❌ 스모크 실패"
    return "✅ 스모크 통과" if asserted else "ℹ️ 수집만 확인 (단언 0건 — 대응 테스트 없음)"


def _run(cmd, cwd):
    """pytest 서브프로세스(cwd=repo 루트) — (returncode, tail 출력).
    Run a pytest subprocess from the repo root; return (returncode, tail output)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=cwd,
            timeout=_RUN_TIMEOUT, encoding="utf-8", errors="replace",
        )
        tail = "\n".join((r.stdout or "").splitlines()[-8:])
        return r.returncode, tail
    except subprocess.TimeoutExpired:
        return None, f"⏱️ 스모크 타임아웃({_RUN_TIMEOUT}s) — 전체 게이트는 push-time 에 실행 / smoke timed out"
    except OSError as e:
        return None, f"실행 오류 / run error: {e}"


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # 입력 파싱 실패 — advisory 훅은 조용히 통과 / unparsable input, pass quietly
    path = data.get("tool_input", {}).get("file_path", "")
    if not is_src_file(path):
        return 0  # src 편집만 대상 / only src edits

    repo = Path(__file__).resolve().parents[2]
    target = derive_test_target(path, repo)
    base = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    asserted = bool(target) and (repo / target).exists()
    if asserted:
        scope, cmd = target, [*base, target, "-x", "--timeout=15"]
    else:
        # 대응 테스트 없음 → collection 스모크(import/parametrize 파손 = #1041 클래스 조기 탐지).
        # No matching test → collection smoke (catches import/parametrize breakage).
        scope, cmd = "tests/unit (collect)", [*base, "tests/unit", "--co"]

    rc, tail = _run(cmd, cwd=str(repo))
    print(f"{_banner(rc, asserted)} [{scope}] — best-effort 조기탐지 (전체 게이트=push-time 6-step ②)")
    if rc != 0 and tail:
        print(tail)
    return 0  # 비차단 advisory / non-blocking advisory


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure
    sys.exit(main())
