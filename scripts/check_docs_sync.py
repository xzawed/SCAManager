#!/usr/bin/env python3
"""
docs 값 정합 점검 — README 배지 · 문서 인용이 원천(requirements.txt 핀 · pylint 값)과 맞는가.
docs value-sync checker — README badges and doc quotes against their sources.

🔴 테스트 수는 보지 않는다 — 문서에 적지 않기 때문이다. 원천은 실행 결과다
(PR 본문 수치 줄 ↔ CI junit = `check_test_count_sync.py` · E2E = `e2e/EXPECTED_COUNT` = `check_e2e_scope.py`).
Test counts are not documented, so they are not checked here; their sources are run results.

축 1 = 의존성 핀(check_dependency_pins) — **ground truth 대조**다. 문서끼리가 아니라
`requirements.txt` 실핀과 대조하므로, 문서 사본이 함께 틀려도 적발된다(backlog R15 재발 차단).
축 2 = pylint 값 4지점 동치(check_lint_badge) — CI `--fail-under` 가 README 배지에서 파생된다.
Axis 1 compares pins against requirements.txt (ground truth); axis 2 keeps the pylint sites equal.
"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# README FastAPI 배지: "FastAPI-0.141-009688" — 관례상 핀의 major.minor 만 표기
# README FastAPI badge — by convention it carries only the pin's major.minor
_FASTAPI_BADGE = re.compile(r"FastAPI-(\d+\.\d+)-")
# README FastAPI 배지가 파생되는 핀 이름
# Pin names the README FastAPI badge derives from
_DOC_PIN_NAMES = ("fastapi", "starlette")
# 버전 문자열 (PEP 440 흔한 형태 — 숫자로 시작, 이후 숫자/문자/점/하이픈)
_VERSION = r"[0-9][0-9A-Za-z.\-]*"


def _first(pattern: re.Pattern, text: str) -> str | None:
    """첫 매치의 첫 그룹, 없으면 None. / First match's first group, or None."""
    m = pattern.search(text)
    return m.group(1) if m else None


def check_dependency_pins(project_root: Path) -> tuple[bool, list[str]]:
    """requirements.txt 실핀 ↔ 문서 인용·배지 정합을 검사해 (ok, 메시지 목록) 반환.

    기대값을 `requirements.txt`(ground truth)에서 유도하므로 문서 사본이 함께 틀려도 red 다.
    인용이 0건이면 '검사 범위 붕괴' 로 실패시킨다 — 빈 범위 위의 ✅ 가 fail-open 이기 때문.
    Expectations come from requirements.txt; an empty citation scope fails rather than passes.
    """
    msgs: list[str] = []
    reqs = (project_root / "requirements.txt").read_text(encoding="utf-8")

    pins: dict[str, str | None] = {
        name: _first(re.compile(rf"^{name}==({_VERSION})$", re.MULTILINE), reqs)
        for name in _DOC_PIN_NAMES
    }
    for name, pin in pins.items():
        if pin is None:
            msgs.append(f"❌ requirements.txt 에 `{name}==` 핀 미발견 (핀 형식 변경됐는지 확인)")

    fastapi_pin = pins["fastapi"]
    if fastapi_pin is not None:
        want = ".".join(fastapi_pin.split(".")[:2])   # 배지는 major.minor 만 표기
        for fname in ("README.md", "README.ko.md"):
            badge = _first(_FASTAPI_BADGE, (project_root / fname).read_text(encoding="utf-8"))
            if badge is None:
                msgs.append(f"❌ {fname} FastAPI 배지 패턴 미발견 (형식 변경됐는지 확인)")
            elif badge != want:
                msgs.append(
                    f"❌ {fname} FastAPI 배지 {badge} ↔ 핀 {fastapi_pin} (기대 {want}) 불일치"
                )
    return (not msgs), msgs


# --- pylint 진리값 4지점 (문서감사 PR-4, 2026-08-12) -------------------------
# 🔴 배지·STATE 2지점·ci.yml 주석이 **10.00/10** 을 주장했으나 실측은 **9.99/10** 이었다
#    (E1136 config.py · E1125 ai_review.py · C0302 pipeline.py). 5지점 어디에도 집행자가
#    없었다 — 이 파일은 Tests·FastAPI 배지만 봤고 CI 는 리터럴 floor 만 강제했다.
# The pylint score was claimed in five places and enforced in none.
_LINT_BADGE = re.compile(r"badge/pylint-(\d+\.\d+)%2F10")
_LINT_VALUE = re.compile(r"\*\*(\d+\.\d+)/10\*\*")
_LINT_CI_COMMENT = re.compile(r"현재\s+(\d+\.\d+)/10")


def _lint_from_line(text: str, prefix: str, pattern: re.Pattern) -> float | None:
    """`prefix` 로 시작하는 **줄**에서만 값을 뽑는다.

    🔴 파일 전역 검색을 쓰지 않는다 — `docs/STATE.md` 는 과거 사이클 서사에서 `pylint 10.00`
    을 여러 번 언급하고, 그것들은 **당시 사실 기록**이라 정정 대상이 아니다(docs.md 규칙).
    Line-scoped: historical cycle notes mention old scores and must not be rewritten.
    """
    for line in text.splitlines():
        if line.startswith(prefix):
            m = pattern.search(line)
            if m:
                return float(m.group(1))
    return None


def lint_badge_sites(project_root: Path) -> list[tuple[str, float | None]]:
    """pylint 값을 주장하는 4지점을 (이름, 값) 으로 수집한다 — README 2 · STATE pylint 행 · ci.yml 주석."""
    sites: list[tuple[str, float | None]] = []
    for name in ("README.md", "README.ko.md"):
        text = (project_root / name).read_text(encoding="utf-8")
        m = _LINT_BADGE.search(text)
        sites.append((name, float(m.group(1)) if m else None))

    state = (project_root / "docs" / "STATE.md").read_text(encoding="utf-8")
    sites.append(("STATE.md pylint 행", _lint_from_line(state, "| pylint |", _LINT_VALUE)))

    ci = (project_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    m = _LINT_CI_COMMENT.search(ci)
    sites.append(("ci.yml 주석", float(m.group(1)) if m else None))
    return sites


def check_lint_badge(project_root: Path) -> tuple[bool, list[str]]:
    """4지점이 **같은 값**을 말하는가. 하나라도 못 읽으면 fail-closed."""
    sites = lint_badge_sites(project_root)
    missing = [name for name, value in sites if value is None]
    if missing:
        return False, [f"❌ pylint 값을 읽지 못한 지점: {', '.join(missing)} (정규식 drift 의심)"]
    values = {value for _, value in sites}
    if len(values) == 1:
        return True, []
    return False, [
        "❌ pylint 값이 지점마다 다르다:",
        *[f"   {name}: {value}" for name, value in sites],
        # 🔴 리스트 안 **암묵적** 문자열 연결 금지 — 쉼표 누락과 구별되지 않아 CodeQL
        #    `py/implicit-string-concatenation-in-list` 가 잡는다(#1331 에서 실제 red).
        # Explicit `+`: implicit concatenation inside a list is indistinguishable from a typo.
        "   🔴 CI 의 --fail-under 는 README 배지에서 파생되므로, 배지가 실측보다 높으면 "
        + "그 배지가 주장하는 빌드를 그 배지가 실패시킨다.",
    ]


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    pin_ok, pin_msgs = check_dependency_pins(project_root)
    lint_ok, lint_msgs = check_lint_badge(project_root)
    print("=== docs 값 정합 점검 / Docs Value-Sync Check ===\n")
    if pin_ok:
        print("✅ requirements.txt 핀 ↔ README FastAPI 배지 일치")
    if lint_ok:
        sites = lint_badge_sites(project_root)
        print(f"✅ pylint 값 {len(sites)}지점 일치 — {sites[0][1]}/10 (CI --fail-under 가 배지에서 파생)")
    if pin_ok and lint_ok:
        return 0
    for m in pin_msgs + lint_msgs:
        print(m)
    print(
        "\n해결: (핀) requirements.txt 실핀에 맞춰 README/README.ko FastAPI 배지를 갱신."
        " (pylint) `py -3 -m pylint src/` 실측값으로 README 2배지 · STATE pylint 행 · ci.yml 주석을 맞춘다."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
