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


def is_src_file(path):
    """편집 파일이 src/ 하위 파일인지.
    Whether the edited file lives under src/."""
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


def derive_test_target(path):
    """편집된 src 파일 → 대응 tests/unit 서브영역(상대 경로). 서브영역 없으면 None.
    Map an edited src file to its tests/unit subarea; None if there's no subarea.

    src/gate/engine.py → tests/unit/gate ; src/main.py → None (collection 스모크 fallback).
    """
    if not is_src_file(path):
        return None
    parts = [p for p in _after_src(path).split("/") if p]
    if len(parts) < 2:  # src 직속 파일 — 서브영역 없음 / direct src file, no subarea
        return None
    return f"tests/unit/{parts[0]}"


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
    target = derive_test_target(path)
    base = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if target and (repo / target).is_dir():
        scope, cmd = target, [*base, target, "-x", "--timeout=15"]
    else:
        # 대응 서브영역 없음(직속 파일 등) → collection 스모크(import/parametrize 파손 = #1041 클래스 조기 탐지).
        # No matching subarea → collection smoke (catches import/parametrize breakage — the #1041 class).
        scope, cmd = "tests/unit (collect)", [*base, "tests/unit", "--co"]

    rc, tail = _run(cmd, cwd=str(repo))
    banner = "✅ 스모크 통과" if rc == 0 else ("⚠️ 스모크 미완(타임아웃/오류)" if rc is None else "❌ 스모크 실패")
    print(f"{banner} [{scope}] — best-effort 조기탐지 (전체 게이트=push-time 6-step ②)")
    if rc != 0 and tail:
        print(tail)
    return 0  # 비차단 advisory / non-blocking advisory


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure
    sys.exit(main())
