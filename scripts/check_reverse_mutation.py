#!/usr/bin/env python3
"""역-뮤테이션 게이트 — PR 의 테스트가 **그 PR 이 고친 결함을 실제로 관측하는가** (P1).

## 왜 만드나 (2026-08-07 다중 관점 진단의 지배 원인)

이 저장소가 반복해 온 결함의 형태는 하나로 수렴한다:

> **결함을 고친 당사자가 그 결함을 검증할 관측자를 같은 PR 안에서 만들고,
> 그 관측자는 하필 그 PR 이 고친 결함에만 맹목이다.**

실측된 사례(전부 외부 검증이 뒤늦게 잡았다):
- R61 — 5번째 호출부를 가드가 못 봄 + 정규식이 4가지 우회 허용
- R58 — 공허화 경로가 둘이 아니라 셋
- R63 — 비-dict JSON 경로가 여전히 2행을 남김
- R65 — **모든 가드가 스파이/패치라 "기록된다" 가 한 번도 관측된 적 없음**
- R57 — CI env 무검증 · 인자 순서 무검증 · 판정 불가를 "변경 없음" 이라 단언

산문 규칙으로는 닫히지 않는다. 이 저장소의 🔴 규칙 337개 중 실측 준수율이
**0/42**(정책 13) · **발화율 100% / 이행률 0%**(R43)인 것들이 있다 — 규칙이 도달해도
지켜지지 않는다는 뜻이고, 그래서 **기계 질문**이 필요하다.

## 계약

PR 의 **생산 표면 변경 전체**를 base 로 되돌린 뒤, 그 PR 이 추가/수정한 테스트만 실행한다.

- **red 여야 한다.** green 이면 그 테스트는 이 PR 이 고친 것을 보지 않는다 → 게이트 실패.
- 되돌림이 no-op 이면(파일이 실제로 안 바뀜) **판정 불가로 실패**한다 — 뮤테이션 유효성
  (AGENTS.md 불변식 2)을 게이트 자신에게도 적용한다.
- baseline(되돌리기 전)이 이미 red 면 **판정 불가로 실패**한다 — 무엇 때문에 빨간지 모른다.
- **e2e 시험이 바뀐 PR 은 E2E 잡이 잰다** — 단위 잡은 넘기고(⏭️), E2E 잡이 `--with-e2e` 로 생산 변경을
  제자리에서 되돌리고 CSS 를 다시 빌드한 뒤 이 PR 이 바꾼 단위 · e2e 시험을 함께 돌린다. 어느 쪽이든 red 면 관측됨이다
  (회고 원장 L12 P2-23 · P2-53 — 단위만 재면 e2e 관측 PR 이 «대상 아님» 이거나 거짓 빨강이었다).
- **삭제한 테스트는 대상이 아니다.** HEAD 에 없는 경로는 고를 수 없다 — 고르면 pytest 가
  0건 수집 + 비-0 을 내 *되돌리기 전에 이미 red* 로 오판한다 (`#1385`).
  선택이 비면 이 축은 **안 잰다**(성공 배너가 아니다). 셀렉터 고장으로 글롭이
  비는 스코프 붕괴와는 다른 빈 범위다.

## 🔴 이 게이트가 닫지 못하는 것 (정직 기준)

- **신호 등급이 둘이다.** 되돌림으로 테스트가 `import` 하던 심볼이 사라지면 *collection
  error* 가 나는데, 이는 결합은 증명하지만 **단언의 내용은 증명하지 않는다**. 실제
  assertion 실패가 강한 신호다. 소급 검증 5건 중 3건이 collection error 였다 —
  그래서 출력에서 **두 등급을 구분해 인쇄**한다(숨기지 않는다).
- 테스트를 **한 줄도 안 건드린 PR** 은 대상이 아니다. 그런 PR 이 결함을 고쳤다면 이
  게이트는 침묵한다 — 그 축은 커버리지/리뷰가 맡는다.
- 되돌림 단위가 **파일 전체**라 한 PR 이 두 결함을 고쳤을 때 어느 쪽을 관측하는지는 모른다.

Reverse-mutation gate: revert the PR's production changes and re-run only the tests it
touched. If they still pass, those tests do not observe what the PR changed.
"""
from __future__ import annotations

import argparse
import ast
import os
import shlex
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]

# 🔴 PR 본문은 **단일 리더**를 통해서만 읽는다 — 원문을 정규식에 넘기면 HTML 주석 안
# 마커가 "리뷰어 비가시 + 게이트 통과" 를 성립시킨다(회고 N-P0-1 · backlog R20 결함 1).
# 스크립트 간 공유 관용구는 `retro_scope.py:34` 선례를 따른다(standalone 실행이라
# sys.path 조작이 필요하다). 단일성 강제: `tests/unit/scripts/test_pr_body_single_reader.py`.
# Read the PR body only through the single hardened reader; see the guard test.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_claim_review_trace import (  # noqa: E402  # pylint: disable=wrong-import-position
    read_pr_body,
)


# 되돌릴 "생산 표면".
# 🔴 `src/` 만 되돌리면 안 된다 — `#1298`·`#1305` 는 `src/` 변경이 **0건**이라 원리적으로
#    미검출된다(설계 적대 검증이 실측으로 짚은 지점). 가드·워크플로·훅도 생산물이다.
PROD_PREFIXES = (
    "src/",
    "scripts/",
    "alembic/",
    ".github/workflows/",
    ".claude/hooks/",
    ".claude/workflows/",
    ".claude/settings.json",
    ".pre-commit-config.yaml",
    "e2e/conftest.py",
)
TEST_PREFIXES = ("tests/",)

# 면제 — 이 게이트가 원리적으로 판정할 수 없는 PR 을 저자가 **명시**한다.
# 🔴 사유 16자 이상. 조용한 통과가 아니라 보이는 결정이 되도록 job summary 에 계수한다.
import re  # noqa: E402  # pylint: disable=wrong-import-order
# (stdout 재구성 이후 import — guards.md 관용구. 단일 리더 shim 이 위에 있어 정렬 경고가 뜬다.)

_EXEMPT = re.compile(
    r"^[ \t]*(?![`'\"])reverse-mutation-not-applicable\s*:\s*\S.{15,}", re.MULTILINE)
_LINE_BREAKS = re.compile(r"\s+")


def _run(args: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )


def classify(files: list[str]) -> tuple[list[str], list[str]]:
    """(생산 표면, 테스트) 로 분류."""
    prod = [f for f in files
            if f.startswith(PROD_PREFIXES) and not f.startswith(TEST_PREFIXES)]
    tests = [f for f in files if f.startswith(TEST_PREFIXES) and f.endswith(".py")]
    return prod, tests


def e2e_tests_of(files: list[str]) -> list[str]:
    """바뀐 e2e 시험 **모듈** — `e2e/` 의 `test_*.py`. 도우미 · `e2e/conftest.py`(생산 표면)는 시험이 아니다.

    🔴 단위 잡이 넘기는 조건과 E2E 잡이 재는 조건이 이 한 함수다 — 둘이 갈리면 어느 잡도 안 재는 PR 이 생긴다.
    One predicate for both the unit job's hand-off and the E2E job's scope, so no PR falls between them.
    """
    return [f for f in files
            if f.startswith("e2e/") and f.endswith(".py") and Path(f).name.startswith("test_")]


def e2e_present(files: list[str], prod: list[str], head_sha: str, cwd: Path) -> list[str]:
    """E2E 잡이 잴 e2e 시험 — 생산 변경이 있고 HEAD 에 남아 있는 바뀐 e2e 시험 모듈. 지운 시험은 대상이 아니다."""
    return existing_at(head_sha, e2e_tests_of(files), cwd) if prod else []


def _test_modules(paths: list[str]) -> list[str]:
    """실제로 돌릴 시험 모듈(`test_*.py`) — 도우미만 돌리면 pytest 가 «수집 0건»(exit 5)을 낸다."""
    return [p for p in paths if Path(p).name.startswith("test_")]


def _blob_exists(sha: str, path: str, cwd: Path) -> bool:
    """`sha` 트리에 `path` blob 이 있는가."""
    probe = _run(["git", "cat-file", "-e", f"{sha}:{path}"], cwd, timeout=60)
    return probe.returncode == 0


def existing_at(sha: str, paths: list[str], cwd: Path) -> list[str]:
    """`sha` 트리에 실제로 있는 경로만 남긴다.

    PR 이 테스트를 삭제하면 `git diff --name-only` 에 그 경로가 남는다.
    worktree 는 HEAD 라 파일이 없고, pytest 가 0건 수집 + 비-0 을 내
    '되돌리기 전에 이미 red' 로 오판한다 (`#1385` · 2026-08-16).
    삭제된 테스트는 보호할 관측자가 없다 — 대상이 아니다.
    Keep only paths that exist as blobs at `sha`. A test the PR deleted
    cannot be a reverse-mutation target (#1385).
    """
    return [p for p in paths if _blob_exists(sha, p, cwd)]


def changed_files(base_sha: str, head_sha: str, cwd: Path) -> list[str] | None:
    """`base...head`(merge-base) 변경 파일. 판정 불가면 None.

    🔴 three-dot 이어야 한다 — two-dot 은 base 가 앞서간 만큼을 함께 세어
    **남의 변경을 이 PR 의 것으로** 오판한다.
    """
    proc = _run(["git", "diff", "--name-only", f"{base_sha}...{head_sha}"], cwd, timeout=120)
    if proc.returncode != 0:
        return None
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _append_step_summary(markdown: str) -> None:
    """job summary 에 누적 — `::notice` 는 로그 안쪽이라 아무도 보지 않는다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


def _pytest(paths: list[str], cwd: Path, extra: list[str] | None = None,
            cache_dir: str | None = None) -> subprocess.CompletedProcess:
    """되돌림이 **실제로 반영되도록** 바이트코드 캐시를 끄고 실행한다.

    🔴 이것이 없으면 게이트가 **fail-open** 한다 (2026-08-08 CI 실측, Linux 에서만 발현):
    baseline 실행이 `src/x.py` 를 `__pycache__/x.pyc` 로 컴파일한다. 그 다음
    `git checkout base -- src/x.py` 가 소스를 되돌리는데, 되돌린 내용이 **같은 바이트 수**
    이고 두 작업이 **같은 초** 안에 일어나면 Python 의 (mtime, size) 검증이 통과해
    **옛 `.pyc` 를 그대로 재사용**한다. 그러면 되돌렸는데도 테스트가 초록이고,
    게이트는 *"이 테스트는 변경을 관측하지 않는다"* 고 **거짓 보고**한다.

    Windows 에서는 파일 연산이 느려 초가 넘어가므로 재현되지 않았다 — 플랫폼 비대칭이
    이 결함을 로컬에서 숨겼다.

    Disable bytecode caching so the revert is actually observed; otherwise a same-size revert
    within the same second reuses the stale .pyc and the gate reports a false "vacuous".

    `cache_dir` 를 주면 pytest 의 실패 기록만 그 임시 폴더에 남긴다(리포 밖) — `--lf` 로 «되돌려서 빨간 그 시험» 을
    되돌리지 않고 다시 돌리려고. 바이트코드 캐시는 그때도 끈다.
    With `cache_dir`, pytest's last-failed record goes to that temp folder so `--lf` can re-run the same test.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cache = ["-o", f"cache_dir={cache_dir}"] if cache_dir else ["-p", "no:cacheprovider"]
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-B", "-m", "pytest", *paths, "-q", "--no-header",
         *cache, *(extra or [])],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=1800, check=False, env=env,
    )
    return proc


# e2e 는 루트와 다른 프로세스 설정으로 돈다(`e2e/pytest.ini` · asyncio 끔 · 시험마다 벽) — CI 스위트 스텝과 같은 꼴.
# e2e runs with its own settings, like the CI suite step.
_E2E_FLAGS = ["-p", "no:asyncio", "--timeout=120"]

# `git diff -U0` 의 hunk 머리 — 새 쪽 시작 줄 · 줄 수(생략 = 1, 0 = 그 자리에서 지움).
# A `git diff -U0` hunk header: the new side's start line and count (omitted = 1, 0 = a deletion there).
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _changed_lines(base_sha: str, head_sha: str, path: str, cwd: Path) -> set[int] | None:
    """이 PR 이 `path` 에서 고친 HEAD 쪽 줄 번호 — 못 읽으면 None. 지운 자리는 그 앞뒤 줄로 친다."""
    proc = _run(["git", "diff", "-U0", "--no-color", "--no-ext-diff", f"{base_sha}...{head_sha}", "--", path],
                cwd, timeout=120)
    if proc.returncode != 0:
        return None
    lines: set[int] = set()
    for hunk in _HUNK.finditer(proc.stdout or ""):
        start, count = int(hunk.group(1)), int(hunk.group(2) or "1")
        lines.update(range(start, start + count) if count else (start, start + 1))
    return lines


def _test_spans(source: str) -> list[tuple[str, int, int]]:
    """(pytest 이름, 첫 줄, 끝 줄) — 최상위 `test*` 함수와 `Test*` 클래스의 `test*` 메서드. 데코레이터 줄 포함."""
    def span(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int]:
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        return first, node.end_lineno or node.lineno

    def is_test(node: ast.stmt) -> bool:
        return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")

    spans: list[tuple[str, int, int]] = []
    for node in ast.parse(source).body:
        if is_test(node):
            spans.append((node.name, *span(node)))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            spans.extend((f"{node.name}::{item.name}", *span(item)) for item in node.body if is_test(item))
    return spans


def e2e_targets(base_sha: str, head_sha: str, modules: list[str], cwd: Path) -> list[str]:
    """돌릴 e2e 시험 — 모듈마다 **이 PR 이 고친 시험 함수**만. 함수 밖만 바뀌었거나 못 읽으면 그 모듈 전체.

    🔴 e2e 모듈 하나가 시험 수백 건이다(CI 에서 십 분대). 모듈째 두 번 돌리면 스텝 벽에 닿는다 — 이 PR 의 시험은
    이 PR 이 고친 함수이므로 그것만 돌린다. 이름으로 고르므로 병합 커밋에서 줄이 밀려도 같은 시험이다.
    Only the test functions this PR touched (a module can hold hundreds of e2e tests); the whole module when
    only module-level code changed or the source cannot be read.
    """
    targets: list[str] = []
    for module in modules:
        lines = _changed_lines(base_sha, head_sha, module, cwd)
        source = _run(["git", "show", f"{head_sha}:{module}"], cwd, timeout=60)
        try:
            spans = _test_spans(source.stdout or "") if source.returncode == 0 else None
        except SyntaxError:
            spans = None
        hit = [name for name, first, last in spans or [] if any(first <= n <= last for n in lines or ())]
        targets.extend([f"{module}::{name}" for name in hit] if hit else [module])
    return targets


# 🔴 **요약 줄 하나에서만 읽는다.** blob 전체를 검색하면 SUT 가 인쇄한 숫자가 요약을
#    대신한다 — 첫 수정은 부분문자열만 좁히고 이 축을 그대로 뒀고, `retry: 3 failed of 10`
#    이 있는 수집 오류가 여전히 assertion 으로 등급됐다(Grok 반증 01a040cc, 직접 재현).
#    요약 줄은 pytest 가 붙이는 **지속시간 꼬리**로 식별한다. 실측 5형태 전부 갖는다:
#      `1 passed in 0.01s` · `1 failed in 0.17s` · `1 error in 0.29s`
#      `10 passed, 14 warnings in 0.37s` · `7535 passed, 5 skipped, … in 317.37s`
#    SUT 가 인쇄한 줄에는 그 꼬리가 없다.
#    관용구 정본: `check_test_count_sync.py` 는 **줄을 고른 뒤** 그 줄에서 센다.
# Read one summary line, identified by pytest's duration tail; a whole-blob search lets the
# code under test print the verdict.
_SUMMARY_LINE = re.compile(r"\bin \d+(?:\.\d+)?s\b")
_FAILED_COUNT = re.compile(r"(?<![\w.-])(\d[\d,_]*)\s+failed\b", re.IGNORECASE)
_ERROR_COUNT = re.compile(r"(?<![\w.-])(\d[\d,_]*)\s+errors?\b", re.IGNORECASE)

# 등급마다 **자기 단서**를 갖는다. 단서를 공유하면 라벨이 과·소주장한다 —
# 혼합 실행을 `collection` 으로 내리면 「단언 내용은 증명하지 않는다」가 거짓이 되고
# (단언은 실제로 발화했다), `assertion` 으로 올리면 일부가 실행조차 안 된 사실이 사라진다.
# Each grade carries its own caveat; sharing one makes the label over- or under-claim.
_GRADE_CAVEAT = {
    "collection": "  (수집 오류 — 결합은 증명하나 단언 내용은 증명하지 않는다)",
    "mixed": "  (일부는 단언 발화, 일부는 실행조차 안 됨 — 관측 범위가 부분적이다)",
    "unknown": "  (요약 줄을 못 찾았다 — 등급을 **안 쟀다**)",
}


def _summary_count(rx: "re.Pattern[str]", line: str) -> int:
    """요약 줄에서 개수 하나. 🔴 `0 failed` 는 **실패가 없다**는 뜻이므로 0 을 그대로 낸다."""
    m = rx.search(line)
    return int(m.group(1).replace(",", "").replace("_", "")) if m else 0


def _summary_line(proc: subprocess.CompletedProcess) -> str | None:
    """마지막 요약 줄. 🔴 **stdout 을 먼저 본다** — 이어 붙이면 세션 이후 stderr 줄이
    요약을 가로챈다(Grok 01a040dc Q2). pytest 의 통계 줄은 stdout 에 있다.
    """
    for stream in (proc.stdout, proc.stderr):
        hits = [l for l in (stream or "").splitlines() if _SUMMARY_LINE.search(l)]
        if hits:
            return hits[-1]
    return None


def _grade(proc: subprocess.CompletedProcess) -> str:
    """red 의 등급 — `assertion` · `collection` · `mixed` · `unknown`.

    혼합은 **자기 이름**을 갖는다. 어느 쪽으로 반올림해도 단서가 거짓이 되기 때문이다.
    A mixed run gets its own name: rounding it either way makes the caveat lie.
    """
    line = _summary_line(proc)
    if line is None:
        return "unknown"
    failed = _summary_count(_FAILED_COUNT, line)
    errors = _summary_count(_ERROR_COUNT, line)
    if failed and errors:
        return "mixed"
    if errors:
        return "collection"
    if failed:
        return "assertion"
    return "unknown"


def evaluate(base_sha: str, head_sha: str, repo: Path | None = None) -> tuple[int, list[str]]:
    """(exit code, 출력 줄) — 순수 판정부.

    🔴 `repo` 를 인자로 받는 이유: 테스트가 **합성 git 리포**를 만들어 판정 전체를
    실행할 수 있어야 한다. 이 저장소만 대상으로 하면 게이트 자신을 검증할 때
    "스파이로 대체하고 kwargs 만 본다"(R65 가 잡은 클래스)로 흐른다.
    """
    root = repo or _ROOT
    lines: list[str] = []
    files = changed_files(base_sha, head_sha, root)
    if files is None:
        return 1, ["🔴 변경 파일을 산출하지 못했다 — **판정 불가**(fail-closed)."]

    prod, tests = classify(files)
    e2e = e2e_present(files, prod, head_sha, root)
    if e2e:
        # 🔴 e2e 로 관측하는 PR 을 단위 시험만으로 재면 «대상 아님» 이거나 거짓 빨강이다 — E2E 잡이 함께 잰다.
        # A PR whose e2e tests changed is judged in the E2E job, unit and e2e tests together.
        return 0, [f"⏭️  e2e 시험이 바뀐 PR — E2E 잡(`--with-e2e`)이 단위 · e2e 시험을 함께 되돌려 잰다 "
                   f"(생산 {len(prod)}건 · 단위 {len(tests)}건 · e2e {len(e2e)}건)."]
    if not tests:
        return 0, [f"⏭️  테스트 변경 0건 — 이 게이트의 대상이 아니다 (생산 표면 {len(prod)}건)."]
    if not prod:
        return 0, [f"⏭️  생산 표면 변경 0건 — 되돌릴 것이 없다 (테스트 {len(tests)}건)."]

    # HEAD 에 있는 테스트만 고른다. 삭제분은 대상이 아니다 (`#1385`).
    # Only tests that still exist at HEAD are targets; a deleted test is not.
    present = existing_at(head_sha, tests, root)
    if not present:
        # 정당한 빈 범위 — 이 PR 이 바꾼 테스트를 전부 지웠다. 측정할 관측자가 없다.
        # 셀렉터 고장(classify 가 0건)은 위의 '테스트 변경 0건' 분기.
        # 둘 다 ✅/통과 를 찍지 않는다 — 안 잰 것을 통과로 읽히면 traps A6 이다.
        # Legitimately empty: every changed test was deleted by this PR.
        # Distinct from selector collapse (classify returned no tests).
        # Neither path may print a success banner (traps A6).
        return 0, [
            f"⏭️  HEAD 에 남은 테스트 0건 — 삭제된 테스트는 역-뮤테이션 대상이 아니다. "
            f"이 축은 안 쟀음 (생산 표면 {len(prod)}건 · 삭제된 테스트 {len(tests)}건).",
        ]

    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "wt"
        add = _run(["git", "worktree", "add", "--detach", str(wt), head_sha], root, timeout=600)
        if add.returncode != 0:
            return 1, [f"🔴 worktree 생성 실패 — 판정 불가: {add.stderr[-200:]}"]
        try:
            base_proc = _pytest(present, wt)
            if base_proc.returncode != 0:
                return 1, [
                    "🔴 되돌리기 **전에 이미 red** — 무엇 때문에 빨간지 알 수 없다(판정 불가).",
                    f"   {(base_proc.stdout or '')[-400:]}",
                ]

            existing, created = [], []
            for f in prod:
                (existing if _blob_exists(base_sha, f, wt) else created).append(f)
            if existing:
                rv = _run(["git", "checkout", base_sha, "--", *existing], wt, timeout=600)
                if rv.returncode != 0:
                    return 1, [f"🔴 되돌리기 실패 — 판정 불가: {rv.stderr[-200:]}"]
            for f in created:
                _run(["git", "rm", "-f", "--quiet", f], wt, timeout=120)

            # 🔴 뮤테이션 유효성 (AGENTS.md 불변식 2) — 게이트 자신에게도 적용한다.
            #    `git diff` 는 작업트리↔index 를 보므로 `checkout` 뒤에는 항상 비어 있다.
            dirty = _run(["git", "status", "--porcelain"], wt, timeout=120)
            if not (dirty.stdout or "").strip():
                return 1, ["🔴 되돌림이 **no-op** — 뮤테이션이 무효라 아무것도 증명하지 못한다."]

            after = _pytest(present, wt)
            # 요약 줄도 같은 규칙 — 개수 접두가 있는 줄만 요약으로 본다.
            # Same rule for the summary line: only count-prefixed lines qualify.
            tail = [l for l in (after.stdout or "").splitlines()
                    if _SUMMARY_LINE.search(l)]
            summary = tail[-1] if tail else "?"

            if after.returncode != 0:
                grade = _grade(after)
                lines.append(
                    f"✅ 역-뮤테이션 red — 이 PR 의 테스트가 변경을 관측한다 ({summary})")
                lines.append(f"   신호 등급: **{grade}**" + _GRADE_CAVEAT.get(grade, ""))
                lines.append(f"   되돌린 생산 파일 {len(prod)}건 · 실행 테스트 {len(present)}건")
                return 0, lines

            lines.append("🔴 역-뮤테이션이 **green** — 이 PR 의 테스트는 이 PR 의 변경을 "
                         "관측하지 않는다.")
            lines.append(f"   되돌린 생산 파일 {len(prod)}건: {', '.join(prod[:6])}"
                         + (" …" if len(prod) > 6 else ""))
            lines.append(f"   실행 테스트 {len(present)}건: {', '.join(present[:6])}")
            lines.append(f"   결과: {summary}")
            lines.append("")
            lines.append("   → 그 변경을 **실제로 깨뜨리는** 단언을 추가하세요.")
            lines.append("   → 이 게이트로 판정할 수 없는 변경이면 PR 본문에 적으세요:")
            lines.append("        reverse-mutation-not-applicable: <왜 판정 불가인가 — 16자 이상>")
            lines.append("      🔴 그 사용은 job summary 에 계수됩니다.")
            return 1, lines
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt)], root, timeout=600)


def _clean(root: Path, paths: list[str]) -> bool | None:
    """`paths`(되돌릴 생산 파일)에 HEAD 와 다른 점이 없는가 — 못 재면 None.

    🔴 이 경로만 본다. 앞 스텝(스위트 · 빌드)이 다른 추적 파일을 건드렸어도 되돌림 · 복원은 이 경로만 쓰므로
    판정을 막지 않는다. 이 경로에 미커밋 수정이 있으면 덮어쓰거나 잃으므로 판정 불가다.
    Only the reverted paths: other tracked files a prior step touched are neither written nor read here.
    """
    proc = _run(["git", "status", "--porcelain", "--untracked-files=no", "--", *paths], root, timeout=120)
    if proc.returncode != 0:
        return None
    return not (proc.stdout or "").strip()


def _report_run(label: str, proc: subprocess.CompletedProcess | None) -> str:
    if proc is None:
        return f"   {label}: 돌릴 시험 없음"
    summary = _summary_line(proc) or "?"
    if proc.returncode == 0:
        return f"   {label}: {summary} · green"
    grade = _grade(proc)
    return f"   {label}: {summary} · 신호 등급 **{grade}**{_GRADE_CAVEAT.get(grade, '')}"


def evaluate_with_e2e(base_sha: str, head_sha: str, repo: Path | None = None,
                      rebuild: str | None = None) -> tuple[int, list[str]]:
    """E2E 잡의 판정 — 생산 변경을 **제자리에서** 되돌리고 이 PR 이 바꾼 단위 · e2e 시험을 함께 다시 돌린다.

    🔴 제자리인 이유: e2e 는 빌드한 CSS · node_modules · 브라우저가 있는 그 잡의 체크아웃에서만 돈다. 끝나면 복원한다.
    🔴 e2e 기준선은 «그 시험» 으로 잰다 — 되돌려서 빨간 e2e 시험을 복원한 트리에서 다시 돌려 초록이어야 관측이다
    (스위트 초록만 믿으면 순서 의존 · 불안정이 거짓 «관측» 을 낸다). 단위 기준선은 되돌리기 전에 잰다.
    🔴 되돌릴 생산 파일에 미커밋 수정이 있으면 덮어쓰거나 잃으므로 판정 불가로 실패한다.
    Revert in place, then restore; an e2e red counts only if that test passes again on the restored tree.
    """
    root = repo or _ROOT
    files = changed_files(base_sha, head_sha, root)
    if files is None:
        return 1, ["🔴 변경 파일을 산출하지 못했다 — **판정 불가**(fail-closed)."]
    prod, tests = classify(files)
    # 단위 잡이 넘긴 조건과 같은 함수 — 여기서 쉬는 PR 은 단위 잡이 쟀다(어느 쪽도 안 재는 PR 이 없다).
    # The same predicate as the unit job's hand-off: a PR skipped here was judged there.
    e2e_run = e2e_present(files, prod, head_sha, root)
    if not e2e_run:
        return 0, ["⏭️  단위 잡의 몫 — 생산 변경이 없거나, HEAD 에 남은 바뀐 e2e 시험 모듈이 없다."]
    # 단위 쪽은 시험 모듈만 — 도우미만 넘기면 pytest 가 «수집 0건»(exit 5)으로 기준선을 빨갛게 만든다.
    # Unit side runs test modules only; a helper alone would make the baseline exit 5.
    unit = _test_modules(existing_at(head_sha, tests, root))
    clean = _clean(root, prod)
    if clean is not True:
        return 1, ["🔴 되돌릴 생산 파일에 미커밋 수정이 있다(또는 못 쟀다) — 제자리 되돌림이 그것을 덮는다(판정 불가)."]
    if unit:
        before = _pytest(unit, root)
        if before.returncode != 0:
            return 1, ["🔴 되돌리기 **전에 이미 red**(단위) — 무엇 때문에 빨간지 알 수 없다(판정 불가).",
                       f"   {(before.stdout or '')[-400:]}"]

    targets = e2e_targets(base_sha, head_sha, e2e_run, root)
    with tempfile.TemporaryDirectory(prefix="reverse-mutation-lf-") as cache:
        return _revert_and_run(root, base_sha, prod, unit, targets, rebuild, cache)


def _revert_and_run(root: Path, base_sha: str, prod: list[str], unit: list[str], targets: list[str],
                    rebuild: str | None, cache: str) -> tuple[int, list[str]]:
    """제자리에서 되돌리고 → 단위(관측하면 끝) → e2e(첫 실패에서 멈춤) → 복원 → 빨간 e2e 시험을 복원한 트리에서 다시."""
    existing = [f for f in prod if _blob_exists(base_sha, f, root)]
    created = [f for f in prod if f not in existing]
    unit_after = e2e_after = None
    try:
        if existing:
            rv = _run(["git", "checkout", base_sha, "--", *existing], root, timeout=600)
            if rv.returncode != 0:
                return 1, [f"🔴 되돌리기 실패 — 판정 불가: {rv.stderr[-200:]}"]
        for f in created:
            _run(["git", "rm", "-f", "--quiet", f], root, timeout=120)
        if _clean(root, prod) is not False:
            return 1, ["🔴 되돌림이 **no-op** — 뮤테이션이 무효라 아무것도 증명하지 못한다."]
        if rebuild:
            try:
                built = _run(shlex.split(rebuild), root, timeout=900)
            except (OSError, subprocess.SubprocessError) as exc:
                return 1, [f"🔴 되돌린 뒤 빌드를 못 돌렸다 — 판정 불가: {exc}"]
            if built.returncode != 0:
                return 1, [f"🔴 되돌린 뒤 빌드 실패 — 판정 불가: {(built.stdout or '')[-200:]}{(built.stderr or '')[-200:]}"]
        unit_after = _pytest(unit, root) if unit else None
        if unit_after is None or unit_after.returncode == 0:
            # 단위가 관측하지 않았을 때만 e2e 를 돈다 — 첫 실패에서 멈추고, 그 시험을 아래에서 되돌리지 않고 다시 돌린다.
            # e2e only when the unit side did not observe; stop at the first failure and re-check it below.
            e2e_after = _pytest(targets, root, [*_E2E_FLAGS, "--maxfail=1"], cache_dir=cache)
    finally:
        # 🔴 나눠 복원한다 — PR 이 지운 생산 파일은 HEAD 에 없어, 한 번에 `checkout HEAD -- …` 하면 경로 하나 때문에
        #    통째로 실패하고 트리가 되돌린 채 남는다. HEAD 에 있는 것은 체크아웃, 없는 것은 다시 지운다.
        # Restore in two groups: a path the PR deleted is absent from HEAD and would fail the whole checkout.
        keep = [f for f in prod if _blob_exists("HEAD", f, root)]
        if keep:
            _run(["git", "checkout", "HEAD", "--", *keep], root, timeout=600)
        for f in prod:
            if f not in keep:
                _run(["git", "rm", "-f", "--quiet", "--ignore-unmatch", f], root, timeout=120)
        if rebuild:
            try:
                _run(shlex.split(rebuild), root, timeout=900)
            except (OSError, subprocess.SubprocessError):
                pass  # 복원 뒤 재빌드는 최선 노력 — 판정은 이미 났다 / best effort after the verdict

    counts = f"   되돌린 생산 파일 {len(prod)}건 · 단위 {len(unit)}건 · e2e 대상 {len(targets)}개"
    if unit_after is not None and unit_after.returncode != 0:
        return 0, ["✅ 역-뮤테이션(e2e 잡) red — 이 PR 의 단위 시험이 변경을 관측한다(e2e 는 돌리지 않았다)",
                   _report_run("단위", unit_after), counts]
    report = [_report_run("단위", unit_after), _report_run("e2e", e2e_after), counts]
    if e2e_after is not None and e2e_after.returncode != 0:
        # 🔴 되돌려서 빨간 그 시험이 **되돌리지 않은 트리**에서 초록이어야 관측이다 — 아니면 순서 의존 · 불안정 · 환경이다.
        # The test that went red after the revert must pass on the restored tree; otherwise the red proves nothing.
        confirm = _pytest(targets, root, [*_E2E_FLAGS, "--lf", "--last-failed-no-failures", "none"], cache_dir=cache)
        report.append(_report_run("e2e 복원 뒤 그 시험", confirm))
        if confirm.returncode == 0:
            return 0, ["✅ 역-뮤테이션(e2e 잡) red — 이 PR 의 e2e 시험이 변경을 관측한다(복원 뒤 그 시험 초록)", *report]
        return 1, ["🔴 되돌려서 빨간 e2e 시험이 **복원한 트리에서도** 초록이 아니다 — 되돌림이 낸 red 가 아니다(판정 불가).",
                   *report]
    return 1, ["🔴 역-뮤테이션(e2e 포함)이 **green** — 이 PR 의 단위 · e2e 시험은 이 PR 의 변경을 관측하지 않는다.",
               *report, "",
               "   → 그 변경을 **실제로 깨뜨리는** 단언을 추가하세요.",
               "   → 이 게이트로 판정할 수 없는 변경이면 PR 본문에 적으세요:",
               "        reverse-mutation-not-applicable: <왜 판정 불가인가 — 16자 이상>"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="역-뮤테이션 게이트")
    parser.add_argument("--with-e2e", action="store_true",
                        help="E2E 잡 — 제자리에서 되돌리고 단위 · e2e 시험을 함께 잰다")
    parser.add_argument("--rebuild", default="", help="되돌린 뒤 · 복원한 뒤 돌릴 빌드 명령(예: npm run build)")
    args = parser.parse_args([] if argv is None else argv)
    print("=== 역-뮤테이션 게이트 / Reverse-Mutation Gate ===\n")
    base_sha = os.environ.get("PR_BASE_SHA", "")
    head_sha = os.environ.get("PR_HEAD_SHA", "")
    if not (base_sha and head_sha):
        print("⏭️  PR 환경변수(PR_BASE_SHA/PR_HEAD_SHA)가 없다 — 로컬 실행에서는 쉰다.")
        return 0

    exemption = _EXEMPT.search(read_pr_body())
    if exemption:
        reason = _LINE_BREAKS.sub(" ", exemption.group(0).strip())[:200]
        print(f"::notice title=reverse-mutation exempted::{reason}")
        _append_step_summary(f"- ⏭️ **역-뮤테이션 면제** — {reason}\n")
        print(f"⏭️  면제 마커 확인 — {reason}")
        return 0

    if args.with_e2e:
        code, lines = evaluate_with_e2e(base_sha, head_sha, rebuild=args.rebuild or None)
    else:
        code, lines = evaluate(base_sha, head_sha)
    stream = sys.stdout if code == 0 else sys.stderr
    for line in lines:
        print(line, file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
