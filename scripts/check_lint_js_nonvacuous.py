"""`make lint-js` 공허화 차단 — eslint 가 **실제로 무언가를 검사했는지** 강제한다 (#1227 항목 3).

🔴 왜 필요한가 — `make lint-js` 는 `npx eslint … || true` 라 **모든 실패를 삼킨다**. 그래서
설정 파일을 못 찾아 **0개 파일을 검사한 상태**와 "위반 0건" 이 구별되지 않았고, 실제로 #1222
(eslint 8→10 범프) 창에서 설정이 완전히 깨져도 CI 는 초록이었다. 게다가 이 타깃은 **어떤 CI
workflow 에도 배선돼 있지 않았다**(`.github/` 전역 참조 0건).

🔴 설계 (사용자 결정 2026-07-29) — **위반은 advisory, 공허화는 fail-closed**:

  * eslint 가 JSON 을 못 내면(설정 부재·기동 실패) → **exit 1**
  * 검사된 파일이 0개면 → **exit 1**
  * 검사돼야 할 템플릿이 결과에서 빠졌으면 → **exit 1**  (조용한 부분 스킵 차단)
  * 위반(에러/경고)이 있으면 → 출력만 하고 **exit 0**  (기존 advisory 성격 보존, 정책 17 안정성)

즉 "위반 0건" 과 **"아무것도 검사하지 않은 0건"** 을 구별하는 것이 이 스크립트의 유일한 책임이다.

Anti-vacuity gate for `make lint-js` (#1227 item 3). The target swallows every failure with
`|| true`, so "zero violations" was indistinguishable from "linted zero files" — and the target was
never wired into CI at all. Violations stay advisory; vacuity fails closed.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess  # nosec B404
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "eslint.config.mjs"
TEMPLATE_DIR = REPO_ROOT / "src" / "templates"
TEMPLATE_GLOB = "src/templates/**/*.html"

# 외부 스크립트(`src=`)는 인라인 본문이 없으므로 제외 / Exclude external scripts (no inline body).
_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_JINJA_RE = re.compile(r"\{\{|\{%")

# 템플릿이 아닌 무시 항목 / Non-template ignore entries.
NON_TEMPLATE_IGNORES = frozenset({"src/static/vendor/**"})


def templates_with_jinja_in_script() -> set[str]:
    """`<script>` 안에 Jinja2 구문이 있어 JS 파서가 깨지는 템플릿 집합 (실측 계산)."""
    found = set()
    for path in sorted(TEMPLATE_DIR.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        if any(_JINJA_RE.search(block) for block in _SCRIPT_RE.findall(source)):
            found.add(f"src/templates/{path.name}")
    return found


def config_ignores() -> set[str]:
    """`eslint.config.mjs` 의 `ignores` 배열 항목을 읽는다."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    block = re.search(r"ignores:\s*\[(.*?)\]", text, re.DOTALL)
    if block is None:
        raise RuntimeError("eslint.config.mjs 에서 ignores 배열을 찾지 못했다")
    return set(re.findall(r'"([^"]+)"', block.group(1)))


def expected_linted_templates() -> set[str]:
    """검사돼야 할 템플릿 = 전체 템플릿 − ignores."""
    everything = {f"src/templates/{p.name}" for p in TEMPLATE_DIR.glob("*.html")}
    return everything - config_ignores()


# 🔴 `npx` 가 아니라 `node <eslint.js>` 로 호출한다 — Windows 에서 `npx`/`eslint` 는 `.cmd`
#    래퍼라 `CreateProcess` 로 실행할 수 없어 `WinError 2` 가 난다(실측). 그러면 이 가드가
#    개발 PC 에서 **항상 실패**해 "가드가 시끄러우니 끄자" 로 이어진다(정책 17 안정성).
#    `node` 는 실 실행 파일이라 플랫폼 무관하게 동작하고, npx 해석 단계도 없어 더 빠르다.
# 🔴 Invoke `node <eslint.js>` rather than `npx`: on Windows both `npx` and `eslint` are `.cmd`
#    shims that CreateProcess cannot execute (WinError 2, measured), which would make this guard
#    fail on every dev machine. `node` is a real executable and works everywhere.
ESLINT_JS = REPO_ROOT / "node_modules" / "eslint" / "bin" / "eslint.js"


def _run_eslint() -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 B607
        ["node", str(ESLINT_JS), TEMPLATE_GLOB, "--format=json"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        # 🔴 인코딩 명시 필수 — 미지정 시 Windows 기본 코드페이지(cp949)로 디코딩해 eslint 출력의
        #    UTF-8 문자(템플릿 본문의 em dash 등)에서 UnicodeDecodeError 로 죽는다(실측).
        # 🔴 Explicit encoding is required: without it Windows decodes with the local code page and
        #    dies on UTF-8 characters in eslint's output (measured).
        encoding="utf-8", errors="replace",
        timeout=600, check=False, shell=False,
    )


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지(🔴)·한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 print crash on Windows local runs (UTF-8, replace on miss)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def main() -> int:  # pylint: disable=too-many-return-statements
    """advisory + 공허화 차단 — 위반은 exit 0, "아무것도 검사 안 함" 은 exit 1.

    🔴 return 이 많은 것은 의도다 — 각 return 은 **서로 다른 공허화 사유**를 그 자리에서
    구별해 보고한다(조달 실패 / 기동 실패 / 파싱 실패 / 0건 / 부분 스킵). 헬퍼로 묶으면 사유가
    한 덩어리로 뭉개져 CI 로그에서 원인 판별이 어려워진다 (테스트 규칙의 R0914 결정 트리와 동일
    판단 — 응집을 깨뜨릴 때는 inline disable + 사유).
    """
    _make_stdout_safe()
    if not ESLINT_JS.is_file():
        # 미설치는 "위반 0건" 이 아니라 **조달 실패**다 — 조용히 통과시키면 가드가 공허해진다.
        # A missing install is a procurement failure, not "zero violations".
        print(f"FAIL: eslint 미설치 ({ESLINT_JS}) — `npm ci` 필요", file=sys.stderr)
        return 1
    try:
        proc = _run_eslint()
    except OSError as exc:
        print(f"FAIL: eslint 를 실행할 수 없다 ({exc}) — 조달 실패", file=sys.stderr)
        return 1

    if not proc.stdout.strip().startswith("["):
        print("FAIL: eslint 가 JSON 을 내지 못했다 — 설정 부재/기동 실패로 **0개 파일 검사** 상태다.",
              file=sys.stderr)
        print(f"  exit={proc.returncode}\n  stderr={proc.stderr.strip()[:500]}", file=sys.stderr)
        return 1
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"FAIL: eslint JSON 파싱 실패 — {exc}", file=sys.stderr)
        return 1

    if not results:
        print(f"FAIL: 검사된 파일이 0개다 (glob={TEMPLATE_GLOB}) — 검사 범위가 비었다.",
              file=sys.stderr)
        return 1

    linted = {
        pathlib.Path(entry["filePath"]).resolve().relative_to(REPO_ROOT).as_posix()
        for entry in results
    }
    missing = expected_linted_templates() - linted
    if missing:
        print(f"FAIL: 검사돼야 할 템플릿이 결과에서 빠졌다(조용한 부분 스킵): {sorted(missing)}",
              file=sys.stderr)
        return 1

    # 여기부터는 advisory — 위반을 보고하되 종료 코드는 0
    # Advisory from here on: report violations without failing the build.
    errors = sum(e["errorCount"] for e in results)
    warnings = sum(e["warningCount"] for e in results)
    print(f"lint-js: {len(linted)}개 파일 검사 · error {errors} · warning {warnings} (advisory)")
    for entry in results:
        rel = pathlib.Path(entry["filePath"]).resolve().relative_to(REPO_ROOT).as_posix()
        for msg in entry["messages"]:
            level = "error" if msg.get("severity") == 2 else "warning"
            print(f"  {rel}:{msg.get('line', 0)}  {level}  {msg.get('message', '')} "
                  f"({msg.get('ruleId') or 'parse'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
