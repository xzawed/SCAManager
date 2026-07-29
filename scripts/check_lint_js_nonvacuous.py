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
from html.parser import HTMLParser

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "eslint.config.mjs"
TEMPLATE_DIR = REPO_ROOT / "src" / "templates"
TEMPLATE_GLOB = "src/templates/**/*.html"

_JINJA_RE = re.compile(r"\{\{|\{%")


class _InlineScriptCollector(HTMLParser):
    """인라인 `<script>` 본문만 수집한다 — 외부 스크립트(`src=`)는 인라인 본문이 없어 제외.

    🔴 태그 매칭에 정규식을 쓰지 않는다 — `<script >`·속성 값 안의 `>`·대소문자 변형을
    놓치고(CodeQL `py/bad-tag-filter`), 무시 목록의 **근거 전체가 이 스캔의 정확도에 달려 있어**
    heuristic 을 쓸 수 없다. stdlib 파서는 `<script>` 를 CDATA 로 처리해 본문을 그대로 준다.
    🔴 No regex for tag matching: it misses `<script >`, `>` inside attribute values and case
    variants (CodeQL py/bad-tag-filter). The ignore list's entire justification rests on this
    scan's accuracy, so use the stdlib parser, which treats `<script>` as CDATA.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.blocks: list[str] = []
        self._capturing = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self._capturing = not any(name.lower() == "src" for name, _ in attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            self._capturing = False

    def handle_data(self, data):
        if self._capturing:
            self.blocks.append(data)


def _inline_script_blocks(source: str) -> list[str]:
    """템플릿 소스에서 인라인 `<script>` 본문 목록을 반환한다."""
    collector = _InlineScriptCollector()
    collector.feed(source)
    collector.close()
    return collector.blocks


# 템플릿이 아닌 무시 항목 / Non-template ignore entries.
NON_TEMPLATE_IGNORES = frozenset({"src/static/vendor/**"})


def _rel(path: pathlib.Path) -> str:
    """리포 루트 기준 POSIX 상대경로."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def all_templates() -> set[str]:
    """디스크의 전체 템플릿 집합.

    🔴 `rglob` 필수 — eslint CLI 에 넘기는 glob 이 `src/templates/**/*.html`(재귀)이다.
    얕은 `glob("*.html")` 을 쓰면 **하위 디렉토리 템플릿이 양쪽 집합 어디에도 들어오지 않아**
    린트되든 무시되든 아무 검사도 받지 않는다(Grok claim-review 적발).
    🔴 rglob is required: the CLI glob is recursive. A shallow glob leaves nested templates out of
    both sets, so they escape every check regardless of whether they are linted.
    """
    return {_rel(p) for p in TEMPLATE_DIR.rglob("*.html")}


def templates_with_jinja_in_script() -> set[str]:
    """`<script>` 안에 Jinja2 구문이 있어 JS 파서가 깨지는 템플릿 집합 (실측 계산).

    이 집합이 **무시돼도 되는 유일한 근거**다 — 다른 이유로 무시된 파일은 근거 없는 커버리지 축소.
    """
    found = set()
    for path in sorted(TEMPLATE_DIR.rglob("*.html")):
        source = path.read_text(encoding="utf-8")
        if any(_JINJA_RE.search(block) for block in _inline_script_blocks(source)):
            found.add(_rel(path))
    return found


# ─────────────────────────────────────────────────────────────────────────────
# 🔴 설정 파일을 파싱해 커버리지를 **추론하지 않는다** (Grok claim-review 2026-07-29 적발).
#
# 이전 판은 `eslint.config.mjs` 의 `ignores` 배열을 정규식으로 읽어 "검사돼야 할 집합" 을
# 계산했다. 그 판정은 설정의 **손실 있는 투영**이라 아래가 전부 통과했다:
#   · 두 번째 config 객체의 `ignores`  (정규식이 첫 배열만 읽음)
#   · 작은따옴표·템플릿 리터럴·스프레드 항목  (큰따옴표만 매칭)
#   · `files:` 를 좁혀 사실상 제외      (`files` 를 아예 안 봄)
#   · `globalIgnores()` 등 다른 무시 API
# 즉 "무시 목록은 임의 집합이 될 수 없다" 는 단언이 거짓이었다.
#
# 이제 **eslint 의 실제 실행 결과에서 무시 집합을 역산**한다:
#     실제_무시 = 디스크 전체 템플릿 − eslint 가 실제로 린트한 파일
# 설정을 어떤 방식으로 바꾸든 린트 결과가 바뀌므로 위 우회가 전부 red 가 된다.
#
# 🔴 Do NOT infer coverage by parsing the config (caught by Grok claim-review). The old regex read
# only the first double-quoted `ignores` array, so a second config object, single quotes, `files:`
# narrowing and other ignore APIs all passed. Coverage is now derived from what eslint ACTUALLY
# linted: actual_ignored = all templates on disk − files eslint reported.
# ─────────────────────────────────────────────────────────────────────────────


def config_ignores() -> set[str]:
    """`eslint.config.mjs` 의 첫 `ignores` 배열 항목 (보조 — 오프라인 조기 피드백 전용).

    🔴 이 함수는 **봉인의 근거가 아니다.** 설정 문법의 일부만 읽으므로 우회 가능하며, 실제
    커버리지 판정은 `main()` 의 역산(위 주석)이 담당한다. 오프라인 테스트가 설정 편집 직후
    빠르게 경고하도록 남겨둔 보조 수단일 뿐이다.
    🔴 NOT the basis of any seal — it reads only part of the config syntax. The real coverage
    verdict lives in main(); this only gives fast offline feedback right after a config edit.
    """
    text = CONFIG_PATH.read_text(encoding="utf-8")
    block = re.search(r"ignores:\s*\[(.*?)\]", text, re.DOTALL)
    if block is None:
        raise RuntimeError("eslint.config.mjs 에서 ignores 배열을 찾지 못했다")
    return set(re.findall(r"""["']([^"']+)["']""", block.group(1)))


def expected_linted_templates() -> set[str]:
    """린트돼야 할 템플릿 = 전체 템플릿 − Jinja-in-script 템플릿.

    🔴 설정(`ignores`)이 아니라 **디스크 사실**에서 계산한다 — 설정을 기준으로 삼으면
    "설정이 무시하라고 했으니 안 봐도 된다" 는 순환이 되어, 근거 없는 무시를 스스로 승인한다.
    🔴 Derived from disk facts, not from `ignores`: keying off the config would be circular and
    would self-approve unjustified exclusions.
    """
    return all_templates() - templates_with_jinja_in_script()


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

    # 🔴 대조 집합이 비면 이하 모든 차집합 단언이 **공허하게 참**이 된다 (Grok 적발).
    # 디스크에 템플릿이 없다 = 스캔 경로(TEMPLATE_DIR)가 무너졌다는 뜻이지 "통과" 가 아니다.
    # 이 분기가 없으면 `everything`·`justified` 가 동시에 비어 두 봉인이 **함께 공허**해진다.
    # 🔴 With an empty reference set every set-difference below is vacuously true. Without this
    # branch both seals go vacuous together when TEMPLATE_DIR breaks.
    everything = all_templates()
    if not everything:
        print(f"FAIL: 디스크에서 템플릿을 찾지 못했다 ({TEMPLATE_DIR}) — 스캔 범위가 무너졌다.",
              file=sys.stderr)
        return 1

    # `results` 가 비는 경우(=eslint 가 아무것도 검사 안 함)는 아래 `unjustified` 가 덮는다:
    # linted=∅ → actual_ignored=everything → 근거 없는 제외로 잡힌다. 별도 분기를 두지 않는다
    # (정책 16 — 중복 분기는 뮤테이션으로 죽지 않아 가드 품질을 오히려 흐린다).
    # An empty `results` is covered by the `unjustified` check below, so no separate branch.

    linted = {_rel(pathlib.Path(entry["filePath"])) for entry in results}

    # 🔴 핵심 봉인 — eslint 의 **실제 동작**에서 무시 집합을 역산해 정당한 근거와 대조한다.
    # 설정을 어떤 문법으로 바꾸든(두 번째 ignores 배열·작은따옴표·files 축소·globalIgnores)
    # 린트 결과가 달라지므로 여기서 red 가 된다. 설정 파싱으로는 이 우회를 잡을 수 없었다.
    # 🔴 The seal: derive the ignored set from what eslint actually did and compare it against the
    # only legitimate justification. Any config-syntax bypass changes the lint result and fails here.
    actual_ignored = everything - linted
    justified = templates_with_jinja_in_script()

    unjustified = actual_ignored - justified
    if unjustified:
        print("FAIL: 정당한 근거 없이 린트에서 제외된 템플릿(검사 범위 축소): "
              f"{sorted(unjustified)}\n"
              "  → `<script>` 안 Jinja2 가 없는데 무시되고 있다. ignores/files 설정을 확인할 것.",
              file=sys.stderr)
        return 1

    unexpectedly_linted = justified - actual_ignored
    if unexpectedly_linted:
        print("FAIL: Jinja2 파싱 불가 템플릿이 무시되지 않고 린트됐다(파싱 오류 유발): "
              f"{sorted(unexpectedly_linted)}", file=sys.stderr)
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
